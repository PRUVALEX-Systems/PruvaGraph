import { ModuleRepository, IGraphStore } from '@pruvalex/shared-types';

export interface ITokenLedgerEntry {
    id: number;
    module: string;
    tool_name: string;
    server_id: string;
    tokens_in: number;
    tokens_out: number;
    latency_ms: number;
    ts: number;
}

export class ContextLensRepository {
    private repo: ModuleRepository;
    constructor(store: IGraphStore) {
        this.repo = store.scope('token');
    }
    
    getRecentCalls(limit = 100): ITokenLedgerEntry[] {
        return this.repo.all<ITokenLedgerEntry>(
            `SELECT * FROM token_ledger ORDER BY ts DESC LIMIT ?`, limit
        );
    }
    
    getTotalUsage(): { totalIn: number; totalOut: number } {
        return this.repo.get<{ totalIn: number; totalOut: number }>(
            `SELECT sum(tokens_in) as totalIn, sum(tokens_out) as totalOut FROM token_ledger`
        ) ?? { totalIn: 0, totalOut: 0 };
    }

    getUsageByModule(): Array<{ module: string; totalIn: number; totalOut: number; calls: number }> {
        return this.repo.all(
            `SELECT module, 
                    SUM(tokens_in) as totalIn, 
                    SUM(tokens_out) as totalOut,
                    COUNT(*) as calls
             FROM token_ledger 
             GROUP BY module 
             ORDER BY totalIn DESC`
        );
    }
}

