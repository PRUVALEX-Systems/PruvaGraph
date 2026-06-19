import { IGraphStore, ModuleRepository } from '@pruvalex/shared-types';

export interface IDriftGuardIndex {
    id: string;
    symbol: string;
    package: string;
    file_uri: string;
    version: string;
    signature: string;
    created_at: number;
}

export class DriftGuardRepository {
    private repo: ModuleRepository;

    constructor(store: IGraphStore) {
        this.repo = store.scope('driftguard');
    }

    upsertSymbol(id: string, symbol: string, pkg: string, file_uri: string, version: string, signature: string) {
        this.repo.run(`
            INSERT INTO driftguard_index (id, symbol, package, file_uri, version, signature, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                file_uri = excluded.file_uri,
                version = excluded.version,
                signature = excluded.signature,
                created_at = excluded.created_at
        `, id, symbol, pkg, file_uri, version, signature, Date.now());
    }

    getSymbol(symbol: string, pkg: string): IDriftGuardIndex | undefined {
        return this.repo.get<IDriftGuardIndex>(`SELECT * FROM driftguard_index WHERE symbol = ? AND package = ?`, symbol, pkg);
    }
}

