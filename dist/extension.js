"use strict";var we=Object.defineProperty;var et=(a,e,t)=>e in a?we(a,e,{enumerable:!0,configurable:!0,writable:!0,value:t}):a[e]=t;var r=(a,e)=>we(a,"name",{value:e,configurable:!0});var $=(a,e)=>()=>{try{return e||a((e={exports:{}}).exports,e),e.exports}catch(t){throw e=0,t}};var G=(a,e,t)=>et(a,typeof e!="symbol"?e+"":e,t);var I=$((ea,Ce)=>{"use strict";var ke=require("vscode"),Q;function tt(a){Q=a}r(tt,"setOutputChannel");function at(a){if(Q&&typeof Q.appendLine=="function"){Q.appendLine(`[PruvaGraph] ${a}`);return}typeof globalThis<"u"&&Array.isArray(globalThis.__PRUVAGRAPH_TEST_LOG_MESSAGES__)&&globalThis.__PRUVAGRAPH_TEST_LOG_MESSAGES__.push(`[PruvaGraph] ${a}`),console&&typeof console.log=="function"&&console.log(`[PruvaGraph] ${a}`)}r(at,"log");function nt(){let a="",e="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";for(let t=0;t<32;t++)a+=e.charAt(Math.floor(Math.random()*e.length));return a}r(nt,"getNonce");function st(a){return a.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;")}r(st,"escapeHtml");function ot(){var a,e,t;return((t=(e=(a=ke.workspace.workspaceFolders)==null?void 0:a[0])==null?void 0:e.uri)==null?void 0:t.fsPath)||null}r(ot,"getWorkspaceRoot");function rt(){ke.window.showWarningMessage("PruvaGraph: Please open a folder first.")}r(rt,"noWorkspace");Ce.exports={setOutputChannel:tt,log:at,getNonce:nt,escapeHtml:st,getWorkspaceRoot:ot,noWorkspace:rt}});var W=$((na,J)=>{"use strict";var le=require("vscode"),de=require("path"),F=require("fs"),{spawn:it}=require("child_process"),{execSync:lt}=require("child_process"),{log:Se,getWorkspaceRoot:Be,noWorkspace:aa}=I(),y,V,N,ie;function dt({statusBarItem:a,getPanel:e}){y=a,Object.defineProperty(J.exports,"_panel",{get:e,configurable:!0})}r(dt,"initCliRunner");function _e(a,e,t){let n=a,s=e;try{lt(`${a} --version`,{stdio:"ignore"})}catch{n="python",s=a==="pruvagraph"?["-m","pruvagraph",...e]:["-m","pruvagraph",...e.slice(1)]}return it(n,s,{cwd:t,shell:!1,env:{...process.env}})}r(_e,"spawnCLI");function ct(a,e,t,n,s){return new Promise(o=>{var d,c;let i=_e(a,e,t),g=le.window.createOutputChannel("PruvaGraph"),u=r(b=>{b.toString().split(`
`).filter(h=>h.trim()).forEach(h=>{Se(h),s(h)})},"handleData");(d=i.stdout)==null||d.on("data",u),(c=i.stderr)==null||c.on("data",u),i.on("error",b=>{let m=`Error running pruvagraph: ${b.message}.
Install: pip install pruvagraph`;Se(m),s(m),n.post("error",{message:m}),o()}),i.on("exit",b=>{b!==0&&s(`pruvagraph exited with code ${b}`),o()})})}r(ct,"runCLI");function Ee(a){if(!a)return null;let e=de.join(a,"pruvagraph-out","cost_report.json");if(!F.existsSync(e))return null;try{let t=JSON.parse(F.readFileSync(e,"utf8")),n=Number(t.naive_cost_usd||0),s=Math.round(n*1e6/3),o=Number(t.total_input_tokens||0)+Number(t.total_output_tokens||0),i=Math.max(0,s-o),g=s>0?Math.max(0,Math.round((1-o/s)*100)):0;return{cacheHits:Number(t.cache_hits||0),apiCallsAvoided:Number(t.calls_saved||0),totalFilesProcessed:Number(t.total_files_processed||0),llmCallsMade:Number(t.llm_calls_made||0),totalInputTokens:Number(t.total_input_tokens||0),totalOutputTokens:Number(t.total_output_tokens||0),actualCostUsd:Number(t.actual_cost_usd||0),naiveCostUsd:n,costSavedUsd:Number(t.cost_saved_usd||0),savingsPct:Number(t.savings_pct||0),naiveTokens:s,actualTokens:o,tokensSaved:i,compressionPct:g,runDuration:Number(t.run_duration_seconds||0)}}catch{return null}}r(Ee,"loadCostReport");function ce(a){if(!y)return;V&&(clearTimeout(V),V=void 0),N&&(clearTimeout(N),N=void 0);let e=J.exports._panel;if(a&&typeof a.costSavedUsd=="number"&&a.costSavedUsd>0){y.text=`$(graph) PruvaGraph: $${a.costSavedUsd.toFixed(4)} Saved`,y.color=new le.ThemeColor("charts.green"),y.tooltip="Open the PruvaGraph cost report and savings receipt.",y.backgroundColor=new le.ThemeColor("statusBarItem.prominentBackground"),y.show(),V=setTimeout(()=>{y&&(y.backgroundColor=void 0)},1200),ie={value:1,tooltip:`$${a.costSavedUsd.toFixed(4)} saved`};let t=r(()=>{e&&e.badge!==void 0&&(e.badge=void 0,N=setTimeout(()=>{e&&(e.badge=ie),N=setTimeout(t,600)},400))},"updateBadgePulse");e&&(e.badge=ie,N=setTimeout(t,800))}else y.text="$(graph) PruvaGraph",y.color=void 0,y.tooltip="Run a build or dry run to populate savings data.",y.backgroundColor=void 0,y.show(),e&&(e.badge=void 0)}r(ce,"updateStatusBar");function pt(a){let e=Be(),t=e?Ee(e):null;a.post("savingsData",{data:t}),ce(t)}r(pt,"sendSavingsReceipt");async function ut(a,e){let t=Be();if(!t){a.post("status",{graphBuilt:!1,watchMode:e});return}let n=de.join(t,"pruvagraph-out","graph.json"),s=de.join(t,"pruvagraph-out","cost_report.json"),o=F.existsSync(n),i=0,g=0,u=0,d=0;if(o){try{let c=JSON.parse(F.readFileSync(n,"utf8"));i=(c.nodes||[]).length,g=(c.links||c.edges||[]).length}catch{}if(F.existsSync(s))try{let c=JSON.parse(F.readFileSync(s,"utf8"));u=c.savings_pct||0,d=c.cost_saved_usd||0}catch{}}a.post("status",{graphBuilt:o,nodeCount:i,edgeCount:g,savingsPct:u,savedUsd:d,watchMode:e,root:t}),ce(o?{costSavedUsd:d}:null)}r(ut,"sendStatus");J.exports={initCliRunner:dt,spawnCLI:_e,runCLI:ct,loadCostReport:Ee,updateStatusBar:ce,sendSavingsReceipt:pt,sendStatus:ut}});var $e=$((oa,Te)=>{"use strict";var M=require("vscode"),{log:pe}=I(),{spawnCLI:gt}=W(),K;function bt(a){if(!M.workspace.getConfiguration("pruvagraph").get("modules.driftguard.enabled",!1)){pe("[DriftGuard] Disabled via settings.");return}K=M.languages.createDiagnosticCollection("pruvagraph-driftguard"),a.subscriptions.push(K),a.subscriptions.push(M.workspace.onDidSaveTextDocument(n=>{n.languageId!=="python"&&!n.fileName.endsWith(".py")||ht(n)})),pe("[DriftGuard] Enabled \u2014 will validate Python imports on save.")}r(bt,"initDriftGuard");async function ht(a){var i,g,u;if(!K)return;let t=a.getText().split(`
`),n=[],s=((u=(g=(i=M.workspace.workspaceFolders)==null?void 0:i[0])==null?void 0:g.uri)==null?void 0:u.fsPath)||".",o=/^\s*(?:from\s+([\w.]+)\s+import\s+([\w*]+)|import\s+([\w.]+))/;for(let d=0;d<t.length;d++){let c=t[d].match(o);if(!c)continue;let b=c[1]||c[3],m=c[2]||null;if(b&&!b.startsWith("."))try{let h=await mt(b,m,s);if(h&&!h.valid){let k=new M.Range(d,0,d,t[d].length),P=h.suggestion?`DriftGuard: ${b}${m?"."+m:""} \u2014 ${h.suggestion}`:`DriftGuard: ${b}${m?"."+m:""} not found`,ne=new M.Diagnostic(k,P,M.DiagnosticSeverity.Warning);ne.source="PruvaGraph DriftGuard",n.push(ne)}}catch(h){pe(`[DriftGuard] Error validating ${b}: ${h.message}`)}}K.set(a.uri,n)}r(ht,"_runDriftGuardOnFile");function mt(a,e,t){return new Promise(n=>{var u,d;let s=["validate-import",a];e&&e!=="*"&&s.push(e),s.push("--root",t);let o=gt("pruvagraph",s,t),i="",g="";(u=o.stdout)==null||u.on("data",c=>{i+=c.toString()}),(d=o.stderr)==null||d.on("data",c=>{g+=c.toString()}),o.on("error",()=>n(null)),o.on("exit",c=>{if(c===0)n({valid:!0,suggestion:null});else{let b=g.match(/→\s*(.+)/);n({valid:!1,suggestion:b?b[1].trim():g.trim()||null})}})})}r(mt,"_runValidateImport");Te.exports={initDriftGuard:bt}});var Z=$((ia,Ie)=>{"use strict";var p=require("vscode"),j=require("path"),L=require("fs"),{log:E,escapeHtml:X,getWorkspaceRoot:x,noWorkspace:S}=I(),{runCLI:B,spawnCLI:vt,sendStatus:Y,sendSavingsReceipt:U}=W(),C=!1;function ft(){return C}r(ft,"getWatchMode");async function xt(a){let e=x();if(!e)return S();let t=p.workspace.getConfiguration("pruvagraph"),n=t.get("llmBackend","none"),s=t.get("dedupThreshold",.82);a.post("buildStart",{root:e}),E(`Building graph for ${e} \u2026`);let o=[".","--backend",String(n),"--dedup-threshold",String(s),"--stream"];await B("pruvagraph",o,e,a,i=>{a.post("buildLog",{line:i})}),await Y(a,C),await U(a)}r(xt,"runBuild");async function yt(a){try{let e=await p.commands.executeCommand("vscode.executeDocumentSymbolProvider",a);return e?e.map(t=>({name:t.name,detail:t.detail||"",kind:p.SymbolKind[t.kind]||"Unknown",range:{start:{line:t.range.start.line,character:t.range.start.character},end:{line:t.range.end.line,character:t.range.end.character}}})):[]}catch{return[]}}r(yt,"extractSymbolsViaLSP");async function wt(a){let e=x();if(!e)return S();a.post("buildStart",{root:e}),E(`[N3] Fast Building via LSP for ${e} \u2026`);let t=await p.workspace.findFiles("**/*.{py,js,ts,jsx,tsx,java,go,rs}","**/node_modules/**"),n={};a.post("buildLog",{line:`[N3] Found ${t.length} files. Extracting LSP symbols...`});let s=0;for(let d of t.slice(0,50)){let c=await yt(d);c&&c.length>0&&(n[d.fsPath]=c,s++)}a.post("buildLog",{line:`[N3] Extracted symbols for ${s} files. Passing to pipeline...`});let o=j.join(e,"pruvagraph-out");L.existsSync(o)||L.mkdirSync(o,{recursive:!0});let i=j.join(o,"lsp_extractions.json");L.writeFileSync(i,JSON.stringify(n,null,2),"utf-8");let u=p.workspace.getConfiguration("pruvagraph").get("llmBackend","none");await B("pruvagraph",["build-from-lsp",i,"--backend",String(u),"--stream"],e,a,d=>{a.post("buildLog",{line:d})}),await Y(a,C),await U(a)}r(wt,"runBuildFast");async function kt(a,e=""){let t=x();if(!t)return S();let n=await p.window.showInputBox({prompt:"Ask your codebase anything",placeHolder:"How does auth connect to the database?",value:e});if(!n)return;a.post("queryStart",{question:n}),E(`Querying: ${n}`);let o=p.workspace.getConfiguration("pruvagraph").get("llmBackend","none");await B("pruvagraph",["query",n,"--backend",String(o)],t,a,i=>{a.post("queryResult",{line:i})}),await U(a)}r(kt,"runQuery");async function Ct(a){let e=x();if(!e)return S();let t=[];await B("pruvagraph",["cost-report"],e,a,n=>{t.push(n),a.post("logLine",{line:n})}),t.length>0&&a.post("costReport",{text:t.join(`
`)}),await U(a)}r(Ct,"runCostReport");function Pe(){let a=p.workspace.getConfiguration("pruvagraph");return["ghostmemory","driftguard","contextlens","taskweaver","budgetgovernor","rulesforge"].filter(t=>a.get(`modules.${t}.enabled`,!0)===!1)}r(Pe,"getDisabledModules");async function St(a){let e=x();if(!e)return S();let t=await p.window.showQuickPick(["VS Code + Cursor + Claude Code (All)","VS Code only","Cursor only","Claude Code only"],{placeHolder:"Choose where to install PruvaGraph MCP"});if(!t)return;let s={"VS Code + Cursor + Claude Code (All)":[],"VS Code only":["--vscode"],"Cursor only":["--cursor"],"Claude Code only":["--claude-code"]}[t]||[],o=Pe();o.length>0&&(s.push("--disable-modules",o.join(",")),E(`[settings-gating] Disabled modules: ${o.join(", ")}`)),await B("pruvagraph",["install",...s],e,a,i=>{a.post("logLine",{line:i}),E(i)}),p.window.showInformationMessage("\u2713 PruvaGraph MCP installed! Restart your IDE to activate.")}r(St,"runInstallMCP");async function Bt(){let a=x();if(!a)return S();let e=j.join(a,"pruvagraph-out","graph.html");if(!L.existsSync(e)){await p.window.showWarningMessage("No graph found. Build one first?","Build Now","Cancel")==="Build Now"&&await p.commands.executeCommand("pruvagraph.build");return}p.env.openExternal(p.Uri.file(e))}r(Bt,"openVisualizer");async function _t(a){let e=x();if(!e)return S();let t=j.join(e,"pruvagraph-out");if(await p.window.showWarningMessage("Clear PruvaGraph cache? The next build will re-extract all files.","Clear Cache","Cancel")==="Clear Cache")try{L.rmSync(t,{recursive:!0,force:!0}),a.post("logLine",{line:"\u2713 Cache cleared."}),p.window.showInformationMessage("PruvaGraph cache cleared."),Y(a,C)}catch(s){a.post("logLine",{line:`\u26A0 Error: ${s.message}`})}}r(_t,"clearCache");function Et(a){var e,t;if(C=!C,a.post("watchStatus",{active:C}),C){let n=x();if(!n){C=!1;return}E("Watch mode ON"),p.window.showInformationMessage("PruvaGraph watch mode ON \u2014 auto-rebuilds on file save.");let s=vt("pruvagraph",["watch","."],n);a._watchProc=s,(e=s.stdout)==null||e.on("data",o=>{let i=o.toString().trim();i&&a.post("buildLog",{line:i})}),s.on("exit",()=>{C=!1,a.post("watchStatus",{active:!1})})}else E("Watch mode OFF"),(t=a._watchProc)==null||t.kill(),a._watchProc=void 0,p.window.showInformationMessage("PruvaGraph watch mode OFF.")}r(Et,"toggleWatch");async function Tt(a){let e=p.window.activeTextEditor,n=((e==null?void 0:e.document.getText(e.selection))||"").trim()||await p.window.showInputBox({prompt:"Enter function/class name to find callers",placeHolder:"MyClass or myFunction"});if(!n)return;let s=x();s&&(a.post("queryStart",{question:`Callers of: ${n}`}),await B("pruvagraph",["query",`who calls ${n}`,"--backend","none"],s,a,o=>{a.post("queryResult",{line:o})}))}r(Tt,"findCallers");async function $t(a){let e=p.window.activeTextEditor,n=((e==null?void 0:e.document.getText(e.selection))||"").trim()||await p.window.showInputBox({prompt:"Enter module/function to get dependencies",placeHolder:"AuthService or src/auth/index.ts"});if(!n)return;let s=x();s&&(a.post("queryStart",{question:`Dependencies of: ${n}`}),await B("pruvagraph",["query",`dependencies of ${n}`,"--backend","none"],s,a,o=>{a.post("queryResult",{line:o})}))}r($t,"getDependencies");async function Pt(a){let e=await p.window.showQuickPick([{label:"$(terminal) pip install pruvagraph",description:"Standard pip install",value:"pip"},{label:"$(zap) uvx pruvagraph (faster)",description:"Install via uv \u2014 faster, recommended",value:"uvx"}],{placeHolder:"Choose installation method"});if(!e)return;let t=process.platform==="win32",n=e.value==="uvx"?"uvx":t?"pip":"pip3",s=e.value==="uvx"?["pruvagraph","."]:["install","--upgrade","pruvagraph"];a.post("buildStart",{root:"Installing pruvagraph\u2026"}),E(`Running: ${n} ${s.join(" ")}`),await B(n,s,x()||process.cwd(),a,o=>{a.post("buildLog",{line:o})}),p.window.showInformationMessage("\u2713 pruvagraph installed! Now run Build Graph."),a.post("buildLog",{line:`
\u2713 Installation complete. Click "Build Graph" to start.`})}r(Pt,"runInstallPkg");async function It(a){let e=x();if(!e)return S();a.post("buildStart",{root:e}),E("Dry run: estimating cost savings\u2026");let n=p.workspace.getConfiguration("pruvagraph").get("llmBackend","none"),s=[];await B("pruvagraph",[".","--dry-run","--backend",String(n)],e,a,o=>{s.push(o),a.post("buildLog",{line:o})}),s.length>0&&a.post("costReport",{text:s.join(`
`)}),await U(a)}r(It,"runDryRun");async function Mt(a){let e=x();if(!e)return S();let t=j.join(e,"pruvagraph-out","last_diff.json");if(!L.existsSync(t)){p.window.showInformationMessage("No diff available. Run PruvaGraph build at least twice to see what changed.","Build Now").then(d=>{d==="Build Now"&&p.commands.executeCommand("pruvagraph.build")});return}let n;try{n=JSON.parse(L.readFileSync(t,"utf8"))}catch(d){p.window.showErrorMessage(`Could not read diff: ${d.message}`);return}let s=p.window.createWebviewPanel("pruvagraphDiff","PruvaGraph \u2014 Graph Diff",p.ViewColumn.Beside,{enableScripts:!1}),o=n.git_sha?` [${n.git_sha}]`:"",i=n.timestamp?new Date(n.timestamp*1e3).toLocaleString():"",g=n.diff_summary||"no changes",u=r((d,c,b)=>d.length===0?'<span class="empty">none</span>':d.map(m=>`<div class="item ${b}">${c} ${X(String(m))}</div>`).join(""),"renderList");s.webview.html=`<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<style>
  body { font-family: var(--vscode-font-family, monospace); font-size:12px;
         background:var(--vscode-editor-background); color:var(--vscode-foreground); padding:16px; }
  h2 { font-size:14px; margin-bottom:4px; }
  .meta { color:var(--vscode-descriptionForeground); font-size:11px; margin-bottom:16px; }
  h3 { font-size:12px; font-weight:600; margin:14px 0 6px; }
  .item { padding:2px 6px; border-radius:3px; margin:2px 0; font-family:monospace; font-size:11px; }
  .added   { background:rgba(166,227,161,0.12); color:#a6e3a1; }
  .removed { background:rgba(243,139,168,0.12); color:#f38ba8; }
  .changed { background:rgba(249,226,175,0.12); color:#f9e2af; }
  .empty   { color:var(--vscode-descriptionForeground); font-style:italic; }
  .badge   { display:inline-block; padding:1px 6px; border-radius:3px; font-size:10px;
             font-weight:700; margin-left:6px; background:#7C6EFA; color:#fff; }
</style></head><body>
<h2>\u{1F4CA} Graph Diff${o} <span class="badge">D1</span></h2>
<div class="meta">${i?`Built ${i} \xB7 `:""}${g}</div>
<h3>\u2795 Added Nodes (${n.added_nodes.length})</h3>${u(n.added_nodes,"\u2795","added")}
<h3>\u2796 Removed Nodes (${n.removed_nodes.length})</h3>${u(n.removed_nodes,"\u2796","removed")}
<h3>\u270F\uFE0F Changed Nodes (${n.changed_nodes.length})</h3>${u(n.changed_nodes,"\u270F\uFE0F","changed")}
<h3>\u{1F517} Added Edges (${n.added_edges.length})</h3>${u(n.added_edges.map(d=>d.join(" \u2192 ")),"\u{1F517}","added")}
<h3>\u{1F5D1} Removed Edges (${n.removed_edges.length})</h3>${u(n.removed_edges.map(d=>d.join(" \u2192 ")),"\u{1F5D1}","removed")}
</body></html>`,a.post("diffLoaded",{summary:g,added:n.added_nodes.length,removed:n.removed_nodes.length,changed:n.changed_nodes.length})}r(Mt,"showDiff");async function Lt(a){var c;let e=x();if(!e)return S();let t=p.window.activeTextEditor,s=((c=t==null?void 0:t.document.getText(t.selection))==null?void 0:c.trim())||""||await p.window.showInputBox({prompt:"[D2] Enter symbol, class, function or file to analyse",placeHolder:"SessionManager  or  auth.py  or  build_graph"});if(!s)return;let o=await p.window.showQuickPick(["3 (default)","4","5","2 (fast)"],{placeHolder:"BFS depth \u2014 how many hops of dependents to include?"}),i=o?parseInt(o[0]):3,g=p.window.createWebviewPanel("pruvagraphImpact",`Impact: ${s}`,p.ViewColumn.Beside,{enableScripts:!1});g.webview.html=`<!DOCTYPE html><html><body style="font-family:monospace;padding:16px;background:var(--vscode-editor-background);color:var(--vscode-foreground)">
<h2 style="font-size:14px">\u26A0\uFE0F Analyzing impact of <code>${X(s)}</code>\u2026</h2>
<p style="color:var(--vscode-descriptionForeground);font-size:11px">Running impact analysis (BFS depth ${i})\u2026</p>
</body></html>`;let u=[];await B("pruvagraph",["impact",s,"--depth",String(i),"--format","table"],e,a,b=>{u.push(b)});let d=X(u.join(`
`));g.webview.html=`<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<style>
  body { font-family:var(--vscode-font-family,monospace); font-size:12px;
         background:var(--vscode-editor-background); color:var(--vscode-foreground); padding:16px; }
  pre  { font-family:monospace; font-size:11px; line-height:1.6; white-space:pre-wrap; word-break:break-word; }
  .badge { display:inline-block; padding:1px 6px; border-radius:3px;
           font-size:10px; font-weight:700; background:#f9e2af; color:#1e1e2e; margin-left:6px; }
</style></head><body>
<h2 style="font-size:14px">\u26A0\uFE0F Impact: <code>${X(s)}</code> <span class="badge">D2</span></h2>
<pre>${d||"No output received \u2014 is graph built?"}</pre>
</body></html>`}r(Lt,"analyzeImpact");async function Rt(a){let e=x();if(!e)return S();let n=p.workspace.getConfiguration("pruvagraph").get("llmBackend","none");await p.window.showInformationMessage("[M1] Build per-package graphs for the entire monorepo?","Build Monorepo","Cancel")==="Build Monorepo"&&(a.post("buildStart",{root:e}),E("[M1] Building monorepo graph\u2026"),await B("pruvagraph",[".","--monorepo","--no-viz","--backend",String(n)],e,a,o=>{a.post("buildLog",{line:o})}),await Y(a,C),p.window.showInformationMessage("\u2713 Monorepo graph built. See pruvagraph-out/cross_graph.json"))}r(Rt,"buildMonorepo");Ie.exports={runBuild:xt,runBuildFast:wt,runQuery:kt,runCostReport:Ct,runInstallMCP:St,openVisualizer:Bt,clearCache:_t,toggleWatch:Et,findCallers:Tt,getDependencies:$t,runInstallPkg:Pt,runDryRun:It,showDiff:Mt,analyzeImpact:Lt,buildMonorepo:Rt,getDisabledModules:Pe,getWatchMode:ft}});var Le=$((da,Me)=>{"use strict";var{getNonce:Dt}=I();function At(a,e){let t=Dt();return`<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy"
  content="default-src 'none'; style-src ${a.cspSource} 'unsafe-inline'; script-src 'nonce-${t}';">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PruvaGraph</title>
<style>
:root {
  --bg: var(--vscode-sideBar-background, #1e1e2e);
  --surface: var(--vscode-editor-background, #181825);
  --border: var(--vscode-widget-border, #313244);
  --text: var(--vscode-foreground, #cdd6f4);
  --muted: var(--vscode-descriptionForeground, #6c7086);
  --accent: #7C6EFA;
  --green: #a6e3a1;
  --cyan: #89dceb;
  --yellow: #f9e2af;
  --red: #f38ba8;
  --link: var(--vscode-textLink-foreground, #89b4fa);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text);
       font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, sans-serif);
       font-size: 12px; padding: 0; overflow-x: hidden; }

/* Header */
.header { padding: 10px 12px 8px; border-bottom: 1px solid var(--border); }
.logo { display: flex; align-items: center; gap: 7px; margin-bottom: 4px; }
.logo-icon { width: 18px; height: 18px; flex-shrink: 0; }
.logo-text { font-size: 13px; font-weight: 700; color: var(--accent); letter-spacing: 0.3px; }
.logo-badge { font-size: 9px; background: var(--green); color: #1e1e2e;
              padding: 1px 5px; border-radius: 3px; font-weight: 700; margin-left: auto; }
.subtitle { color: var(--muted); font-size: 10px; }

/* Tabs */
.tabs { display: flex; border-bottom: 1px solid var(--border); background: var(--surface); }
.tab { flex: 1; text-align: center; padding: 8px 0; cursor: pointer; color: var(--muted); font-weight: 600; font-size: 11px; border-bottom: 2px solid transparent; transition: all 0.2s ease; }
.tab:hover { color: var(--text); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-content { display: none; padding-bottom: 20px; }
.tab-content.active { display: block; }

/* Dashboard UI */
.metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 10px; }
.metric-card { border-radius: 12px; padding: 14px; background: rgba(255,255,255,0.04); border: 1px solid rgba(124,58,237,0.2); transition: all 0.3s ease; }
.metric-card:hover { background: rgba(255,255,255,0.06); border-color: rgba(124,58,237,0.4); transform: translateY(-2px); }
.metric-label { font-size: 0.75rem; color: rgba(255,255,255,0.6); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; font-weight: 600; }
.metric-value { font-size: 1.5rem; font-weight: 700; background: linear-gradient(135deg, #7c3aed, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin: 0; }
.metric-value.savings { background: linear-gradient(135deg, #10b981, #34d399); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.metric-value.tokens { background: linear-gradient(135deg, #f59e0b, #fbbf24); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.metric-secondary { font-size: 0.8rem; color: rgba(255,255,255,0.5); margin-top: 6px; }
.premium-card { border-radius: 14px; padding: 16px; margin: 10px; background: linear-gradient(135deg, rgba(124,58,237,0.1), rgba(167,139,250,0.05)); border: 1px solid rgba(124,58,237,0.3); }
.premium-card h3 { margin: 0 0 12px; font-size: 0.9rem; font-weight: 700; color: #ffffff; display: flex; align-items: center; gap: 8px; }
.premium-card h3::before { content: '\u2728'; font-size: 1rem; }
.stat-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
.stat-row:last-child { border-bottom: none; }
.stat-label { font-size: 0.85rem; color: rgba(255,255,255,0.7); }
.stat-value { font-weight: 700; font-size: 0.9rem; color: #ffffff; }

/* Status card */
.status-card { margin: 8px 10px; padding: 10px 12px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; }
.status-row-basic { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.status-dot.built { background: var(--green); box-shadow: 0 0 6px var(--green); }
.status-dot.empty { background: var(--muted); }
.status-dot.watch { background: var(--yellow); animation: pulse 2s infinite; }
.status-label-basic { font-weight: 600; flex: 1; }
.status-meta { color: var(--muted); font-size: 10px; }

/* Buttons */
.btn-group { margin: 8px 10px; display: flex; flex-direction: column; gap: 5px; }
.btn { display: flex; align-items: center; gap: 7px; background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 7px 10px; border-radius: 6px; cursor: pointer; font-size: 12px; width: 100%; text-align: left; transition: border-color 0.15s, background 0.15s; }
.btn:hover { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 8%, var(--surface)); }
.btn.primary { background: var(--accent); border-color: var(--accent); color: white; font-weight: 600; }
.btn.primary:hover { background: #6a5de8; }
.btn.danger  { border-color: var(--red); color: var(--red); }
.btn.danger:hover { background: color-mix(in srgb, var(--red) 12%, var(--surface)); }
.btn.active  { border-color: var(--yellow); color: var(--yellow); }
.btn-icon { font-size: 14px; }
.btn-label { flex: 1; }
.btn-badge { font-size: 9px; background: var(--accent); color: white; padding: 1px 5px; border-radius: 3px; }

/* Accessibility: focus indicators (WCAG 2.1 AA) */
.btn:focus-visible, .tab:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 4px;
}
*:focus { outline: none; }

/* Output / log */
.section-title { font-size: 10px; font-weight: 700; text-transform: uppercase; color: var(--muted); letter-spacing: 0.8px; padding: 6px 12px 3px; }
.log-box { margin: 0 10px 8px; padding: 8px 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; max-height: 160px; overflow-y: auto; font-family: monospace; font-size: 10px; color: var(--muted); display: none; }
.log-box.visible { display: block; }
.log-line { line-height: 1.5; white-space: pre-wrap; word-break: break-all; }
.log-line.ok   { color: var(--green); }
.log-line.warn { color: var(--yellow); }
.log-line.err  { color: var(--red); }

/* Query result */
.query-box { margin: 0 10px 8px; padding: 8px 10px; background: var(--surface); border: 1px solid var(--border); border-radius: 6px; max-height: 200px; overflow-y: auto; font-size: 11px; line-height: 1.6; display: none; }
.query-box.visible { display: block; }

/* Progress */
.progress-bar { height: 2px; background: var(--accent); border-radius: 2px; width: 0; transition: width 0.3s; margin: 0 10px 6px; display: none; }
.progress-bar.active { display: block; animation: progress-anim 2s linear infinite; }

@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
@keyframes progress-anim { 0% { width: 0; margin-left: 10px; } 50% { width: calc(100% - 20px); } 100% { width: 0; margin-left: calc(100% - 10px); } }

/* Divider */
.divider { border: none; border-top: 1px solid var(--border); margin: 6px 10px; }

/* Footer */
.footer { padding: 6px 12px; color: var(--muted); font-size: 10px; border-top: 1px solid var(--border); display: flex; gap: 8px; }
.footer a { color: var(--link); text-decoration: none; cursor: pointer; }

/* ContextLens placeholder */
.context-lens-box { margin: 10px; padding: 16px; border: 1px dashed var(--border); border-radius: 8px; text-align: center; color: var(--muted); }
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <div class="logo">
    <svg class="logo-icon" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="4" cy="4" r="3" fill="#7C6EFA"/>
      <circle cx="14" cy="4" r="3" fill="#22D3EE"/>
      <circle cx="9" cy="14" r="3" fill="#34D399"/>
      <line x1="4" y1="4" x2="14" y2="4" stroke="#7C6EFA" stroke-width="1.5"/>
      <line x1="4" y1="4" x2="9"  y2="14" stroke="#7C6EFA" stroke-width="1.5"/>
      <line x1="14" y1="4" x2="9" y2="14" stroke="#22D3EE" stroke-width="1.5"/>
    </svg>
    <span class="logo-text">PRUVALEX PruvaGraph</span>
    <span class="logo-badge">FREE</span>
  </div>
  <div class="subtitle">Measured LLM cost reduction \xB7 No server needed</div>
</div>

<!-- Tabs (WCAG: role=tablist, role=tab, aria-selected, aria-controls) -->
<div class="tabs" role="tablist" aria-label="PruvaGraph panels">
  <div class="tab active" role="tab" tabindex="0" data-tab="explorer"
       aria-selected="true" aria-controls="tab-explorer" id="tab-btn-explorer"
       onclick="switchTab('explorer')" onkeydown="handleTabKey(event,'explorer')">Explorer</div>
  <div class="tab" role="tab" tabindex="-1" data-tab="context"
       aria-selected="false" aria-controls="tab-context" id="tab-btn-context"
       onclick="switchTab('context')" onkeydown="handleTabKey(event,'context')">ContextLens</div>
  <div class="tab" role="tab" tabindex="-1" data-tab="cost"
       aria-selected="false" aria-controls="tab-cost" id="tab-btn-cost"
       onclick="switchTab('cost')" onkeydown="handleTabKey(event,'cost')">Cost Dashboard</div>
</div>

<!-- Progress bar -->
<div class="progress-bar" id="progressBar"></div>

<!-- TAB 1: EXPLORER -->
<div id="tab-explorer" class="tab-content active" role="tabpanel" aria-labelledby="tab-btn-explorer">
  <div class="status-card" id="statusCard" role="status" aria-live="polite" aria-label="Graph build status">
    <div class="status-row-basic">
      <div class="status-dot empty" id="statusDot" aria-hidden="true"></div>
      <div class="status-label-basic" id="statusLabel">No graph built yet</div>
    </div>
    <div class="status-meta" id="statusMeta">Run "Build Graph" to analyse your codebase</div>
  </div>

  <div class="btn-group">
    <button class="btn primary" onclick="send('build')" aria-label="Build Graph (Ctrl+Shift+G)" id="btn-build">
      <span class="btn-icon" aria-hidden="true">\u26A1</span>
      <span class="btn-label">Build Graph</span>
      <span style="font-size:9px;opacity:0.7" aria-hidden="true">Ctrl+Shift+G</span>
    </button>
    <button class="btn" onclick="send('buildFast')" aria-label="Build Fast using LSP" id="btn-buildFast">
      <span class="btn-icon" aria-hidden="true">\u{1F680}</span>
      <span class="btn-label">Build Fast (LSP)</span>
      <span class="btn-badge" style="background:var(--green);color:#000" aria-hidden="true">N3</span>
    </button>
    <button class="btn" onclick="send('query')" aria-label="Query Codebase (Ctrl+Shift+/)" id="btn-query">
      <span class="btn-icon" aria-hidden="true">\u{1F50D}</span>
      <span class="btn-label">Query Codebase</span>
      <span style="font-size:9px;opacity:0.7" aria-hidden="true">Ctrl+Shift+/</span>
    </button>
    <button class="btn" onclick="send('openViz')" aria-label="Open Graph Visualizer in browser" id="btn-openViz">
      <span class="btn-icon" aria-hidden="true">\u{1F310}</span>
      <span class="btn-label">Open Graph Visualizer</span>
    </button>
  </div>
  <hr class="divider" role="separator">
  <div class="btn-group">
    <button class="btn" onclick="send('installMCP')" aria-label="Install MCP server for Claude Code and Cursor" id="btn-installMCP">
      <span class="btn-icon" aria-hidden="true">\u{1F50C}</span>
      <span class="btn-label">Install MCP (Claude Code / Cursor)</span>
    </button>
    <button class="btn" id="watchBtn" onclick="send('watchToggle')" aria-label="Toggle Watch Mode" aria-pressed="false">
      <span class="btn-icon" aria-hidden="true">\u{1F441}</span>
      <span class="btn-label">Enable Watch Mode</span>
    </button>
    <button class="btn" onclick="send('dryRun')" aria-label="Dry Run to estimate savings (free)" id="btn-dryRun">
      <span class="btn-icon" aria-hidden="true">\u{1F9EA}</span>
      <span class="btn-label">Dry Run \u2014 Estimate Savings</span>
      <span class="btn-badge" aria-label="Free feature">FREE</span>
    </button>
  </div>
  <hr class="divider" role="separator">
  <!-- v1.3.0: Diff & Impact -->
  <div class="section-title" role="heading" aria-level="3">Diff &amp; Impact <span style="font-size:9px;background:#7C6EFA;color:#fff;padding:1px 5px;border-radius:3px;margin-left:4px" aria-hidden="true">v1.3.0</span></div>
  <div class="btn-group">
    <button class="btn" onclick="send('showDiff')" aria-label="Show Graph Diff between builds" id="btn-showDiff">
      <span class="btn-icon" aria-hidden="true">\u{1F4CA}</span>
      <span class="btn-label">Show Graph Diff</span>
      <span class="btn-badge" style="background:var(--cyan);color:#000" aria-hidden="true">D1</span>
    </button>
    <button class="btn" onclick="send('analyzeImpact')" aria-label="Analyze Change Impact on dependent modules" id="btn-analyzeImpact">
      <span class="btn-icon" aria-hidden="true">\u26A0\uFE0F</span>
      <span class="btn-label">Analyze Change Impact</span>
      <span class="btn-badge" style="background:var(--yellow);color:#000" aria-hidden="true">D2</span>
    </button>
    <button class="btn" onclick="send('buildMonorepo')" aria-label="Build Monorepo Graph across all packages" id="btn-buildMonorepo">
      <span class="btn-icon" aria-hidden="true">\u{1F5C2}</span>
      <span class="btn-label">Build Monorepo Graph</span>
      <span class="btn-badge" style="background:var(--green);color:#000" aria-hidden="true">M1</span>
    </button>
  </div>
  <hr class="divider" role="separator">
  <div class="section-title" role="heading" aria-level="3">Setup</div>
  <div class="btn-group">
    <button class="btn" onclick="send('installPkg')" aria-label="Install Python package via pip" id="btn-installPkg">
      <span class="btn-icon" aria-hidden="true">\u{1F4E6}</span>
      <span class="btn-label">Install Python Package</span>
      <span style="font-size:9px;opacity:0.6" aria-hidden="true">pip install pruvagraph</span>
    </button>
  </div>
  <hr class="divider" role="separator">
  <!-- Query output -->
  <div class="section-title" id="queryTitle" style="display:none" role="heading" aria-level="3">Query Result</div>
  <div class="query-box" id="queryBox" aria-live="polite" aria-label="Query result output"></div>
  <!-- Build log -->
  <div class="section-title" id="logTitle" style="display:none" role="heading" aria-level="3">Output</div>
  <div class="log-box" id="logBox" aria-live="polite" aria-label="Build log output"></div>
  <hr class="divider" role="separator">
  <div class="btn-group">
    <button class="btn danger" onclick="send('clearCache')" aria-label="Clear graph cache" id="btn-clearCache">
      <span class="btn-icon" aria-hidden="true">\u{1F5D1}</span>
      <span class="btn-label">Clear Cache</span>
    </button>
  </div>
</div>

<!-- TAB 2: CONTEXT LENS -->
<div id="tab-context" class="tab-content" role="tabpanel" aria-labelledby="tab-btn-context">
  <div class="context-lens-box">
    <h3>\u{1F50D} ContextLens</h3>
    <p style="margin-top:8px">Inline symbol relationships and semantic hints will appear here when you select code in the editor.</p>
    <button class="btn primary" style="margin-top:12px; display:inline-block; width:auto;"
            onclick="send('analyzeImpact')" aria-label="Analyze selected code for impact" id="btn-analyzeSelected">Analyze Selected Code</button>
  </div>
</div>

<!-- TAB 3: COST DASHBOARD -->
<div id="tab-cost" class="tab-content" role="tabpanel" aria-labelledby="tab-btn-cost">
  <div class="metric-grid" role="list" aria-label="Cost metrics">
    <div class="metric-card" role="listitem">
      <div class="metric-label" id="lbl-savings">\u{1F4B0} Estimated Savings</div>
      <p class="metric-value savings" aria-labelledby="lbl-savings">$<span id="savings">0.00</span></p>
      <div class="metric-secondary">vs. baseline cost</div>
    </div>
    <div class="metric-card" role="listitem">
      <div class="metric-label" id="lbl-tokens">\u{1F680} Tokens Saved</div>
      <p class="metric-value tokens" aria-labelledby="lbl-tokens"><span id="tokensSaved">0</span></p>
      <div class="metric-secondary">total reduction</div>
    </div>
    <div class="metric-card" role="listitem">
      <div class="metric-label" id="lbl-cache">\u26A1 Cache Hits</div>
      <p class="metric-value" aria-labelledby="lbl-cache"><span id="cacheHits">0</span></p>
      <div class="metric-secondary"><span id="cacheRate">0</span>% compression</div>
    </div>
    <div class="metric-card" role="listitem">
      <div class="metric-label" id="lbl-baseline">\u{1F4C9} Baseline Cost</div>
      <p class="metric-value" style="color:var(--muted)" aria-labelledby="lbl-baseline">$<span id="dedupProjected">0.00</span></p>
      <div class="metric-secondary">without PruvaGraph</div>
    </div>
  </div>
  <div class="premium-card" role="region" aria-label="Token usage breakdown">
    <h3>Token Usage Breakdown</h3>
    <div class="stat-row">
      <span class="stat-label" id="lbl-tokensIn">Total Input Tokens</span>
      <span class="stat-value" aria-labelledby="lbl-tokensIn"><span id="tokensIn">0</span></span>
    </div>
    <div class="stat-row">
      <span class="stat-label" id="lbl-tokensOut">Total Output Tokens</span>
      <span class="stat-value" aria-labelledby="lbl-tokensOut"><span id="tokensOut">0</span></span>
    </div>
    <div class="stat-row">
      <span class="stat-label" id="lbl-apiAvoided">API Calls Avoided</span>
      <span class="stat-value" aria-labelledby="lbl-apiAvoided"><span id="apiAvoided">0</span> calls</span>
    </div>
  </div>
  <div class="btn-group">
    <button class="btn" onclick="send('refreshSavings')" aria-label="Refresh cost metrics" id="btn-refreshSavings">
      <span class="btn-icon" aria-hidden="true">\u{1F504}</span>
      <span class="btn-label">Refresh Metrics</span>
    </button>
    <button class="btn" onclick="send('costReport')" aria-label="View raw JSON cost report" id="btn-costReport">
      <span class="btn-icon" aria-hidden="true">\u{1F4CA}</span>
      <span class="btn-label">View Raw JSON Report</span>
    </button>
  </div>
</div>

<!-- Footer -->
<div class="footer" style="margin-top:10px;">
  <span>by <a onclick="send('openExternal',{url:'https://pruvalex.eu'})" style="cursor:pointer">PRUVALEX</a></span>
  <span>\xB7</span>
  <a onclick="send('openExternal',{url:'https://github.com/pruvalex/pruvagraph'})" style="cursor:pointer">GitHub</a>
</div>

<script nonce="${t}">
const vscode = acquireVsCodeApi();

function send(command, extra = {}) {
  vscode.postMessage({ command, ...extra });
}

const TAB_ORDER = ['explorer', 'context', 'cost'];

function switchTab(tabId) {
  document.querySelectorAll('.tab').forEach(t => {
    const isActive = t.getAttribute('data-tab') === tabId;
    t.classList.toggle('active', isActive);
    t.setAttribute('aria-selected', isActive ? 'true' : 'false');
    t.setAttribute('tabindex', isActive ? '0' : '-1');
  });
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  const activeContent = document.getElementById('tab-' + tabId);
  if (activeContent) activeContent.classList.add('active');
}

function handleTabKey(event, tabId) {
  const idx = TAB_ORDER.indexOf(tabId);
  let next = -1;
  if (event.key === 'ArrowRight') next = (idx + 1) % TAB_ORDER.length;
  else if (event.key === 'ArrowLeft') next = (idx - 1 + TAB_ORDER.length) % TAB_ORDER.length;
  else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); switchTab(tabId); return; }
  if (next >= 0) {
    event.preventDefault();
    const nextBtn = document.getElementById('tab-btn-' + TAB_ORDER[next]);
    if (nextBtn) { switchTab(TAB_ORDER[next]); nextBtn.focus(); }
  }
}

let building = false;
let queryLines = [];
let logLines = [];

window.addEventListener('message', (event) => {
  const msg = event.data;
  switch (msg.command) {
    case 'status':      return onStatus(msg);
    case 'buildStart':  return onBuildStart(msg);
    case 'buildLog':    return onBuildLog(msg);
    case 'queryStart':  return onQueryStart(msg);
    case 'queryResult': return onQueryResult(msg);
    case 'costReport':  return onCostReport(msg);
    case 'savingsData': return onSavingsData(msg);
    case 'logLine':     return onLogLine(msg);
    case 'watchStatus': return onWatchStatus(msg);
    case 'diffLoaded':  return onDiffLoaded(msg);
    case 'error':       return onError(msg);
  }
});

function onStatus(msg) {
  const dot = document.getElementById('statusDot');
  const lbl = document.getElementById('statusLabel');
  const meta = document.getElementById('statusMeta');
  if (msg.watchMode) dot.className = 'status-dot watch';
  else if (msg.graphBuilt) dot.className = 'status-dot built';
  else dot.className = 'status-dot empty';

  if (msg.graphBuilt) {
    lbl.textContent = 'Graph ready';
    const folder = msg.root ? msg.root.split(/[\\\\/]/).pop() : '';
    const counts = (msg.nodeCount || msg.edgeCount) ? ' \xB7 ' + (msg.nodeCount||0) + ' nodes \xB7 ' + (msg.edgeCount||0) + ' edges' : '';
    meta.textContent = folder + counts;
  } else {
    lbl.textContent = 'No graph built yet';
    meta.textContent = 'Run "Build Graph" to analyse your codebase';
  }

  const watchBtn = document.getElementById('watchBtn');
  if (msg.watchMode) {
    watchBtn.className = 'btn active';
    watchBtn.querySelector('.btn-label').textContent = 'Disable Watch Mode';
    watchBtn.setAttribute('aria-pressed', 'true');
    watchBtn.setAttribute('aria-label', 'Disable Watch Mode');
  } else {
    watchBtn.className = 'btn';
    watchBtn.querySelector('.btn-label').textContent = 'Enable Watch Mode';
    watchBtn.setAttribute('aria-pressed', 'false');
    watchBtn.setAttribute('aria-label', 'Enable Watch Mode');
  }
}

function onBuildStart(msg) {
  building = true; logLines = [];
  switchTab('explorer');
  document.getElementById('logTitle').style.display = 'block';
  const lb = document.getElementById('logBox');
  lb.innerHTML = ''; lb.classList.add('visible');
  document.getElementById('progressBar').classList.add('active');
  appendLog('Building graph\u2026', 'ok');
}

function onBuildLog(msg) {
  appendLog(msg.line);
  const line = msg.line || '';
  if (line.includes('\u2713') || line.includes('Graph:') || line.includes('complete') ||
      line.includes('Error') || line.includes('error') || line.includes('exited with code')) {
    document.getElementById('progressBar').classList.remove('active');
    building = false;
  }
}

function onQueryStart(msg) {
  queryLines = [];
  switchTab('explorer');
  document.getElementById('queryTitle').style.display = 'block';
  const qb = document.getElementById('queryBox');
  qb.innerHTML = ''; qb.classList.add('visible');
  appendQuery('\u{1F50D} ' + msg.question);
  appendQuery('');
}

function onQueryResult(msg) { appendQuery(msg.line); }

function onCostReport(msg) {
  switchTab('explorer');
  document.getElementById('queryTitle').style.display = 'block';
  document.getElementById('queryTitle').textContent = 'Raw Cost Report';
  const qb = document.getElementById('queryBox');
  qb.innerHTML = '<pre style="white-space:pre-wrap;font-size:10px;font-family:monospace">' + escHtml(msg.text) + '</pre>';
  qb.classList.add('visible');
}

function formatNumber(num) {
  if (!num) return '0';
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
  return num.toLocaleString();
}

function onSavingsData(msg) {
  const data = msg.data;
  if (!data) return;
  const safeNum = (v, digits = 2) => (typeof v === 'number' && isFinite(v)) ? v.toFixed(digits) : '0.' + '0'.repeat(digits);
  document.getElementById('savings').textContent = safeNum(data.costSavedUsd);
  document.getElementById('tokensSaved').textContent = formatNumber(data.tokensSaved || 0);
  document.getElementById('cacheHits').textContent = formatNumber(data.cacheHits || 0);
  document.getElementById('cacheRate').textContent = data.compressionPct != null ? data.compressionPct : 0;
  document.getElementById('dedupProjected').textContent = safeNum(data.naiveCostUsd);
  document.getElementById('tokensIn').textContent = formatNumber(data.totalInputTokens || 0);
  document.getElementById('tokensOut').textContent = formatNumber(data.totalOutputTokens || 0);
  document.getElementById('apiAvoided').textContent = formatNumber(data.apiCallsAvoided || 0);
}

function onLogLine(msg) {
  document.getElementById('logTitle').style.display = 'block';
  document.getElementById('logBox').classList.add('visible');
  appendLog(msg.line);
}

function onWatchStatus(msg) {
  const dot = document.getElementById('statusDot');
  const watchBtn = document.getElementById('watchBtn');
  if (msg.active) {
    dot.className = 'status-dot watch';
    watchBtn.className = 'btn active';
    watchBtn.querySelector('.btn-label').textContent = 'Disable Watch Mode';
  } else {
    const lbl = document.getElementById('statusLabel');
    dot.className = (lbl && lbl.textContent === 'Graph ready') ? 'status-dot built' : 'status-dot empty';
    watchBtn.className = 'btn';
    watchBtn.querySelector('.btn-label').textContent = 'Enable Watch Mode';
  }
}

function onDiffLoaded(msg) {
  document.getElementById('logTitle').style.display = 'block';
  document.getElementById('logTitle').textContent = 'Graph Diff';
  document.getElementById('logBox').classList.add('visible');
  appendLog('\u{1F4CA} ' + (msg.summary || 'No changes'), 'ok');
  if (msg.added) appendLog('  \u2795 ' + msg.added + ' added', 'ok');
  if (msg.removed) appendLog('  \u2796 ' + msg.removed + ' removed', 'err');
  if (msg.changed) appendLog('  \u270F\uFE0F ' + msg.changed + ' changed', 'warn');
}

function onError(msg) {
  document.getElementById('logTitle').style.display = 'block';
  document.getElementById('logBox').classList.add('visible');
  appendLog('\u26A0 ' + msg.message, 'err');
  appendLog('Install: pip install pruvagraph', 'warn');
  document.getElementById('progressBar').classList.remove('active');
}

function appendLog(text, cls = '') {
  const lb = document.getElementById('logBox');
  const line = document.createElement('div');
  line.className = 'log-line ' + cls;
  line.textContent = text;
  lb.appendChild(line);
  lb.scrollTop = lb.scrollHeight;
}

function appendQuery(text) {
  const qb = document.getElementById('queryBox');
  const line = document.createElement('div');
  line.style.cssText = 'margin-bottom:3px';
  line.textContent = text;
  qb.appendChild(line);
  qb.scrollTop = qb.scrollHeight;
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

send('ready');
</script>
</body>
</html>`}r(At,"getWebviewHtml");Me.exports={getWebviewHtml:At}});var Ne=$((pa,qe)=>{"use strict";var ee=require("vscode"),{sendStatus:Re,sendSavingsReceipt:De}=W(),{getWatchMode:Ae}=Z(),ue,ze;function zt(){return ze}r(zt,"getPanel");var te=class te{constructor(e){this._extensionUri=e,this._view=void 0,this._watchProc=void 0}resolveWebviewView(e){this._view=e,ze=e,ue||(ue=Le().getWebviewHtml),e.webview.options={enableScripts:!0,localResourceRoots:[ee.Uri.joinPath(this._extensionUri,"media")]},e.webview.html=ue(e.webview,this._extensionUri);let t=Z();e.webview.onDidReceiveMessage(n=>{switch(n.command){case"build":return t.runBuild(this);case"buildFast":return t.runBuildFast(this);case"query":return t.runQuery(this,n.text);case"costReport":return t.runCostReport(this);case"refreshSavings":return De(this);case"installMCP":return t.runInstallMCP(this);case"openViz":return t.openVisualizer();case"clearCache":return t.clearCache(this);case"watchToggle":return t.toggleWatch(this);case"showOutput":return ee.commands.executeCommand("workbench.action.output.toggleOutput");case"ready":return Promise.all([Re(this,Ae()),De(this)]);case"installPkg":return t.runInstallPkg(this);case"dryRun":return t.runDryRun(this);case"showDiff":return t.showDiff(this);case"analyzeImpact":return t.analyzeImpact(this);case"buildMonorepo":return t.buildMonorepo(this);case"openExternal":return ee.env.openExternal(ee.Uri.parse(n.url))}}),Re(this,Ae())}post(e,t){this._view&&this._view.webview.postMessage({command:e,...t})}};r(te,"PruvaGraphViewProvider"),G(te,"viewType","pruvagraphPanel");var ge=te;qe.exports={PruvaGraphViewProvider:ge,getPanel:zt}});var We=$((ga,Ge)=>{"use strict";var _=require("vscode"),Fe=require("path"),he=require("fs"),{spawn:qt}=require("child_process");function be(a,e){return new Promise(t=>{var d,c,b,m,h;let n=((b=(c=(d=_.workspace.workspaceFolders)==null?void 0:d[0])==null?void 0:c.uri)==null?void 0:b.fsPath)||".",s=e||n,o=qt("python",["-m","pruvagraph.cli",...a],{cwd:s,shell:!1,env:{...process.env,PYTHONUTF8:"1"}}),i="",g="",u=setTimeout(()=>{o.kill(),t(JSON.stringify({error:"CLI timeout (15s)"}))},15e3);(m=o.stdout)==null||m.on("data",k=>{i+=k.toString()}),(h=o.stderr)==null||h.on("data",k=>{g+=k.toString()}),o.on("error",k=>{clearTimeout(u),t(JSON.stringify({error:k.message}))}),o.on("exit",()=>{clearTimeout(u),t(i||JSON.stringify({error:g||"no output"}))})})}r(be,"_runPythonCLI");function Oe(a){try{let e=Fe.join(a,"pruvagraph-out","benchmark_results.jsonl");if(!he.existsSync(e))return null;let t=he.readFileSync(e,"utf-8").trim().split(`
`).filter(Boolean),n=JSON.parse(t[0]),s=t.slice(1).map(o=>JSON.parse(o));return{summary:n,questions:s}}catch{return null}}r(Oe,"_loadBenchmarkData");var w=class w{static createOrShow(e,t="dashboard"){let n=_.window.activeTextEditor?_.window.activeTextEditor.viewColumn:_.ViewColumn.One;if(w.currentPanel){w.currentPanel._panel.reveal(n),w.currentPanel._initialTab=t,w.currentPanel._refresh();return}let s=_.window.createWebviewPanel(w.viewType,"PruvaGraph Analytics",n,{enableScripts:!0,retainContextWhenHidden:!0,localResourceRoots:[]});w.currentPanel=new w(s,e,t)}constructor(e,t,n="dashboard"){this._panel=e,this._context=t,this._disposables=[],this._initialTab=n,this._refresh(),this._panel.onDidDispose(()=>this.dispose(),null,this._disposables),this._panel.webview.onDidReceiveMessage(s=>this._handleMessage(s),null,this._disposables)}_handleMessage(e){var n,s,o;let t=((o=(s=(n=_.workspace.workspaceFolders)==null?void 0:n[0])==null?void 0:s.uri)==null?void 0:o.fsPath)||".";if(e.command==="refresh"){this._refresh();return}if(e.command==="setBudget"){_.window.showInputBox({prompt:"Token budget cap (e.g. 50000)",value:"50000"}).then(async i=>{i&&/^\d+$/.test(i)&&(await be(["budget","set",i],t),this._refresh())});return}if(e.command==="openViz"){let i=Fe.join(t,"pruvagraph-out","graph.html");he.existsSync(i)?_.env.openExternal(_.Uri.file(i)):_.window.showWarningMessage("No graph.html found. Run pruvagraph build first.")}}async _refresh(){var o,i,g;let e=((g=(i=(o=_.workspace.workspaceFolders)==null?void 0:o[0])==null?void 0:i.uri)==null?void 0:g.fsPath)||".",t=Oe(e),n={session_set:!1,cap:0,spent:0,remaining:0,pct_used:0,status:"NO_BUDGET"},s=[];try{n=JSON.parse(await be(["budget","check","--format","json"],e))}catch{}try{s=JSON.parse(await be(["task-progress","--all","--format","json"],e))}catch{}this._panel.webview.html=this._buildHtml(t,n,s)}_buildHtml(e,t,n){let s=t&&t.error?t:n&&n.error?n:null;if(s)return`<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><style>body{font-family:sans-serif;padding:20px;color:#ccc;background:#0d1117;}code{background:#21262d;padding:4px;border-radius:4px;}</style></head>
<body><h2>&#9888; PRUVALEX Engine Error</h2><p>Python CLI execution failed. Ensure python is installed and pruvagraph is accessible.</p>
<pre style="background:#21262d;padding:10px;border-radius:4px;white-space:pre-wrap;"><code>${r(v=>String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"),"_escErr")(s.error)}</code></pre>
<p>Run: <code>pip install pruvalex-pruvagraph</code> to resolve this.</p></body></html>`;let o=e?e.summary:{},i=+(o.avg_savings_pct||0),g=+(o.avg_tokens_graph||0),u=+(o.avg_tokens_raw||0),d=+(o.question_count||0),c={tier0_cache:0,tier1_deterministic:0,tier2_embedding:0,tier3_subgraph:0,tier_unknown:0};(e?e.questions:[]).forEach(l=>{let v=l.method_used||"tier_unknown";c[v]=(c[v]||0)+1});let b=(e?e.questions:[]).filter(l=>l.savings_pct>0).sort((l,v)=>v.savings_pct-l.savings_pct).slice(0,8),m=Math.min(+(t.pct_used||0),100),h=(m/100*339).toFixed(1),k=t.status==="EXCEEDED"?"#ff4d4d":t.status==="WARNING"?"#f5a623":"#4ecdc4",P={};(Array.isArray(n)?n:[]).forEach(l=>{P[l.task_id]||(P[l.task_id]=[]),P[l.task_id].push(l)});let fe=Object.keys(P),xe=[{key:"tier0_cache",label:"Tier 0 \u2014 Cache",color:"#3fb950",desc:"Free: exact match"},{key:"tier1_deterministic",label:"Tier 1 \u2014 Deterministic",color:"#4ecdc4",desc:"Free: graph traversal"},{key:"tier2_embedding",label:"Tier 2 \u2014 Embedding",color:"#58a6ff",desc:"Low: local embed"},{key:"tier3_subgraph",label:"Tier 3 \u2014 LLM Subgraph",color:"#f5a623",desc:"LLM on 2-hop only"},{key:"tier_unknown",label:"Unknown",color:"#8b949e",desc:"Not detected"}],se=Object.values(c).reduce((l,v)=>l+v,0)||1,A=70,z=70,q=50,O=-Math.PI/2,Je=xe.map(l=>{let v=c[l.key]||0,T=v/se,oe=T*2*Math.PI,re=A+q*Math.cos(O),Ke=z+q*Math.sin(O);O+=oe;let Xe=A+q*Math.cos(O),Ye=z+q*Math.sin(O),Ze=T>.5?1:0;return{...l,count:v,pct:(T*100).toFixed(1),path:T>.001?`M ${A} ${z} L ${re.toFixed(2)} ${Ke.toFixed(2)} A ${q} ${q} 0 ${Ze} 1 ${Xe.toFixed(2)} ${Ye.toFixed(2)} Z`:""}}),ye=r(l=>String(l).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"),"_esc");return`<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PruvaGraph Analytics</title>
<style>
:root{
  --bg:var(--vscode-editor-background, #0d1117); --surface:var(--vscode-sideBar-background, #161b22);
  --bdr:var(--vscode-widget-border, #30363d); --txt:var(--vscode-foreground, #e6edf3);
  --mut:var(--vscode-descriptionForeground, #8b949e);
  --tel:#4ecdc4; --amb:#f5a623; --red:#ff4d4d; --grn:#3fb950; --blu:#58a6ff;
  --acc:var(--vscode-button-background, #7c6efa); --fnt:var(--vscode-font-family, system-ui, sans-serif);
  --mono:var(--vscode-editor-font-family, monospace);
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--txt);font-family:var(--fnt);font-size:13px;padding:0;overflow-x:hidden;}
.tab-bar{display:flex;background:var(--surface);border-bottom:1px solid var(--bdr);position:sticky;top:0;z-index:10;}
.tab{flex:1;text-align:center;padding:10px 6px;cursor:pointer;color:var(--mut);font-size:11px;font-weight:600;
  border-bottom:2px solid transparent;transition:all 0.2s;letter-spacing:0.3px;}
.tab:hover{color:var(--txt);}
.tab.active{color:var(--acc);border-bottom-color:var(--acc);}
.panel{display:none;padding:16px;}
.panel.active{display:block;}
.kpi-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:16px;}
.kpi{background:var(--surface);border:1px solid var(--bdr);border-radius:10px;padding:14px;transition:border-color 0.2s;}
.kpi:hover{border-color:var(--acc);}
.kpi-label{font-size:10px;color:var(--mut);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:6px;font-weight:600;}
.kpi-value{font-size:22px;font-weight:700;font-family:var(--mono);}
.kpi-value.g{color:var(--grn);} .kpi-value.t{color:var(--tel);} .kpi-value.b{color:var(--blu);}
.card{background:var(--surface);border:1px solid var(--bdr);border-radius:10px;padding:14px;margin-bottom:12px;}
.card-title{font-size:11px;font-weight:700;text-transform:uppercase;color:var(--mut);letter-spacing:0.6px;margin-bottom:12px;}
.bar-chart{display:flex;flex-direction:column;gap:6px;}
.bar-row{display:flex;align-items:center;gap:8px;}
.bar-label{font-size:11px;color:var(--mut);width:160px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.bar-track{flex:1;display:flex;flex-direction:column;gap:3px;}
.bar-seg{display:flex;align-items:center;gap:4px;height:10px;}
.bar-fill{height:10px;border-radius:4px;transition:width 0.4s ease;}
.bar-fill.g{background:var(--grn);} .bar-fill.r{background:var(--red);}
.bar-tok{font-size:10px;color:var(--mut);font-family:var(--mono);width:40px;flex-shrink:0;}
.bar-pct{font-size:11px;font-weight:700;color:var(--grn);width:36px;text-align:right;flex-shrink:0;font-family:var(--mono);}
.donut-wrap{display:flex;align-items:center;gap:20px;}
.legend{display:flex;flex-direction:column;gap:8px;}
.legend-row{display:flex;align-items:flex-start;gap:8px;font-size:12px;}
.dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;margin-top:2px;}
.timeline{display:flex;flex-direction:column;gap:12px;}
.timeline-task{border-left:2px solid var(--acc);padding-left:12px;}
.t-task-id{font-size:11px;font-weight:700;color:var(--acc);margin-bottom:6px;}
.t-track{display:flex;flex-direction:column;gap:6px;}
.t-item{background:var(--bg);border:1px solid var(--bdr);border-radius:6px;padding:8px 10px;}
.t-item.done{border-left:3px solid var(--grn);}
.t-item.pending{border-left:3px solid var(--amb);}
.t-item.failed{border-left:3px solid var(--red);}
.t-desc{font-size:12px;margin-bottom:3px;}
.t-meta{font-size:10px;color:var(--mut);font-family:var(--mono);}
.sbadge{display:inline-block;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700;margin-left:4px;}
.sbadge.done{background:rgba(63,185,80,0.15);color:var(--grn);}
.sbadge.pending{background:rgba(245,166,35,0.15);color:var(--amb);}
.sbadge.failed{background:rgba(255,77,77,0.15);color:var(--red);}
.sha{font-family:var(--mono);font-size:10px;background:#21262d;padding:1px 4px;border-radius:3px;}
.budget-wrap{display:flex;align-items:center;gap:24px;}
.budget-details{display:flex;flex-direction:column;gap:8px;flex:1;}
.b-row{display:flex;justify-content:space-between;font-size:12px;padding:4px 0;border-bottom:1px solid var(--bdr);}
.b-row:last-child{border:none;}
.b-row .val{font-weight:700;font-family:var(--mono);}
.bstatus{font-size:10px;font-weight:700;text-align:center;margin-top:4px;text-transform:uppercase;letter-spacing:0.5px;}
.bstatus.OK{color:var(--tel);} .bstatus.WARNING{color:var(--amb);} .bstatus.EXCEEDED{color:var(--red);} .bstatus.NO_BUDGET{color:var(--mut);}
.btn{display:inline-flex;align-items:center;gap:6px;background:var(--acc);color:#fff;
  border:none;border-radius:6px;padding:7px 14px;font-size:12px;font-weight:600;cursor:pointer;transition:opacity .15s;}
.btn:hover{opacity:.85;}
.btn.ghost{background:transparent;color:var(--mut);border:1px solid var(--bdr);}
.btn.ghost:hover{color:var(--txt);border-color:var(--txt);}
.btn-row{display:flex;gap:8px;margin-bottom:16px;}
.empty{color:var(--mut);font-size:12px;padding:20px;text-align:center;
  border:1px dashed var(--bdr);border-radius:8px;}
code{font-family:var(--mono);background:#21262d;padding:1px 5px;border-radius:3px;font-size:11px;}
table{width:100%;border-collapse:collapse;font-size:12px;}
th{text-align:left;padding:6px 8px;color:var(--mut);border-bottom:1px solid var(--bdr);font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:0.4px;}
td{padding:6px 8px;border-bottom:1px solid var(--bdr);}
tr:last-child td{border:none;}
</style></head><body>

<div class="tab-bar">
  <div class="tab ${this._initialTab==="dashboard"?"active":""}"  id="tab-dashboard" onclick="sw('dashboard')">&#128200; Cost Dashboard</div>
  <div class="tab ${this._initialTab==="tiermap"?"active":""}"   id="tab-tiermap"   onclick="sw('tiermap')">&#9685; Tier Map</div>
  <div class="tab ${this._initialTab==="timeline"?"active":""}"  id="tab-timeline"  onclick="sw('timeline')">&#9201; Agent Timeline</div>
  <div class="tab ${this._initialTab==="budget"?"active":""}"    id="tab-budget"    onclick="sw('budget')">&#128180; Budget Meter</div>
</div>

<!-- PANEL 1 \u2014 Cost Savings Dashboard -->
<div id="dashboard" class="panel ${this._initialTab==="dashboard"?"active":""}">
  <div class="btn-row">
    <button class="btn" onclick="post('refresh')">&#8635; Refresh</button>
    <button class="btn ghost" onclick="post('openViz')">&#128200; Open Graph</button>
  </div>
  <div class="kpi-grid">
    <div class="kpi"><div class="kpi-label">Avg Token Savings</div>
      <div class="kpi-value g">${i.toFixed(1)}%</div></div>
    <div class="kpi"><div class="kpi-label">Avg Tokens \u2014 Graph</div>
      <div class="kpi-value t">${Math.round(g).toLocaleString()}</div></div>
    <div class="kpi"><div class="kpi-label">Avg Tokens \u2014 Raw</div>
      <div class="kpi-value b">${Math.round(u).toLocaleString()}</div></div>
    <div class="kpi"><div class="kpi-label">Questions Benchmarked</div>
      <div class="kpi-value">${d}</div></div>
  </div>
  <div class="card">
    <div class="card-title">Top 8 Questions by Savings (&#9646; Graph &nbsp; &#9646; Raw)</div>
    ${b.length>0?`<div class="bar-chart">${b.map(l=>{let v=Math.max(l.tokens_raw,l.tokens_graph,1),T=(l.tokens_graph/v*100).toFixed(1),oe=(l.tokens_raw/v*100).toFixed(1),re=ye(l.question.length>42?l.question.slice(0,40)+"\u2026":l.question);return`<div class="bar-row" title="${ye(l.question)}">
        <div class="bar-label">${re}</div>
        <div class="bar-track">
          <div class="bar-seg"><div class="bar-fill g" style="width:${T}%"></div><span class="bar-tok">${l.tokens_graph}</span></div>
          <div class="bar-seg"><div class="bar-fill r" style="width:${oe}%"></div><span class="bar-tok">${l.tokens_raw}</span></div>
        </div>
        <div class="bar-pct">${l.savings_pct.toFixed(0)}%</div>
      </div>`}).join("")}</div>`:'<div class="empty">No benchmark data. Run: <code>pruvagraph benchmark-suite</code></div>'}
  </div>
  <div class="card" style="font-size:11px;color:var(--mut);">
    <strong style="color:var(--txt);">Truth Machine</strong> &mdash;
    Numbers from <code>benchmark_results.jsonl</code> (real run, 84 questions on this repo).
    Regenerate: <code>pruvagraph benchmark-suite</code>
  </div>
</div>

<!-- PANEL 2 \u2014 Cascade Tier Map -->
<div id="tiermap" class="panel ${this._initialTab==="tiermap"?"active":""}">
  <div class="btn-row"><button class="btn" onclick="post('refresh')">&#8635; Refresh</button></div>
  <div class="card">
    <div class="card-title">Query Tier Distribution</div>
    ${d>0?`<div class="donut-wrap">
      <svg width="140" height="140" viewBox="0 0 140 140">
        ${Je.filter(l=>l.path).map(l=>`<path d="${l.path}" fill="${l.color}" opacity="0.9"/>`).join("")}
        <circle cx="${A}" cy="${z}" r="34" fill="var(--bg)"/>
        <text x="${A}" y="${z-5}" text-anchor="middle" font-size="18"
              font-family="var(--mono)" fill="var(--txt)" font-weight="700">${se}</text>
        <text x="${A}" y="${z+14}" text-anchor="middle" font-size="9"
              font-family="var(--fnt)" fill="var(--mut)">queries</text>
      </svg>
      <div class="legend">${xe.filter(l=>c[l.key]>0).map(l=>`
        <div class="legend-row">
          <div class="dot" style="background:${l.color}"></div>
          <div>
            <div>${l.label} <strong style="font-family:var(--mono)">${c[l.key]}</strong> (${(c[l.key]/se*100).toFixed(1)}%)</div>
            <div style="font-size:11px;color:var(--mut);">${l.desc}</div>
          </div>
        </div>`).join("")}</div>
    </div>`:'<div class="empty">No benchmark data. Run benchmark first.</div>'}
  </div>
  <div class="card">
    <div class="card-title">Tier Cost Reference</div>
    <table>
      <tr><th>Tier</th><th>Cost/Query</th><th>Mechanism</th></tr>
      <tr><td style="color:#3fb950;">0 \u2014 Cache</td><td>$0.000</td><td style="color:var(--mut);">Exact query cache hit</td></tr>
      <tr><td style="color:#4ecdc4;">1 \u2014 Deterministic</td><td>$0.000</td><td style="color:var(--mut);">Graph traversal, no LLM</td></tr>
      <tr><td style="color:#58a6ff;">2 \u2014 Embedding</td><td>~$0.00001</td><td style="color:var(--mut);">Local BAAI embed, no API</td></tr>
      <tr><td style="color:#f5a623;">3 \u2014 LLM Subgraph</td><td>~$0.0001</td><td style="color:var(--mut);">LLM on 2-hop graph (~450 tokens avg)</td></tr>
    </table>
  </div>
</div>

<!-- PANEL 3 \u2014 Agent Run Timeline -->
<div id="timeline" class="panel ${this._initialTab==="timeline"?"active":""}">
  <div class="btn-row"><button class="btn" onclick="post('refresh')">&#8635; Refresh</button></div>
  <div class="card">
    <div class="card-title">TaskWeaver \u2014 Agent Checkpoints</div>
    ${fe.length>0?`<div class="timeline">${fe.map(l=>`
      <div class="timeline-task">
        <div class="t-task-id">&#128204; Task: ${l}</div>
        <div class="t-track">${P[l].map((v,T)=>`
          <div class="t-item ${v.status}">
            <div class="t-desc">${T+1}. ${v.description}
              &nbsp;<span class="sbadge ${v.status}">${v.status}</span></div>
            <div class="t-meta">
              ${v.git_sha?`<span class="sha">${v.git_sha.slice(0,8)}</span>&nbsp;`:""}
              ${(v.created_at||"").replace("T"," ").replace("Z","")}</div>
          </div>`).join("")}
        </div>
      </div>`).join("")}</div>`:'<div class="empty">No checkpoints yet.<br>Use the MCP tool <code>create_checkpoint</code> or CLI:<br><code>pruvagraph checkpoint --task my-task --description "..."</code></div>'}
  </div>
</div>

<!-- PANEL 4 \u2014 Token Budget Meter -->
<div id="budget" class="panel ${this._initialTab==="budget"?"active":""}">
  <div class="btn-row">
    <button class="btn" onclick="post('setBudget')">&#43; Set Budget</button>
    <button class="btn ghost" onclick="post('refresh')">&#8635; Refresh</button>
  </div>
  <div class="card">
    <div class="card-title">Session Token Budget</div>
    <div class="budget-wrap">
      <div>
        <svg width="120" height="120" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="54" fill="none" stroke="#21262d" stroke-width="12"/>
          <circle cx="60" cy="60" r="54" fill="none" stroke="${k}" stroke-width="12"
            stroke-dasharray="${h} 339.29" stroke-linecap="round"
            transform="rotate(-90 60 60)" style="transition:stroke-dasharray .5s;"/>
          <text x="60" y="56" text-anchor="middle" font-family="var(--mono)"
            font-size="18" font-weight="700" fill="${k}">${m.toFixed(0)}%</text>
          <text x="60" y="72" text-anchor="middle" font-family="var(--fnt)"
            font-size="9" fill="var(--mut)">used</text>
        </svg>
        <div class="bstatus ${t.status}">${t.status}</div>
      </div>
      <div class="budget-details">
        ${t.session_set?`
        <div class="b-row"><span>Budget Cap</span><span class="val">${(t.cap||0).toLocaleString()} tokens</span></div>
        <div class="b-row"><span>Spent</span><span class="val">${(t.spent||0).toLocaleString()} (${m.toFixed(1)}%)</span></div>
        <div class="b-row"><span>Remaining</span><span class="val" style="color:${k}">${(t.remaining||0).toLocaleString()} tokens</span></div>
        <div class="b-row"><span>Status</span><span class="val" style="color:${k}">${t.status}</span></div>
        `:`<div style="color:var(--mut);font-size:12px;padding:8px 0;">No budget set for this session.<br><br>
        Click <strong>+ Set Budget</strong> to configure a token cap.<br>
        Budget tracks automatically via <code>_dispatch()</code> on every MCP tool call.</div>`}
      </div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">How Budget Tracking Works</div>
    <div style="font-size:12px;color:var(--mut);line-height:1.8;">
      Every MCP tool call flows through <code>_dispatch()</code>, which estimates tokens
      as <code>len(result)&nbsp;//&nbsp;4</code> and records spend automatically &mdash; zero agent effort.<br>
      Thresholds:&nbsp;
      <span style="color:var(--tel);">OK</span> (&lt;80%)&nbsp;
      <span style="color:var(--amb);">WARNING</span> (80&ndash;99%)&nbsp;
      <span style="color:var(--red);">EXCEEDED</span> (&ge;100%)
    </div>
  </div>
</div>

<script>
const vscode = acquireVsCodeApi();
function post(cmd) { vscode.postMessage({ command: cmd }); }
function sw(name) {
  ['dashboard','tiermap','timeline','budget'].forEach((id, i) => {
    document.getElementById(id).classList.toggle('active', id === name);
    document.querySelectorAll('.tab')[i].classList.toggle('active', id === name);
  });
}
</script>
</body></html>`}dispose(){w.currentPanel=void 0,this._panel.dispose(),this._disposables.forEach(e=>e.dispose()),this._disposables=[]}};r(w,"PruvaGraphDashboard"),G(w,"currentPanel"),G(w,"viewType","pruvagraphDashboard");var me=w;Ge.exports={PruvaGraphDashboard:me,_loadBenchmarkData:Oe}});var Qe=$((ha,He)=>{"use strict";var ve=require("vscode"),R;function Nt(a){R=a,je()&&Ue("pruvagraph.telemetry.activations")}r(Nt,"initTelemetry");function Ft(a){je()&&Ue(`pruvagraph.telemetry.cmd.${a}`)}r(Ft,"trackCommand");function Ot(){if(!R)return{};let a={},e=R.globalState.keys().filter(t=>t.startsWith("pruvagraph.telemetry."));for(let t of e)a[t]=R.globalState.get(t,0);return a}r(Ot,"getTelemetrySummary");function je(){return typeof ve.env.isTelemetryEnabled=="boolean"?ve.env.isTelemetryEnabled:ve.workspace.getConfiguration("telemetry").get("enableTelemetry",!0)}r(je,"_isEnabled");function Ue(a){if(!R)return;let e=R.globalState.get(a,0);R.globalState.update(a,e+1)}r(Ue,"_increment");He.exports={initTelemetry:Nt,trackCommand:Ft,getTelemetrySummary:Ot}});var D=require("vscode"),{setOutputChannel:Gt,log:H}=I(),{initCliRunner:Wt,spawnCLI:jt,sendStatus:Ut,sendSavingsReceipt:Ht}=W(),{initDriftGuard:Ve}=$e(),{PruvaGraphViewProvider:Qt,getPanel:Vt}=Ne(),{PruvaGraphDashboard:ae}=We(),{initTelemetry:Jt,trackCommand:Kt}=Qe(),f=Z();function Xt(a){let e=D.window.createOutputChannel("PruvaGraph");Gt(e);let t=D.window.createStatusBarItem(D.StatusBarAlignment.Right,100);t.command="pruvagraph.costReport",t.text="$(graph) PruvaGraph",t.tooltip="Open PruvaGraph Cost Report",t.show(),a.subscriptions.push(t),Wt({statusBarItem:t,getPanel:Vt});let n=new Qt(a.extensionUri);a.subscriptions.push(D.window.registerWebviewViewProvider("pruvagraphPanel",n)),[["pruvagraph.build",()=>f.runBuild(n)],["pruvagraph.buildFast",()=>f.runBuildFast(n)],["pruvagraph.query",()=>f.runQuery(n)],["pruvagraph.costReport",()=>f.runCostReport(n)],["pruvagraph.installMCP",()=>f.runInstallMCP(n)],["pruvagraph.openViz",()=>f.openVisualizer()],["pruvagraph.clearCache",()=>f.clearCache(n)],["pruvagraph.watchToggle",()=>f.toggleWatch(n)],["pruvagraph.findCallers",()=>f.findCallers(n)],["pruvagraph.getDeps",()=>f.getDependencies(n)],["pruvagraph.installPkg",()=>f.runInstallPkg(n)],["pruvagraph.dryRun",()=>f.runDryRun(n)],["pruvagraph.showDiff",()=>f.showDiff(n)],["pruvagraph.analyzeImpact",()=>f.analyzeImpact(n)],["pruvagraph.buildMonorepo",()=>f.buildMonorepo(n)],["pruvagraph.showDashboard",()=>ae.createOrShow(a)],["pruvagraph.showTierMap",()=>ae.createOrShow(a,"tiermap")],["pruvagraph.showTimeline",()=>ae.createOrShow(a,"timeline")],["pruvagraph.showBudget",()=>ae.createOrShow(a,"budget")]].forEach(([o,i])=>{a.subscriptions.push(D.commands.registerCommand(o,()=>(Kt(o),i())))}),Ve(a),Jt(a),a.subscriptions.push(D.workspace.onDidChangeConfiguration(o=>{if(!["pruvagraph.modules.driftguard.enabled","pruvagraph.modules.contextlens.enabled","pruvagraph.modules.ghostmemory.enabled","pruvagraph.modules.taskweaver.enabled","pruvagraph.modules.budgetgovernor.enabled","pruvagraph.modules.rulesforge.enabled"].some(h=>o.affectsConfiguration(h)))return;let{getWorkspaceRoot:g}=I(),u=g();if(!u)return;let d=f.getDisabledModules(),c=d.length>0?d.join(","):"(none)";H(`[settings-gating] Module toggle changed \u2014 re-writing MCP configs. Disabled: ${c}`);let b=["install"];d.length>0&&b.push("--disable-modules",d.join(","));let m=jt("pruvagraph",b,u);m.on("exit",h=>{h===0?(H("[settings-gating] MCP config files updated \u2713 \u2014 restart MCP server to apply."),D.window.showInformationMessage(`PruvaGraph: MCP config updated (disabled: ${c}). Restart MCP server to apply.`)):H(`[settings-gating] pruvagraph install exited ${h} \u2014 MCP config may be stale.`)}),m.on("error",h=>{H(`[settings-gating] Could not update MCP config: ${h.message}`)})})),H("PRUVALEX PruvaGraph activated \u2713")}r(Xt,"activate");function Yt(){}r(Yt,"deactivate");module.exports={activate:Xt,deactivate:Yt,initDriftGuard:Ve,sendStatus:Ut,sendSavingsReceipt:Ht};
