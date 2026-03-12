-- Migration: control_logs table for oc_control audit trail
-- Run on VPS:
--   sudo docker exec -i oc_postgres psql -U openclawd -d openclawd < migrations/002_control_logs.sql

CREATE TABLE IF NOT EXISTS control_logs (
    id          SERIAL PRIMARY KEY,
    sender      TEXT NOT NULL,
    command     TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'ok',
    response    TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);
