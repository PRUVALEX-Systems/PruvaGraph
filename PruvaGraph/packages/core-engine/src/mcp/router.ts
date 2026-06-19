import { IMCPTransport, IEventBus, PRUVALEXEventMap } from '@pruvalex/shared-types';
import { encode } from 'gpt-tokenizer';

let mcpClient: any = null;
try {
    // Optional: only available if @modelcontextprotocol/sdk is installed
    import('@modelcontextprotocol/sdk/client/index.js').then(({ Client }) => {
        import('@modelcontextprotocol/sdk/client/stdio.js').then(({ StdioClientTransport }) => {
            mcpClient = { Client, StdioClientTransport };
        });
    });
} catch (_e) {
    // SDK not installed — external server calls will fail gracefully
}

export class MCPRouter implements IMCPTransport {
    private localTools: Map<string, (args: unknown) => Promise<unknown>> = new Map();
    private events: IEventBus<PRUVALEXEventMap>;

    constructor(events: IEventBus<PRUVALEXEventMap>) {
        this.events = events;
    }

    async call(server: string, tool: string, args: unknown): Promise<unknown> {
        const start = Date.now();
        let result: unknown;
        
        const argsStr = JSON.stringify(args ?? {});
        const tokensIn = encode(argsStr).length;

        const moduleFromTool = (t: string): string => {
            if (t.startsWith('validate_') || t.startsWith('check_') || t.startsWith('get_api_')) return 'driftguard';
            if (t.startsWith('get_active_context') || t.startsWith('measure_') || t.startsWith('trace_')) return 'contextlens';
            if (t.startsWith('store_memory') || t.startsWith('recall_')) return 'ghostmemory';
            if (t.startsWith('create_rule') || t.startsWith('get_applicable') || t.startsWith('delete_rule')) return 'rulesforge';
            if (t.startsWith('create_checkpoint') || t.startsWith('get_task') || t.startsWith('rollback_')) return 'taskweaver';
            return server; // fallback
        };

        try {
            if (server === 'pruvagraph' || server === 'local') {
                const handler = this.localTools.get(tool);
                if (!handler) {
                    throw new Error(`Local tool ${tool} not registered in MCPRouter`);
                }
                result = await handler(args);
            } else {
                if (!mcpClient) {
                    return { 
                        error: `External MCP server '${server}' not supported without @modelcontextprotocol/sdk`,
                        hint: 'npm install @modelcontextprotocol/sdk in core-engine'
                    };
                }
                // Proxy to real @modelcontextprotocol/sdk client
                throw new Error(`External server ${server} not yet configured`);
            }
        } finally {
            const latencyMs = Date.now() - start;
            
            const resultStr = JSON.stringify(result ?? {});
            const tokensOut = encode(resultStr).length;

            const moduleName = moduleFromTool(tool);

            // Emit to TokenLedger/ContextLens
            this.events.emit('mcp:call', {
                server,
                tool,
                module: moduleName,
                tokensIn,
                tokensOut,
                latencyMs
            });
        }
        
        return result;
    }

    registerTool(toolName: string, handler: (args: unknown) => Promise<unknown>): void {
        this.localTools.set(toolName, handler);
    }
}

