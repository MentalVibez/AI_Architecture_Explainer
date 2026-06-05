"""Opt-in field-level encryption for sensitive JSON columns.

Set ATLAS_FIELD_ENCRYPTION_KEY to a Fernet key to activate.
Generate a key:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Encrypted values are stored as a JSON-array sentinel:
  [{"__enc": "v1", "ct": "<fernet_ciphertext>"}]

Unencrypted records (missing key, or written before encryption was enabled)
are returned as-is so old data is never silently corrupted.
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_SENTINEL_KEY = "__enc"
_VERSION = "v1"


def _fernet():
    """Return a configured Fernet instance, or None when no key is set."""
    from app.core.config import settings

    raw_key = settings.atlas_field_encryption_key.strip()
    if not raw_key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)
    except Exception as exc:
        logger.error("field_encryption: invalid ATLAS_FIELD_ENCRYPTION_KEY — %s", exc)
        return None


def encrypt_json(data: Any) -> Any:
    """Encrypt a JSON-serialisable value before writing to a JSON column.

    Returns data unchanged when ATLAS_FIELD_ENCRYPTION_KEY is not set.
    Encrypted form: list with a single sentinel dict so the JSON column
    type constraint is still satisfied.
    """
    f = _fernet()
    if f is None:
        return data

    plaintext = json.dumps(data, separators=(",", ":")).encode()
    ciphertext = f.encrypt(plaintext).decode()
    return [{_SENTINEL_KEY: _VERSION, "ct": ciphertext}]


def decrypt_json(data: Any) -> Any:
    """Decrypt a value read from a JSON column.

    Returns data unchanged when:
    - It is not in sentinel format (old plaintext record)
    - The encryption key is not configured
    - Decryption fails (key rotation / corruption — logged, not raised)
    """
    if not isinstance(data, list) or not data:
        return data

    first = data[0]
    if not (isinstance(first, dict) and first.get(_SENTINEL_KEY) == _VERSION):
        return data  # plaintext or unknown format

    f = _fernet()
    if f is None:
        logger.warning("field_encryption: encrypted record found but ATLAS_FIELD_ENCRYPTION_KEY is not set")
        return data

    try:
        plaintext = f.decrypt(first["ct"].encode())
        return json.loads(plaintext)
    except Exception as exc:
        logger.error("field_encryption: decryption failed — %s", exc)
        return data  # return ciphertext rather than crash


def is_encrypted(data: Any) -> bool:
    """Return True if data is in sentinel-encrypted format."""
    return (
        isinstance(data, list)
        and len(data) == 1
        and isinstance(data[0], dict)
        and data[0].get(_SENTINEL_KEY) == _VERSION
    )
