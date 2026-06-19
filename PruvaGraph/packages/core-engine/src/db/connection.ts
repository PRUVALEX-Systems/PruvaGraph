import Database from 'better-sqlite3';
import * as path from 'path';
import { IGraphStoreInternal, ModuleRepository } from '@pruvalex/shared-types';

export class GraphStore implements IGraphStoreInternal {
    private db: Database.Database;

    constructor(storagePath?: string) {
        const dbPath = storagePath ? path.join(storagePath, 'pruvagraph.db') : 'pruvagraph.db';
        this.db = new Database(dbPath);
    }

    scope(modulePrefix: string): ModuleRepository {
        const ALLOWED_PREFIXES = ['driftguard', 'ghostmemory', 'rulesforge', 'taskweaver', 'token', 'contextlens'];
        // Wait, the prompt said 'token', I will use 'token' for contextlens and token ledger
        if (!ALLOWED_PREFIXES.includes(modulePrefix)) {
            throw new Error(`[GraphStore] Unknown module prefix: ${modulePrefix}`);
        }
        const db = this.db;
        return {
            run(sql: string, ...params: unknown[]) {
                return db.prepare(sql).run(...params);
            },
            get<T>(sql: string, ...params: unknown[]): T | undefined {
                return db.prepare(sql).get(...params) as T | undefined;
            },
            all<T>(sql: string, ...params: unknown[]): T[] {
                return db.prepare(sql).all(...params) as T[];
            }
        };
    }
    
    _internalExec(sql: string): void {
        this.db.exec(sql);
    }

    _internalQuery<T>(sql: string, ...params: unknown[]): T[] {
        return this.db.prepare(sql).all(...params) as T[];
    }
    
    migrate(): void {
        this.db.exec(`PRAGMA journal_mode = WAL;`);
        this.db.exec(`PRAGMA synchronous = NORMAL;`);
        this.db.exec(`PRAGMA foreign_keys = ON;`);

        this.db.exec(`
            CREATE TABLE IF NOT EXISTS driftguard_index (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                package TEXT NOT NULL,
                file_uri TEXT NOT NULL,
                version TEXT,
                signature TEXT,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ghostmemory_entries (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                project TEXT NOT NULL DEFAULT 'default',
                embedding BLOB,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rulesforge_rules (
                id TEXT PRIMARY KEY,
                rule_name TEXT NOT NULL,
                layer TEXT NOT NULL DEFAULT 'global',
                condition TEXT NOT NULL,
                action TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS taskweaver_checkpoints (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                commit_sha TEXT NOT NULL,
                files_changed TEXT NOT NULL,
                git_sha TEXT,
                created_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS token_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module TEXT NOT NULL,
                tool_name TEXT NOT NULL DEFAULT '',
                server_id TEXT NOT NULL DEFAULT 'pruvagraph',
                tokens_in INTEGER NOT NULL DEFAULT 0,
                tokens_out INTEGER NOT NULL DEFAULT 0,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                ts INTEGER NOT NULL
            );
        `);
    }
}

