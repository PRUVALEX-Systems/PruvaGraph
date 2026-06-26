"""
Arch4 — Privacy Shield

Strips secrets and PII from file content BEFORE sending to any LLM API.
Every byte that leaves the machine must pass through this filter.

Why this matters:
  - Enterprise clients WILL NOT use tools that risk leaking secrets
  - One leaked API key = GDPR violation, security breach, trust destroyed
  - Privacy Shield = compliance checkbox for enterprise sales

What gets redacted:
  - API keys / tokens (OpenAI, Anthropic, Stripe, GitHub, AWS, etc.)
  - Passwords and secrets in config files
  - Private keys (RSA, EC, PEM)
  - Database connection strings (with credentials)
  - OAuth client secrets
  - JWT secrets / signing keys
  - Environment variable values that look like secrets
  - Email addresses (optional, for GDPR-sensitive deployments)
  - IP addresses in non-test contexts (optional)

Audit trail: every redaction is logged to privacy_audit.jsonl.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

# ── Redaction patterns ────────────────────────────────────────────────────────

@dataclass
class RedactionRule:
    name:        str
    pattern:     re.Pattern
    replacement: str
    severity:    str = "high"   # "high" | "medium" | "low"


_RULES: list[RedactionRule] = [

    # ── API Keys (provider-specific formats) ──────────────────────────────────
    RedactionRule("openai_key",
        re.compile(r'\b(sk-(?:proj-)?[a-zA-Z0-9]{20,})\b'),
        "[REDACTED:openai_key]"),

    RedactionRule("anthropic_key",
        re.compile(r'\b(sk-ant-[a-zA-Z0-9\-]{20,})\b'),
        "[REDACTED:anthropic_key]"),

    RedactionRule("github_pat",
        re.compile(r'\b(gh[pousr]_[a-zA-Z0-9]{36,})\b'),
        "[REDACTED:github_pat]"),

    RedactionRule("stripe_key",
        re.compile(r'\b(sk_(?:live|test)_[a-zA-Z0-9]{24,})\b'),
        "[REDACTED:stripe_key]"),

    RedactionRule("stripe_pub",
        re.compile(r'\b(pk_(?:live|test)_[a-zA-Z0-9]{24,})\b'),
        "[REDACTED:stripe_pubkey]"),

    RedactionRule(
        name="aws_secret_key",
        # New regex: matches AWS-style access keys, session tokens, and AWS secret values.
        pattern=re.compile(r'(?i)(?:aws(?:_secret_access_key|_access_key_id|_session_token)?)[=\s:]+[\'"]?((?:AKIA|AGPA|AIDA|AROA|ASCA)[A-Z0-9]{16}|(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])|aws_sec_[a-zA-Z0-9]+)[\'"]?'),
        replacement="[REDACTED:aws_key]"
    ),

    RedactionRule("google_api_key",
        re.compile(r'\b(AIza[0-9A-Za-z\-_]{35,})\b'),
        "[REDACTED:google_api_key]"),

    RedactionRule("sendgrid_key",
        re.compile(r'\b(SG\.[a-zA-Z0-9\-_]{22}\.[a-zA-Z0-9\-_]{43})\b'),
        "[REDACTED:sendgrid_key]"),

    RedactionRule("slack_token",
        re.compile(r'\b(xoxb-[A-Za-z0-9\-]{10,})\b'),
        "[REDACTED:slack_token]"),

    RedactionRule("twilio_token",
        re.compile(r'\b(SK[a-f0-9]{32})\b'),
        "[REDACTED:twilio_key]"),

    # ── Private keys (PEM format) ─────────────────────────────────────────────
    RedactionRule("pem_private_key",
        re.compile(
            r'(-----BEGIN (?:RSA |EC |DSA |OPENSSH |PRIVATE |CERTIFICATE )?(?:PRIVATE )?KEY-----[\s\S]*?-----END [^-]+-----)',
            re.DOTALL,
        ),
        "[REDACTED:private_key_block]",
        severity="high"),

    # ── Passwords and secrets in config ───────────────────────────────────────
    RedactionRule("password_assignment",
        re.compile(
            r'((?:password|passwd|secret|api[_\-]?key|auth[_\-]?token|access[_\-]?token|secret[_\-]?key)'
            r'\s*(?:=|:)\s*)(["\']?)([^"\'\s\n]{8,})\2',
            re.I,
        ),
        r'\1\2[REDACTED:secret_value]\2'),

    RedactionRule("env_secret",
        re.compile(
            r'(^|\n)((?:API[_\-]?KEY|SECRET|PASSWORD|AUTH[_\-]?TOKEN|ACCESS[_\-]?TOKEN|PRIVATE[_\-]?KEY|SIGNING[_\-]?KEY|JWT[_\-]?SECRET)'
            r'\s*=\s*["\']?)([^\n"\'\s]{8,})(["\']?)',
            re.I,
        ),
        r'\1\2[REDACTED:env_secret]\4'),

    # ── Database connection strings ────────────────────────────────────────────
    RedactionRule("db_connection_string",
        re.compile(
            r'((?:postgres|postgresql|mysql|mongodb|redis|mssql|sqlite|amqp|redis)'
            r'(?:\+\w+)?://)([^:]+):([^@]+)@',
            re.I,
        ),
        r'\1[REDACTED:db_user]:[REDACTED:db_pass]@'),

    # ── JWT tokens ────────────────────────────────────────────────────────────
    RedactionRule("jwt_token",
        re.compile(r'\b(eyJ[a-zA-Z0-9\-_]{20,}\.[a-zA-Z0-9\-_]{20,}\.[a-zA-Z0-9\-_]{20,})\b'),
        "[REDACTED:jwt_token]"),

    # ── Generic high-entropy tokens (heuristic) ───────────────────────────────
    RedactionRule("high_entropy_hex",
        re.compile(
            r'(?:token|secret|key|hash|credential)\s*[=:]\s*["\']?([0-9a-f]{32,64})["\']?',
            re.I,
        ),
        r'[KEY]=[REDACTED:hex_secret]',
        severity="medium"),

    RedactionRule("high_entropy_base64",
        re.compile(
            r'(?:token|secret|key|hash|credential|cert|certificate|apikey|api_key|auth)\s*[=:]\s*["\']?((?:[A-Za-z0-9+/]{4}){6,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{4})?)["\']?',
            re.I,
        ),
        r'[KEY]=[REDACTED:base64_secret]',
        severity="medium"),

]


# ── Main shield class ─────────────────────────────────────────────────────────

@dataclass
class RedactionResult:
    original_length: int
    redacted_length: int
    redaction_count: int
    rules_triggered: list[str]
    content:         str


class PrivacyShield:
    """
    Apply all redaction rules to content before sending to LLM.
    Logs each redaction to audit trail.
    """

    def __init__(
        self,
        audit_dir: Path | None = None,
        enabled: bool = True,
        redact_emails: bool = False,
        redact_ips: bool = False,
    ) -> None:
        self._enabled        = enabled
        self._redact_emails  = redact_emails
        self._redact_ips     = redact_ips
        self._audit_path     = (audit_dir / "privacy_audit.jsonl") if audit_dir else None

        # Optional extras
        self._extra_rules: list[RedactionRule] = []
        if redact_emails:
            self._extra_rules.append(RedactionRule(
                "email", re.compile(r'\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b'),
                "[REDACTED:email]", severity="medium",
            ))
        if redact_ips:
            self._extra_rules.append(RedactionRule(
                "ipv4", re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'),
                "[REDACTED:ip]", severity="low",
            ))

    def scrub(self, content: str, source_file: str = "") -> RedactionResult:
        """
        Apply all redaction rules to content.
        Returns RedactionResult with cleaned content and audit info.
        """
        if not self._enabled:
            return RedactionResult(
                original_length=len(content),
                redacted_length=len(content),
                redaction_count=0,
                rules_triggered=[],
                content=content,
            )

        original_len  = len(content)
        triggered     = []
        total_count   = 0
        scrubbed      = content

        all_rules = _RULES + self._extra_rules
        for rule in all_rules:
            new_content, n = rule.pattern.subn(rule.replacement, scrubbed)
            if n > 0:
                scrubbed = new_content
                total_count += n
                triggered.append(f"{rule.name}×{n}")

        result = RedactionResult(
            original_length=original_len,
            redacted_length=len(scrubbed),
            redaction_count=total_count,
            rules_triggered=triggered,
            content=scrubbed,
        )

        if total_count > 0 and self._audit_path:
            self._log_audit(source_file, result)

        return result

    def scrub_batch(
        self,
        file_contents: list[tuple[str, str]],
    ) -> list[tuple[str, str]]:
        """
        Scrub a batch of (path, content) tuples.
        Returns scrubbed batch with same structure.
        """
        result = []
        for path, content in file_contents:
            r = self.scrub(content, source_file=path)
            result.append((path, r.content))
        return result

    def _log_audit(self, source_file: str, result: RedactionResult) -> None:
        """Append redaction event to audit log."""
        if not self._audit_path:
            return
        try:
            self._audit_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "timestamp":       time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "file":            source_file,
                "redactions":      result.redaction_count,
                "rules_triggered": result.rules_triggered,
            }
            with self._audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

    def audit_summary(self) -> str:
        """Human-readable audit log summary."""
        if not self._audit_path or not self._audit_path.exists():
            return "No audit log found."
        try:
            lines   = self._audit_path.read_text(encoding="utf-8").splitlines()
            entries = [json.loads(l) for l in lines if l.strip()]
            total   = sum(e.get("redactions", 0) for e in entries)
            files   = len({e.get("file") for e in entries})
            return (
                f"Privacy Shield Audit: {len(entries)} events, "
                f"{total} total redactions across {files} files."
            )
        except Exception:
            return "Audit log unreadable."


# ── Convenience function ──────────────────────────────────────────────────────

def scrub_content(
    content: str,
    source_file: str = "",
    audit_dir: Path | None = None,
) -> str:
    """One-shot scrubbing. Returns cleaned content."""
    shield = PrivacyShield(audit_dir=audit_dir)
    return shield.scrub(content, source_file=source_file).content


def has_secrets(content: str) -> bool:
    """Quick check — does this content contain any detectable secrets?"""
    for rule in _RULES:
        if rule.pattern.search(content):
            return True
    return False
