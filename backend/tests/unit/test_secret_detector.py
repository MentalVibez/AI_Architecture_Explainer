"""
tests/unit/test_secret_detector.py

Covers SecretDetector.detect_secrets, mask_all_secrets, and get_summary.
"""
from app.utils.secret_detector import SecretDetector


# ── detect_secrets ─────────────────────────────────────────────────────────────

def test_detect_api_key_assignment():
    text = 'api_key = "sk-abcdefghijklmnopqrstuvwxyz1234567890"'
    secrets = SecretDetector.detect_secrets(text)
    assert any(s["type"] == "api_key" for s in secrets)


def test_detect_password_in_config():
    text = "password = 'super-secret-value'"
    secrets = SecretDetector.detect_secrets(text)
    assert any(s["type"] == "password" for s in secrets)


def test_detect_github_token_prefix():
    text = "GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz12345678901234"
    secrets = SecretDetector.detect_secrets(text)
    assert any(s["type"] == "github_token" for s in secrets)


def test_detect_private_key_header():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA..."
    secrets = SecretDetector.detect_secrets(text)
    assert any(s["type"] == "private_key" for s in secrets)


def test_no_false_positives_on_clean_text():
    text = "This file documents the project structure. No secrets here."
    secrets = SecretDetector.detect_secrets(text)
    assert secrets == []


def test_line_number_is_correct():
    text = "line1\nline2\napi_key = 'abcdefghijklmnopqrstuvwxyz'"
    secrets = SecretDetector.detect_secrets(text)
    api_secrets = [s for s in secrets if s["type"] == "api_key"]
    assert api_secrets and api_secrets[0]["line"] == 3


# ── mask_all_secrets ──────────────────────────────────────────────────────────

def test_mask_all_secrets_replaces_pattern():
    text = "password = 'my_super_secret_pass'"
    masked = SecretDetector.mask_all_secrets(text)
    assert "my_super_secret_pass" not in masked
    assert "*" in masked


def test_mask_all_secrets_leaves_clean_text_unchanged():
    text = "print('hello world')"
    assert SecretDetector.mask_all_secrets(text) == text


def test_mask_all_secrets_multiple_secrets():
    text = (
        "api_key = 'sk-abcdefghijklmnopqrstuvwxyz'\n"
        "password = 'hunter2hunter2'"
    )
    masked = SecretDetector.mask_all_secrets(text)
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in masked
    assert "hunter2hunter2" not in masked


def test_mask_preserves_surrounding_text():
    text = "export api_key = 'abcdefghijklmnopqrstuvwxyz' # comment"
    masked = SecretDetector.mask_all_secrets(text)
    assert "export" in masked
    assert "# comment" in masked


# ── get_summary ───────────────────────────────────────────────────────────────

def test_get_summary_counts_types():
    secrets = [
        {"type": "api_key"}, {"type": "api_key"}, {"type": "password"}
    ]
    summary = SecretDetector.get_summary(secrets)
    assert summary == {"api_key": 2, "password": 1}


def test_get_summary_empty():
    assert SecretDetector.get_summary([]) == {}
