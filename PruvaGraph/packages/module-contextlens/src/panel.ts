import * as vscode from 'vscode';
import { getWebviewShell } from '@pruvalex/shared-ui';

import { WebviewHost } from '@pruvalex/shared-types';

export class ContextLensPanel {
    private panel: vscode.WebviewPanel | undefined;
    private host: WebviewHost;

    constructor(host: WebviewHost) {
        this.host = host;
    }

    public show(ledgerData: any[], moduleData: any[]) {
        this.panel = this.host.registerPanel('contextLens', 'ContextLens Debugger');
        if (this.panel) {
            const htmlContent = this.generateHtml(ledgerData, moduleData);
            this.panel.webview.html = getWebviewShell('ContextLens', htmlContent);
        }
    }

    private generateHtml(ledgerData: any[], moduleData: any[]): string {
        const rows = ledgerData.map(l => `
            <tr>
                <td>${l.module}</td>
                <td>${l.tool_name}</td>
                <td>${l.tokens_in}</td>
                <td>${l.tokens_out}</td>
                <td>${l.latency_ms}ms</td>
                <td>${new Date(l.ts).toLocaleTimeString()}</td>
            </tr>
        `).join('');

        const moduleRows = moduleData.map(m => `
            <tr>
                <td>${m.module}</td>
                <td>${m.totalIn}</td>
                <td>${m.totalOut}</td>
                <td>${m.calls}</td>
            </tr>
        `).join('');

        return `
            <div class="surface" style="padding: 16px;">
                <h2 style="color: var(--omni-accent); margin-top: 0;">ContextLens Debugger</h2>
                
                <h3>Usage By Module</h3>
                <table style="width: 100%; text-align: left; border-collapse: collapse; margin-bottom: 24px;">
                    <thead>
                        <tr style="border-bottom: 0.5px solid var(--omni-border);">
                            <th>Module</th>
                            <th>Total Tokens In</th>
                            <th>Total Tokens Out</th>
                            <th>Calls</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${moduleRows}
                    </tbody>
                </table>

                <h3>Recent Calls</h3>
                <table style="width: 100%; text-align: left; border-collapse: collapse;">
                    <thead>
                        <tr style="border-bottom: 0.5px solid var(--omni-border);">
                            <th>Module</th>
                            <th>Tool</th>
                            <th>Tokens In</th>
                            <th>Tokens Out</th>
                            <th>Latency</th>
                            <th>Time</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows}
                    </tbody>
                </table>
            </div>
        `;
    }
}

