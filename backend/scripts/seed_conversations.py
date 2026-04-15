#!/usr/bin/env python3
# [OWNER: Dev 2 — P1 Conversation Engine]
"""One-time seeder: parse Fiverr chat screenshot PDFs and upsert to Qdrant.

Each PDF is a full Fiverr inbox conversation screenshot exported to PDF.
The seeder extracts (customer_message, agent_reply) pairs, embeds the
customer messages, and upserts them into the Qdrant 'conversations'
collection as the P1 knowledge base.

Two extraction strategies (tried in order):
  1. pdfplumber — fast text extraction for text-based PDFs
  2. GPT-4.1 Vision — renders pages to PNG and sends to vision API for
     image-based PDFs (Fiverr screenshot exports are always image-based)

Usage (from backend/ directory):
    python scripts/seed_conversations.py

Requirements:
    - Qdrant running (make vm3-up or docker-compose.server.yml up)
    - Redis running
    - OPENAI_API_KEY set in .env
    - pdfplumber + PyMuPDF installed (already in pyproject.toml)
"""

import asyncio
import base64
import json
import sys
import uuid
from pathlib import Path
from typing import Any

import structlog

# Add backend/ to path so `from src.*` imports resolve when running as script
sys.path.insert(0, str(Path(__file__).parent.parent))

import fitz  # PyMuPDF  # noqa: E402
import pdfplumber  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402

from src.core.settings import settings  # noqa: E402
from src.infrastructure.clients.llm_client import LLMClient  # noqa: E402
from src.infrastructure.clients.qdrant_client import QdrantVectorClient  # noqa: E402
from src.infrastructure.clients.redis_cache_client import RedisCacheClient  # noqa: E402

log = structlog.get_logger()

# conversations/ folder is at the repo root (one level above backend/)
CONVERSATIONS_DIR = Path(__file__).parent.parent.parent / "conversations"

# Max PDF pages to send to vision API (caps token cost per file)
_MAX_VISION_PAGES = 6

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


# ── PDF extraction: text path ─────────────────────────────────────────────────

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract selectable text from a PDF using pdfplumber.

    Reads raw bytes first so Windows path quirks (parentheses, spaces)
    never reach pdfplumber's internal file resolver.
    Returns empty string for image-based (scanned/screenshot) PDFs.
    """
    pages: list[str] = []
    pdf_bytes = pdf_path.read_bytes()
    import io  # noqa: PLC0415
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text and text.strip():
                pages.append(text.strip())
    return "\n\n".join(pages)


# ── PDF extraction: vision path ───────────────────────────────────────────────

def render_pdf_pages(pdf_path: Path, max_pages: int = _MAX_VISION_PAGES) -> list[str]:
    """Render PDF pages to base64-encoded PNG strings for the vision API.

    Loads from bytes so Windows path quirks (parentheses, spaces) are bypassed.
    Uses a 2× DPI scale so text in screenshots is legible to GPT-4.1 Vision.
    """
    pdf_bytes = pdf_path.read_bytes()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images: list[str] = []
    scale = fitz.Matrix(2.0, 2.0)  # 144 DPI — sharp enough for chat text
    for page_num in range(min(len(doc), max_pages)):
        pix = doc[page_num].get_pixmap(matrix=scale, alpha=False)
        png_bytes = pix.tobytes("png")
        images.append(base64.b64encode(png_bytes).decode())
    doc.close()
    return images


# ── LLM-based conversation parsing ───────────────────────────────────────────

async def parse_conversation_text(
    raw_text: str, openai_client: AsyncOpenAI
) -> dict[str, Any]:
    """Use GPT-4.1 structured output to parse raw chat text into turns."""
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


async def parse_conversation_vision(
    page_images: list[str],
    openai_client: AsyncOpenAI,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Use GPT-4.1 Vision to parse a screenshot-based PDF directly.

    Sends each rendered page as a base64 PNG in the user message content array.
    On JSON truncation (output token limit hit), retries with half the pages
    so at least a partial set of conversation pairs is extracted.
    """
    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": "Parse this Fiverr conversation from the screenshots below:",
        }
    ]
    for b64 in page_images:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64}",
                    "detail": "high",  # high detail for small chat text
                },
            }
        )

    response = await openai_client.chat.completions.create(
        model=settings.LLM_PRIMARY_MODEL,
        messages=[
            {"role": "system", "content": _PARSE_SYSTEM},
            {"role": "user", "content": content},
        ],
        tools=[_PARSE_TOOL],
        tool_choice={"type": "function", "function": {"name": "parse_conversation"}},
        temperature=0.0,
        max_tokens=max_tokens,
    )
    raw_args = response.choices[0].message.tool_calls[0].function.arguments
    try:
        return json.loads(raw_args)
    except json.JSONDecodeError:
        half = max(1, len(page_images) // 2)
        if half < len(page_images):
            # First try: halve the pages at the same token budget
            log.warning(
                "seeder.vision_json_truncated",
                pages_sent=len(page_images),
                retrying_with=half,
            )
            return await parse_conversation_vision(
                page_images[:half], openai_client, max_tokens=max_tokens
            )
        if max_tokens < 16384:
            # Already at 1 page — content is large (e.g. Unicode/emoji heavy).
            # Double the token budget and retry.
            new_limit = min(max_tokens * 2, 16384)
            log.warning(
                "seeder.vision_token_limit_increase",
                pages_sent=len(page_images),
                old_max_tokens=max_tokens,
                new_max_tokens=new_limit,
            )
            return await parse_conversation_vision(
                page_images, openai_client, max_tokens=new_limit
            )
        raise


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

    Tries pdfplumber text extraction first; falls back to GPT-4.1 Vision
    for image-based screenshot PDFs (the typical Fiverr export format).

    Returns the number of documents upserted.
    """
    log.info("seeder.processing", file=pdf_path.name)

    # ── Strategy 1: text extraction ───────────────────────────────────────────
    raw_text = extract_pdf_text(pdf_path)
    if raw_text.strip():
        log.info("seeder.text_extraction", file=pdf_path.name, chars=len(raw_text))
        parsed = await parse_conversation_text(raw_text, openai_client)
    else:
        # ── Strategy 2: GPT-4.1 Vision (image-based PDF) ─────────────────────
        log.info("seeder.vision_fallback", file=pdf_path.name)
        page_images = render_pdf_pages(pdf_path)
        if not page_images:
            log.warning("seeder.empty_pdf", file=pdf_path.name)
            return 0
        log.info("seeder.vision_sending", file=pdf_path.name, pages=len(page_images))
        parsed = await parse_conversation_vision(page_images, openai_client)

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
