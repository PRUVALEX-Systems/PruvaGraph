/**
 * PRUVALEX PruvaGraph — Savings Receipt Webview
 * Nordic-minimalist design with premium cost visualization
 * 
 * Displays:
 * - Tokens processed & saved
 * - Dollar amount saved
 * - Compression metrics
 * - Run metadata
 * 
 * Auto-updates after: runBuild, runQuery, runDryRun
 */

const fs = require('fs');
const path = require('path');
const vscode = require('vscode');

/**
 * Register and open Savings Receipt panel
 * Called after build/query/dry-run completes
 */
async function openSavingsReceipt(context, provider) {
  const receiptsPanel = vscode.window.createWebviewPanel(
    'pruvaGraphReceipt',
    '💰 PruvaGraph Savings Receipt',
    vscode.ViewColumn.Beside,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
      localResourceRoots: [
        vscode.Uri.joinPath(context.extensionUri, 'media'),
      ],
    }
  );

  // Fetch latest cost data
  const costData = await getCostDataForReceipt();
  
  // Generate HTML
  receiptsPanel.webview.html = getSavingsReceiptHtml(
    receiptsPanel.webview,
    context.extensionUri,
    costData
  );

  // Handle messages from receipt webview
  receiptsPanel.webview.onDidReceiveMessage(async (msg) => {
    switch (msg.command) {
      case 'copyToClipboard':
        await vscode.env.clipboard.writeText(msg.data);
        vscode.window.showInformationMessage('✓ Receipt copied to clipboard');
        break;
      case 'exportPDF':
        // Future: Export to PDF
        vscode.window.showInformationMessage('PDF export coming soon!');
        break;
      case 'shareSlack':
        // Future: Share formatted receipt to Slack
        vscode.window.showInformationMessage('Slack integration coming soon!');
        break;
    }
  });

  return receiptsPanel;
}

/**
 * Fetch latest cost report from pruvagraph-out/
 */
async function getCostDataForReceipt() {
  const root = vscode.workspace.rootPath || vscode.workspace.workspaceFolders?.[0]?.uri?.fsPath;
  if (!root) return null;

  const costReportPath = path.join(root, 'pruvagraph-out', 'cost_report.json');
  const graphJsonPath = path.join(root, 'pruvagraph-out', 'graph.json');

  let costData = null;
  let graphData = null;

  try {
    if (fs.existsSync(costReportPath)) {
      const content = fs.readFileSync(costReportPath, 'utf8');
      costData = JSON.parse(content);
    }
    if (fs.existsSync(graphJsonPath)) {
      const content = fs.readFileSync(graphJsonPath, 'utf8');
      graphData = JSON.parse(content);
    }
  } catch (err) {
    console.error('Error reading cost data:', err);
  }

  return { costData, graphData };
}

/**
 * Nordic-minimalist HTML for Savings Receipt
 * Design: Monochrome + Premium accent (electric purple/cyan for dollars)
 */
function getSavingsReceiptHtml(webview, extensionUri, { costData, graphData }) {
  const nonce = getNonce();
  
  // Default values if no data
  const costSaved = costData?.cost_saved_usd || 0;
  const savingsPct = costData?.savings_pct || 0;
  const actualCost = costData?.actual_cost_usd || 0;
  const naiveCost = costData?.naive_cost_usd || 0;
  const tokensSaved = Math.round((naiveCost - actualCost) * 1_000_000 / 3);
  const callsSaved = costData?.calls_saved || 0;
  const cacheHits = costData?.cache_hits || 0;
  const nodeCount = graphData?.nodes?.length || 0;
  const edgeCount = (graphData?.links || graphData?.edges || []).length || 0;
  const runTime = costData?.run_duration_seconds || 0;
  const timestamp = new Date().toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  });

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PruvaGraph Savings Receipt</title>
  <style nonce="${nonce}">
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }

    :root {
      /* Nordic Palette */
      --bg-primary: #f8f9fa;
      --bg-secondary: #ffffff;
      --bg-tertiary: #f0f1f3;
      --text-primary: #1a1d23;
      --text-secondary: #54565e;
      --text-muted: #a0a5b0;
      --border: #e8eaed;
      --accent-primary: #7c6efa;      /* Purple */
      --accent-secondary: #22d3ee;    /* Cyan */
      --accent-tertiary: #34d399;     /* Emerald */
      --success: #10b981;
      --danger: #ef4444;
    }

    html {
      background: var(--bg-primary);
      color: var(--text-primary);
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", sans-serif;
      line-height: 1.5;
      letter-spacing: 0.3px;
      background: var(--bg-primary);
      color: var(--text-primary);
      padding: 12px;
      overflow-y: auto;
    }

    /* ──────────────────────────────────────────────────────────── */
    /* Header & Logo                                                */
    /* ──────────────────────────────────────────────────────────── */

    .receipt-header {
      text-align: center;
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }

    .receipt-logo {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }

    .receipt-logo-icon {
      width: 24px;
      height: 24px;
      background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
      font-weight: bold;
      font-size: 14px;
    }

    .receipt-logo-text {
      font-size: 14px;
      font-weight: 600;
      letter-spacing: 0.5px;
      color: var(--text-primary);
    }

    .receipt-title {
      font-size: 20px;
      font-weight: 700;
      margin-bottom: 4px;
      color: var(--text-primary);
    }

    .receipt-subtitle {
      font-size: 12px;
      color: var(--text-muted);
      letter-spacing: 0.4px;
    }

    /* ──────────────────────────────────────────────────────────── */
    /* Savings Amount (Hero Section)                                */
    /* ──────────────────────────────────────────────────────────── */

    .savings-hero {
      background: linear-gradient(135deg, rgba(124, 110, 250, 0.08), rgba(34, 211, 238, 0.08));
      border: 1px solid rgba(124, 110, 250, 0.15);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 16px;
      text-align: center;
      backdrop-filter: blur(8px);
    }

    .savings-amount-label {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 1px;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 8px;
    }

    .savings-amount {
      font-size: 42px;
      font-weight: 800;
      letter-spacing: -1px;
      background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 8px;
    }

    .savings-pct {
      font-size: 14px;
      font-weight: 600;
      color: var(--success);
      letter-spacing: 0.5px;
    }

    /* ──────────────────────────────────────────────────────────── */
    /* Metrics Grid                                                 */
    /* ──────────────────────────────────────────────────────────── */

    .metrics-section {
      margin-bottom: 16px;
    }

    .metrics-title {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 1px;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 10px;
      padding: 0 4px;
    }

    .metrics-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 16px;
    }

    .metric-card {
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
      transition: all 0.2s ease-out;
    }

    .metric-card:hover {
      border-color: var(--accent-primary);
      box-shadow: 0 2px 8px rgba(124, 110, 250, 0.06);
    }

    .metric-label {
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.5px;
      color: var(--text-muted);
      margin-bottom: 6px;
      text-transform: uppercase;
    }

    .metric-value {
      font-size: 18px;
      font-weight: 700;
      color: var(--text-primary);
      line-height: 1;
    }

    .metric-value.accent {
      color: var(--accent-primary);
    }

    .metric-value.success {
      color: var(--success);
    }

    /* ──────────────────────────────────────────────────────────── */
    /* Cost Breakdown (Single Column)                               */
    /* ──────────────────────────────────────────────────────────── */

    .breakdown-section {
      margin-bottom: 16px;
    }

    .breakdown-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 0;
      border-bottom: 1px solid var(--border);
      font-size: 12px;
    }

    .breakdown-row:last-child {
      border-bottom: none;
    }

    .breakdown-label {
      color: var(--text-secondary);
      font-weight: 500;
    }

    .breakdown-value {
      font-weight: 600;
      color: var(--text-primary);
      font-family: 'Courier New', monospace;
      letter-spacing: 0.3px;
    }

    .breakdown-value.accent {
      color: var(--accent-primary);
    }

    /* ──────────────────────────────────────────────────────────── */
    /* Metadata Footer                                              */
    /* ──────────────────────────────────────────────────────────── */

    .receipt-footer {
      border-top: 1px solid var(--border);
      padding-top: 12px;
      margin-top: 16px;
      font-size: 10px;
      color: var(--text-muted);
      text-align: center;
      line-height: 1.6;
    }

    .receipt-timestamp {
      font-weight: 500;
      letter-spacing: 0.3px;
      margin-bottom: 4px;
    }

    /* ──────────────────────────────────────────────────────────── */
    /* Action Buttons                                               */
    /* ──────────────────────────────────────────────────────────── */

    .action-buttons {
      display: flex;
      gap: 8px;
      margin-top: 16px;
    }

    .btn {
      flex: 1;
      padding: 10px 12px;
      border: 1px solid var(--border);
      background: var(--bg-secondary);
      color: var(--text-primary);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.5px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s ease-out;
      text-transform: uppercase;
    }

    .btn:hover {
      background: var(--bg-tertiary);
      border-color: var(--accent-primary);
      color: var(--accent-primary);
    }

    .btn.primary {
      background: var(--accent-primary);
      color: white;
      border-color: var(--accent-primary);
    }

    .btn.primary:hover {
      background: var(--accent-secondary);
      border-color: var(--accent-secondary);
      box-shadow: 0 4px 12px rgba(34, 211, 238, 0.2);
    }

    .btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }

    /* ──────────────────────────────────────────────────────────── */
    /* Responsive                                                   */
    /* ──────────────────────────────────────────────────────────── */

    @media (max-width: 320px) {
      .metrics-grid {
        grid-template-columns: 1fr;
      }

      .savings-amount {
        font-size: 32px;
      }
    }

    /* Scrollbar */
    ::-webkit-scrollbar {
      width: 8px;
    }

    ::-webkit-scrollbar-track {
      background: var(--bg-primary);
    }

    ::-webkit-scrollbar-thumb {
      background: var(--border);
      border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
      background: var(--text-muted);
    }
  </style>
</head>
<body>

<!-- Header -->
<div class="receipt-header">
  <div class="receipt-logo">
    <div class="receipt-logo-icon">💾</div>
    <div class="receipt-logo-text">PRUVALEX</div>
  </div>
  <div class="receipt-title">Savings Receipt</div>
  <div class="receipt-subtitle">PruvaGraph Cost Analysis</div>
</div>

<!-- Hero Savings Section -->
<div class="savings-hero">
  <div class="savings-amount-label">You Saved</div>
  <div class="savings-amount">$${costSaved.toFixed(2)}</div>
  <div class="savings-pct">↓ ${savingsPct.toFixed(1)}% LLM Cost</div>
</div>

<!-- Metrics Grid -->
<div class="metrics-section">
  <div class="metrics-title">Key Metrics</div>
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="metric-label">Tokens Processed</div>
      <div class="metric-value">${tokensSaved.toLocaleString()}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Tokens Saved</div>
      <div class="metric-value success">${tokensSaved.toLocaleString()}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">API Calls Saved</div>
      <div class="metric-value accent">${callsSaved.toLocaleString()}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Cache Hits</div>
      <div class="metric-value">${cacheHits.toLocaleString()}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Nodes in Graph</div>
      <div class="metric-value">${nodeCount.toLocaleString()}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Edges in Graph</div>
      <div class="metric-value">${edgeCount.toLocaleString()}</div>
    </div>
  </div>
</div>

<!-- Cost Breakdown -->
<div class="breakdown-section">
  <div class="metrics-title">Cost Breakdown</div>
  <div class="breakdown-row">
    <span class="breakdown-label">Actual Cost</span>
    <span class="breakdown-value">$${actualCost.toFixed(6)}</span>
  </div>
  <div class="breakdown-row">
    <span class="breakdown-label">Naive Cost (est.)</span>
    <span class="breakdown-value">$${naiveCost.toFixed(4)}</span>
  </div>
  <div class="breakdown-row">
    <span class="breakdown-label">Cost Saved</span>
    <span class="breakdown-value accent">$${costSaved.toFixed(4)}</span>
  </div>
  <div class="breakdown-row">
    <span class="breakdown-label">Run Duration</span>
    <span class="breakdown-value">${runTime.toFixed(2)}s</span>
  </div>
</div>

<!-- Action Buttons -->
<div class="action-buttons">
  <button class="btn primary" onclick="send('copyToClipboard')">
    📋 Copy
  </button>
  <button class="btn" onclick="send('exportPDF')" disabled>
    📄 PDF
  </button>
  <button class="btn" onclick="send('shareSlack')" disabled>
    💬 Slack
  </button>
</div>

<!-- Footer -->
<div class="receipt-footer">
  <div class="receipt-timestamp">${timestamp}</div>
  <div>PruvaGraph v1.9.0 — Enterprise Intelligence Platform</div>
</div>

<script nonce="${nonce}">
  const vscode = acquireVsCodeApi();

  function send(command) {
    const clipboardData = \`
PRUVALEX PruvaGraph — Savings Receipt
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You Saved: $${costSaved.toFixed(2)}
Savings: ${savingsPct.toFixed(1)}%

Key Metrics:
  • Tokens Saved: ${tokensSaved.toLocaleString()}
  • API Calls Saved: ${callsSaved.toLocaleString()}
  • Cache Hits: ${cacheHits.toLocaleString()}
  • Graph: ${nodeCount.toLocaleString()} nodes, ${edgeCount.toLocaleString()} edges

Cost Breakdown:
  • Actual Cost: $${actualCost.toFixed(6)}
  • Naive Cost (est.): $${naiveCost.toFixed(4)}
  • Cost Saved: $${costSaved.toFixed(4)}
  • Run Duration: ${runTime.toFixed(2)}s

Generated: ${timestamp}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    \`.trim();

    vscode.postMessage({
      command,
      data: clipboardData,
    });
  }
</script>

</body>
</html>`;
}

/**
 * Generate nonce for CSP policy
 */
function getNonce() {
  let text = '';
  const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += possible.charAt(Math.floor(Math.random() * possible.length));
  }
  return text;
}

module.exports = {
  openSavingsReceipt,
  getCostDataForReceipt,
  getSavingsReceiptHtml,
};
