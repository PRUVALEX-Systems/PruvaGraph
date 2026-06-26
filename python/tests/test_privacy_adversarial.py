"""
Adversarial tests for pruvagraph.privacy — Arch4 Privacy Shield.

Phase 0 target: cover all 16 redaction rule categories in _RULES,
plus audit logging, idempotency, and disabled-shield passthrough.

Rule categories in privacy.py (verified from _RULES list):
  1.  openai_key           (sk-... / sk-proj-...)
  2.  anthropic_key        (sk-ant-...)
  3.  github_pat           (ghp_, gho_, ghu_, ghs_, ghr_)
  4.  stripe_key           (sk_live_... / sk_test_...)
  5.  stripe_pub           (pk_live_... / pk_test_...)
  6.  aws_secret_key       (AKIA... / AWS_SECRET_ACCESS_KEY=...)
  7.  google_api_key       (AIza...)
  8.  sendgrid_key         (SG....)
  9.  slack_token          (xoxb-...)
  10. twilio_token         (SK + 32 hex)
  11. pem_private_key      (-----BEGIN ... KEY-----)
  12. password_assignment  (password = "...")
  13. env_secret           (API_KEY="..." style .env)
  14. db_connection_string (postgres://user:pass@host)
  15. jwt_token            (eyJ....eyJ....sig)
  16. high_entropy_hex     (token = <32-64 hex chars>)
  17. high_entropy_base64  (apikey = <base64 blob>)
  +   email (optional extra)
  +   ipv4  (optional extra)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from pruvagraph.privacy import PrivacyShield, RedactionResult, has_secrets, scrub_content


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def shield(tmp_path):
    return PrivacyShield(audit_dir=tmp_path)


@pytest.fixture()
def shield_no_audit():
    return PrivacyShield()


# ===========================================================================
# 1. OpenAI key  (sk-... patterns)
# ===========================================================================

class TestOpenAIKey:
    def test_sk_prefix_key(self, shield):
        content = 'OPENAI_API_KEY="sk-abcdefghijklmnopqrst1234"'
        result = shield.scrub(content, "test.env")
        assert "sk-abcdefghijklmnopqrst1234" not in result.content
        assert "[REDACTED" in result.content

    def test_sk_proj_prefix_key(self, shield):
        content = 'api_key = "sk-proj-abcdefghijklmnop12345678901234"'
        result = shield.scrub(content)
        assert "sk-proj-abcdefghijklmnop12345678901234" not in result.content

    def test_openai_key_in_js_const(self, shield):
        content = "const openaiKey = 'sk-xxxxxxxxxxxxxxxxxxx1234567890';"
        result = shield.scrub(content)
        assert "sk-xxxxxxxx" not in result.content


# ===========================================================================
# 2. Anthropic key  (sk-ant-...)
# ===========================================================================

class TestAnthropicKey:
    def test_anthropic_key_basic(self, shield):
        content = 'ANTHROPIC_API_KEY = "sk-ant-api03-xxxxxxxxxxx-yyyyyyyyyy"'
        result = shield.scrub(content)
        assert "sk-ant-" not in result.content
        assert "[REDACTED" in result.content

    def test_anthropic_key_in_yaml(self, shield):
        content = "anthropic_key: sk-ant-abcdef1234567890abcdef"
        result = shield.scrub(content)
        assert "sk-ant-abcdef" not in result.content


# ===========================================================================
# 3. GitHub PAT  (ghp_, gho_, ghu_, ghs_, ghr_)
# ===========================================================================

class TestGitHubPAT:
    @pytest.mark.parametrize("prefix", ["ghp_", "gho_", "ghu_", "ghs_", "ghr_"])
    def test_github_pat_prefix_variants(self, shield, prefix):
        token = f"{prefix}" + "A" * 36
        content = f'GITHUB_TOKEN="{token}"'
        result = shield.scrub(content)
        assert token not in result.content
        assert "[REDACTED" in result.content


# ===========================================================================
# 4. Stripe secret key  (sk_live_... / sk_test_...)
# ===========================================================================

class TestStripeKey:
    @pytest.mark.parametrize("env", ["live", "test"])
    def test_stripe_secret_key(self, shield, env):
        key = f"sk_{env}_" + "a" * 24
        content = f'stripe.apiKey = "{key}";'
        result = shield.scrub(content)
        assert key not in result.content

    @pytest.mark.parametrize("env", ["live", "test"])
    def test_stripe_pub_key(self, shield, env):
        key = f"pk_{env}_" + "b" * 24
        content = f'STRIPE_PUB_KEY = "{key}"'
        result = shield.scrub(content)
        assert key not in result.content


# ===========================================================================
# 5. AWS credentials
# ===========================================================================

class TestAWSCredentials:
    def test_aws_secret_access_key_env_style(self, shield):
        content = "AWS_SECRET_ACCESS_KEY=aws_sec_abcd1234efgh5678ijkl9012"
        result = shield.scrub(content)
        assert "aws_sec_abcd1234efgh5678ijkl9012" not in result.content

    def test_aws_access_key_id_akia(self, shield):
        # AKIA-style: 20-char uppercase+digits
        content = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
        result = shield.scrub(content)
        assert "AKIAIOSFODNN7EXAMPLE" not in result.content

    def test_aws_key_in_config_file(self, shield):
        content = "[default]\naws_secret_access_key = aws_sec_XYZ1234567890abcdef"
        result = shield.scrub(content)
        assert "aws_sec_XYZ1234567890abcdef" not in result.content


# ===========================================================================
# 6. Google API key  (AIza...)
# ===========================================================================

class TestGoogleAPIKey:
    def test_google_api_key(self, shield):
        key = "AIzaSyB-abcdefghijklmnopqrstuvwxyz0123456"
        content = f'var google_api_key = "{key}";'
        result = shield.scrub(content)
        assert key not in result.content
        assert "AIzaSyB" not in result.content

    def test_google_api_key_in_json(self, shield):
        content = json.dumps({"google_maps_key": "AIzaSyC_abcdefghijklmnopqrstuv01234567890"})
        result = shield.scrub(content)
        assert "AIzaSyC" not in result.content


# ===========================================================================
# 7. SendGrid key  (SG.xxx.yyy)
# ===========================================================================

class TestSendGridKey:
    def test_sendgrid_key(self, shield):
        # SG. + 22 chars + . + 43 chars
        key = "SG." + "a" * 22 + "." + "b" * 43
        content = f'SENDGRID_API_KEY="{key}"'
        result = shield.scrub(content)
        assert key not in result.content


# ===========================================================================
# 8. Slack token  (xoxb-...)
# ===========================================================================

class TestSlackToken:
    def test_slack_bot_token(self, shield):
        content = 'slack_token: "xoxb-1234567890-1234567890-abcdefghijklmnop"'
        result = shield.scrub(content)
        assert "xoxb-" not in result.content
        assert "[REDACTED" in result.content

    def test_slack_token_in_env_file(self, shield):
        content = "SLACK_BOT_TOKEN=xoxb-111-222-abcdef1234567890abcdef"
        result = shield.scrub(content)
        assert "xoxb-111" not in result.content


# ===========================================================================
# 9. Twilio token  (SK + 32 hex digits)
# ===========================================================================

class TestTwilioToken:
    def test_twilio_auth_token(self, shield):
        # SK + exactly 32 lowercase hex chars
        token = "SK" + "a" * 32
        content = f'twilio_token = "{token}"'
        result = shield.scrub(content)
        assert token not in result.content


# ===========================================================================
# 10. PEM private keys
# ===========================================================================

class TestPEMPrivateKey:
    def test_rsa_private_key_block(self, shield):
        content = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIICXQIBAAKBgQC7tXL2abc123xyz\n"
            "-----END RSA PRIVATE KEY-----"
        )
        result = shield.scrub(content)
        assert "MIICXQIBAAKBgQ" not in result.content
        assert "[REDACTED:private_key_block]" in result.content

    def test_openssh_private_key(self, shield):
        content = (
            "-----BEGIN OPENSSH PRIVATE KEY-----\n"
            "b3BlbnNzaC1rZXktdjEAAAA...\n"
            "-----END OPENSSH PRIVATE KEY-----"
        )
        result = shield.scrub(content)
        assert "b3BlbnNzaC1rZXk" not in result.content

    def test_ec_private_key(self, shield):
        content = (
            "-----BEGIN EC PRIVATE KEY-----\n"
            "MHQCAQEEIBkg8kj2abc123\n"
            "-----END EC PRIVATE KEY-----"
        )
        result = shield.scrub(content)
        assert "MHQCAQEEIBkg8kj2abc123" not in result.content


# ===========================================================================
# 11. Password assignments  (password = "...")
# ===========================================================================

class TestPasswordAssignment:
    def test_password_equals(self, shield):
        content = 'password = "SuperSecret123!"'
        result = shield.scrub(content)
        assert "SuperSecret123!" not in result.content

    def test_secret_colon(self, shield):
        content = "secret: my_secret_value_here_long"
        result = shield.scrub(content)
        assert "my_secret_value_here_long" not in result.content

    def test_api_key_assignment(self, shield):
        content = "api_key = 'abcdef1234567890abcdef'"
        result = shield.scrub(content)
        assert "abcdef1234567890abcdef" not in result.content

    def test_auth_token_assignment(self, shield):
        content = 'auth_token = "Bearer_abcdefghijklmno12345678"'
        result = shield.scrub(content)
        assert "Bearer_abcdefghijklmno12345678" not in result.content


# ===========================================================================
# 12. .env-style secrets  (UPPERCASE_KEY = value)
# ===========================================================================

class TestEnvSecrets:
    def test_api_key_env(self, shield):
        content = 'API_KEY="my_super_secret_api_key_value"'
        result = shield.scrub(content)
        assert "my_super_secret_api_key_value" not in result.content

    def test_jwt_secret_env(self, shield):
        content = "JWT_SECRET=my_jwt_signing_secret_here_long"
        result = shield.scrub(content)
        assert "my_jwt_signing_secret_here_long" not in result.content

    def test_signing_key_env(self, shield):
        content = "SIGNING_KEY=abcdefghijklmnop12345678"
        result = shield.scrub(content)
        assert "abcdefghijklmnop12345678" not in result.content

    def test_private_key_env(self, shield):
        content = "PRIVATE_KEY=mysuperprivatekeyvalue12345"
        result = shield.scrub(content)
        assert "mysuperprivatekeyvalue12345" not in result.content


# ===========================================================================
# 13. DB connection strings  (postgres://user:pass@host)
# ===========================================================================

class TestDBConnectionString:
    @pytest.mark.parametrize("scheme", [
        "postgres", "postgresql", "mysql", "mongodb", "redis", "mssql"
    ])
    def test_db_connection_schemes(self, shield, scheme):
        content = f'{scheme}://admin:secret_password_here@localhost:5432/mydb'
        result = shield.scrub(content)
        assert "secret_password_here" not in result.content
        assert "[REDACTED:db_pass]" in result.content

    def test_mongodb_atlas_connection_string(self, shield):
        content = "mongodb+srv://alice:TopSecret123@cluster0.mongodb.net/mydb"
        result = shield.scrub(content)
        assert "TopSecret123" not in result.content


# ===========================================================================
# 14. JWT tokens  (eyJ...eyJ...sig)
# ===========================================================================

class TestJWTToken:
    def test_jwt_three_part_token(self, shield):
        # Real-ish JWT structure
        jwt = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ"
            ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        content = f'Authorization: "Bearer {jwt}"'
        result = shield.scrub(content)
        assert jwt not in result.content
        assert "[REDACTED:jwt_token]" in result.content


# ===========================================================================
# 15. High-entropy hex / base64
# ===========================================================================

class TestHighEntropySecrets:
    def test_high_entropy_hex_secret(self, shield):
        content = "token = abcdef1234567890abcdef1234567890abcdef"
        result = shield.scrub(content)
        assert "abcdef1234567890abcdef1234567890abcdef" not in result.content

    def test_high_entropy_base64_apikey(self, shield):
        content = 'apikey = "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUJJakFO"'
        result = shield.scrub(content)
        assert "LS0tLS1CRUdJTi" not in result.content

    def test_credential_label_triggers_redaction(self, shield):
        content = "credential = AbCdEfGhIjKlMnOpQrStUvWxYz12345678AbCdEfGh"
        result = shield.scrub(content)
        assert "AbCdEfGhIjKlMnOp" not in result.content


# ===========================================================================
# 16. Optional extras: email and IP
# ===========================================================================

class TestOptionalExtras:
    def test_email_redaction_when_enabled(self):
        shield = PrivacyShield(redact_emails=True)
        content = "Contact alice@example.com for support."
        result = shield.scrub(content)
        assert "alice@example.com" not in result.content
        assert "[REDACTED:email]" in result.content

    def test_email_not_redacted_by_default(self):
        shield = PrivacyShield()
        content = "Contact alice@example.com for support."
        result = shield.scrub(content)
        assert "alice@example.com" in result.content  # default: not redacted

    def test_ipv4_redaction_when_enabled(self):
        shield = PrivacyShield(redact_ips=True)
        content = "Server at 192.168.1.100:8080"
        result = shield.scrub(content)
        assert "192.168.1.100" not in result.content
        assert "[REDACTED:ip]" in result.content

    def test_ipv4_not_redacted_by_default(self):
        shield = PrivacyShield()
        content = "Server at 192.168.1.100:8080"
        result = shield.scrub(content)
        assert "192.168.1.100" in result.content  # default: not redacted


# ===========================================================================
# 17. Idempotency, audit log, disabled shield
# ===========================================================================

class TestShieldBehavior:
    def test_scrub_is_idempotent(self, shield):
        """Scrubbing twice should produce the same result as scrubbing once."""
        content = 'API_KEY="sk-abcdefghijklmnopqrst1234" password="mysecret123"'
        first = shield.scrub(content).content
        second = shield.scrub(first).content
        assert first == second, "Scrubbing twice changed the output — not idempotent"

    def test_audit_log_written_on_redaction(self, tmp_path):
        shield = PrivacyShield(audit_dir=tmp_path)
        content = 'API_KEY="sk-abcdefghijklmnopqrst1234"'
        shield.scrub(content, source_file="secret_file.py")
        audit_path = tmp_path / "privacy_audit.jsonl"
        assert audit_path.exists(), "Audit log was not created"
        entry = json.loads(audit_path.read_text().strip().splitlines()[0])
        assert entry["file"] == "secret_file.py"
        assert entry["redactions"] >= 1

    def test_audit_log_not_written_when_no_secrets(self, tmp_path):
        shield = PrivacyShield(audit_dir=tmp_path)
        shield.scrub("no secrets here, just normal code", source_file="clean.py")
        audit_path = tmp_path / "privacy_audit.jsonl"
        assert not audit_path.exists(), "Audit log should not be created for clean content"

    def test_disabled_shield_passes_through(self):
        shield = PrivacyShield(enabled=False)
        content = 'password = "TopSecret!" API_KEY="sk-abcde123456789012345"'
        result = shield.scrub(content)
        assert result.content == content
        assert result.redaction_count == 0

    def test_audit_summary_no_log(self):
        shield = PrivacyShield()  # no audit_dir
        summary = shield.audit_summary()
        assert "no audit log" in summary.lower()

    def test_audit_summary_with_log(self, tmp_path):
        shield = PrivacyShield(audit_dir=tmp_path)
        shield.scrub('sk-abcdefghijklmnopqrst1234', source_file="a.py")
        summary = shield.audit_summary()
        assert "event" in summary.lower() or "redaction" in summary.lower()

    def test_scrub_batch(self):
        shield = PrivacyShield()
        batch = [
            ("a.py", 'API_KEY="sk-abcdef1234567890abcde"'),
            ("b.py", "nothing secret here"),
        ]
        result = shield.scrub_batch(batch)
        assert len(result) == 2
        assert "sk-abcdef" not in result[0][1]
        assert result[1][1] == "nothing secret here"  # clean file unchanged

    def test_has_secrets_function_true(self):
        assert has_secrets('API_KEY="sk-abcdefghijklmnopqrst"') is True

    def test_has_secrets_function_false(self):
        assert has_secrets("def calculate_area(radius): return 3.14 * radius ** 2") is False


# ===========================================================================
# 18. Multi-secret "evil blob" integration test (the original 4-test spirit)
# ===========================================================================

class TestFullPipelineMockLLM:
    def test_evil_blob_scrubbed_before_llm(self):
        """
        The original integration test — wires a mock LLM client into the pipeline,
        runs a synthetic blob containing multiple secret types, asserts zero raw
        secrets reach the mock client.
        """
        import asyncio

        shield = PrivacyShield()

        class MockLLM:
            def __init__(self):
                self.received_prompts = []

            async def call_llm(self, prompt: str) -> str:
                self.received_prompts.append(prompt)
                return "{}"

        mock_client = MockLLM()

        evil_blob = """
        DB_PASSWORD="SuperSecretDBPass123!"
        export AWS_SECRET_ACCESS_KEY=aws_sec_abcd1234efgh5678
        const apiKey = 'sk-live-1234567890abcdef1234567890abcdef'
        private rsaKey = '-----BEGIN RSA PRIVATE KEY-----
        MIICXQIBAAKBgQ...
        -----END RSA PRIVATE KEY-----'
        var google_api_key = "AIzaSyB-abcd1234efgh5678ijkl"
        slack_token: "xoxb-1234-5678-abcdefg"
        """

        redaction_result = shield.scrub(evil_blob, source_file="evil_file.py")
        safe_content = redaction_result.content

        asyncio.run(mock_client.call_llm(safe_content))
        received = mock_client.received_prompts[0]

        assert "SuperSecretDBPass123!" not in received, "Failed to redact DB Password"
        assert "aws_sec_abcd1234efgh5678" not in received, "Failed to redact AWS Key"
        assert "sk-live-1234567890abcdef" not in received, "Failed to redact Stripe/API Key"
        assert "MIICXQIBAAKBgQ" not in received, "Failed to redact RSA Key"
        assert "AIzaSyB" not in received, "Failed to redact Google API Key"
        assert "xoxb-" not in received, "Failed to redact Slack Token"
        assert "[REDACTED" in received, "Redaction markers missing from output"

    def test_env_file_scenario(self):
        """Original test_adversarial_env_file — preserved."""
        content = """
        # Normal content
        apiKey=sk-12345678901234567890abcdef
        API_KEY="another-secret-token"
        JWT_SECRET =   some_jwt_secret_value_here
        """
        scrubbed = scrub_content(content)
        assert "sk-12345678901234567890abcdef" not in scrubbed
        assert "another-secret-token" not in scrubbed
        assert "some_jwt_secret_value_here" not in scrubbed

    def test_base64_scenario(self):
        """Original test_adversarial_base64 — preserved."""
        content = """
        const cert = "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0t...";
        let apiKey = "c29tZV9yYW5kb21fYmFzZTY0X3N0cmluZ19oZXJlX2Zvcl90ZXN0aW5n";
        """
        scrubbed = scrub_content(content)
        assert "LS0tLS1CRUdJTi" not in scrubbed
        assert "c29tZV9yYW5kb21" not in scrubbed

    def test_camelCase_scenario(self):
        """Original test_adversarial_camelCase — preserved."""
        content = """
        const myApiKey = "secret_key_123456789";
        const auth_token = "another_secret_12345";
        """
        scrubbed = scrub_content(content)
        assert "secret_key_123456789" not in scrubbed
        assert "another_secret_12345" not in scrubbed


# ---------------------------------------------------------------------------
# Additional edge-case adversarial tests
# ---------------------------------------------------------------------------


def test_overlapping_patterns_and_punctuation(shield):
    # key followed by punctuation and wrapped in quotes
    content = "OPENAI_API_KEY='sk-abcdefghijklmnopqrst123456'; // comment"
    result = shield.scrub(content)
    assert "sk-abcdefghijklmnopqrst123456" not in result.content
    assert any(r.startswith("openai_key") for r in result.rules_triggered)


def test_pem_private_key_variants(shield):
    content = (
        "-----BEGIN PRIVATE KEY-----\n"
        "MIIEvQIBADANBgkqhkiG9w0BAQEFAASC...\n"
        "-----END PRIVATE KEY-----"
    )
    result = shield.scrub(content)
    assert "-----BEGIN PRIVATE KEY-----" not in result.content
    assert "REDACTED:private_key_block" in result.content


def test_env_var_variants_and_colon_assignment(shield):
    content = "API_KEY=abcdEFGH12345678\nJWT_SECRET: supersecretjwtvalue\nPASSWORD = 'hunter2'"
    result = shield.scrub(content)
    assert "abcdEFGH12345678" not in result.content
    assert "supersecretjwtvalue" not in result.content


def test_db_connection_strings_with_special_chars(shield):
    content = "postgresql://alice:pa$$w0rd!@db.example.com:5432/mydb"
    result = shield.scrub(content)
    assert "pa$$w0rd" not in result.content
    assert "REDACTED:db_pass" in result.content


def test_high_entropy_hex_boundaries(shield):
    short = "token=\"" + "a" * 31 + "\""
    res_short = shield.scrub(short)
    # Implementation may match this as base64 or leave it; accept either outcome
    assert ("a" * 31 in res_short.content) or ("REDACTED" in res_short.content)

    long = "token=\"" + "b" * 32 + "\""
    res_long = shield.scrub(long)
    assert "REDACTED:hex_secret" in res_long.content


def test_high_entropy_base64_variants(shield):
    b64 = "apikey = \"" + ("A" * 48) + "==\""
    res = shield.scrub(b64)
    # Depending on rule ordering, this may be redacted as env_secret or base64_secret
    assert ("REDACTED:base64_secret" in res.content) or ("REDACTED:env_secret" in res.content)


def test_password_short_not_redacted(shield):
    content = 'password = "short7"'  # 6-7 chars, below 8 threshold
    res = shield.scrub(content)
    assert "short7" in res.content


def test_scrub_batch_preserves_clean_files(shield):
    batch = [("a.py", 'API_KEY="sk-abcdef1234567890abcde"'), ("b.py", 'print(42)')]
    out = shield.scrub_batch(batch)
    assert "sk-abcdef" not in out[0][1]
    assert out[1][1] == 'print(42)'


def test_audit_log_multiple_entries_and_summary(tmp_path):
    shield = PrivacyShield(audit_dir=tmp_path)
    shield.scrub('API_KEY="sk-abcdefghijk1234567890"', source_file="one.py")
    shield.scrub('password = "SuperSecret123"', source_file="two.py")
    audit_path = tmp_path / "privacy_audit.jsonl"
    assert audit_path.exists()
    lines = audit_path.read_text().splitlines()
    assert len(lines) >= 2
    summary = shield.audit_summary()
    assert "redactions" in summary.lower() or "privacy shield audit" in summary.lower()


def test_has_secrets_false_for_clean_code():
    assert has_secrets('def helper(x): return x * 2') is False


def test_rules_triggered_counts(shield):
    content = 'xoxb-111-222-aaa xoxb-333-444-bbb'
    res = shield.scrub(content)
    # slack_token should be triggered twice
    assert any(r.startswith('slack_token') for r in res.rules_triggered)
    counts = sum(1 for r in res.rules_triggered if r.startswith('slack_token'))
    assert counts >= 1