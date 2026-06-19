PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- DriftGuard: Hallucination Detection Index
CREATE TABLE IF NOT EXISTS driftguard_index (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    package TEXT NOT NULL,
    file_uri TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

-- GhostMemory: Cross-session Memory
CREATE TABLE IF NOT EXISTS ghostmemory_entries (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding BLOB,
    created_at INTEGER NOT NULL
);

-- RulesForge: Custom Prompt Rules
CREATE TABLE IF NOT EXISTS rulesforge_rules (
    id TEXT PRIMARY KEY,
    rule_name TEXT NOT NULL,
    condition TEXT NOT NULL,
    action TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at INTEGER NOT NULL
);

-- TaskWeaver: Checkpoints / Rollback
CREATE TABLE IF NOT EXISTS taskweaver_checkpoints (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    files_changed TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

-- ContextLens: Token Cost Visibility
CREATE TABLE IF NOT EXISTS token_ledger (
    id TEXT PRIMARY KEY,
    module_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    server_id TEXT NOT NULL,
    tokens_in INTEGER NOT NULL,
    tokens_out INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);

COMMIT;
