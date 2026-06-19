import * as vscode from 'vscode';
import { CoreEngineAPI } from '@pruvalex/shared-types';
import { GraphStore, MCPRouter, WorkspaceContext, EventBus, TokenLedger, WebviewRegistry } from '@pruvalex/core-engine';

export function buildCoreEngine(context: vscode.ExtensionContext): CoreEngineAPI {
    const events = new EventBus();
    const db = new GraphStore(context.globalStorageUri.fsPath);
    
    // Auto-migrate schema on activation
    db.migrate();

    // Start ledger recording
    new TokenLedger(events, db);

    return {
        db,
        mcp: new MCPRouter(events),
        workspace: new WorkspaceContext(context.extensionUri.fsPath),
        events,
        webview: new WebviewRegistry()
    };
}

