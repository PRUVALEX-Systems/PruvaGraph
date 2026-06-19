import * as vscode from 'vscode';

export interface WebviewHost {
    registerPanel(id: string, title: string, options?: vscode.WebviewPanelOptions): vscode.WebviewPanel | undefined;
    getPanel(id: string): vscode.WebviewPanel | undefined;
    disposePanel(id: string): void;
}

export class WebviewRegistry implements WebviewHost {
    private panels: Map<string, vscode.WebviewPanel> = new Map();

    registerPanel(id: string, title: string, options: vscode.WebviewPanelOptions = {}): vscode.WebviewPanel {
        const existing = this.panels.get(id);
        if (existing) {
            existing.reveal();
            return existing;
        }
        const panel = vscode.window.createWebviewPanel(
            id, title, vscode.ViewColumn.Two,
            { enableScripts: true, ...options }
        );
        panel.onDidDispose(() => this.panels.delete(id));
        this.panels.set(id, panel);
        return panel;
    }

    getPanel(id: string): vscode.WebviewPanel | undefined {
        return this.panels.get(id);
    }

    disposePanel(id: string): void {
        this.panels.get(id)?.dispose();
        this.panels.delete(id);
    }

    dispose(): void {
        for (const panel of this.panels.values()) panel.dispose();
        this.panels.clear();
    }
}
