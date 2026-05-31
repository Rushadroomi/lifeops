-- LifeOps Database Schema
-- Run once on first start (handled automatically by Docker init)

CREATE TABLE IF NOT EXISTS event_logs (
    id          SERIAL PRIMARY KEY,
    event_id    TEXT UNIQUE NOT NULL,
    title       TEXT NOT NULL,
    start       TIMESTAMP NOT NULL,
    "end"       TIMESTAMP NOT NULL,
    status      TEXT NOT NULL DEFAULT 'synced',
    category    TEXT NOT NULL DEFAULT 'general',
    duration    INTEGER NOT NULL DEFAULT 60,
    deleted     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_logs_start    ON event_logs(start);
CREATE INDEX IF NOT EXISTS idx_event_logs_deleted  ON event_logs(deleted);
CREATE INDEX IF NOT EXISTS idx_event_logs_event_id ON event_logs(event_id);
