-- Task 8: app-owned Postgres schema `app` in Lakebase (database databricks_postgres).
--
-- Run by the Fleetwise Seller Hub at startup AS THE APP SERVICE PRINCIPAL (Task 10), never by a
-- developer: the SP has CAN_CONNECT_AND_CREATE, so it must create the schema to own it (a schema
-- created by a person would leave the SP with "permission denied for schema app").
-- Idempotent: safe on every app start. Never drops or rewrites data.
--
-- Write-back: Lakehouse Sync (CDF config on Postgres schema `app`) streams every insert/update/
-- delete of these tables into UC as lb_<table>_history; it requires REPLICA IDENTITY FULL on each
-- table, set below. The `writeback_merge` job task folds that history into silver/gold Delta.
-- Column types stay within the Lakehouse Sync supported set (int8, text, timestamptz).

CREATE SCHEMA IF NOT EXISTS app;

-- A seller's decision on a next best action (serving.next_best_actions.action_id). Append-only
-- from the app: a new decision is a new row; the latest row per action_id is the current state.
CREATE TABLE IF NOT EXISTS app.seller_actions (
  id              bigserial PRIMARY KEY,
  action_id       text NOT NULL,
  opportunity_id  text NOT NULL,
  persona_user_id text NOT NULL,
  decision        text NOT NULL CHECK (decision IN ('accepted', 'done', 'dismissed')),
  reason          text,
  created_at      timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE app.seller_actions REPLICA IDENTITY FULL;
CREATE INDEX IF NOT EXISTS seller_actions_action_idx ON app.seller_actions (action_id, created_at DESC);
CREATE INDEX IF NOT EXISTS seller_actions_persona_idx ON app.seller_actions (persona_user_id, created_at DESC);

-- Free-text notes a seller keeps on an opportunity.
CREATE TABLE IF NOT EXISTS app.notes (
  id              bigserial PRIMARY KEY,
  opportunity_id  text NOT NULL,
  persona_user_id text NOT NULL,
  body            text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE app.notes REPLICA IDENTITY FULL;
CREATE INDEX IF NOT EXISTS notes_opportunity_idx ON app.notes (opportunity_id, created_at DESC);

-- Follow-up email drafts (generated in the app, edited by the seller).
CREATE TABLE IF NOT EXISTS app.email_drafts (
  id              bigserial PRIMARY KEY,
  opportunity_id  text NOT NULL,
  persona_user_id text NOT NULL,
  subject         text NOT NULL,
  body            text NOT NULL,
  created_at      timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE app.email_drafts REPLICA IDENTITY FULL;
CREATE INDEX IF NOT EXISTS email_drafts_opportunity_idx ON app.email_drafts (opportunity_id, created_at DESC);
