Bilkul! Yeh ek complete step-by-step guide hai — har phase ke liye exactly kya karna hai, kaise karna hai, aur agar kuch kaam na kare toh kya check karein.

---

## 🛠️ Prerequisites — Pehle Yeh Setup Karo

### Step 0A: System Requirements Check

```bash
# Terminal mein yeh commands chalao:

# 1. Node.js version check (20+ chahiye)
node --version
# Expected: v20.x.x ya usse zyada

# 2. Python version check (3.11+ chahiye)
python3 --version
# Expected: Python 3.11.x ya 3.12.x ya 3.13.x

# 3. Git available hai?
git --version
# Expected: git version 2.x.x

# 4. VS Code installed hai?
code --version
# Expected: koi version number
```

---

### Step 0B: Extension Build Karo

```bash
# 1. Repo ka pruvagraph folder mein jao
cd "PRUVALEX Graph optimise LLM cost tool/pruvagraph"

# 2. Dependencies install karo
npm install

# 3. Sab packages build karo
npm run build --workspaces

# 4. Extension package banao
cd extension
npx vsce package --no-dependencies
# Yeh ek .vsix file banayega jaise: pruvagraph-0.0.1.vsix
```

---

### Step 0C: Extension Install Karo VS Code Mein

```bash
# Method 1: Command line se
code --install-extension pruvagraph-0.0.1.vsix

# Method 2: VS Code UI se
# VS Code kholo → Extensions panel (Ctrl+Shift+X)
# Top-right mein "..." click karo
# "Install from VSIX..." select karo
# apni .vsix file choose karo
```

---

### Step 0D: Developer Tools Kholo (ZAROORI HAI)

VS Code mein:
```
Help → Toggle Developer Tools
```
Ya shortcut: `Ctrl+Shift+I` (Windows/Linux) / `Cmd+Option+I` (Mac)

**Console tab ko select karo** — yahan saare PRUVALEX logs aayenge.

---

## ✅ Phase 1: Core Engine & PruvaGraph Initialization

### 1.1 — TypeScript Project Kholo

```bash
# Agar apna project nahi hai toh ek test project banao:
mkdir my-test-project
cd my-test-project
npm init -y
npx tsc --init
mkdir src
echo 'export function hello() { return "world"; }' > src/index.ts
code .
```

### 1.2 — Initialize Graph Command Chalao

VS Code mein:
```
Ctrl+Shift+P (Mac: Cmd+Shift+P)
```
Type karo: `PRUVALEX: Initialize Graph`
Enter dabaao.

### 1.3 — Kya Verify Karna Hai

**A) Toast Notification (bottom-right corner mein):**
```
"Initializing PruvaGraph Knowledge..."
```

**B) Output Channel kholo:**
```
View → Output
Dropdown mein "PRUVALEX: PruvaGraph Engine" select karo
```
Yahan yeh lines dikhni chahiye:
```
[PRUVALEX] Checking Python environment...
[PRUVALEX] Creating isolated virtual environment...
[PRUVALEX] Installing/Updating PruvaGraph engine...
[PRUVALEX] Running graph extraction...
[PRUVALEX] Graph extraction complete!
```

**C) File system check:**
```bash
# Workspace folder mein yeh check karo
ls -la my-test-project/
# .venv_pruvagraph/ folder dikhna chahiye

ls -la my-test-project/pruvagraph-out/
# graph.json file dikhni chahiye
```

**D) Developer Tools Console mein:**
```
SQLite Database initialized
[GraphStore] Migration complete
```

### 1.4 — Agar Fail Ho Toh

```bash
# Python nahi mila? Manually install karo:
# Mac:
brew install python@3.11

# Ubuntu/Debian:
sudo apt-get install python3.11

# Windows: python.org se installer download karo
```

---

## ✅ Phase 2: DriftGuard Testing

### 2.1 — Test File Banao

`src/` folder mein ek nayi file banao: `test-drift.ts`

```typescript
// yeh line add karo — QuantumCompiler FAKE hai, exist nahi karta
import { QuantumCompiler } from 'some-fake-package';

// yeh sahi hai (react installed hoga)
import { useState } from 'react';

function myFunction() {
    const compiler = new QuantumCompiler();  // fake
    const [count, setCount] = useState(0);   // real
}
```

### 2.2 — Kya Verify Karna Hai

**A) Yellow squiggly line:**
`QuantumCompiler` ke upar yellow wavy underline dikhega.

**B) Hover karo usse:**
```
DriftGuard: Symbol 'QuantumCompiler' from 'some-fake-package' 
not found in installed packages.
```

**C) Problems panel mein (View → Problems):**
```
DriftGuard warning: QuantumCompiler not found
```

**D) Developer Tools Console mein:**
```javascript
[drift:detected] {uri: "file:///path/to/test-drift.ts", symbol: "QuantumCompiler", reason: "..."}
```

### 2.3 — Agar DriftGuard Kaam Na Kare

```bash
# driftguard_index table populated hai?
# SQLite browser ya command line se check karo:

sqlite3 ~/.vscode/globalStorage/pruvagraph.pruvagraph/pruvagraph.db
.tables
# token_ledger, driftguard_index, ghostmemory_entries etc dikhne chahiye

SELECT count(*) FROM driftguard_index;
# Agar 0 aaya, initialize graph dobara chalao

.quit
```

---

## ✅ Phase 3: ContextLens Testing

### 3.1 — Panel Kholo

```
Ctrl+Shift+P → PRUVALEX: ContextLens — Show
```

Ek nayi panel VS Code ke right side mein khulegi — **"ContextLens Debugger"** title hoga.

### 3.2 — MCP Tool Call Trigger Karo

MCP tools call karne ke 3 tarike hain:

**Method A: Claude Code se (agar install hai)**
```bash
# Claude Code terminal mein:
claude
# Phir ask karo: "validate the symbol useState from react"
# Yeh internally mcp.call() trigger karega
```

**Method B: Directly Node.js script se (testing ke liye)**
```javascript
// test-mcp.js banao workspace mein:
const { execSync } = require('child_process');

// Ya ek simple VS Code command banao jo tool call kare
data
```

**Method C: VS Code Command se (sabse easy)**

Koi bhi file kholo aur save karo — DriftGuard automatically `validateDocument` chalata hai jo internally MCP call karta hai. Yeh token_ledger mein entry add karega.

### 3.3 — Kya Verify Karna Hai

**A) Panel mein table dikhe:**
```
Module/Server | Tokens In | Tokens Out | Latency | Time
pruvagraph       | 45        | 12         | 23ms    | 3:45 PM
```

**B) Tokens In > 0 hona chahiye** (Fix 3 ke baad)

**C) Panel auto-refresh hona chahiye** har naye call ke baad

**D) Developer Tools Console mein:**
```
[ContextLens] Token ledger updated
```

### 3.4 — SQLite Directly Check Karo

```bash
sqlite3 ~/.vscode/globalStorage/pruvagraph.pruvagraph/pruvagraph.db \
  "SELECT module, tool_name, tokens_in, tokens_out, latency_ms FROM token_ledger ORDER BY ts DESC LIMIT 5;"
```

---

## ✅ Phase 4: GhostMemory Testing

GhostMemory MCP tools ke through kaam karta hai. Inhe call karne ka sabse direct tarika hai:

### 4.1 — Memory Store Karo

**Claude Code ke saath:**
```bash
# Claude Code terminal mein:
claude

# Phir yeh message bhejo:
# "Use the store_memory MCP tool to remember: 
#  'API keys are always stored in the KeyVault service, never locally'"
```

**Ya developer script se:**

Workspace mein `test-ghostmemory.js` banao:
```javascript
// yeh script PRUVALEX ke MCP server ko directly call karta hai
const http = require('http');

const toolCall = {
    jsonrpc: "2.0",
    method: "tools/call",
    params: {
        name: "store_memory",
        arguments: {
            content: "API keys are always stored in the KeyVault service, never locally",
            tags: ["security", "api-keys", "architecture"],
            project: "my-test-project"
        }
    },
    id: 1
};

// HTTP request to MCP server
const req = http.request({
    hostname: 'localhost',
    port: 3000,  // PRUVALEX MCP server port
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
}, (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => console.log('Response:', JSON.parse(data)));
});

req.write(JSON.stringify(toolCall));
req.end();
```

### 4.2 — Cross-Session Test

```bash
# Step 1: Memory store karo (upar wala step)
# Step 2: VS Code completely band karo
# Step 3: Dobara kholo same project
# Step 4: recall_relevant tool call karo with query "API keys"
```

### 4.3 — Verify Karo

```bash
# SQLite mein check karo:
sqlite3 ~/.vscode/globalStorage/pruvagraph.pruvagraph/pruvagraph.db \
  "SELECT id, content, tags, project, created_at FROM ghostmemory_entries;"

# Output kuch aisa dikhna chahiye:
# abc-123|API keys are always stored...|["security","api-keys"]|my-test-project|1750000000
```

---

## ✅ Phase 5: RulesForge Testing

### 5.1 — Rule Create Karo

**Claude Code ke saath:**
```bash
# MCP tool call:
# Tool: create_rule
# Args: {
#   "rule_name": "Interface naming convention",
#   "condition": "interface\\s+(?!I[A-Z])",
#   "action": "All interfaces must start with 'I' prefix",
#   "layer": "typescript"
# }
```

**SQLite se verify:**
```bash
sqlite3 ~/.vscode/globalStorage/pruvagraph.pruvagraph/pruvagraph.db \
  "SELECT id, rule_name, layer, condition FROM rulesforge_rules;"
```

### 5.2 — Rules Query Karo

```bash
# Tool: get_applicable_rules
# Args: { "file_uri": "path/to/your/file.ts", "layer": "typescript" }
```

**Expected response:**
```json
{
  "rules": [
    {
      "id": "uuid-here",
      "rule_name": "Interface naming convention",
      "condition": "interface\\s+(?!I[A-Z])",
      "action": "All interfaces must start with 'I' prefix",
      "layer": "typescript"
    }
  ]
}
```

**⚠️ Important Note:** RulesForge abhi sirf rules store aur return karta hai. Automatic enforcement (AI suggestion intercept) Phase 6 ke baad aayega jab AST integration hoga.

---

## ✅ Phase 6: TaskWeaver Testing

### 6.1 — Git Repository Setup

```bash
cd my-test-project
git init
git add .
git commit -m "initial commit"

# Verify:
git log --oneline
# Ek commit dikhna chahiye
```

### 6.2 — Checkpoint Create Karo

```bash
# Tool: create_checkpoint
# Args:
# {
#   "task_id": "test-refactor-001",
#   "files_changed": ["src/index.ts"],
#   "git_sha": "HEAD"
# }
```

**SQLite verify:**
```bash
sqlite3 ~/.vscode/globalStorage/pruvagraph.pruvagraph/pruvagraph.db \
  "SELECT id, task_id, commit_sha, files_changed FROM taskweaver_checkpoints;"
```

### 6.3 — File Change Karo

```typescript
// src/index.ts mein kuch badlo:
export function hello() { return "world CHANGED"; }

git add src/index.ts
git commit -m "changed hello function"
```

### 6.4 — Rollback Karo

```bash
# Tool: rollback_to_checkpoint
# Args: { "id": "<checkpoint-id-from-step-6.2>" }

# Verify file wapas pehle jaise ho gayi:
cat src/index.ts
# "world CHANGED" nahi hona chahiye, sirf "world" hona chahiye

# Git log mein bhi verify karo:
git log --oneline
```

---

## 📋 Phase 7: Cross-Module Integration Test

### 7.1 — Runtime Module Toggle Test

```
VS Code Settings kholo: Ctrl+, (Mac: Cmd+,)
Search: "pruvagraph"
```

Yahan 5 toggles dikhenge. DriftGuard band karo:

```json
{
  "pruvagraph.modules.driftguard.enabled": false
}
```

**Verify:**
- VS Code reload **nahi** maanga
- Developer Tools Console mein: `[PRUVALEX] Deactivating module: driftguard`
- DriftGuard warnings file save karne par **nahi** dikhne chahiye

Dobara on karo:
- Console: `[PRUVALEX] Activating module: driftguard`
- DriftGuard warnings 2 second ke andar wapas dikhne chahiye

### 7.2 — Final Database Verification

```bash
# Sab tables exist karni chahiye:
sqlite3 ~/.vscode/globalStorage/pruvagraph.pruvagraph/pruvagraph.db ".tables"

# Expected output (koi bhi order mein):
# driftguard_index  ghostmemory_entries  rulesforge_rules
# taskweaver_checkpoints  token_ledger

# Har table mein data check karo:
sqlite3 ~/.vscode/globalStorage/pruvagraph.pruvagraph/pruvagraph.db "
  SELECT 'driftguard'  , count(*) FROM driftguard_index
  UNION ALL
  SELECT 'ghostmemory' , count(*) FROM ghostmemory_entries
  UNION ALL
  SELECT 'rulesforge'  , count(*) FROM rulesforge_rules
  UNION ALL
  SELECT 'taskweaver'  , count(*) FROM taskweaver_checkpoints
  UNION ALL
  SELECT 'token_ledger', count(*) FROM token_ledger;
"
```

### 7.3 — ContextLens Per-Module Breakdown Check

```bash
# Verify karo ki module attribution sahi hai:
sqlite3 ~/.vscode/globalStorage/pruvagraph.pruvagraph/pruvagraph.db "
  SELECT module, tool_name, COUNT(*) as calls, 
         SUM(tokens_in) as total_tokens_in
  FROM token_ledger
  GROUP BY module
  ORDER BY calls DESC;
"

# Expected: 'pruvagraph' nahi, actual module names dikhne chahiye:
# driftguard | validate_symbol | 5 | 230
# ghostmemory| store_memory    | 2 | 45
# etc.
```

---

## 🚨 Common Problems & Solutions

| Problem | Cause | Fix |
|---|---|---|
| Extension activate nahi hua | Build fail | `npm run build --workspaces` dobara chalao, errors dekho |
| Python not found | PATH issue | `which python3` chalao, path manually set karo |
| `pruvagraph.db` nahi mila | First activation nahi hua | Command Palette se Initialize Graph chalao |
| DriftGuard kuch nahi pakad raha | Index empty | Initialize Graph chalao, phir wait karo |
| Token count 0 dikh raha | BUG-03 | Fix Prompt 01 ka Fix 3 apply karo pehle |
| Rollback kaam nahi kiya | BUG-04 | Fix Prompt 01 ka Fix 4 apply karo pehle |
| Settings toggle reload maang raha | BUG-07 | Fix Prompt 02 ka Fix 7 apply karo |

---

**Short mein:** Pehle prerequisites setup karo → extension build karke install karo → Developer Tools khola rakho → har phase mein ek ek step follow karo. Koi bhi error aaye toh Developer Tools Console mein exact error message paste karo — wahan se debug kar sakte hain.

