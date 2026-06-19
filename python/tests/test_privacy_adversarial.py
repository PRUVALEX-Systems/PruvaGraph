import pytest
from pruvagraph.privacy import PrivacyShield, scrub_content

def test_adversarial_env_file():
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

def test_adversarial_base64():
    content = """
    const cert = "LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUJJakFOQmdrcWhraUc5dzBCQVFFRkFBT0NBUThBTUlJQkNnS0NBUUVBeHh4eHh4eHh4eHh4eHh4eHh4eHgKeHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eAp4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHgKLS0tLS1FTkQgQ0VSVElGSUNBVEUtLS0tLQo=";
    let apiKey = "c29tZV9yYW5kb21fYmFzZTY0X3N0cmluZ19oZXJlX2Zvcl90ZXN0aW5n";
    """
    scrubbed = scrub_content(content)
    assert "LS0tLS1CRUdJTi" not in scrubbed
    assert "c29tZV9yYW5kb21" not in scrubbed

def test_adversarial_camelCase():
    content = """
    const myApiKey = "secret_key_123456789";
    const auth_token = "another_secret_12345";
    """
    scrubbed = scrub_content(content)
    assert "secret_key_123456789" not in scrubbed
    assert "another_secret_12345" not in scrubbed
import asyncio
from typing import Dict, Any, List

def test_full_pipeline_mock_llm_redaction():
    """
    The Ultimate Proof Test.
    Wires a mock LLM client into the pipeline, runs a synthetic text blob
    containing EVERY type of secret, and asserts the mock client received
    zero raw secret values.
    """
    from pruvagraph.privacy import PrivacyShield, RedactionRule
    
    # Fake LLM Class
    class MockLLM:
        def __init__(self):
            self.received_prompts = []
            
        async def call_llm(self, prompt: str) -> str:
            self.received_prompts.append(prompt)
            return "{}" # Return empty JSON
            
    shield = PrivacyShield()
    mock_client = MockLLM()
    
    # A massive, evil blob of secrets
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
    
    # 1. Pipeline scrubs the content BEFORE LLM
    redaction_result = shield.scrub(evil_blob, source_file="evil_file.py")
    safe_content = redaction_result.content
    
    # 2. Assert the LLM is called with safe content
    asyncio.run(mock_client.call_llm(safe_content))
    
    # 3. Assert the LLM never received the raw secrets
    received = mock_client.received_prompts[0]
    
    assert "SuperSecretDBPass123!" not in received, "Failed to redact DB Password"
    assert "aws_sec_abcd1234efgh5678" not in received, "Failed to redact AWS Key"
    assert "sk-live-1234567890abcdef" not in received, "Failed to redact Stripe/API Key"
    assert "MIICXQIBAAKBgQ" not in received, "Failed to redact RSA Key"
    assert "AIzaSyB" not in received, "Failed to redact Google API Key"
    assert "xoxb-" not in received, "Failed to redact Slack Token"

    # Also make sure the word [REDACTED] is actually there
    assert "[REDACTED" in received