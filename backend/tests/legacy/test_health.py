import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "ok"
    assert payload["llm_check_mode"] == "config_only"
    assert payload["jobs"]["execution_mode"] == "database_worker_queue"
    assert payload["jobs"]["topology"] == "separate_web_and_worker_processes"
