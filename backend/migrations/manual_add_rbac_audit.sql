-- Run against existing PostgreSQL databases when upgrading to RBAC + audit columns.
-- (SQLAlchemy create_all does not ALTER existing tables.)

ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(32) NOT NULL DEFAULT 'viewer';
ALTER TABLE agent_logs ADD COLUMN IF NOT EXISTS triggered_by_role VARCHAR(32);

-- Optional: backfill from legacy data if needed.
