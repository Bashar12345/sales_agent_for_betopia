# [OWNER: Zohra — Data Foundation (P3)]
"""IEventBusPort — abstract interface for NATS JetStream publish / subscribe.

CloudEvents 1.0 envelope is applied by the concrete implementation
(NATSClient) — callers pass plain dicts as the event payload.

Subject naming convention:
  leads.created | leads.updated
  conversations.updated | conversations.closed
  quotations.generated | quotations.sent
"""

from abc import ABC, abstractmethod
from typing import Any


class IEventBusPort(ABC):
    @abstractmethod
    async def publish(
        self,
        subject: str,
        event_type: str,
        payload: dict[str, Any],
        source: str = "sales-agent-api",
    ) -> None:
        """Publish a CloudEvents-wrapped message to the given NATS subject."""

    @abstractmethod
    async def close(self) -> None:
        """Drain and close the NATS connection gracefully."""
