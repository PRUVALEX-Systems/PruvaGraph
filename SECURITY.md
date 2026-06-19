# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| Latest stable | ✅ Security fixes |
| Previous minor | ✅ Critical fixes only |
| Older versions | ❌ |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Security vulnerabilities in PRUVALEX PruvaGraph should be reported privately so that a fix can be developed and released before public disclosure.

### How to Report

**Email:** security@pruvalex.com  
**Subject line:** `[SECURITY] PRUVALEX — [brief description]`  
**PGP Key:** Available upon request via security@pruvalex.com

### What to Include

A good security report includes:
- A description of the vulnerability and its potential impact.
- The PRUVALEX version affected.
- Step-by-step reproduction instructions.
- Any proof-of-concept code (if applicable).
- Your assessment of severity (Critical / High / Medium / Low).

### What Happens Next

1. **Acknowledgement:** We will acknowledge receipt within **48 hours** (business days).
2. **Initial assessment:** Within **5 business days**, we will confirm whether the report is a valid vulnerability and assign a severity level.
3. **Fix development:** We aim to release a patch within:
   - Critical: 7 days
   - High: 14 days
   - Medium: 30 days
   - Low: Next planned release
4. **Disclosure:** We will coordinate the public disclosure date with you. We follow a **90-day coordinated disclosure** policy. We will credit you in the release notes and CHANGELOG unless you prefer to remain anonymous.

### Scope

**In scope:**
- Arbitrary code execution via the extension host process.
- SQLite injection via the `IGraphStore` API.
- Unauthorized read/write of `pruvagraph.db` by external processes.
- PruvaGraphRunner spawning processes beyond its intended scope.
- Credential or API key exfiltration via the extension.
- Bypass of the forbidden-import architecture enforcement.
- VSIX supply chain compromise.

**Out of scope:**
- Vulnerabilities in third-party dependencies (report directly to those maintainers; we will apply patches promptly when they release fixes).
- Theoretical attacks requiring physical access to the developer's machine.
- VS Code platform vulnerabilities (report to Microsoft's Security Response Center).
- Social engineering attacks against users.

### Safe Harbor

PRUVALEX will not pursue legal action against security researchers who:
- Report vulnerabilities privately via the process above.
- Do not access, modify, or delete data beyond what is necessary to demonstrate the vulnerability.
- Do not disclose the vulnerability publicly before the agreed disclosure date.
- Do not exploit the vulnerability for any purpose other than demonstrating its existence.

We appreciate responsible security research and will thank all valid reporters publicly (with permission).

---

## Security Architecture Notes

For enterprise security teams evaluating PRUVALEX:

**Data storage:** All developer data is stored in `pruvagraph.db` (SQLite) in VS Code's `globalStoragePath`. This directory is user-writable only on the developer's local machine. No data is transmitted externally by the core extension.

**Network calls:** The extension makes network calls only when:
- An external LLM provider is configured (e.g., Anthropic Claude API, OpenAI).
- The user's VS Code telemetry settings are enabled (PRUVALEX respects `vscode.env.isTelemetryEnabled`).
- Explicit update checks are performed.

All network calls can be disabled for air-gapped deployments via `pruvagraph.llm.provider: "ollama"` and `pruvagraph.telemetry.enabled: false`.

**Process spawning:** PruvaGraphRunner spawns exactly one child process (`python -m pruvagraph.cli`). This process has no shell access, runs as the current user, and its stdout/stderr are piped to a VS Code Output Channel (never to disk or network).

**Secret storage:** API keys are stored in VS Code's native `SecretStorage` API (backed by OS keychain). They are never written to `pruvagraph.db` or any other file.
