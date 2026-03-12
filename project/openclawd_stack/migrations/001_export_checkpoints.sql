-- Migration: create export_checkpoints table
-- Run manually or let SQLAlchemy auto-create on startup

CREATE TABLE IF NOT EXISTS export_checkpoints (
    name       TEXT        PRIMARY KEY,
    last_id    INTEGER     NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
