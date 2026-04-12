-- PostgreSQL 17 initialization script
-- Runs once when the Docker container is first created

-- Enable logical replication (for future Debezium CDC)
ALTER SYSTEM SET wal_level = 'logical';
ALTER SYSTEM SET max_replication_slots = 4;
ALTER SYSTEM SET max_wal_senders = 4;

-- Enable pg_stat_statements for query performance monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- UUID extension (native in PG17, but explicit for clarity)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Full-text search support
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Grant replication permission to application user (for CDC)
ALTER USER betopia REPLICATION;

-- Create publication for Debezium CDC (future)
-- CREATE PUBLICATION betopia_cdc FOR ALL TABLES;
