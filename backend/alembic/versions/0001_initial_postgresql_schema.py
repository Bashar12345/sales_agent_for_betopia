"""Initial PostgreSQL schema — v3.0

Creates all tables for the Sales Intelligence Agent.
Tables created in FK-dependency order:
  1. sales_agents
  2. leads         (FK → sales_agents)
  3. conversations (FK → leads, sales_agents)
  4. messages      (FK → conversations)
  5. quotations    (FK → conversations, leads, sales_agents)
  6. resources     (FK → sales_agents)
  7. suggestions   (FK → conversations, messages)

PostgreSQL ENUM types are created up-front via postgresql.ENUM.create(checkfirst=True)
so the migration is safe to re-run and never conflicts with SQLAlchemy's auto-create.

Revision ID: 0001
Revises:
Create Date: 2026-04-13 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Enum type definitions (reused in both upgrade and downgrade) ───────────────
_ENUMS = {
    "agentrole":         ("SALESPERSON", "SALES_MANAGER", "ADMIN", "READ_ONLY"),
    "leadstatus":        ("new", "in_conversation", "quoted", "won", "lost"),
    "leadsource":        ("fiverr", "manual"),
    "conversationstatus": ("active", "closed", "quoted"),
    "messagerole":       ("customer", "salesman", "system"),
    "messagedirection":  ("in", "out"),
    "quotationstatus":   ("draft", "under_review", "sent", "accepted", "rejected"),
    "resourcetype":      ("price_list", "service_catalogue", "past_quotation",
                          "conversation_sample", "other"),
    "suggestionstrategy": ("discovery", "value_proposition", "social_proof",
                           "urgency", "negotiation"),
    "suggestiontone":    ("professional", "friendly", "empathetic",
                          "assertive", "consultative"),
}


def _enum(name: str, **kw) -> PgEnum:
    """Return a PgEnum for use in column definitions (create_type=False — already created)."""
    return PgEnum(*_ENUMS[name], name=name, create_type=False, **kw)


def upgrade() -> None:
    conn = op.get_bind()

    # ── Create all PostgreSQL ENUM types (checkfirst=True → idempotent) ───────
    for name, values in _ENUMS.items():
        PgEnum(*values, name=name).create(conn, checkfirst=True)

    # ── 1. sales_agents ───────────────────────────────────────────────────────
    op.create_table(
        "sales_agents",
        sa.Column("id", PgUUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", _enum("agentrole"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("odoo_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("email", name="uq_sales_agents_email"),
    )
    op.create_index("ix_sales_agents_email", "sales_agents", ["email"])

    # ── 2. leads ──────────────────────────────────────────────────────────────
    op.create_table(
        "leads",
        sa.Column("id", PgUUID(as_uuid=False), primary_key=True),
        sa.Column("fiverr_order_id", sa.String(128), nullable=True),
        sa.Column("fiverr_buyer_username", sa.String(128), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("budget", sa.Float(), nullable=True),
        sa.Column("requirement_summary", sa.Text(), nullable=False),
        sa.Column("status", _enum("leadstatus"), nullable=False, server_default="new"),
        sa.Column("source", _enum("leadsource"), nullable=False, server_default="fiverr"),
        sa.Column("assigned_agent_id", PgUUID(as_uuid=False),
                  sa.ForeignKey("sales_agents.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("fiverr_order_id", name="uq_leads_fiverr_order_id"),
    )
    op.create_index("ix_leads_fiverr_order_id", "leads", ["fiverr_order_id"])
    op.create_index("ix_leads_email", "leads", ["email"])
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_assigned_agent_id", "leads", ["assigned_agent_id"])

    # ── 3. conversations ──────────────────────────────────────────────────────
    op.create_table(
        "conversations",
        sa.Column("id", PgUUID(as_uuid=False), primary_key=True),
        sa.Column("lead_id", PgUUID(as_uuid=False),
                  sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", PgUUID(as_uuid=False),
                  sa.ForeignKey("sales_agents.id"), nullable=False),
        sa.Column("status", _enum("conversationstatus"), nullable=False,
                  server_default="active"),
        sa.Column("vector_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_conversations_lead_id", "conversations", ["lead_id"])
    op.create_index("ix_conversations_agent_id", "conversations", ["agent_id"])

    # ── 4. messages ───────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", PgUUID(as_uuid=False), primary_key=True),
        sa.Column("conversation_id", PgUUID(as_uuid=False),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", _enum("messagerole"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("used_in_quotation", sa.Boolean(), nullable=False,
                  server_default="false"),
        # ISO 8601 string — kept as VARCHAR to match the ORM's String(64) mapping
        sa.Column("created_at", sa.String(64), nullable=True),
        # P1 fields added in v3.0
        sa.Column("direction", _enum("messagedirection"), nullable=True),
        sa.Column("intent_label", sa.String(64), nullable=True),
        sa.Column("suggestion_selected_rank", sa.Integer(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # ── 5. quotations ─────────────────────────────────────────────────────────
    op.create_table(
        "quotations",
        sa.Column("id", PgUUID(as_uuid=False), primary_key=True),
        sa.Column("conversation_id", PgUUID(as_uuid=False),
                  sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("lead_id", PgUUID(as_uuid=False),
                  sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("agent_id", PgUUID(as_uuid=False),
                  sa.ForeignKey("sales_agents.id"), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("line_items", JSONB(astext_type=sa.Text()), nullable=False,
                  server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("total_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("status", _enum("quotationstatus"), nullable=False,
                  server_default="draft"),
        sa.Column("doc_path", sa.String(512), nullable=True),
        sa.Column("vector_id", sa.String(64), nullable=True),
        sa.Column("odoo_order_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_quotations_conversation_id", "quotations", ["conversation_id"])
    op.create_index("ix_quotations_lead_id", "quotations", ["lead_id"])
    op.create_index("ix_quotations_status", "quotations", ["status"])

    # ── 6. resources ──────────────────────────────────────────────────────────
    op.create_table(
        "resources",
        sa.Column("id", PgUUID(as_uuid=False), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("resource_type", _enum("resourcetype"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("vector_id", sa.String(64), nullable=True),
        sa.Column("uploaded_by_agent_id", PgUUID(as_uuid=False),
                  sa.ForeignKey("sales_agents.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_resources_resource_type", "resources", ["resource_type"])

    # ── 7. suggestions ────────────────────────────────────────────────────────
    op.create_table(
        "suggestions",
        sa.Column("id", PgUUID(as_uuid=False), primary_key=True),
        sa.Column("conversation_id", PgUUID(as_uuid=False),
                  sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", PgUUID(as_uuid=False),
                  sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lead_id", PgUUID(as_uuid=False), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("strategy", _enum("suggestionstrategy"), nullable=False),
        sa.Column("tone", _enum("suggestiontone"), nullable=False),
        sa.Column("preview_text", sa.Text(), nullable=False),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("conversion_signal", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("generated_by", sa.String(64), nullable=False,
                  server_default="gpt-4.1"),
        sa.Column("intent_label", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_suggestions_conversation_id", "suggestions", ["conversation_id"])
    op.create_index("ix_suggestions_message_id", "suggestions", ["message_id"])
    op.create_index("ix_suggestions_lead_id", "suggestions", ["lead_id"])


def downgrade() -> None:
    # Drop tables in reverse FK-dependency order
    op.drop_table("suggestions")
    op.drop_table("resources")
    op.drop_table("quotations")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("leads")
    op.drop_table("sales_agents")

    # Drop PostgreSQL ENUM types
    conn = op.get_bind()
    for name in reversed(list(_ENUMS.keys())):
        PgEnum(name=name, create_type=False).drop(conn, checkfirst=True)
