import * as vscode from 'vscode';
import { PRUVALEXModule, CoreEngineAPI } from '@pruvalex/shared-types';
import { GhostMemoryRepository } from './repository.js';
import * as crypto from 'crypto';

export const ghostmemoryModule: PRUVALEXModule = {
    id: 'ghostmemory',
    activate(deps: CoreEngineAPI): vscode.Disposable {
        const repo = new GhostMemoryRepository(deps.db);

        deps.mcp.registerTool('store_memory', async (args: any) => {
            const { content, tags, project } = args as { content: string, tags: string[], project: string };
            const id = crypto.randomUUID();
            repo.insertMemory(id, content, tags || [], project || 'default');
            return { id, status: 'stored' };
        });

        deps.mcp.registerTool('recall_relevant', async (args: any) => {
            const { query, top_k, project } = args as { query: string, top_k?: number, project?: string };
            const results = repo.recallRelevant(query, project || 'default', top_k || 5);
            return { results: results.map(r => ({...r, tags: JSON.parse(r.tags)})) };
        });

        deps.mcp.registerTool('tag_memory', async (args: any) => {
            const { id, tags } = args as { id: string, tags: string[] };
            repo.updateTags(id, tags);
            return { id, status: 'tags updated' };
        });

        const onSuggestionAccepted = deps.events.on('suggestion:accepted', async ({ uri, diff }) => {
            // Auto-store accepted suggestions as memory
            const id = crypto.randomUUID();
            const project = vscode.workspace.workspaceFolders?.[0]?.name || 'default';
            repo.insertMemory(id, `[auto-learned] Accepted suggestion in ${uri}:\n${diff}`,
                ['auto-learned', 'suggestion'], project, null);
            console.log(`[GhostMemory] Stored accepted suggestion from ${uri}`);
        });

        return {
            dispose: () => {
                onSuggestionAccepted.dispose();
            }
        };
    }
};

