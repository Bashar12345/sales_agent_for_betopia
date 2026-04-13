# [OWNER: Dev 2 — P1 Conversation Engine]
"""Anthropic Claude Sonnet 4.6 client.

Used as the P1 fallback provider when GPT-4.1 exceeds the 3-second timeout,
and as the P2 enrichment model (200K context, tool_use).

Capabilities used:
  - tool_use   — structured suggestion output (P1 fallback)
  - tool_use   — requirements enrichment, budget estimation (P2)
  - 200K ctx   — full conversation thread analysis
"""

import json
from typing import Any

import structlog
import anthropic

from src.core.exceptions import LLMError
from src.core.settings import settings
from src.domain.entities.suggestion import SuggestionStrategy, SuggestionTone

log = structlog.get_logger()

_SUGGESTION_TOOL = {
    "name": "generate_suggestions",
    "description": "Generate 5 ranked reply suggestions for the salesperson",
    "input_schema": {
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
                        "preview_text": {"type": "string", "maxLength": 120},
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
}

_ENRICHMENT_TOOL = {
    "name": "enrich_requirements",
    "description": "Enrich extracted requirements with budget estimate, stack, and risk flags",
    "input_schema": {
        "type": "object",
        "properties": {
            "enriched_summary": {"type": "string"},
            "recommended_stack": {"type": "array", "items": {"type": "string"}},
            "risk_flags": {"type": "array", "items": {"type": "string"}},
            "budget_min_usd": {"type": "number"},
            "budget_max_usd": {"type": "number"},
            "lead_score": {"type": "integer", "minimum": 0, "maximum": 100},
        },
        "required": [
            "enriched_summary", "recommended_stack", "risk_flags",
            "budget_min_usd", "budget_max_usd", "lead_score",
        ],
    },
}


class AnthropicClient:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    # ── P1 fallback: suggestion generation ───────────────────────────────────

    async def generate_suggestions(self, prompt: str) -> list[dict[str, Any]]:
        """Generate 5 reply suggestions via Claude tool_use."""
        try:
            message = await self._client.messages.create(
                model=settings.LLM_FALLBACK_MODEL,
                max_tokens=2048,
                tools=[_SUGGESTION_TOOL],
                tool_choice={"type": "tool", "name": "generate_suggestions"},
                messages=[{"role": "user", "content": prompt}],
            )
            for block in message.content:
                if block.type == "tool_use" and block.name == "generate_suggestions":
                    data: dict[str, Any] = block.input  # type: ignore[assignment]
                    for s in data["suggestions"]:
                        s["generated_by"] = settings.LLM_FALLBACK_MODEL
                    return data["suggestions"]
            raise LLMError("Claude returned no tool_use block for suggestions")
        except Exception as exc:
            log.error("anthropic.suggestions_failed", error=str(exc))
            raise LLMError(f"Claude suggestion generation failed: {exc}") from exc

    # ── P2 enrichment: requirements analysis ─────────────────────────────────

    async def enrich_requirements(
        self,
        raw_summary: str,
        conversation_context: str = "",
    ) -> dict[str, Any]:
        """Enrich extracted requirements with budget range, stack, risk flags, and lead score."""
        content = (
            "You are a senior technical sales consultant analysing a client's project requirements.\n\n"
            f"## Extracted requirements:\n{raw_summary}"
        )
        if conversation_context:
            content += f"\n\n## Conversation context:\n{conversation_context}"
        content += (
            "\n\nEnrich these requirements with: recommended tech stack, "
            "realistic budget range (USD), risk flags, and a lead quality score (0-100)."
        )

        try:
            message = await self._client.messages.create(
                model=settings.LLM_FALLBACK_MODEL,
                max_tokens=1024,
                tools=[_ENRICHMENT_TOOL],
                tool_choice={"type": "tool", "name": "enrich_requirements"},
                messages=[{"role": "user", "content": content}],
            )
            for block in message.content:
                if block.type == "tool_use" and block.name == "enrich_requirements":
                    return block.input  # type: ignore[return-value]
            raise LLMError("Claude returned no tool_use block for enrichment")
        except Exception as exc:
            log.error("anthropic.enrichment_failed", error=str(exc))
            raise LLMError(f"Requirements enrichment failed: {exc}") from exc
