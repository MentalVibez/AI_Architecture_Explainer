"""Unit tests for metrics_service."""

from __future__ import annotations

import pytest

from app.services.metrics_service import estimate_cost_usd, schedule_record


def test_estimate_cost_usd_basic() -> None:
    # 1M input + 1M output = $3 + $15 = $18
    assert estimate_cost_usd(1_000_000, 1_000_000) == pytest.approx(18.0)


def test_estimate_cost_usd_zero() -> None:
    assert estimate_cost_usd(0, 0) == 0.0


def test_estimate_cost_usd_input_only() -> None:
    # 1M input = $3.00
    assert estimate_cost_usd(1_000_000, 0) == pytest.approx(3.0)


def test_estimate_cost_usd_output_only() -> None:
    # 1M output = $15.00
    assert estimate_cost_usd(0, 1_000_000) == pytest.approx(15.0)


def test_estimate_cost_usd_small_call() -> None:
    # 1k input ($0.003) + 500 output ($0.0075) = $0.0105
    cost = estimate_cost_usd(1000, 500)
    assert cost == pytest.approx(0.0105)


def test_schedule_record_no_event_loop_is_silent() -> None:
    # Outside an event loop this should not raise
    schedule_record(
        stage="test",
        model="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=50,
        duration_ms=1200,
    )


@pytest.mark.asyncio
async def test_record_llm_usage_swallows_db_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """record_llm_usage must not raise even if the DB write fails."""
    from app.services import metrics_service

    async def boom():
        raise RuntimeError("DB unavailable")

    class FakeSession:
        def add(self, obj):
            pass
        async def commit(self):
            raise RuntimeError("DB unavailable")
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    monkeypatch.setattr(
        "app.services.metrics_service.AsyncSessionLocal",
        lambda: FakeSession(),
        raising=False,
    )

    import app.core.database
    monkeypatch.setattr(app.core.database, "AsyncSessionLocal", lambda: FakeSession())

    # Should complete without raising
    await metrics_service.record_llm_usage(
        stage="test_stage",
        model="claude-sonnet-4-6",
        input_tokens=200,
        output_tokens=100,
        duration_ms=800,
    )
