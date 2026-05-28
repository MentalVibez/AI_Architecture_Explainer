from app.services.route_extractor import EndpointMap, RouteEndpoint


async def test_map_endpoint_handles_rich_stack_items(client, monkeypatch):
    async def fake_stack_analysis(owner, repo):
        return {
            "detected_stack": {
                "backend": [
                    {"name": "FastAPI", "evidence": ["pyproject.toml"], "confidence": 0.95}
                ],
                "frontend": [],
            }
        }

    async def fake_extract_endpoints(**kwargs):
        return EndpointMap(
            repo=f"{kwargs['owner']}/{kwargs['repo']}",
            framework=kwargs["framework"],
            framework_confidence=kwargs["framework_confidence"],
            framework_from_profile=kwargs["from_profile"],
            endpoints=[
                RouteEndpoint(method="GET", path="/agents", source_file="app/api/routes.py")
            ],
            files_scanned=["app/api/routes.py"],
            parse_strategy="fastapi",
        )

    async def fake_enrich(endpoint_map):
        return {
            "groups": [
                {
                    "name": "Agents",
                    "description": "Agent endpoints",
                    "endpoints": [
                        {
                            "method": "GET",
                            "path": "/agents",
                            "description": "List agents",
                            "params": [],
                            "auth_likely": False,
                        }
                    ],
                }
            ],
            "summary": "FastAPI route surface.",
            "api_style": "REST",
            "auth_pattern": "Unknown",
            "warnings": [],
        }

    monkeypatch.setattr("app.api.routes_map.run_stack_analysis", fake_stack_analysis)
    monkeypatch.setattr("app.api.routes_map.extract_endpoints", fake_extract_endpoints)
    monkeypatch.setattr("app.api.routes_map.enrich_endpoint_map", fake_enrich)

    response = await client.get("/api/map/MentalVibez/ai-agent-orchestrator")

    assert response.status_code == 200
    body = response.json()
    assert body["profile_used"]["framework"] == "fastapi"
    assert body["profile_used"]["detected_backend"] == ["FastAPI"]
    assert body["raw_endpoint_count"] == 1


async def test_map_endpoint_profile_failure_returns_structured_502(client, monkeypatch):
    async def fake_stack_analysis(owner, repo):
        return {"detected_stack": {"backend": [], "frontend": []}}

    def fake_build_profile(detected_stack):
        raise TypeError("bad profile")

    monkeypatch.setattr("app.api.routes_map.run_stack_analysis", fake_stack_analysis)
    monkeypatch.setattr("app.api.routes_map._build_profile", fake_build_profile)

    response = await client.get("/api/map/MentalVibez/ai-agent-orchestrator")

    assert response.status_code == 502
    assert response.json() == {"detail": "Could not build repository stack profile."}
