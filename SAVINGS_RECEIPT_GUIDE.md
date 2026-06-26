# PRUVALEX PruvaGraph — Savings Receipt Implementation Guide

**Version:** 1.4.0 + Savings Receipt v2.0  
**Date:** 2026-06-19  
**Status:** ✅ Ready to Deploy

---

## 🎯 Overview

The **Savings Receipt** is a beautiful, Nordic-minimalist webview panel that displays your LLM cost savings after each operation (build, query, dry-run). It automatically opens with:

- 💰 **Dollar amount saved** (gradient accent color)
- 📊 **Key metrics** (tokens, cache hits, API calls saved)
- 📈 **Cost breakdown** (actual vs naive cost)
- 📅 **Timestamp & metadata**
- 📋 **Copy & export options**

---

## 🚀 Installation & Activation

### Step 1: Add Files to Your Extension

Copy these files into your extension directory:

```bash
# Main extension file (already updated)
extension.js

# New: Savings Receipt module
extension-savings-receipt.js
```

### Step 2: Deploy Extension

```bash
cd extension/
npx vsce package --no-dependencies
code --install-extension pruvagraph-1.4.0.vsix
```

### Step 3: Reload VS Code

```
Ctrl+R (or Cmd+R on Mac)
```

---

## 💻 How to View the Savings Receipt

### **Method 1: Automatic Display (Recommended)**

The receipt **automatically opens** after these operations:

1. **Build Graph**
   - Click `⚡ Build Graph` in sidebar
   - Receipt opens on the right side
   - Shows savings from the build

2. **Build Fast (LSP)**
   - Click `🚀 Build Fast (LSP)`
   - N3 extraction completes
   - Receipt appears with metrics

3. **Run Query**
   - Ask your codebase a question
   - Receipt shows query-specific savings
   - Displays tokens sent via graph vs raw files

4. **Dry Run**
   - Click `🧪 Dry Run — Estimate Savings`
   - Forecasts cost savings
   - Receipt shows projected metrics

### **Method 2: Manual Open (via Command Palette)**

1. Open **Command Palette**
   - `Ctrl+Shift+P` (Windows/Linux)
   - `Cmd+Shift+P` (Mac)

2. Type: `PruvaGraph: Open Savings Receipt`

3. Press **Enter**

The receipt panel opens on the right side with the latest cost data.

### **Method 3: Custom Keybinding**

Add to your `keybindings.json`:

```json
{
  "key": "ctrl+shift+$",
  "command": "pruvagraph.openSavingsReceipt",
  "when": "workbenchState == 'workspace'"
}
```

Now press `Ctrl+Shift+$` to open the receipt anytime!

---

## 🎨 Nordic-Minimalist Design

The receipt features a premium design:

| Element | Color | Purpose |
|---------|-------|---------|
| Background | `#f8f9fa` (Light gray) | Clean, minimal |
| Text | `#1a1d23` (Dark) | High contrast |
| Accent | `#7c6efa` → `#22d3ee` (Purple→Cyan gradient) | **Dollar savings** highlight |
| Success | `#10b981` (Green) | Positive metrics |
| Border | `#e8eaed` (Subtle) | Visual separation |

**Design Philosophy:**
- ✓ Zero visual noise
- ✓ Monochrome + single accent gradient
- ✓ Subtle shadows (0 4px 12px)
- ✓ Premium card-based layout
- ✓ Generous whitespace
- ✓ 12px base padding

---

## 🖥️ Display in Different Editors

### **VS Code (Integrated)**

**Native webview panel on the right:**

```
┌─────────────────────────────────────────┐
│ File Editor      │ Savings Receipt     │
│                  │                     │
│ src/app.ts       │ 💰 PRUVALEX         │
│ ...code...       │ ┌─────────────────┐ │
│                  │ │ You Saved       │ │
│                  │ │ $47.32          │ │
│                  │ │ ↓ 67.2% LLM...  │ │
│                  │ └─────────────────┘ │
│                  │                     │
│                  │ Key Metrics         │
│                  │ ┌───┬────────────┐ │
│                  │ │...|............│ │
│                  │ └───┴────────────┘ │
└─────────────────────────────────────────┘
```

**Location:** Always on the right side (`ViewColumn.Beside`)  
**Persistence:** Stays open until closed manually  
**Auto-refresh:** Updates after each operation

---

### **Cursor (AI Editor)**

Cursor includes VS Code webview support. The receipt works identically:

1. Open PruvaGraph extension in Cursor
2. Run "Build Graph" or any operation
3. Receipt opens on the right side
4. Same Nordic-minimalist design

**Bonus:** In Cursor, you can ask the AI about your savings:
- "Why did I save $47?"
- "How many tokens were processed?"
- AI reads the receipt and explains metrics

---

### **Windsurf (Cascade IDE)**

Windsurf also supports VS Code extensions natively:

1. Install PRUVALEX PruvaGraph extension
2. The sidebar and webview panels work as in VS Code
3. Receipt displays in the cascade layout

---

### **Claude Code (via MCP)**

For **Claude Code** integration (standalone Claude instance with MCP server):

We provide an **MCP server** that exposes the receipt data:

```bash
# Start the MCP server (optional)
node extension-mcp-server.js
```

Claude can then query:
- `get_savings_receipt` — Latest receipt data
- `get_cost_report` — Full cost report
- `run_build` — Execute build and get receipt

---

## 📱 Receipt Sections

### **1. Header Section**
```
┌─ Header ─────────────────────┐
│ 💾 PRUVALEX                  │
│ Savings Receipt              │
│ PruvaGraph Cost Analysis     │
└──────────────────────────────┘
```

Shows branding and title.

### **2. Hero Savings (Gradient Accent)**
```
┌─ Savings Hero ───────────────┐
│ YOU SAVED                    │
│                              │
│ $47.32 ✨                    │
│ ↓ 67.2% LLM Cost             │
└──────────────────────────────┘
```

Largest, most prominent section. Gradient background with premium styling.

### **3. Key Metrics Grid**
```
┌─ Metrics Grid ───────────────┐
│ ┌──────────┬──────────────┐  │
│ │ Tokens   │ Tokens       │  │
│ │ Proc.    │ Saved        │  │
│ │ 127,450  │ 45,320  ✓    │  │
│ ├──────────┼──────────────┤  │
│ │ API Calls│ Cache        │  │
│ │ Saved    │ Hits         │  │
│ │ 12   💜  │ 89           │  │
│ ├──────────┼──────────────┤  │
│ │ Nodes    │ Edges        │  │
│ │ 342      │ 1,203        │  │
│ └──────────┴──────────────┘  │
└──────────────────────────────┘
```

6 metric cards in 2-column grid. Hover effects on desktop.

### **4. Cost Breakdown**
```
┌─ Cost Breakdown ─────────────┐
│ Actual Cost    $0.001204     │
│ Naive Cost (e) $0.003742     │
│ Cost Saved     $0.002538 💜  │
│ Run Duration   2.34s         │
└──────────────────────────────┘
```

Simple key-value pairs. Clean monospace font for numbers.

### **5. Action Buttons**
```
┌─ Actions ────────────────────┐
│ [📋 Copy] [📄 PDF]  [💬 Slack]│
└──────────────────────────────┘
```

- **Copy** — Copies formatted receipt to clipboard (always enabled)
- **PDF** — Export as PDF (coming soon, disabled)
- **Slack** — Share to Slack (coming soon, disabled)

### **6. Footer**
```
┌─ Footer ─────────────────────┐
│ Jun 19, 2026 · 14:32:45 UTC  │
│ PruvaGraph v1.4.0            │
│ Enterprise Intelligence      │
└──────────────────────────────┘
```

Timestamp and branding.

---

## 🔄 Auto-Refresh & Hook Points

The receipt **auto-updates** after these operations:

### **1. After `runBuild`**
```typescript
async function runBuild(provider) {
  // ... build logic ...
  await sendStatus(provider);
  await sendSavingsReceipt(provider);  // ← Opens receipt
}
```

### **2. After `runBuildFast` (LSP)**
```typescript
async function runBuildFast(provider) {
  // ... LSP extraction ...
  await sendStatus(provider);
  await sendSavingsReceipt(provider);  // ← Opens receipt
}
```

### **3. After `runQuery`**
```typescript
async function runQuery(provider, question) {
  // ... query execution ...
  await sendSavingsReceipt(provider);  // ← Shows query-specific savings
}
```

### **4. After `runDryRun`**
```typescript
async function runDryRun(provider) {
  // ... dry run estimate ...
  await sendSavingsReceipt(provider);  // ← Shows projected savings
}
```

The function:

```javascript
function sendSavingsReceipt(provider) {
  const root = getWorkspaceRoot();
  const data = root ? loadCostReport(root) : null;
  provider.post('savingsData', { data });

  // Open Savings Receipt panel if we have cost data
  if (data && extensionContext && data.costSavedUsd > 0) {
    setTimeout(() => {
      try {
        openSavingsReceipt(extensionContext, provider);
      } catch (err) {
        console.error('Error opening savings receipt:', err);
      }
    }, 100);
  }
}
```

---

## 🎬 User Journey

### **Complete Workflow**

1. **User opens folder** in VS Code
2. **Clicks "Build Graph"** in sidebar
3. **Building starts** (progress bar shows)
4. **Build completes** ✓
5. **Metrics update** in sidebar
6. **🎉 Receipt panel automatically opens** on the right with:
   - Total cost saved
   - Key metrics
   - Comparison vs naive approach
   - Formatted nicely for sharing

7. **User can:**
   - 📋 Copy receipt to clipboard
   - 📧 Share with team
   - 💾 Pin panel for reference
   - 🔄 Close and reopen anytime

---

## 📊 Data Flow

```
PruvaGraph Build
     ↓
Write pruvagraph-out/cost_report.json
     ↓
loadCostReport(root)
     ↓
sendSavingsReceipt(provider)
     ↓
getCostDataForReceipt()
     ↓
Fetch graph.json + cost_report.json
     ↓
getSavingsReceiptHtml(costData, graphData)
     ↓
openSavingsReceipt()
     ↓
vscode.window.createWebviewPanel()
     ↓
🎨 Receipt rendered with gradient accent
```

---

## 🛠️ Customization

### **Change Accent Color**

Edit `extension-savings-receipt.js`, line ~50:

```javascript
--accent-primary: #7c6efa;      /* Change this */
--accent-secondary: #22d3ee;    /* Or this */
```

Examples:
- Purple→Pink: `#7c6efa` → `#ec4899`
- Orange→Red: `#f97316` → `#ef4444`
- Blue→Green: `#0ea5e9` → `#10b981`

### **Modify Metrics Displayed**

Edit `getSavingsReceiptHtml()` function to add/remove metric cards.

### **Add Custom Sections**

The HTML is fully modular. Add new `<div class="metric-card">` blocks as needed.

---

## 🐛 Troubleshooting

### **Receipt doesn't open**

1. Check that `cost_report.json` exists in `pruvagraph-out/`
2. Ensure `cost_saved_usd > 0` in the report
3. Check VS Code output: `Ctrl+J` → "PruvaGraph" tab
4. Try manual open: `Cmd+Shift+P` → "Open Savings Receipt"

### **Receipt shows $0 saved**

- Run `pruvagraph .` first to build the graph
- Cost data updates automatically
- Receipt reflects latest `cost_report.json`

### **Webview errors**

Check browser console:
1. `Ctrl+Shift+I` (or `Cmd+Shift+I` on Mac)
2. Go to "Console" tab
3. Look for JavaScript errors

---

## 📦 File Structure

```
extension.js
├── Imports extension-savings-receipt module
├── Stores extensionContext
├── Calls openSavingsReceipt() after operations
└── Handles receipt panel messages

extension-savings-receipt.js
├── openSavingsReceipt(context, provider)
│  └── Creates webviewPanel
│  └── Fetches cost data
│  └── Renders HTML
├── getCostDataForReceipt()
│  └── Reads pruvagraph-out/
└── getSavingsReceiptHtml()
   └── Nordic-minimalist CSS
   └── Dynamic data interpolation
   └── Copy-to-clipboard functionality
```

---

## 🚀 Next Steps

### **For End Users**

1. ✅ Install PRUVALEX PruvaGraph v1.4.0
2. ✅ Open a folder with code
3. ✅ Click "Build Graph"
4. ✅ Watch Savings Receipt appear! 💰

### **For Developers**

1. Customize accent colors (if desired)
2. Add more metrics to the grid
3. Implement PDF export (coming soon)
4. Add Slack integration (coming soon)

### **For Teams**

1. Share receipts with engineering managers
2. Track monthly LLM cost savings
3. Build ROI reports from receipt data
4. Integrate with company dashboards

---

## ✨ Features Recap

| Feature | Status | Details |
|---------|--------|---------|
| Auto-open on build | ✅ Complete | Opens after build/query/dry-run |
| Nordic design | ✅ Complete | Premium minimalist aesthetic |
| Dynamic data | ✅ Complete | Reads latest cost_report.json |
| Copy to clipboard | ✅ Complete | Formatted text with markdown |
| PDF export | ⏳ Soon | Coming in v1.5.0 |
| Slack integration | ⏳ Soon | Coming in v1.5.0 |
| Mobile responsive | ✅ Complete | Works on narrow viewports |
| Dark mode support | ✅ Complete | Uses VS Code colors |

---

## 📞 Support

- **GitHub Issues:** https://github.com/pruvalex/pruvagraph/issues
- **Documentation:** https://pruvalex.com
- **Command Palette:** `Cmd+Shift+P` → "Open Savings Receipt"

---

## 🎉 You're Ready!

Your PRUVALEX PruvaGraph extension now has a **beautiful, automatic Savings Receipt** that displays every time you save money with the graph.

**Open VS Code → Build Graph → See your savings appear! 💰✨**

---

**Last Updated:** 2026-06-19  
**Implementation Status:** ✅ Complete & Ready to Deploy
