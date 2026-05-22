"""Unit tests for PR webhook signature verification and comment formatting."""

from __future__ import annotations

import hashlib
import hmac

import pytest
from fastapi import HTTPException

from app.api.routes_webhook import _verify_signature
from app.services.pr_comment_service import build_comment, build_error_comment

# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------

def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_verify_signature_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes_webhook.settings.github_webhook_secret", "mysecret")
    body = b'{"action":"opened"}'
    sig = _sign(body, "mysecret")
    _verify_signature(body, sig)  # must not raise


def test_verify_signature_wrong_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes_webhook.settings.github_webhook_secret", "mysecret")
    body = b'{"action":"opened"}'
    sig = _sign(body, "wrongsecret")
    with pytest.raises(HTTPException) as exc_info:
        _verify_signature(body, sig)
    assert exc_info.value.status_code == 403


def test_verify_signature_missing_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes_webhook.settings.github_webhook_secret", "mysecret")
    with pytest.raises(HTTPException) as exc_info:
        _verify_signature(b"body", None)
    assert exc_info.value.status_code == 403


def test_verify_signature_no_secret_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes_webhook.settings.github_webhook_secret", "")
    with pytest.raises(HTTPException) as exc_info:
        _verify_signature(b"body", "sha256=abc")
    assert exc_info.value.status_code == 400


def test_verify_signature_malformed_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes_webhook.settings.github_webhook_secret", "secret")
    with pytest.raises(HTTPException) as exc_info:
        _verify_signature(b"body", "md5=abc123")
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Comment formatting
# ---------------------------------------------------------------------------

class _FakeReview:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "abc-123")
        self.production_suitable = kwargs.get("production_suitable", True)
        self.verdict_label = kwargs.get("verdict_label", "Production Suitable")
        self.overall_score = kwargs.get("overall_score", 85)
        self.summary_json = kwargs.get("summary_json", {"developer": "Clean, well-structured codebase."})
        self.findings_json = kwargs.get("findings_json", [])
        self.error_code = kwargs.get("error_code", None)
        self.error_message = kwargs.get("error_message", None)


def test_build_comment_includes_verdict() -> None:
    review = _FakeReview()
    comment = build_comment(review, "https://example.com/review/abc-123")
    assert "Production Suitable" in comment
    assert "85/100" in comment


def test_build_comment_includes_summary() -> None:
    review = _FakeReview()
    comment = build_comment(review, "https://example.com/review/abc-123")
    assert "Clean, well-structured codebase." in comment


def test_build_comment_includes_link() -> None:
    review = _FakeReview()
    comment = build_comment(review, "https://example.com/review/abc-123")
    assert "https://example.com/review/abc-123" in comment


def test_build_comment_findings_table() -> None:
    review = _FakeReview(findings_json=[
        {"title": "SQL injection", "severity": "high"},
        {"title": "Missing rate limit", "severity": "medium"},
    ])
    comment = build_comment(review, "https://example.com/r/1")
    assert "SQL injection" in comment
    assert "Missing rate limit" in comment
    assert "🔴" in comment
    assert "🟡" in comment


def test_build_comment_truncates_findings() -> None:
    findings = [{"title": f"Finding {i}", "severity": "low"} for i in range(15)]
    review = _FakeReview(findings_json=findings)
    comment = build_comment(review, "https://example.com/r/1")
    assert "7 more" in comment


def test_build_error_comment() -> None:
    comment = build_error_comment("Repository not found")
    assert "Repository not found" in comment
    assert "CodeBaseAtlas" in comment


def test_build_comment_no_score() -> None:
    review = _FakeReview(overall_score=None, verdict_label=None)
    comment = build_comment(review, "https://example.com/r/1")
    assert "CodeBaseAtlas" in comment
    assert "Analysis complete" in comment
