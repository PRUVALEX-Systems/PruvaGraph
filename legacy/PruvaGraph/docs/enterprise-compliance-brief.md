# PRUVALEX Enterprise
## AI Coding Compliance Brief for EU-Regulated Organizations

**Version:** 1.0  
**Publisher:** PRUVALEX GmbH, Frankfurt am Main  
**Audience:** CTO, CISO, Compliance Officers, Engineering Leadership  
**Classification:** Public — Shareable with Procurement and Legal Teams

---

## Executive Summary

PRUVALEX is a VS Code extension that provides AI-assisted coding capabilities with a built-in audit trail, cryptographic accountability, and air-gap deployment support — designed specifically for organizations operating under EU regulatory frameworks including the EU AI Act, GDPR, and sector-specific requirements in banking (MaRisk, BAIT) and healthcare (MDR, GDPR).

Unlike general-purpose AI coding tools that operate as opaque cloud services, PRUVALEX is:

- **Local-first:** All developer context, code analysis, and memory storage occurs on the developer's machine. No source code leaves the organization's perimeter without explicit configuration.
- **Auditable:** Every AI tool call is logged to a local, tamper-evident ledger with token counts, latency, and cryptographic timestamps.
- **Air-gap capable:** Enterprise deployments can operate with zero external network calls, using locally hosted LLM inference.

---

## EU AI Act Alignment

The EU AI Act (Regulation 2024/1689) applies to AI systems that are placed on the market or put into service in the EU. AI coding tools used in software development for regulated industries may fall under Article 6 high-risk classification depending on their application.

PRUVALEX's architecture addresses the key requirements applicable to AI-assisted development tooling:

### Article 9 — Risk Management System

**Requirement:** High-risk AI systems shall implement a risk management system covering identification, estimation, and evaluation of risks.

**PRUVALEX Implementation:**

**DriftGuard** (Hallucination Detection) directly addresses the risk of AI-generated code referencing non-existent APIs, deprecated methods, or incorrect function signatures. It maintains a local index of installed SDK symbols and flags hallucinated references as VS Code diagnostics — red underlines, identical to TypeScript compiler errors. Every hallucination detected is logged with the symbol name, package, file URI, and timestamp.

The `driftguard_index` SQLite table provides a machine-readable record of which AI suggestions were flagged before the developer accepted them, supporting post-incident analysis if an AI-generated defect reaches production.

### Article 13 — Transparency and Provision of Information

**Requirement:** High-risk AI systems shall be designed and developed to ensure that their operation is sufficiently transparent.

**PRUVALEX Implementation:**

**ContextLens** provides real-time transparency of all AI tool invocations. The `token_ledger` table records every call to every AI model with:
- Module that triggered the call
- Tool name and server identifier
- Tokens consumed (input and output)
- Latency in milliseconds
- Unix timestamp

This data is available in the VS Code panel, exportable as CSV, and accessible via the `measure_token_usage()` and `trace_last_tool_calls()` MCP tools. Organizations can integrate this export into their existing audit log infrastructure (SIEM, Splunk, ELK).

### Article 12 — Record-Keeping

**Requirement:** High-risk AI systems shall be designed to enable logging of events throughout their lifetime.

**PRUVALEX Implementation:**

**TaskWeaver** creates cryptographically-linked checkpoints at developer-defined intervals. Each checkpoint records:
- Git commit SHA (tamper-evident via git's SHA-1 chain)
- List of files changed by AI assistance in this work unit
- Timestamp
- Correlation ID linking to `token_ledger` entries

The checkpoint history provides a complete audit trail from AI suggestion to committed code — fulfilling the Article 12 requirement for traceability of AI-assisted decisions.

---

## GDPR Compliance

PRUVALEX stores no personal data in external systems by default. Developer context (GhostMemory entries, code patterns, project notes) is stored exclusively in `pruvagraph.db` on the developer's machine.

**Data minimization (Article 5(1)(c)):** The `token_ledger` records token counts and latency but does not store the content of AI prompts or responses unless the organization explicitly enables extended logging for their compliance workflow.

**Right to erasure (Article 17):** All PRUVALEX data can be deleted by removing `pruvagraph.db` from VS Code's global storage directory. A CLI command (`pruvagraph.clearAllData`) is provided for IT-managed erasure workflows.

**Data residency:** For organizations with data residency requirements, the air-gap deployment mode (see below) ensures all data remains within the organization's infrastructure.

---

## Air-Gap Deployment

PRUVALEX Enterprise supports fully air-gapped deployments where the developer workstation has no internet access.

**Components replaceable with on-premises equivalents:**

| Component | Default (Cloud) | Air-Gap Replacement |
|---|---|---|
| LLM inference | Anthropic Claude API | Ollama + Llama 3.1 / Mistral (local) |
| Python package installation | PyPI | Pre-staged `.venv_pruvagraph` via IT provisioning |
| Extension updates | VS Code Marketplace | Private VSIX distribution via internal package registry |

**IT Provisioning Script:**  
PRUVALEX provides an IT provisioning PowerShell/Bash script that pre-stages the `.venv_pruvagraph` virtual environment on developer workstations before PRUVALEX is installed, eliminating the need for any network calls during activation.

**Offline LLM Configuration:**
```json
// settings.json (deployed via MDM/Group Policy)
{
  "pruvagraph.llm.provider": "ollama",
  "pruvagraph.llm.endpoint": "http://localhost:11434",
  "pruvagraph.llm.model": "llama3.1:8b",
  "pruvagraph.telemetry.enabled": false,
  "pruvagraph.updates.channel": "internal"
}
```

---

## Banking-Specific Compliance (MaRisk / BAIT)

For German banking organizations subject to BaFin's Minimum Requirements for Risk Management (MaRisk AT 7.2) and Banking Supervisory Requirements for IT (BAIT):

**IT security requirements (BAIT Section 4):** PRUVALEX's local-first architecture means source code never transits external networks. All AI calls can be routed through the organization's existing proxy infrastructure with standard HTTPS inspection.

**Change management (MaRisk AT 8):** TaskWeaver checkpoints create a developer-level change trail that complements organization-level change management systems. Checkpoint data can be exported and linked to JIRA/ServiceNow change tickets via the REST export API.

**Vendor risk:** PRUVALEX is a Frankfurt-based entity subject to German law. Enterprise contracts include data processing agreements (DPA) under GDPR Article 28.

---

## Security Architecture

**Data at rest:** `pruvagraph.db` is an unencrypted SQLite file. Organizations requiring encryption at rest should use filesystem-level encryption (BitLocker on Windows, FileVault on macOS) — the IT standard for developer workstations in regulated environments. This approach avoids dependency on SQLite's SEE (Encryption Extension) commercial license.

**No credential storage:** PRUVALEX does not store API keys in `pruvagraph.db`. API keys for cloud LLM providers are stored in VS Code's native SecretStorage (backed by OS keychain — Keychain on macOS, Windows Credential Manager, libsecret on Linux).

**Process isolation:** The PruvaGraph Python engine runs as a separate child process with no shell access and no environment variable passthrough from the extension host.

**Supply chain:** The bundled Python package is installed from a local wheel file — not from PyPI — during deployment. All dependencies are pinned to exact versions with hash verification.

---

## Procurement Information

| Item | Value |
|---|---|
| Publisher | PRUVALEX GmbH |
| Headquarters | Frankfurt am Main, Germany |
| Extension ID | `PRUVALEX.pruvagraph` |
| Licensing model | Per-seat annual subscription |
| Enterprise pricing | From €500/month per team (custom) |
| Contract terms | Annual, invoiced quarterly |
| DPA | Available on request |
| SLA | 99.5% uptime for licensing server; local extension has no uptime dependency |
| Support | Dedicated Slack channel + named account manager for Enterprise tier |

**To begin a proof-of-concept:** Contact enterprise@pruvalex.com with subject *"PRUVALEX Enterprise POC — [Organization Name]"*. POC period: 30 days, no cost, no commitment.

---

*Document revision: 1.0*  
*Next scheduled review: Quarterly*  
*Contact: enterprise@pruvalex.com*

