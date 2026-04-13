# [OWNER: Niloy — P1 Conversation Engine]
"""ReplyService — scores and filters LLM-generated reply candidates.

The LLM port (application layer) returns N raw reply strings.
This service applies business rules to rank and select the best ones
before they reach the salesman's UI.
"""

from src.domain.entities.message import Message, MessageRole


class ReplyService:
    MAX_REPLIES_TO_RETURN = 3
    MAX_REPLY_LENGTH = 500  # characters

    def filter_replies(self, raw_replies: list[str]) -> list[str]:
        """Remove blank replies and truncate over-length ones."""
        filtered = []
        for reply in raw_replies:
            reply = reply.strip()
            if not reply:
                continue
            if len(reply) > self.MAX_REPLY_LENGTH:
                reply = reply[: self.MAX_REPLY_LENGTH] + "…"
            filtered.append(reply)
        return filtered[: self.MAX_REPLIES_TO_RETURN]

    def build_context_window(
        self, messages: list[Message], max_messages: int = 10
    ) -> list[Message]:
        """Return the last N messages to keep LLM context tight."""
        relevant = [m for m in messages if m.role != MessageRole.SYSTEM]
        return sorted(relevant, key=lambda m: m.created_at)[-max_messages:]
