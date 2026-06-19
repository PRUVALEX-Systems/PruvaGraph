import * as vscode from 'vscode';
import { PRUVALEXModule, CoreEngineAPI } from '@pruvalex/shared-types';
import { RulesForgeRepository } from './repository.js';
import * as crypto from 'crypto';

export const rulesforgeModule: PRUVALEXModule = {
    id: 'rulesforge',
    activate(deps: CoreEngineAPI): vscode.Disposable {
        const repo = new RulesForgeRepository(deps.db);

        deps.mcp.registerTool('create_rule', async (args: any) => {
            const { layer, rule_text, source } = args as { layer: string, rule_text: string, source: string };
            const id = crypto.randomUUID();
            repo.insertRule(id, layer || 'global', rule_text, source || 'mcp_tool');
            return { id, status: 'rule created' };
        });

        deps.mcp.registerTool('get_applicable_rules', async (args: any) => {
            const { file_uri, layer } = args as { file_uri?: string, layer?: string };
            // Also integrate AST context if available (file_uri)
            if (file_uri) {
                const tree = deps.workspace.getAST(vscode.Uri.parse(file_uri));
                if (!tree.isAvailable) {
                    console.log('[RulesForge] Tree-sitter not available — using text-based rules only');
                }
            }
            const rules = repo.getRules(layer);
            return { rules, file_uri: file_uri || null };
        });

        deps.mcp.registerTool('delete_rule', async (args: any) => {
            const { id } = args as { id: string };
            repo.deleteRule(id);
            return { status: 'rule deleted' };
        });

        const onSuggestionAccepted = deps.events.on('suggestion:accepted', async ({ uri, diff }) => {
            // Analyze diff to infer a pattern/rule
            // Simple heuristic: if diff contains an interface definition, log naming pattern
            const interfaceMatch = diff.match(/interface\s+(\w+)/);
            if (interfaceMatch) {
                const id = crypto.randomUUID();
                repo.insertRule(
                    id,
                    `Accepted interface name: ${interfaceMatch[1]}`,
                    `auto-learned from ${uri}`,
                    'inferred',
                    'typescript'
                );
                console.log(`[RulesForge] AST Rule learned from accepted suggestion`);
            }
        });

        return {
            dispose: () => {
                onSuggestionAccepted.dispose();
            }
        };
    }
};

