import { IEventBus, PRUVALEXEventMap, IGraphStore } from '@pruvalex/shared-types';

export class TokenLedger {
    constructor(private events: IEventBus<PRUVALEXEventMap>, private dbStore: IGraphStore) {
        this.events.on('mcp:call', (payload) => this.recordCall(payload));
    }

    private recordCall(payload: PRUVALEXEventMap['mcp:call']) {
        const stmt = `
            INSERT INTO token_ledger (module, tool_name, server_id, tokens_in, tokens_out, latency_ms, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        `;
        this.dbStore.scope('token').run(
            stmt,
            payload.module,
            payload.tool,
            payload.server,
            payload.tokensIn,
            payload.tokensOut,
            payload.latencyMs,
            Date.now()
        );
    }
}

