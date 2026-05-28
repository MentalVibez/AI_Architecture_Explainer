from app.api.routes_map import ProfileUsed, _build_profile, _stack_names


def test_build_profile_handles_rich_backend_stack_items():
    detected_stack = {
        "backend": [{"name": "FastAPI", "evidence": ["pyproject.toml"], "confidence": 0.95}],
        "frontend": [],
    }

    assert _build_profile(detected_stack) == ("fastapi", "high")


def test_build_profile_handles_legacy_string_stack_items():
    detected_stack = {"backend": ["django"], "frontend": []}

    assert _build_profile(detected_stack) == ("django", "high")


def test_build_profile_falls_back_to_frontend_nextjs():
    detected_stack = {
        "backend": [],
        "frontend": [{"name": "Next.js", "evidence": ["package.json"], "confidence": 0.95}],
    }

    assert _build_profile(detected_stack) == ("nextjs", "high")


def test_stack_names_filters_unknown_shapes_for_frontend_contract():
    names = _stack_names([
        {"name": "FastAPI", "confidence": 0.95},
        "Django",
        {"label": "missing name"},
        None,
    ])

    profile = ProfileUsed(
        framework="fastapi",
        framework_confidence="high",
        from_profile=True,
        detected_backend=names,
        detected_frontend=[],
    )

    assert profile.detected_backend == ["FastAPI", "Django"]
