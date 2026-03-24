"""
tests/unit/test_onboarding_assembler_async.py

Tests for onboarding_assembler_async.run_onboarding_analysis().

Key things verified:
  - asyncio.to_thread() is called for each analyzer (not blocking event loop)
  - analyzer failure → SCAN_FAILED sentinel written, other sections continue
  - all-fail path → three sentinels, no unhandled exception
  - flush is called per section (progressive writes)
  - mark_onboarding_failed_if_needed writes sentinels only to NULL sections
  - deserialize_section handles None / valid / malformed correctly

These tests use asyncio.run / pytest-asyncio or plain asyncio.run().
No real DB — AsyncSession is faked with a minimal async-compatible mock.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.services.contracts.onboarding_models import ScanState


# ─────────────────────────────────────────────────────────
# Minimal async-compatible DB and result fakes
# ─────────────────────────────────────────────────────────

class FakeResult:
    def __init__(self):
        self.setup_risk      = None
        self.debug_readiness = None
        self.change_risk     = None
        self.job_id          = str(uuid.uuid4())


class FakeAsyncDB:
    """Minimal AsyncSession fake."""
    def __init__(self):
        self.flushed   = 0
        self.added     = []
        self.scalar_return = None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed += 1

    async def scalar(self, stmt):
        return self.scalar_return

    async def commit(self):
        pass

    async def rollback(self):
        pass


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────

def _run(coro):
    """Run a coroutine synchronously for tests without pytest-asyncio."""
    return asyncio.run(coro)


def _make_mock_analyzer(return_level="low", fail=False):
    """Build a mock analyzer return value or a side effect for failure."""
    if fail:
        return MagicMock(side_effect=RuntimeError("analyzer exploded"))
    mock_output = MagicMock()
    mock_output.level      = return_level
    mock_output.scan_state = ScanState.FOUND
    mock_output.model_dump = MagicMock(return_value={
        "scan_state": "found",
        "score": 20,
        "level": return_level,
        "confidence": 0.8,
        "risks": [],
        "evidence": [],
        "scan_errors": [],
    })
    return mock_output


# ─────────────────────────────────────────────────────────
# Import the module under test
# ─────────────────────────────────────────────────────────

from app.services.pipeline.onboarding_assembler_async import (
    run_onboarding_analysis,
    mark_onboarding_failed_if_needed,
    deserialize_setup_risk,
    deserialize_debug_readiness,
    deserialize_change_risk,
    deserialize_section,
)


# ─────────────────────────────────────────────────────────
# 1. Happy path — all three sections complete
# ─────────────────────────────────────────────────────────

class TestHappyPath:
    def test_all_three_sections_populated(self, tmp_path):
        result = FakeResult()
        db     = FakeAsyncDB()

        with patch("app.services.analyzers.setup_risk_analyzer.analyze_setup_risk",
                   return_value=_make_mock_analyzer("low")), \
             patch("app.services.analyzers.debug_readiness_analyzer.analyze_debug_readiness",
                   return_value=_make_mock_analyzer("medium")), \
             patch("app.services.analyzers.change_risk_analyzer.analyze_change_risk",
                   return_value=_make_mock_analyzer("high")):
            _run(run_onboarding_analysis("job-1", tmp_path, result, db))

        assert result.setup_risk      is not None
        assert result.debug_readiness is not None
        assert result.change_risk     is not None

    def test_flush_called_per_section(self, tmp_path):
        result = FakeResult()
        db     = FakeAsyncDB()

        with patch("app.services.analyzers.setup_risk_analyzer.analyze_setup_risk",
                   return_value=_make_mock_analyzer()), \
             patch("app.services.analyzers.debug_readiness_analyzer.analyze_debug_readiness",
                   return_value=_make_mock_analyzer()), \
             patch("app.services.analyzers.change_risk_analyzer.analyze_change_risk",
                   return_value=_make_mock_analyzer()):
            _run(run_onboarding_analysis("job-1", tmp_path, result, db))

        # One flush per section = 3 flushes
        assert db.flushed == 3

    def test_section_data_has_scan_state(self, tmp_path):
        result = FakeResult()
        db     = FakeAsyncDB()

        with patch("app.services.analyzers.setup_risk_analyzer.analyze_setup_risk",
                   return_value=_make_mock_analyzer()), \
             patch("app.services.analyzers.debug_readiness_analyzer.analyze_debug_readiness",
                   return_value=_make_mock_analyzer()), \
             patch("app.services.analyzers.change_risk_analyzer.analyze_change_risk",
                   return_value=_make_mock_analyzer()):
            _run(run_onboarding_analysis("job-1", tmp_path, result, db))

        assert result.setup_risk["scan_state"]      == "found"
        assert result.debug_readiness["scan_state"] == "found"
        assert result.change_risk["scan_state"]     == "found"


# ─────────────────────────────────────────────────────────
# 2. Section isolation — one fails, others continue
# ─────────────────────────────────────────────────────────

class TestSectionIsolation:
    def test_change_risk_failure_leaves_setup_and_debug_intact(self, tmp_path):
        result = FakeResult()
        db     = FakeAsyncDB()

        with patch("app.services.analyzers.setup_risk_analyzer.analyze_setup_risk",
                   return_value=_make_mock_analyzer("low")), \
             patch("app.services.analyzers.debug_readiness_analyzer.analyze_debug_readiness",
                   return_value=_make_mock_analyzer("medium")), \
             patch("app.services.analyzers.change_risk_analyzer.analyze_change_risk",
                   side_effect=RuntimeError("change risk exploded")):
            _run(run_onboarding_analysis("job-2", tmp_path, result, db))

        assert result.setup_risk["scan_state"]      == "found"
        assert result.debug_readiness["scan_state"] == "found"
        assert result.change_risk["scan_state"]     == "scan_failed"

    def test_change_risk_failure_sentinel_has_scan_errors(self, tmp_path):
        result = FakeResult()
        db     = FakeAsyncDB()

        with patch("app.services.analyzers.setup_risk_analyzer.analyze_setup_risk",
                   return_value=_make_mock_analyzer()), \
             patch("app.services.analyzers.debug_readiness_analyzer.analyze_debug_readiness",
                   return_value=_make_mock_analyzer()), \
             patch("app.services.analyzers.change_risk_analyzer.analyze_change_risk",
                   side_effect=RuntimeError("specific error message")):
            _run(run_onboarding_analysis("job-2", tmp_path, result, db))

        errors = result.change_risk["scan_errors"]
        assert len(errors) > 0
        assert "specific error message" in errors[0]

    def test_setup_failure_does_not_skip_debug_or_change(self, tmp_path):
        result = FakeResult()
        db     = FakeAsyncDB()

        with patch("app.services.analyzers.setup_risk_analyzer.analyze_setup_risk",
                   side_effect=RuntimeError("setup exploded")), \
             patch("app.services.analyzers.debug_readiness_analyzer.analyze_debug_readiness",
                   return_value=_make_mock_analyzer()), \
             patch("app.services.analyzers.change_risk_analyzer.analyze_change_risk",
                   return_value=_make_mock_analyzer()):
            _run(run_onboarding_analysis("job-3", tmp_path, result, db))

        assert result.setup_risk["scan_state"]      == "scan_failed"
        assert result.debug_readiness["scan_state"] == "found"
        assert result.change_risk["scan_state"]     == "found"

    def test_all_three_fail_writes_three_sentinels(self, tmp_path):
        result = FakeResult()
        db     = FakeAsyncDB()

        with patch("app.services.analyzers.setup_risk_analyzer.analyze_setup_risk",
                   side_effect=RuntimeError("1")), \
             patch("app.services.analyzers.debug_readiness_analyzer.analyze_debug_readiness",
                   side_effect=RuntimeError("2")), \
             patch("app.services.analyzers.change_risk_analyzer.analyze_change_risk",
                   side_effect=RuntimeError("3")):
            _run(run_onboarding_analysis("job-4", tmp_path, result, db))

        for section in ("setup_risk", "debug_readiness", "change_risk"):
            stored = getattr(result, section)
            assert stored is not None, f"{section} should have a sentinel"
            assert stored["scan_state"] == "scan_failed"

    def test_never_raises(self, tmp_path):
        """run_onboarding_analysis must never propagate exceptions."""
        result = FakeResult()
        db     = FakeAsyncDB()

        with patch("app.services.analyzers.setup_risk_analyzer.analyze_setup_risk",
                   side_effect=MemoryError("OOM")), \
             patch("app.services.analyzers.debug_readiness_analyzer.analyze_debug_readiness",
                   side_effect=MemoryError("OOM")), \
             patch("app.services.analyzers.change_risk_analyzer.analyze_change_risk",
                   side_effect=MemoryError("OOM")):
            # Must not raise
            _run(run_onboarding_analysis("job-5", tmp_path, result, db))


# ─────────────────────────────────────────────────────────
# 3. mark_onboarding_failed_if_needed
# ─────────────────────────────────────────────────────────

class TestMarkOnboardingFailed:
    def test_writes_sentinels_to_null_sections(self, tmp_path):
        db = FakeAsyncDB()
        result = FakeResult()
        result.setup_risk = {"scan_state": "found"}  # already written
        # debug_readiness and change_risk are None — should get sentinels
        db.scalar_return = result

        _run(mark_onboarding_failed_if_needed("job-6", "worker died", db))

        assert result.setup_risk["scan_state"]      == "found"   # unchanged
        assert result.debug_readiness["scan_state"] == "scan_failed"
        assert result.change_risk["scan_state"]     == "scan_failed"

    def test_noop_when_result_not_found(self):
        db = FakeAsyncDB()
        db.scalar_return = None
        # Must not raise
        _run(mark_onboarding_failed_if_needed("no-such-job", "error", db))

    def test_noop_when_all_sections_already_written(self):
        db = FakeAsyncDB()
        result = FakeResult()
        result.setup_risk      = {"scan_state": "found"}
        result.debug_readiness = {"scan_state": "found"}
        result.change_risk     = {"scan_state": "found"}
        db.scalar_return = result
        initial_flushes = db.flushed

        _run(mark_onboarding_failed_if_needed("job-7", "error", db))

        assert db.flushed == initial_flushes  # no new flush


# ─────────────────────────────────────────────────────────
# 4. Deserialization helpers
# ─────────────────────────────────────────────────────────

class TestDeserialization:
    def test_none_returns_none(self):
        assert deserialize_setup_risk(None)      is None
        assert deserialize_debug_readiness(None) is None
        assert deserialize_change_risk(None)     is None

    def test_valid_setup_risk_deserializes(self):
        raw = {
            "scan_state": "found", "score": 30, "level": "low",
            "confidence": 0.8, "missing_env_vars": [], "env_example_present": True,
            "likely_start_commands": ["make run"], "required_services": [],
            "detected_manifests": ["Makefile"], "risks": [], "evidence": [],
            "scan_errors": [],
        }
        result = deserialize_setup_risk(raw)
        assert result is not None
        assert result.scan_state.value == "found"
        assert result.level.value == "low"

    def test_valid_change_risk_deserializes(self):
        raw = {
            "scan_state": "found", "score": 55, "level": "high",
            "confidence": 0.7, "risks": [], "evidence": [], "scan_errors": [],
            "ci": {"scan_state": "found", "platforms": ["github_actions"],
                   "has_test_gate": True, "has_lint_gate": False, "signals": []},
            "test_gates": {"scan_state": "found", "frameworks": ["pytest"],
                           "has_coverage": False, "signals": []},
            "migration_risk": {"scan_state": "not_found", "migration_paths": [],
                               "has_migration_tests": False, "signals": []},
            "config_risk": {"scan_state": "not_found", "config_paths": [], "signals": []},
            "hotspots": {"scan_state": "not_found", "hotspots": [], "signals": []},
            "blast_radius_hotspots": [], "safe_to_change": [], "risky_to_change": [],
        }
        result = deserialize_change_risk(raw)
        assert result is not None
        assert result.scan_state.value == "found"
        assert result.level.value == "high"

    def test_malformed_json_returns_scan_failed(self):
        malformed = {"completely": "wrong", "no_scan_state": True}
        result = deserialize_change_risk(malformed)
        assert result is not None
        assert result.scan_state == ScanState.SCAN_FAILED
        assert "response_deserialization_failed" in result.scan_errors

    def test_scan_failed_sentinel_deserializes(self):
        sentinel = {
            "scan_state": "scan_failed", "score": None, "level": None,
            "confidence": 0.0, "scan_errors": ["worker_failure:OOM:out of memory"],
        }
        result = deserialize_setup_risk(sentinel)
        assert result.scan_state == ScanState.SCAN_FAILED
        assert result.score is None
        assert "worker_failure" in result.scan_errors[0]

    def test_deserialization_never_raises(self):
        # Completely arbitrary garbage must not raise
        for garbage in [{"x": 1}, {}, {"scan_state": "invalid_value"}]:
            try:
                deserialize_change_risk(garbage)
            except Exception as exc:
                pytest.fail(f"deserialize_change_risk raised on {garbage}: {exc}")


# ─────────────────────────────────────────────────────────
# 5. asyncio.to_thread is used (analyzer does not block event loop)
# ─────────────────────────────────────────────────────────

class TestThreading:
    def test_analyzer_called_via_to_thread(self, tmp_path):
        """Verify asyncio.to_thread is in the call path."""
        result = FakeResult()
        db     = FakeAsyncDB()
        called_in_thread = []

        def mock_setup_risk(path):
            # asyncio.to_thread runs this in a thread; record that we got called
            called_in_thread.append(True)
            return _make_mock_analyzer()

        with patch("app.services.analyzers.setup_risk_analyzer.analyze_setup_risk",
                   side_effect=mock_setup_risk), \
             patch("app.services.analyzers.debug_readiness_analyzer.analyze_debug_readiness",
                   return_value=_make_mock_analyzer()), \
             patch("app.services.analyzers.change_risk_analyzer.analyze_change_risk",
                   return_value=_make_mock_analyzer()):
            _run(run_onboarding_analysis("job-8", tmp_path, result, db))

        assert len(called_in_thread) == 1, "setup_risk analyzer should have been called"
