import * as vscode from 'vscode';
import { PRUVALEXModule, CoreEngineAPI } from '@pruvalex/shared-types';
import { DriftGuardRepository } from './repository.js';
import { DriftGuardIndexer } from './indexer.js';
import { DriftGuardValidator } from './validator.js';

export const driftguardModule: PRUVALEXModule = {
    id: 'driftguard',
    activate(deps: CoreEngineAPI): vscode.Disposable {
        const repo = new DriftGuardRepository(deps.db);
        const indexer = new DriftGuardIndexer(deps.workspace, repo);
        const validator = new DriftGuardValidator(repo, deps.workspace, deps.events);

        // Register MCP Tools
        deps.mcp.registerTool('validate_symbol', async (args: any) => {
            const { name, pkg } = args as { name: string, pkg: string };
            const symbol = repo.getSymbol(pkg, name);
            return { valid: !!symbol, symbol };
        });

        deps.mcp.registerTool('check_import', async (args: any) => {
            const { pkg } = args as { pkg: string };
            const manifest = deps.workspace.getPackageManifest();
            const version = manifest.dependencies?.[pkg] || manifest.devDependencies?.[pkg];
            return { installed: !!version, version };
        });

        deps.mcp.registerTool('get_api_signature', async (args: any) => {
            const { method, pkg } = args as { method: string, pkg: string };
            const symbol = repo.getSymbol(pkg, method);
            return { signature: symbol?.signature };
        });

        // Diagnostics hooks
        const onSave = vscode.workspace.onDidSaveTextDocument(doc => validator.validateDocument(doc));
        const onOpen = vscode.workspace.onDidOpenTextDocument(doc => validator.validateDocument(doc));

        // Initial scan of open editors
        vscode.window.visibleTextEditors.forEach(editor => {
            validator.validateDocument(editor.document);
        });

        const acceptFix = vscode.commands.registerCommand('pruvagraph.driftguard.acceptFix', 
            (uri: string, diff: string) => {
                deps.events.emit('suggestion:accepted', { uri, diff });
            }
        );

        return {
            dispose: () => {
                validator.dispose();
                onSave.dispose();
                onOpen.dispose();
                acceptFix.dispose();
            }
        };
    }
};

