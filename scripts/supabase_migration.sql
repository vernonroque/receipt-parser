-- ============================================================
-- Receipt Parser — Supabase Database Setup
-- Run this in your Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================================

-- API Keys table
-- Note: We NEVER store the raw key — only a SHA-256 hash of it.
CREATE TABLE IF NOT EXISTS api_keys (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  key_hash        TEXT NOT NULL UNIQUE,   -- SHA-256 of the raw key
  key_preview     TEXT NOT NULL,          -- e.g. "rp_live_abc...xyz" for display
  revoked         BOOLEAN NOT NULL DEFAULT FALSE,
  request_count   INTEGER NOT NULL DEFAULT 0,
  last_used_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast key lookups on every API request
CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys (key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_user  ON api_keys (user_id);

-- ============================================================
-- Row Level Security (RLS)
-- Users can only see and manage their own keys.
-- The service_role key (used by your FastAPI backend) bypasses RLS.
-- ============================================================

ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

-- Users can read their own keys
CREATE POLICY "users_read_own_keys"
  ON api_keys FOR SELECT
  USING (auth.uid() = user_id);

-- Users can insert their own keys
CREATE POLICY "users_insert_own_keys"
  ON api_keys FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Users can update their own keys (e.g. revoke)
CREATE POLICY "users_update_own_keys"
  ON api_keys FOR UPDATE
  USING (auth.uid() = user_id);


-- ============================================================
-- Optional: Parse history table (uncomment to enable)
-- Useful for debugging and usage analytics
-- ============================================================

-- CREATE TABLE IF NOT EXISTS parse_history (
--   id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--   user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
--   api_key_id      UUID REFERENCES api_keys(id) ON DELETE SET NULL,
--   file_type       TEXT,           -- 'image' or 'pdf'
--   pages_count     INTEGER,
--   success         BOOLEAN,
--   error_message   TEXT,
--   result          JSONB,          -- The full parsed JSON result
--   created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
-- );

-- ALTER TABLE parse_history ENABLE ROW LEVEL SECURITY;

-- CREATE POLICY "users_read_own_history"
--   ON parse_history FOR SELECT
--   USING (auth.uid() = user_id);
