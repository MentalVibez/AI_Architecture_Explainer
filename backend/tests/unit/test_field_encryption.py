"""
tests/unit/test_field_encryption.py

Verifies encrypt_json / decrypt_json / is_encrypted behaviour:
  - Passthrough when no key is configured
  - Roundtrip produces identical data
  - Unencrypted (legacy) records are returned unchanged
  - Corrupted ciphertext returns the raw ciphertext rather than crashing
  - is_encrypted sentinel detection
"""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from app.utils.field_encryption import decrypt_json, encrypt_json, is_encrypted


# ── helpers ──────────────────────────────────────────────────────────────────

def _set_key(monkeypatch, key: str) -> None:
    import app.utils.field_encryption as _mod
    import app.core.config as _cfg
    monkeypatch.setattr(_cfg.settings, "atlas_field_encryption_key", key)
    # Force _fernet() to re-evaluate the patched setting
    monkeypatch.setattr(_mod, "_fernet", lambda: (
        __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet(key.encode())
        if key else None
    ))


# ── passthrough when key is absent ────────────────────────────────────────────

def test_encrypt_json_passthrough_when_no_key(monkeypatch):
    _set_key(monkeypatch, "")
    data = [{"a": 1}]
    assert encrypt_json(data) is data


def test_decrypt_json_passthrough_when_no_key(monkeypatch):
    _set_key(monkeypatch, "")
    data = [{"a": 1}]
    assert decrypt_json(data) is data


# ── roundtrip ─────────────────────────────────────────────────────────────────

_VALID_KEY = Fernet.generate_key().decode()


def test_encrypt_decrypt_roundtrip(monkeypatch):
    _set_key(monkeypatch, _VALID_KEY)
    original = [{"repo": "owner/name", "files": ["a.py", "b.ts"], "count": 42}]
    encrypted = encrypt_json(original)
    assert is_encrypted(encrypted)
    result = decrypt_json(encrypted)
    assert result == original


def test_roundtrip_preserves_nested_structures(monkeypatch):
    _set_key(monkeypatch, _VALID_KEY)
    payload = {"detected_stack": {"backend": [{"name": "FastAPI", "confidence": 0.9}]}}
    assert decrypt_json(encrypt_json(payload)) == payload


def test_roundtrip_preserves_empty_list(monkeypatch):
    _set_key(monkeypatch, _VALID_KEY)
    assert decrypt_json(encrypt_json([])) == []


# ── backward-compat: unencrypted legacy records ────────────────────────────────

def test_decrypt_plain_list_returned_unchanged(monkeypatch):
    _set_key(monkeypatch, _VALID_KEY)
    plain = [{"tree_sha": "abc123"}]
    assert decrypt_json(plain) == plain


def test_decrypt_non_list_returned_unchanged(monkeypatch):
    _set_key(monkeypatch, _VALID_KEY)
    assert decrypt_json(None) is None
    assert decrypt_json({"key": "val"}) == {"key": "val"}
    assert decrypt_json("string") == "string"


def test_decrypt_empty_list_returned_unchanged(monkeypatch):
    _set_key(monkeypatch, _VALID_KEY)
    assert decrypt_json([]) == []


# ── is_encrypted detection ────────────────────────────────────────────────────

def test_is_encrypted_true_for_sentinel(monkeypatch):
    _set_key(monkeypatch, _VALID_KEY)
    encrypted = encrypt_json({"x": 1})
    assert is_encrypted(encrypted) is True


def test_is_encrypted_false_for_plain_list(monkeypatch):
    _set_key(monkeypatch, _VALID_KEY)
    assert is_encrypted([{"x": 1}]) is False


def test_is_encrypted_false_for_empty():
    assert is_encrypted([]) is False
    assert is_encrypted(None) is False
    assert is_encrypted("string") is False


# ── corrupted ciphertext — should log and return raw data, not crash ──────────

def test_decrypt_with_wrong_key_returns_raw(monkeypatch):
    # Encrypt with one key, try to decrypt with a different key
    key_a = Fernet.generate_key().decode()
    key_b = Fernet.generate_key().decode()

    import app.utils.field_encryption as _mod
    from cryptography.fernet import Fernet as _Fernet

    monkeypatch.setattr(_mod, "_fernet", lambda: _Fernet(key_a.encode()))
    encrypted = encrypt_json({"secret": "data"})

    monkeypatch.setattr(_mod, "_fernet", lambda: _Fernet(key_b.encode()))
    result = decrypt_json(encrypted)

    # Must not raise — returns the ciphertext structure unchanged
    assert is_encrypted(result)
