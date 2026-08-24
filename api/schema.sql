-- Cycle records. One row per committee cycle.
-- The full record is kept as JSON: it is the artifact the agent produces, and reshaping it
-- into columns would mean a migration every time the committee gains a role. Columns exist
-- only for the fields we filter or aggregate on.
CREATE TABLE IF NOT EXISTS cycles (
  id            TEXT PRIMARY KEY,
  started_at    TEXT NOT NULL,
  finished_at   TEXT,
  dry_run       INTEGER NOT NULL DEFAULT 1,
  market_open   INTEGER NOT NULL DEFAULT 0,
  equity        REAL NOT NULL DEFAULT 0,
  trades_placed INTEGER NOT NULL DEFAULT 0,
  cost_usd      REAL NOT NULL DEFAULT 0,
  record        TEXT NOT NULL,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cycles_started ON cycles(started_at DESC);

-- One row per structure the committee considered. Refusals are first-class rows: "why we
-- didn't trade" is the more interesting half of an autonomous trader's log.
CREATE TABLE IF NOT EXISTS decisions (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  cycle_id     TEXT NOT NULL REFERENCES cycles(id),
  underlying   TEXT NOT NULL,
  strategy     TEXT NOT NULL,
  fingerprint  TEXT,
  expiry       TEXT,
  outcome      TEXT NOT NULL,     -- executed | refused_gate | refused_committee | dry_run
  blocked_by   TEXT,              -- comma-separated gate names
  bear_verdict TEXT,
  max_loss     REAL,
  net_credit   REAL,
  started_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_decisions_cycle ON decisions(cycle_id);
CREATE INDEX IF NOT EXISTS idx_decisions_outcome ON decisions(outcome);
