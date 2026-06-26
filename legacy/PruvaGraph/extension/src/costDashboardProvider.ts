import * as vscode from 'vscode';
import { CostReportRepository, CostMetrics } from './costReportRepository.js';
import { CoreEngineAPI } from '@pruvalex/shared-types';

export class CostDashboardViewProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'pruvagraph.costDashboard';

    private view?: vscode.WebviewView;
    private costRepo?: CostReportRepository;
    private updateInterval?: NodeJS.Timeout;
    private eventListener?: vscode.Disposable;
    private core?: CoreEngineAPI;

    constructor(private readonly extensionUri: vscode.Uri, core?: CoreEngineAPI) {
        this.core = core;
        if (core) {
            this.costRepo = new CostReportRepository(core.db);
        }
    }

    public resolveWebviewView(webviewView: vscode.WebviewView) {
        try {
            console.log('[PRUVALEX] CostDashboard.resolveWebviewView() called');
            console.log('[PRUVALEX] core available:', !!this.core);
            console.log('[PRUVALEX] costRepo available:', !!this.costRepo);
            
            this.view = webviewView;
            webviewView.webview.options = {
                enableScripts: true,
                localResourceRoots: [
                    vscode.Uri.joinPath(this.extensionUri, 'resources'),
                    vscode.Uri.joinPath(this.extensionUri, 'assets')
                ]
            };

            console.log('[PRUVALEX] Generating HTML...');
            const html = this.getHtml(webviewView.webview);
            console.log('[PRUVALEX] HTML generated, length:', html.length);
            console.log('[PRUVALEX] Setting webview.html...');
            webviewView.webview.html = html;
            console.log('[PRUVALEX] HTML rendered to webview');

            // Load and send initial metrics
            console.log('[PRUVALEX] Updating metrics...');
            this.updateMetrics();
            console.log('[PRUVALEX] Metrics updated');

            if (this.core) {
                console.log('[PRUVALEX] Registering event listener for mcp:call');
                this.eventListener = this.core.events.on('mcp:call', () => {
                    this.updateMetrics();
                });
            } else {
                console.warn('[PRUVALEX] core is not available in resolveWebviewView');
            }

            // Periodic refresh every 5 seconds
            this.updateInterval = setInterval(() => {
                this.updateMetrics();
            }, 5000);

            webviewView.onDidDispose(() => {
                if (this.updateInterval) clearInterval(this.updateInterval);
                this.eventListener?.dispose();
            });

            webviewView.webview.onDidReceiveMessage(async (message: any) => {
                console.log('[PRUVALEX] CostDashboard webview message received:', message);
                if (!message || !message.command) {
                    console.log('[PRUVALEX] CostDashboard webview message missing command');
                    return;
                }

                switch (message.command) {
                    case 'initializeGraph':
                        await vscode.commands.executeCommand('pruvagraph.initializeGraph');
                        break;
                    case 'queryCodebase':
                        await vscode.commands.executeCommand('pruvagraph.queryCodebase');
                        break;
                    case 'toggleWatchMode':
                        await vscode.commands.executeCommand('pruvagraph.toggleWatchMode');
                        break;
                    case 'showCostReport':
                        await vscode.commands.executeCommand('pruvagraph.showCostReport');
                        break;
                    case 'dryRun':
                        await vscode.commands.executeCommand('pruvagraph.dryRun');
                        break;
                    case 'contextLens.show':
                        await vscode.commands.executeCommand('pruvagraph.contextLens.show');
                        break;
                    default:
                        console.log('[PRUVALEX] CostDashboard webview received unknown command:', message.command);
                        break;
                }
            });
            console.log('[PRUVALEX] CostDashboard webview listener registered');
            
            console.log('[PRUVALEX] CostDashboard.resolveWebviewView() completed successfully');
        } catch (err) {
            console.error('[PRUVALEX] CostDashboard.resolveWebviewView() error:', err);
            // Ensure view is still marked as resolved even if there's an error
            webviewView.webview.html = `
                <html>
                    <body style="color: #ff6b6b; padding: 20px; font-family: monospace;">
                        <h2>Error initializing dashboard</h2>
                        <pre>${String(err).substring(0, 500)}</pre>
                        <p>Check the VS Code Developer Console for details.</p>
                    </body>
                </html>
            `;
        }
    }

    private updateMetrics() {
        if (!this.view) {
            console.warn('[PRUVALEX] updateMetrics: view not available');
            return;
        }
        
        // If costRepo is not initialized, send default metrics
        if (!this.costRepo) {
            console.warn('[PRUVALEX] updateMetrics: costRepo not initialized, sending defaults');
            this.view.webview.postMessage({
                type: 'metricsUpdate',
                data: {
                    totalTokensIn: 0,
                    totalTokensOut: 0,
                    tokensSaved: 0,
                    cacheHits: 0,
                    cacheHitRate: 0,
                    estimatedSavings: 0,
                    dedupProjected: 0,
                    costPerMToken: 0.03,
                    activeModules: [],
                    lastUpdated: Date.now()
                }
            });
            return;
        }
        
        try {
            const metrics = this.costRepo.calculateMetrics();
            console.log('[PRUVALEX] Calculated metrics:', metrics);
            this.view.webview.postMessage({
                type: 'metricsUpdate',
                data: metrics
            });
        } catch (err) {
            console.error('[PRUVALEX] Failed to update cost metrics:', err);
            // Send error state but keep view alive
            this.view.webview.postMessage({
                type: 'error',
                message: 'Failed to load metrics'
            });
        }
    }

    public setCore(core: CoreEngineAPI) {
        this.core = core;
        this.costRepo = new CostReportRepository(core.db);
        if (this.view) {
            this.updateMetrics();
        }
    }

    public refreshMetrics() {
        this.updateMetrics();
    }

    public reveal(preserveFocus = false) {
        this.view?.show(preserveFocus);
    }

    private getHtml(webview: vscode.Webview): string {
        return this.getHtmlForWebview(webview);
    }

    private getHtmlForWebview(webview: vscode.Webview): string {
        const logoUri = webview.asWebviewUri(vscode.Uri.joinPath(this.extensionUri, 'assets', 'logo.png'));
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'self' vscode-resource: vscode-webview-resource:; script-src 'unsafe-inline' vscode-resource: vscode-webview-resource:; style-src 'unsafe-inline' vscode-resource: vscode-webview-resource:; img-src 'self' vscode-resource: vscode-webview-resource: data:;" />
    <title>PRUVALEX Cost Dashboard</title>
    <style>
        * {
            box-sizing: border-box;
        }

        html,
        body {
            height: 100%;
            min-height: 100%;
            display: block;
            margin: 0;
            padding: 0;
        }
        
        body {
            font-family: var(--vscode-font-family, 'Segoe WPC', 'Segoe UI', -apple-system, sans-serif);
            color: var(--vscode-foreground, #ffffff);
            background: linear-gradient(135deg, rgba(15,17,21,1) 0%, rgba(25,30,40,1) 100%);
            overflow: hidden;
        }

        .container {
            display: flex;
            flex-direction: column;
            height: 100vh;
            background: var(--vscode-editor-background, #0f1115);
        }

        .header {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px 16px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            background: linear-gradient(180deg, rgba(124,58,237,0.15) 0%, transparent 100%);
        }

        .logo {
            width: 36px;
            height: 36px;
            border-radius: 8px;
            background: rgba(124,58,237,0.2);
            padding: 6px;
            flex-shrink: 0;
        }

        .header-text h1 {
            margin: 0;
            font-size: 0.95rem;
            font-weight: 700;
            background: linear-gradient(135deg, #ffffff, #b0b0ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .header-text p {
            margin: 2px 0 0;
            font-size: 0.75rem;
            color: rgba(255,255,255,0.6);
        }

        .content {
            flex: 1;
            overflow-y: auto;
            padding: 14px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .content::-webkit-scrollbar {
            width: 8px;
        }

        .content::-webkit-scrollbar-track {
            background: transparent;
        }

        .content::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
        }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .metric-card {
            border-radius: 12px;
            padding: 14px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(124,58,237,0.2);
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
        }

        .metric-card:hover {
            background: rgba(255,255,255,0.06);
            border-color: rgba(124,58,237,0.4);
            transform: translateY(-2px);
        }

        .metric-label {
            font-size: 0.75rem;
            color: rgba(255,255,255,0.6);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
            font-weight: 600;
        }

        .metric-value {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #7c3aed, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin: 0;
        }

        .metric-value.savings {
            background: linear-gradient(135deg, #10b981, #34d399);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .metric-value.tokens {
            background: linear-gradient(135deg, #f59e0b, #fbbf24);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .metric-secondary {
            font-size: 0.8rem;
            color: rgba(255,255,255,0.5);
            margin-top: 6px;
        }

        .premium-card {
            border-radius: 14px;
            padding: 16px;
            background: linear-gradient(135deg, rgba(124,58,237,0.1), rgba(167,139,250,0.05));
            border: 1px solid rgba(124,58,237,0.3);
            backdrop-filter: blur(10px);
        }

        .premium-card h3 {
            margin: 0 0 12px;
            font-size: 0.9rem;
            font-weight: 700;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .premium-card h3::before {
            content: '✨';
            font-size: 1rem;
        }

        .stat-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }

        .stat-row:last-child {
            border-bottom: none;
        }

        .stat-label {
            font-size: 0.85rem;
            color: rgba(255,255,255,0.7);
        }

        .stat-value {
            font-weight: 700;
            font-size: 0.9rem;
            color: #ffffff;
        }

        .module-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 8px;
        }

        .module-tag {
            font-size: 0.75rem;
            padding: 6px 10px;
            border-radius: 20px;
            background: rgba(124,58,237,0.2);
            color: #a78bfa;
            border: 1px solid rgba(124,58,237,0.3);
            font-weight: 600;
        }

        .status-card {
            border-radius: 14px;
            padding: 16px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.08);
            margin-top: 12px;
        }

        .status-card h3 {
            margin: 0 0 12px;
            font-size: 0.9rem;
            font-weight: 700;
            color: #ffffff;
        }

        .status-row {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-size: 0.85rem;
        }

        .status-row:last-child {
            border-bottom: none;
        }

        .status-row span:last-child {
            color: #a78bfa;
            font-weight: 600;
        }

        .action-buttons {
            display: grid;
            gap: 8px;
            margin-top: 12px;
        }

        button {
            width: 100%;
            border: none;
            border-radius: 10px;
            padding: 10px 12px;
            font-size: 0.9rem;
            color: var(--vscode-button-foreground, #ffffff);
            background: linear-gradient(135deg, #7c3aed, #a78bfa);
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s ease;
        }

        button:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 24px rgba(124, 58, 237, 0.3);
        }

        button.secondary {
            background: rgba(255,255,255,0.08);
            color: rgba(255,255,255,0.9);
            border: 1px solid rgba(255,255,255,0.12);
        }

        .footer {
            padding: 10px 16px;
            font-size: 0.75rem;
            color: rgba(255,255,255,0.4);
            border-top: 1px solid rgba(255,255,255,0.08);
            text-align: center;
        }
    </style>
</head>
<body>
    <h1 style="color: white; background: red; padding: 20px; margin: 0; font-size: 24px; text-align: center; border-bottom: 3px solid yellow;">⚠️ PRUVALEX DASHBOARD LIVE! ⚠️</h1>
    <div class="container">
        <div class="header">
            <img class="logo" src="${logoUri}" alt="PRUVALEX" />
            <div class="header-text">
                <h1>Cost Dashboard</h1>
                <p>Real-time LLM cost analysis</p>
            </div>
        </div>

        <div class="content">
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-label">💰 Estimated Savings</div>
                    <p class="metric-value savings">$<span id="savings">0.00</span></p>
                    <div class="metric-secondary">vs. baseline cost</div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">🚀 Tokens Saved</div>
                    <p class="metric-value tokens"><span id="tokensSaved">0</span></p>
                    <div class="metric-secondary">total reduction</div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">⚡ Cache Hits</div>
                    <p class="metric-value"><span id="cacheHits">0</span></p>
                    <div class="metric-secondary"><span id="cacheRate">0</span>% hit rate</div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">📈 Dedup Projected</div>
                    <p class="metric-value savings">$<span id="dedupProjected">0.00</span></p>
                    <div class="metric-secondary">additional potential</div>
                </div>
            </div>

            <div class="premium-card">
                <h3>Token Usage</h3>
                <div class="stat-row">
                    <span class="stat-label">Total Input Tokens</span>
                    <span class="stat-value"><span id="tokensIn">0</span></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Total Output Tokens</span>
                    <span class="stat-value"><span id="tokensOut">0</span></span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Cost / M Tokens</span>
                    <span class="stat-value">$<span id="costPerMToken">0.03</span></span>
                </div>
            </div>

            <div class="premium-card">
                <h3>Active Modules</h3>
                <div class="module-list" id="moduleList">
                    <div class="module-tag">ContextLens</div>
                    <div class="module-tag">DriftGuard</div>
                </div>
            </div>

            <div class="status-card">
                <h3>Dashboard Status</h3>
                <div class="status-row"><span>Logo load</span><span id="logoStatus">pending</span></div>
                <div class="status-row"><span>Button wiring</span><span id="buttonStatus">pending</span></div>
                <div class="status-row"><span>Message listener</span><span id="listenerStatus">pending</span></div>
            </div>

            <div class="action-buttons">
                <button onclick="vscode.postMessage({ command: 'queryCodebase' })">Query Codebase</button>
                <button onclick="vscode.postMessage({ command: 'toggleWatchMode' })">Enable Watch Mode</button>
                <button onclick="vscode.postMessage({ command: 'showCostReport' })">Cost Report</button>
                <button onclick="vscode.postMessage({ command: 'dryRun' })">Dry Run</button>
                <button data-command="initializeGraph">Build Graph</button>
                <button class="secondary" data-command="contextLens.show">Open ContextLens</button>
            </div>
        </div>

        <div class="footer">
            <span id="lastUpdate">Last updated: just now</span> • PRUVALEX 99%+ LLM cost reduction
        </div>
    </div>

    <script>
        // Acquire VS Code API once and make it globally accessible.
        // This ensures vscode.postMessage is available for inline event handlers.
        const vscode = window.vscode = typeof acquireVsCodeApi === 'function' ? acquireVsCodeApi() : window.vscode;
        if (!vscode) {
            console.error('[PRUVALEX] acquireVsCodeApi is missing or blocked.');
        }

        function formatNumber(num) {
            if (num >= 1_000_000) return (num / 1_000_000).toFixed(1) + 'M';
            if (num >= 1_000) return (num / 1_000).toFixed(1) + 'K';
            return num.toFixed(0);
        }

        function updateUI(metrics) {
            document.getElementById('savings').textContent = metrics.estimatedSavings.toFixed(2);
            document.getElementById('tokensSaved').textContent = formatNumber(metrics.tokensSaved);
            document.getElementById('cacheHits').textContent = metrics.cacheHits;
            document.getElementById('cacheRate').textContent = metrics.cacheHitRate.toFixed(0);
            document.getElementById('dedupProjected').textContent = metrics.dedupProjected.toFixed(2);
            document.getElementById('tokensIn').textContent = formatNumber(metrics.totalTokensIn);
            document.getElementById('tokensOut').textContent = formatNumber(metrics.totalTokensOut);
            document.getElementById('costPerMToken').textContent = metrics.costPerMToken.toFixed(2);
            
            const moduleList = document.getElementById('moduleList');
            moduleList.innerHTML = '';
            if (metrics.activeModules && metrics.activeModules.length > 0) {
                metrics.activeModules.forEach(mod => {
                    const tag = document.createElement('div');
                    tag.className = 'module-tag';
                    tag.textContent = mod.charAt(0).toUpperCase() + mod.slice(1);
                    moduleList.appendChild(tag);
                });
            } else {
                moduleList.innerHTML = '<span style="color: rgba(255,255,255,0.5); font-size: 0.8rem;">No active modules yet</span>';
            }

            const now = new Date();
            document.getElementById('lastUpdate').textContent = \`Last updated: \${now.toLocaleTimeString()}\`;
        }

        window.addEventListener('message', event => {
            const message = event.data;
            if (message.type === 'metricsUpdate') {
                updateUI(message.data);
            }
        });

        document.querySelectorAll('button[data-command]').forEach(button => {
            button.addEventListener('click', () => {
                const command = button.getAttribute('data-command');
                if (command) {
                    vscode.postMessage({ command });
                }
            });
        });

        window.addEventListener('load', () => {
            document.getElementById('logoStatus').textContent = 'loaded';
            document.getElementById('buttonStatus').textContent = 'wired';
            document.getElementById('listenerStatus').textContent = 'active';
        });
    </script>
</body>
</html>`;
    }
}
