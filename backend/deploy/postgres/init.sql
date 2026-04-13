-- =============================================================================
-- PostgreSQL 17 — Sales Intelligence Agent v3.0 initialization script
-- Runs once when the Docker container is first created (docker-entrypoint-initdb.d)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";       -- uuid_generate_v4()
CREATE EXTENSION IF NOT EXISTS pg_stat_statements; -- query performance monitoring
CREATE EXTENSION IF NOT EXISTS pg_trgm;            -- trigram full-text indexes

-- ---------------------------------------------------------------------------
-- Replication (Debezium CDC → NATS JetStream)
-- ---------------------------------------------------------------------------
ALTER SYSTEM SET wal_level = 'logical';
ALTER SYSTEM SET max_replication_slots = 4;
ALTER SYSTEM SET max_wal_senders = 4;

ALTER USER betopia REPLICATION;

-- Uncomment when Debezium connector is deployed:
-- CREATE PUBLICATION betopia_cdc FOR ALL TABLES;

-- ---------------------------------------------------------------------------
-- Enum types
-- ---------------------------------------------------------------------------
CREATE TYPE lead_status   AS ENUM ('new','contacted','qualified','lost','won');
CREATE TYPE lead_source   AS ENUM ('fiverr','direct','referral','website');
CREATE TYPE conv_status   AS ENUM ('active','paused','closed','quoted');
CREATE TYPE msg_role      AS ENUM ('customer','agent','system');
CREATE TYPE quot_status   AS ENUM ('draft','sent','accepted','rejected','expired');
CREATE TYPE res_type      AS ENUM ('pdf','docx','url','text','image');
CREATE TYPE agent_role    AS ENUM ('AGENT','SALES_MANAGER','ADMIN','READ_ONLY');
CREATE TYPE prop_status   AS ENUM ('generating','ready','sent','accepted','rejected','expired');

-- ---------------------------------------------------------------------------
-- 1. sales_agents
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sales_agents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            VARCHAR(255)    NOT NULL,
    email           VARCHAR(255)    NOT NULL UNIQUE,
    hashed_password VARCHAR(255)    NOT NULL,
    role            agent_role      NOT NULL DEFAULT 'AGENT',
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    odoo_user_id    INTEGER,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sales_agents_email     ON sales_agents (email);
CREATE INDEX IF NOT EXISTS idx_sales_agents_role      ON sales_agents (role);

-- ---------------------------------------------------------------------------
-- 2. leads
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS leads (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fiverr_order_id       VARCHAR(128) UNIQUE,
    fiverr_buyer_username VARCHAR(128),
    name                  VARCHAR(255) NOT NULL,
    email                 VARCHAR(255),
    budget                NUMERIC(12,2),
    requirement_summary   TEXT         NOT NULL DEFAULT '',
    status                lead_status  NOT NULL DEFAULT 'new',
    source                lead_source  NOT NULL DEFAULT 'fiverr',
    assigned_agent_id     UUID         REFERENCES sales_agents(id) ON DELETE SET NULL,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_leads_status           ON leads (status);
CREATE INDEX IF NOT EXISTS idx_leads_email            ON leads (email);
CREATE INDEX IF NOT EXISTS idx_leads_assigned_agent   ON leads (assigned_agent_id);
CREATE INDEX IF NOT EXISTS idx_leads_fiverr_order     ON leads (fiverr_order_id);

-- ---------------------------------------------------------------------------
-- 3. conversations
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversations (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id    UUID         NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    agent_id   UUID         NOT NULL REFERENCES sales_agents(id),
    status     conv_status  NOT NULL DEFAULT 'active',
    vector_id  VARCHAR(64),                   -- Qdrant point ID after indexing
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conversations_lead    ON conversations (lead_id);
CREATE INDEX IF NOT EXISTS idx_conversations_agent   ON conversations (agent_id);
CREATE INDEX IF NOT EXISTS idx_conversations_status  ON conversations (status);

-- ---------------------------------------------------------------------------
-- 4. messages
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS messages (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id     UUID         NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role                msg_role     NOT NULL,
    content             TEXT         NOT NULL,
    used_in_quotation   BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at   ON messages (conversation_id, created_at);

-- ---------------------------------------------------------------------------
-- 5. quotations
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quotations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID            NOT NULL REFERENCES conversations(id),
    lead_id         UUID            NOT NULL REFERENCES leads(id),
    agent_id        UUID            NOT NULL REFERENCES sales_agents(id),
    title           VARCHAR(512)    NOT NULL,
    line_items      JSONB           NOT NULL DEFAULT '[]',
    notes           TEXT            NOT NULL DEFAULT '',
    total_amount    NUMERIC(12,2)   NOT NULL DEFAULT 0,
    currency        VARCHAR(8)      NOT NULL DEFAULT 'USD',
    status          quot_status     NOT NULL DEFAULT 'draft',
    doc_path        VARCHAR(512),               -- PDF on disk / S3 key
    vector_id       VARCHAR(64),                -- Qdrant point ID
    odoo_order_id   INTEGER,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_quotations_lead        ON quotations (lead_id);
CREATE INDEX IF NOT EXISTS idx_quotations_status      ON quotations (status);
CREATE INDEX IF NOT EXISTS idx_quotations_conversation ON quotations (conversation_id);
-- JSONB GIN index for querying individual line items
CREATE INDEX IF NOT EXISTS idx_quotations_line_items  ON quotations USING GIN (line_items);

-- ---------------------------------------------------------------------------
-- 6. resources  (uploaded knowledge-base docs / URLs)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resources (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                    VARCHAR(255) NOT NULL,
    resource_type           res_type     NOT NULL,
    content                 TEXT         NOT NULL,
    file_path               VARCHAR(512),
    original_filename       VARCHAR(255),
    vector_id               VARCHAR(64),          -- Qdrant point ID
    uploaded_by_agent_id    UUID         NOT NULL REFERENCES sales_agents(id),
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_resources_type          ON resources (resource_type);
CREATE INDEX IF NOT EXISTS idx_resources_agent         ON resources (uploaded_by_agent_id);
-- Trigram index for full-text search on resource names
CREATE INDEX IF NOT EXISTS idx_resources_name_trgm     ON resources USING GIN (name gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- 7. requirements_docs  (extracted + enriched by P2 pipeline)  [owned by Dev 3]
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS requirements_docs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id     UUID         NOT NULL REFERENCES conversations(id),
    lead_id             UUID         NOT NULL REFERENCES leads(id),
    raw_extraction      JSONB        NOT NULL DEFAULT '{}',
    enriched_data       JSONB        NOT NULL DEFAULT '{}',
    budget_estimate     NUMERIC(12,2),
    confidence_score    NUMERIC(5,4),           -- 0.0000–1.0000
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reqdocs_conversation ON requirements_docs (conversation_id);
CREATE INDEX IF NOT EXISTS idx_reqdocs_lead         ON requirements_docs (lead_id);

-- ---------------------------------------------------------------------------
-- 8. proposals  (customer-facing PDF)  [owned by Dev 3]
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS proposals (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quotation_id         UUID         NOT NULL REFERENCES quotations(id),
    requirements_doc_id  UUID         REFERENCES requirements_docs(id),
    lead_id              UUID         NOT NULL REFERENCES leads(id),
    agent_id             UUID         NOT NULL REFERENCES sales_agents(id),
    title                VARCHAR(512) NOT NULL,
    executive_summary    TEXT         NOT NULL DEFAULT '',
    valid_days           INTEGER      NOT NULL DEFAULT 30,
    status               prop_status  NOT NULL DEFAULT 'generating',
    pdf_path             VARCHAR(512),
    download_token       VARCHAR(128),
    odoo_order_id        INTEGER,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_proposals_lead      ON proposals (lead_id);
CREATE INDEX IF NOT EXISTS idx_proposals_quotation ON proposals (quotation_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status    ON proposals (status);

-- ---------------------------------------------------------------------------
-- 9. outbox_events  (transactional outbox → NATS JetStream via Debezium CDC)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outbox_events (
    id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    aggregate_id UUID         NOT NULL,
    event_type   VARCHAR(128) NOT NULL,   -- e.g. "leads.created"
    payload      JSONB        NOT NULL,
    published    BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

-- Monthly partition for current month (extend with automation / pg_partman)
CREATE TABLE IF NOT EXISTS outbox_events_default PARTITION OF outbox_events DEFAULT;

CREATE INDEX IF NOT EXISTS idx_outbox_unpublished ON outbox_events (published) WHERE published = FALSE;
CREATE INDEX IF NOT EXISTS idx_outbox_aggregate   ON outbox_events (aggregate_id);

-- ---------------------------------------------------------------------------
-- updated_at auto-trigger
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DO $$
DECLARE tbl TEXT;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['sales_agents','leads','conversations','quotations','resources','requirements_docs','proposals'] LOOP
    EXECUTE format(
      'CREATE TRIGGER trg_%s_updated_at
       BEFORE UPDATE ON %s
       FOR EACH ROW EXECUTE FUNCTION set_updated_at();',
      tbl, tbl
    );
  END LOOP;
END;
$$;
