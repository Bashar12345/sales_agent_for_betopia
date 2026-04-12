"""vLLM in-house client — intent classification + tone validation.

Runs locally (Mistral-7B-Instruct or similar) for near-zero inference cost.
Used in the hot path for:
  - P1 intent classification  (~5 ms, before expensive LLM call)
  - P1 tone validation        (after suggestion generation, filter out bad tone)
  - P1 last-resort suggestion fallback (both cloud providers failed)

The vLLM server exposes an OpenAI-compatible /v1/chat/completions endpoint.
"""

import json
from typing import Any

import structlog
from openai import AsyncOpenAI

from src.core.exceptions import LLMError
from src.core.settings import settings
from src.domain.entities.suggestion import SuggestionStrategy, SuggestionTone

log = structlog.get_logger()

# Intent labels as defined in settings.INTENT_CLASSES
_INTENT_SYSTEM = (
    "You are an intent classification model. "
    "Classify the customer message into exactly one of these labels: "
    + ", ".join(settings.INTENT_CLASSES)
    + ". Reply with only the label, nothing else."
)

_TONE_SYSTEM = (
    "You are a tone validation model. "
    "Given a reply message, return JSON: "
    '{"tone": "<tone_label>", "appropriate": true/false, "reason": "<brief reason>"}. '
    f"Valid tones: {', '.join(t.value for t in SuggestionTone)}."
)


class VLLMClient:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            base_url=settings.VLLM_BASE_URL + "/v1",
            api_key="not-needed",   # vLLM local server doesn't need an API key
        )

    # ── Intent classification ─────────────────────────────────────────────────

    async def classify_intent(self, message: str) -> str:
        """Return one of INTENT_CLASSES for the given customer message."""
        try:
            response = await self._client.chat.completions.create(
                model=settings.VLLM_MODEL,
                messages=[
                    {"role": "system", "content": _INTENT_SYSTEM},
                    {"role": "user", "content": message},
                ],
                max_tokens=20,
                temperature=0.0,
            )
            label = (response.choices[0].message.content or "").strip().lower()
            if label not in settings.INTENT_CLASSES:
                log.warning("vllm.unknown_intent", label=label)
                return "new_inquiry"   # safe default
            return label
        except Exception as exc:
            log.error("vllm.intent_failed", error=str(exc))
            return "new_inquiry"   # degrade gracefully; do NOT raise here

    # ── Tone validation ───────────────────────────────────────────────────────

    async def validate_tone(self, reply_text: str) -> dict[str, Any]:
        """Check whether a suggestion's tone is appropriate to send.

        Returns: {"tone": str, "appropriate": bool, "reason": str}
        """
        try:
            response = await self._client.chat.completions.create(
                model=settings.VLLM_MODEL,
                messages=[
                    {"role": "system", "content": _TONE_SYSTEM},
                    {"role": "user", "content": reply_text},
                ],
                max_tokens=80,
                temperature=0.0,
            )
            raw = (response.choices[0].message.content or "{}").strip()
            return json.loads(raw)
        except Exception as exc:
            log.warning("vllm.tone_validation_failed", error=str(exc))
            return {"tone": "professional", "appropriate": True, "reason": "validation skipped"}

    # ── Last-resort suggestion generation ────────────────────────────────────

    async def generate_suggestions(self, prompt: str) -> list[dict[str, Any]]:
        """Minimal suggestion generation when both cloud providers have failed.

        Returns 5 generic but safe suggestions rather than raising an error —
        the salesperson is always unblocked.
        """
        system = (
            "You are a Fiverr sales assistant. Generate exactly 5 reply suggestions "
            "as a JSON array. Each item: {rank, strategy, tone, preview_text, full_text, conversion_signal}. "
            f"Valid strategies: {[s.value for s in SuggestionStrategy]}. "
            f"Valid tones: {[t.value for t in SuggestionTone]}. "
            "Reply with ONLY the JSON array."
        )
        try:
            response = await self._client.chat.completions.create(
                model=settings.VLLM_MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1200,
                temperature=0.4,
            )
            raw = (response.choices[0].message.content or "[]").strip()
            suggestions: list[dict[str, Any]] = json.loads(raw)
            for s in suggestions:
                s["generated_by"] = settings.VLLM_MODEL
            return suggestions
        except Exception as exc:
            log.error("vllm.suggestions_failed", error=str(exc))
            raise LLMError(f"vLLM suggestion generation failed (last resort): {exc}") from exc
