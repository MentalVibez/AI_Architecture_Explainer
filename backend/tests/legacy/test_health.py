import pytest


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "codebase-atlas-backend"
    assert payload["checks"]["database"] == "ok"


@pytest.mark.asyncio
async def test_liveness(client):
    response = await client.get("/live")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "status": "ok",
        "service": "codebase-atlas-backend",
    }


@pytest.mark.asyncio
async def test_readiness(client):
    response = await client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "codebase-atlas-backend"
    assert payload["checks"]["database"] == "ok"
