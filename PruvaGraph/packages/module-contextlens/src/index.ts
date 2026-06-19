import * as vscode from 'vscode';
import { PRUVALEXModule, CoreEngineAPI } from '@pruvalex/shared-types';
import { ContextLensPanel } from './panel.js';
import { ContextLensRepository } from './repository.js';

export const contextlensModule: PRUVALEXModule = {
    id: 'contextlens',
    activate(deps: CoreEngineAPI): vscode.Disposable {
        const panel = new ContextLensPanel(deps.webview);
        const repo = new ContextLensRepository(deps.db);

        // 1. VS Code Command to open the Debugger Panel
        const showCmd = vscode.commands.registerCommand('PruvaGraph: ContextLens — Show', () => {
            const data = repo.getRecentCalls(100);
            const moduleData = repo.getUsageByModule();
            panel.show(data, moduleData);
        });

        // 2. React to mcp:call by auto-refreshing panel if open
        const onMcpCall = deps.events.on('mcp:call', () => {
            const data = repo.getRecentCalls(100);
            const moduleData = repo.getUsageByModule();
            panel.show(data, moduleData);
        });

        // 3. Register MCP Tools
        deps.mcp.registerTool('get_active_context', async () => {
            return repo.getRecentCalls(10);
        });

        deps.mcp.registerTool('measure_token_usage', async () => {
            return repo.getTotalUsage();
        });

        deps.mcp.registerTool('trace_last_tool_calls', async () => {
            return repo.getRecentCalls(5);
        });

        return {
            dispose: () => {
                showCmd.dispose();
                onMcpCall.dispose();
            }
        };
    }
};

