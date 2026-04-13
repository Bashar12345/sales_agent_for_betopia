#!/usr/bin/env python3
# [OWNER: Dev 2 — P1 Conversation Engine]
"""One-time seeder: parse Fiverr chat screenshot PDFs and upsert to Qdrant.

Each PDF is a full Fiverr inbox conversation screenshot exported to PDF.
The seeder extracts (customer_message, agent_reply) pairs, embeds the
customer messages, and upserts them into the Qdrant 'conversations'
collection as the P1 knowledge base.

Usage (from backend/ directory):
    python scripts/seed_conversations.py

Requirements:
    - Qdrant running (make vm3-up or docker-compose.server.yml up)
    - Redis running
    - OPENAI_API_KEY set in .env
    - pdfplumber installed (already in pyproject.toml)
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any

import structlog

# Add backend/ to path so `from src.*` imports resolve when running as script
sys.path.insert(0, str(Path(__file__).parent.parent))

import pdfplumber  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402

from src.core.settings import settings  # noqa: E402
from src.infrastructure.clients.llm_client import LLMClient  # noqa: E402
from src.infrastructure.clients.qdrant_client import QdrantVectorClient  # noqa: E402
from src.infrastructure.clients.redis_cache_client import RedisCacheClient  # noqa: E402

log = structlog.get_logger()

# conversations/ folder is at the repo root (one level above backend/)
CONVERSATIONS_DIR = Path(__file__).parent.parent.parent / "conversations"

# ── GPT-4.1 structured output tool for parsing raw chat text ─────────────────

_PARSE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "parse_conversation",
        "description": "Parse raw Fiverr chat screenshot text into structured turns",
        "parameters": {
            "type": "object",
            "properties": {
                "conversation_metadata": {
                    "type": "object",
                    "properties": {
                        "project_type": {
                            "type": "string",
                            "description": "e.g. mobile_app, web_app, ecommerce, booking_platform",
                        },
                        "outcome": {
                            "type": "string",
                            "enum": ["won", "lost", "in_progress"],
                        },
                        "budget_usd": {
                            "type": "number",
                            "description": "Total project budget in USD if mentioned, else null",
                        },
                    },
                    "required": ["project_type", "outcome"],
                },
                "turns": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "speaker": {
                                "type": "string",
                                "enum": ["customer", "agent"],
                            },
                            "message": {"type": "string"},
                            "turn_number": {"type": "integer"},
                            "strategy": {
                                "type": "string",
                                "enum": [
                                    "discovery",
                                    "value_proposition",
                                    "social_proof",
                                    "urgency",
                                    "negotiation",
                                ],
                                "description": "For agent turns only: strategy being used",
                            },
                            "intent_label": {
                                "type": "string",
                                "enum": [
                                    "new_inquiry",
                                    "follow_up",
                                    "clarification",
                                    "negotiation",
                                    "angry",
                                    "urgent",
                                ],
                                "description": "For customer turns only: customer's intent",
                            },
                        },
                        "required": ["speaker", "message", "turn_number"],
                    },
                },
            },
            "required": ["conversation_metadata", "turns"],
        },
    },
}

_PARSE_SYSTEM = """\
You are parsing a Fiverr chat conversation that was exported as a screenshot PDF.
The raw text may include timestamps, UI chrome, and navigation elements — ignore those.

Rules:
- Speaker "Me" = the agent/salesperson → set speaker="agent"
- Any other named speaker (e.g. "mitchellpartrid", "ram_zi20") = customer → speaker="customer"
- Skip system messages like "WE HAVE YOUR BACK", "Order placed", file attachments, etc.
- For each agent turn, infer the dominant sales strategy being used
- For each customer turn, infer the customer's intent_label
- For conversation_metadata:
    - project_type: infer from the project being discussed (mobile_app, web_app, etc.)
    - outcome: "won" if an order/milestone was placed and accepted, "lost" if rejected, "in_progress" otherwise
    - budget_usd: total project value in USD if explicitly stated
- Only include real message content — no UI text, no timestamps
"""


# ── PDF text extraction ───────────────────────────────────────────────────────

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from a PDF using pdfplumber."""
    pages: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text and text.strip():
                pages.append(text.strip())
    return "\n\n".join(pages)


# ── LLM-based conversation parsing ───────────────────────────────────────────

async def parse_conversation(raw_text: str, openai_client: AsyncOpenAI) -> dict[str, Any]:
    """Use GPT-4.1 structured output to parse raw chat text into turns."""
    # Limit to 12,000 chars to stay well within token budget
    truncated = raw_text[:12_000]

    response = await openai_client.chat.completions.create(
        model=settings.LLM_PRIMARY_MODEL,
        messages=[
            {"role": "system", "content": _PARSE_SYSTEM},
            {"role": "user", "content": f"Parse this Fiverr conversation:\n\n{truncated}"},
        ],
        tools=[_PARSE_TOOL],
        tool_choice={"type": "function", "function": {"name": "parse_conversation"}},
        temperature=0.0,
    )
    raw_args = response.choices[0].message.tool_calls[0].function.arguments
    return json.loads(raw_args)


# ── Turn pairing ──────────────────────────────────────────────────────────────

def make_pairs(turns: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Pair consecutive (customer, agent) turns.

    Walks the turn list and whenever a customer turn is immediately
    followed by an agent turn, creates a (customer, agent) pair.
    Non-adjacent turns are skipped.
    """
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    i = 0
    while i < len(turns) - 1:
        current = turns[i]
        nxt = turns[i + 1]
        if current.get("speaker") == "customer" and nxt.get("speaker") == "agent":
            pairs.append((current, nxt))
            i += 2
        else:
            i += 1
    return pairs


# ── Per-PDF seeding ───────────────────────────────────────────────────────────

async def seed_pdf(
    pdf_path: Path,
    llm: LLMClient,
    qdrant: QdrantVectorClient,
    cache: RedisCacheClient,
    openai_client: AsyncOpenAI,
) -> int:
    """Parse one PDF and upsert all (customer, agent) pairs to Qdrant.

    Returns the number of documents upserted.
    """
    log.info("seeder.processing", file=pdf_path.name)

    raw_text = extract_pdf_text(pdf_path)
    if not raw_text.strip():
        log.warning("seeder.empty_pdf", file=pdf_path.name)
        return 0

    parsed = await parse_conversation(raw_text, openai_client)
    meta = parsed.get("conversation_metadata", {})
    turns = parsed.get("turns", [])

    if not turns:
        log.warning("seeder.no_turns_extracted", file=pdf_path.name)
        return 0

    pairs = make_pairs(turns)
    if not pairs:
        log.warning("seeder.no_pairs_found", file=pdf_path.name, turns=len(turns))
        return 0

    count = 0
    for customer_turn, agent_turn in pairs:
        customer_message = customer_turn.get("message", "").strip()
        agent_reply = agent_turn.get("message", "").strip()

        if not customer_message or not agent_reply:
            continue

        # Skip very short messages (likely UI noise)
        if len(customer_message) < 10 or len(agent_reply) < 10:
            continue

        # Embed customer message — check Redis cache first (24h TTL)
        vector = await cache.get_embedding(customer_message)
        if vector is None:
            vector = await llm.embed_text(customer_message)
            await cache.set_embedding(customer_message, vector)

        strategy = agent_turn.get("strategy") or "discovery"
        intent = customer_turn.get("intent_label") or "new_inquiry"

        # This formatted string flows directly into similar_conversations list
        # in LLMClient.generate_suggestions() — see v1_suggestion_prompt.yaml
        formatted_text = (
            f"Customer ({intent}): {customer_message}\n"
            f"Agent ({strategy}): {agent_reply}"
        )

        payload: dict[str, Any] = {
            "customer_message": customer_message,
            "agent_reply": agent_reply,
            "intent_label": intent,
            "strategy": strategy,
            "project_type": meta.get("project_type", "unknown"),
            "outcome": meta.get("outcome", "won"),
            "budget_usd": meta.get("budget_usd"),
            "source_file": pdf_path.name,
            "turn_number": customer_turn.get("turn_number", 0),
        }

        # Deterministic doc_id so re-running the seeder is idempotent
        doc_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{pdf_path.name}:{customer_turn.get('turn_number', 0)}",
            )
        )

        await qdrant.upsert(
            collection=settings.QDRANT_COLLECTION_CONVERSATIONS,
            doc_id=doc_id,
            text=formatted_text,
            metadata=payload,
            vector=vector,
        )
        count += 1

    log.info("seeder.pdf_done", file=pdf_path.name, pairs_upserted=count)
    return count


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    pdf_files = sorted(CONVERSATIONS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in: {CONVERSATIONS_DIR}")
        print("Make sure the 'conversations/' folder exists at the repo root.")
        return

    print(f"Found {len(pdf_files)} PDF files in {CONVERSATIONS_DIR}\n")

    llm = LLMClient()
    qdrant = QdrantVectorClient()
    cache = RedisCacheClient()
    openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Ensure Qdrant collections exist before upserting
    await qdrant.ensure_collections()

    total = 0
    failed: list[str] = []

    for pdf_path in pdf_files:
        try:
            count = await seed_pdf(pdf_path, llm, qdrant, cache, openai_client)
            total += count
            print(f"  ✓ {pdf_path.name}: {count} pairs upserted")
        except Exception as exc:
            failed.append(pdf_path.name)
            log.error("seeder.pdf_failed", file=pdf_path.name, error=str(exc))
            print(f"  ✗ {pdf_path.name}: FAILED — {exc}")

    await cache.close()

    print(f"\n{'='*60}")
    print(f"Seeded {total} conversation pairs into Qdrant")
    print(f"Collection: '{settings.QDRANT_COLLECTION_CONVERSATIONS}'")
    if failed:
        print(f"Failed PDFs ({len(failed)}): {', '.join(failed)}")
    print(f"{'='*60}")
    print("\nNext step: run 'make qdrant-status' to verify the collection.")


if __name__ == "__main__":
    asyncio.run(main())
