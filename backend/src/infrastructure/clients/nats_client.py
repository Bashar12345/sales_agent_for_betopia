# [OWNER: Zohra — Data Foundation (P3)]
"""NATS JetStream event bus client.

Architecture role: L7 event bus between the three pipelines.
  P1 publishes: betopia.sales.conversation.message_received
                betopia.sales.conversation.suggestion_selected
  P2 publishes: betopia.sales.requirements.extracted
                betopia.sales.requirements.enriched
                betopia.sales.proposal.ready
  P3 publishes: (CDC events forwarded from Debezium)

Delivery guarantee: at-least-once (JetStream persistent streams).
CloudEvents-compliant envelope: type, source, subject, data.

Lifecycle:
  - connect() called in FastAPI lifespan startup
  - close()   called in FastAPI lifespan shutdown
"""

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import nats
import nats.js
import structlog

from src.core.exceptions import EventBusError
from src.core.settings import settings

log = structlog.get_logger()


def _cloud_event(event_type: str, subject: str, data: dict[str, Any]) -> bytes:
    """Wrap a payload in a minimal CloudEvents-compatible envelope."""
    envelope = {
        "specversion": "1.0",
        "type": event_type,
        "source": f"/{settings.APP_NAME.lower().replace(' ', '-')}",
        "id": str(uuid4()),
        "time": datetime.now(timezone.utc).isoformat(),
        "subject": subject,
        "datacontenttype": "application/json",
        "data": data,
    }
    return json.dumps(envelope).encode()


class NATSClient:
    def __init__(self) -> None:
        self._nc: nats.NATS | None = None
        self._js: nats.js.JetStreamContext | None = None

    async def connect(self) -> None:
        """Connect to NATS and ensure the JetStream stream exists."""
        self._nc = await nats.connect(settings.NATS_URL)
        self._js = self._nc.jetstream()

        # Ensure the persistent stream covers all betopia.sales.* subjects
        try:
            await self._js.find_stream(settings.NATS_STREAM_NAME)
        except Exception:
            # Stream doesn't exist yet — create it
            await self._nc.jsm().add_stream(
                name=settings.NATS_STREAM_NAME,
                subjects=[f"{settings.NATS_SUBJECT_PREFIX}.*.*"],
                max_msgs=10_000_000,
                max_age=7 * 24 * 3600,  # retain 7 days
            )
        log.info("nats.connected", url=settings.NATS_URL, stream=settings.NATS_STREAM_NAME)

    async def close(self) -> None:
        if self._nc:
            await self._nc.close()
            log.info("nats.disconnected")

    @property
    def js(self) -> nats.js.JetStreamContext:
        if self._js is None:
            raise EventBusError("NATS client not connected — call connect() first")
        return self._js

    # ── Publish helpers ───────────────────────────────────────────────────────

    async def publish(
        self,
        event_type: str,
        subject_suffix: str,
        data: dict[str, Any],
    ) -> None:
        """Publish a CloudEvents-wrapped message to JetStream.

        Args:
            event_type:     e.g. "betopia.sales.conversation.message_received"
            subject_suffix: e.g. "conversation.message_received"
            data:           event payload dict
        """
        subject = f"{settings.NATS_SUBJECT_PREFIX}.{subject_suffix}"
        payload = _cloud_event(event_type, subject, data)
        try:
            ack = await self.js.publish(subject, payload)
            log.debug("nats.published", subject=subject, seq=ack.seq)
        except Exception as exc:
            log.error("nats.publish_failed", subject=subject, error=str(exc))
            raise EventBusError(f"NATS publish failed on {subject}: {exc}") from exc

    # ── Convenience event publishers ─────────────────────────────────────────

    async def emit_message_received(
        self, conversation_id: str, message_id: str, lead_id: str
    ) -> None:
        await self.publish(
            event_type="betopia.sales.conversation.message_received",
            subject_suffix="conversation.message_received",
            data={
                "conversation_id": conversation_id,
                "message_id": message_id,
                "lead_id": lead_id,
            },
        )

    async def emit_suggestion_selected(
        self, suggestion_id: str, conversation_id: str, agent_id: str, rank: int
    ) -> None:
        await self.publish(
            event_type="betopia.sales.conversation.suggestion_selected",
            subject_suffix="conversation.suggestion_selected",
            data={
                "suggestion_id": suggestion_id,
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "rank": rank,
            },
        )

    async def emit_requirements_extracted(
        self, requirements_doc_id: str, lead_id: str, confidence: float
    ) -> None:
        await self.publish(
            event_type="betopia.sales.requirements.extracted",
            subject_suffix="requirements.extracted",
            data={
                "requirements_doc_id": requirements_doc_id,
                "lead_id": lead_id,
                "confidence": confidence,
            },
        )

    async def emit_proposal_ready(self, proposal_id: str, lead_id: str) -> None:
        await self.publish(
            event_type="betopia.sales.proposal.ready",
            subject_suffix="proposal.ready",
            data={"proposal_id": proposal_id, "lead_id": lead_id},
        )
