"""Multi-provider LLM client with automatic fallback chain.

Provider hierarchy (P1 Conversation Engine):
  1. GPT-4.1          — primary generation (structured outputs)
  2. Claude Sonnet 4.6 — fallback when GPT-4.1 exceeds LLM_PRIMARY_TIMEOUT (3s)
  3. vLLM (in-house)  — last resort when both cloud providers fail

Intent classification + tone validation always use vLLM to keep costs near $0.

Embedding always uses text-embedding-3-large (3072-d) via OpenAI — no fallback
needed since embeddings are cached 24 h in Redis.

Usage:
    client = LLMClient()
    suggestions = await client.generate_suggestions(payload)
    intent    = await client.classify_intent(message)
    embedding = await client.embed_text(text)
"""

import asyncio
import json
from typing import Any

import structlog
from openai import AsyncOpenAI

from src.application.ports.llm_port import ILLMPort
from src.core.exceptions import LLMError, LLMTimeoutError
from src.core.settings import settings
from src.domain.entities.message import Message
from src.domain.entities.quotation import LineItem
from src.domain.entities.suggestion import (
    Suggestion,
    SuggestionStrategy,
    SuggestionTone,
)

log = structlog.get_logger()

# ── Quotation tool (GPT-4.1 structured output) ────────────────────────────────
_QUOTATION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "create_quotation",
        "description": "Create a structured price quotation from the conversation",
        "parameters": {
            "type": "object",
            "properties": {
                "line_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "quantity": {"type": "number"},
                            "unit_price": {"type": "number"},
                        },
                        "required": ["description", "quantity", "unit_price"],
                    },
                },
                "notes": {"type": "string", "description": "Brief executive summary"},
            },
            "required": ["line_items", "notes"],
        },
    },
}

# ── Suggestion list tool (GPT-4.1 structured output) ─────────────────────────
_SUGGESTION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_suggestions",
        "description": "Generate ranked reply suggestions for the salesperson",
        "parameters": {
            "type": "object",
            "properties": {
                "suggestions": {
                    "type": "array",
                    "minItems": 5,
                    "maxItems": 5,
                    "items": {
                        "type": "object",
                        "properties": {
                            "rank": {"type": "integer", "minimum": 1, "maximum": 5},
                            "strategy": {
                                "type": "string",
                                "enum": [s.value for s in SuggestionStrategy],
                            },
                            "tone": {
                                "type": "string",
                                "enum": [t.value for t in SuggestionTone],
                            },
                            "preview_text": {
                                "type": "string",
                                "maxLength": 120,
                            },
                            "full_text": {"type": "string"},
                            "conversion_signal": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                            },
                        },
                        "required": [
                            "rank", "strategy", "tone",
                            "preview_text", "full_text", "conversion_signal",
                        ],
                    },
                }
            },
            "required": ["suggestions"],
        },
    },
}


class LLMClient(ILLMPort):
    def __init__(self) -> None:
        self._openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # ── Suggestions (P1 pipeline) ─────────────────────────────────────────────

    async def generate_suggestions(
        self,
        customer_message: str,
        intent_label: str,
        recent_messages: list[Message],
        similar_conversations: list[str],
        resources_context: list[str],
    ) -> list[dict[str, Any]]:
        """Return 5 structured suggestion dicts via the fallback chain."""
        history = "\n".join(f"[{m.role.upper()}]: {m.content}" for m in recent_messages)
        context = ""
        if similar_conversations:
            context += "\n\n## Similar past conversations:\n" + "\n---\n".join(
                similar_conversations[:3]
            )
        if resources_context:
            context += "\n\n## Service portfolio context:\n" + "\n---\n".join(
                resources_context[:3]
            )

        prompt = (
            f"You are an expert Fiverr sales consultant. "
            f"The customer's detected intent is: {intent_label}.\n\n"
            f"## Recent conversation:\n{history}\n\n"
            f"## Customer's latest message:\n{customer_message}"
            f"{context}\n\n"
            f"Generate exactly 5 diverse reply suggestions ranked by conversion potential."
        )

        # Try GPT-4.1 with timeout; fallback to Claude Sonnet 4.6 → vLLM
        try:
            return await asyncio.wait_for(
                self._gpt_suggestions(prompt),
                timeout=settings.LLM_PRIMARY_TIMEOUT,
            )
        except (asyncio.TimeoutError, Exception) as primary_exc:
            log.warning(
                "llm.primary_timeout_or_failed",
                error=str(primary_exc),
                fallback="claude-sonnet-4-6",
            )
            try:
                return await asyncio.wait_for(
                    self._claude_suggestions(prompt),
                    timeout=settings.LLM_FALLBACK_TIMEOUT,
                )
            except (asyncio.TimeoutError, Exception) as fallback_exc:
                log.warning(
                    "llm.fallback_failed",
                    error=str(fallback_exc),
                    fallback="vllm",
                )
                return await self._vllm_suggestions(prompt)

    async def _gpt_suggestions(self, prompt: str) -> list[dict[str, Any]]:
        response = await self._openai.chat.completions.create(
            model=settings.LLM_PRIMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            tools=[_SUGGESTION_TOOL],
            tool_choice={"type": "function", "function": {"name": "generate_suggestions"}},
        )
        tool_call = response.choices[0].message.tool_calls[0]
        data = json.loads(tool_call.function.arguments)
        for s in data["suggestions"]:
            s["generated_by"] = settings.LLM_PRIMARY_MODEL
        return data["suggestions"]

    async def _claude_suggestions(self, prompt: str) -> list[dict[str, Any]]:
        """Delegate to the Anthropic client (imported lazily to avoid circular deps)."""
        from src.infrastructure.clients.anthropic_client import AnthropicClient  # noqa: PLC0415

        client = AnthropicClient()
        return await client.generate_suggestions(prompt)

    async def _vllm_suggestions(self, prompt: str) -> list[dict[str, Any]]:
        """Delegate to the vLLM client."""
        from src.infrastructure.clients.vllm_client import VLLMClient  # noqa: PLC0415

        client = VLLMClient()
        return await client.generate_suggestions(prompt)

    # ── Intent classification ─────────────────────────────────────────────────

    async def classify_intent(self, message: str) -> str:
        """Classify customer message intent using vLLM (~$0 cost)."""
        from src.infrastructure.clients.vllm_client import VLLMClient  # noqa: PLC0415

        client = VLLMClient()
        return await client.classify_intent(message)

    # ── Quotation generation ──────────────────────────────────────────────────

    async def generate_quotation_items(
        self,
        transcript: str,
        similar_quotations: list[str],
        resources_context: list[str],
    ) -> tuple[list[LineItem], str]:
        context_block = ""
        if resources_context:
            context_block = "\n\n## Relevant resources:\n" + "\n---\n".join(resources_context)
        if similar_quotations:
            context_block += "\n\n## Similar past quotations:\n" + "\n---\n".join(
                similar_quotations
            )

        prompt = (
            "You are a professional sales assistant. Based on the conversation below, "
            "generate a detailed price quotation with individual line items and a brief summary.\n\n"
            f"## Conversation transcript:\n{transcript}"
            f"{context_block}"
        )

        try:
            response = await self._openai.chat.completions.create(
                model=settings.LLM_PRIMARY_MODEL,
                messages=[{"role": "user", "content": prompt}],
                tools=[_QUOTATION_TOOL],
                tool_choice={"type": "function", "function": {"name": "create_quotation"}},
            )
            tool_call = response.choices[0].message.tool_calls[0]
            data = json.loads(tool_call.function.arguments)
            items = [LineItem(**item) for item in data["line_items"]]
            return items, data.get("notes", "")
        except Exception as exc:
            log.error("llm.quotation_failed", error=str(exc))
            raise LLMError(f"Quotation generation failed: {exc}") from exc

    # ── Embedding (text-embedding-3-large, 3072-d) ───────────────────────────

    async def embed_text(self, text: str) -> list[float]:
        """Embed text using text-embedding-3-large (3072 dimensions).

        Caller is responsible for caching the result in Redis (24 h TTL).
        """
        try:
            response = await self._openai.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=text,
                dimensions=settings.EMBEDDING_DIMENSIONS,
            )
            return response.data[0].embedding
        except Exception as exc:
            raise LLMError(f"Embedding failed: {exc}") from exc
