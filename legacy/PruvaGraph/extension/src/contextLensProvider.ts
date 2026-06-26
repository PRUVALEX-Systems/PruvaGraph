import * as vscode from 'vscode';
import { CoreEngineAPI } from '@pruvalex/shared-types';

export class ContextLensViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'pruvagraph.contextLens';
    private view?: vscode.WebviewView;
    private core?: CoreEngineAPI;

    constructor(private readonly extensionUri: vscode.Uri, core?: CoreEngineAPI) {
        this.core = core;
    }

    public resolveWebviewView(webviewView: vscode.WebviewView) {
        try {
            console.log('[PRUVALEX] ContextLens.resolveWebviewView() called');
            console.log('[PRUVALEX] core available:', !!this.core);
            
            this.view = webviewView;
            webviewView.webview.options = {
                enableScripts: true,
                localResourceRoots: [vscode.Uri.joinPath(this.extensionUri, 'resources')]
            };

            console.log('[PRUVALEX] Generating ContextLens HTML...');
            const html = this.getHtml(webviewView.webview);
            console.log('[PRUVALEX] Setting ContextLens webview.html, length:', html.length);
            webviewView.webview.html = html;
            console.log('[PRUVALEX] ContextLens HTML rendered to webview');

            webviewView.webview.onDidReceiveMessage(async message => {
                if (!message || !message.command) {
                    return;
                }

                if (message.command === 'openContextLensPanel') {
                    await vscode.commands.executeCommand('PruvaGraph: ContextLens — Show');
                }
            });
            
            console.log('[PRUVALEX] ContextLens.resolveWebviewView() completed successfully');
        } catch (err) {
            console.error('[PRUVALEX] ContextLens.resolveWebviewView() error:', err);
            webviewView.webview.html = `
                <html>
                    <body style="color: #ff6b6b; padding: 20px; font-family: monospace;">
                        <h2>Error initializing ContextLens</h2>
                        <pre>${String(err).substring(0, 500)}</pre>
                        <p>Check the VS Code Developer Console for details.</p>
                    </body>
                </html>
            `;
        }
    }

    public setCore(core: CoreEngineAPI) {
        this.core = core;
    }

    private getHtml(webview: vscode.Webview): string {
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline' vscode-resource: https:; script-src 'unsafe-inline' vscode-resource: https:; img-src 'self' data: https:;" />
    <title>ContextLens</title>
    <style>
        body {
            margin: 0;
            padding: 16px;
            color: var(--vscode-foreground, #ffffff);
            background: var(--vscode-editor-background, #1e1e1e);
            font-family: var(--vscode-font-family, 'Segoe WPC', 'Segoe UI', sans-serif);
        }

        h1 {
            margin: 0 0 12px;
            font-size: 1rem;
            font-weight: 700;
        }

        p {
            margin: 0 0 12px;
            color: var(--vscode-descriptionForeground, #cccccc);
            line-height: 1.5;
        }

        button {
            border: none;
            border-radius: 8px;
            padding: 10px 14px;
            background: linear-gradient(135deg, #7c3aed, #a78bfa);
            color: #ffffff;
            font-weight: 700;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <h1 style="color: #10b981;">✓ CONTEXTLENS PANEL LOADED</h1>
    <h1>ContextLens</h1>
    <p>This view is registered and ready. Click below to open the ContextLens debugger panel.</p>
    <button id="openPanel">Open ContextLens Panel</button>

    <script>
        const vscode = acquireVsCodeApi();
        console.log('[ContextLens] Webview initialized');
        document.getElementById('openPanel').addEventListener('click', () => {
            console.log('[ContextLens] Button clicked, sending command');
            vscode.postMessage({ command: 'openContextLensPanel' });
        });
    </script>
</body>
</html>`;
    }
}
