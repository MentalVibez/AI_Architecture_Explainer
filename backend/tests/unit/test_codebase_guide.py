from types import SimpleNamespace

from app.services.onboarding_plan import build_codebase_guide, build_onboarding_plan


def _result(**overrides):
    base = {
        "id": 42,
        "detected_stack": {
            "frontend": [
                {
                    "name": "Next.js",
                    "evidence": ["package.json"],
                    "confidence": 0.95,
                }
            ],
            "backend": [
                {
                    "name": "FastAPI",
                    "evidence": ["backend/app/main.py"],
                    "confidence": 0.91,
                }
            ],
        },
        "entry_points": ["frontend/app/page.tsx", "backend/app/main.py"],
        "folder_map": [
            {"path": "frontend/app", "role": "Next.js route tree"},
            {"path": "backend/app/api", "role": "FastAPI routes"},
        ],
        "caveats": [],
        "confidence_score": 0.87,
        "raw_evidence": [
            {
                "repo": {"owner": "acme", "name": "widget"},
                "tree_paths": [
                    "README.md",
                    "frontend/app/page.tsx",
                    "backend/app/main.py",
                    "backend/tests/test_api.py",
                    ".github/workflows/ci.yml",
                    ".env.example",
                ],
                "fetched_files": ["README.md", "package.json"],
                "readme": "# Widget",
            }
        ],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_builds_codebase_guide_from_atlas_evidence():
    plan = build_codebase_guide(_result())

    assert plan.repo_label == "acme/widget"
    assert plan.week_plan
    assert plan.reading_path[0].path == "frontend/app/page.tsx"
    assert any(concept.name == "FastAPI" for concept in plan.concepts)
    assert plan.starter_tasks
    assert plan.team_questions
    assert plan.mentor_questions == plan.team_questions
    assert "guide" in plan.overview


def test_reading_path_only_references_allowed_evidence_paths():
    result = _result(
        raw_evidence=[
            {
                "repo": {"owner": "acme", "name": "widget"},
                "tree_paths": ["README.md", "app/main.py"],
                "fetched_files": [],
            }
        ],
        entry_points=["app/main.py", "ghost.py"],
        folder_map=[
            {"path": "app", "role": "application code"},
            {"path": "missing", "role": "not in tree but from folder map"},
        ],
    )

    plan = build_codebase_guide(result)
    allowed = {"README.md", "app/main.py", "app", "missing", "ghost.py"}

    assert {item.path for item in plan.reading_path}.issubset(allowed)
    for task in plan.starter_tasks:
        assert set(task.related_paths).issubset(allowed)
    for note in plan.risk_notes:
        assert set(note.related_paths).issubset(allowed)
    assert "invented.py" not in {item.path for item in plan.reading_path}


def test_degraded_evidence_surfaces_setup_blockers_and_low_confidence_risk():
    plan = build_codebase_guide(
        _result(
            confidence_score=0.4,
            entry_points=[],
            folder_map=[],
            raw_evidence=[
                {
                    "repo": {"owner": "acme", "name": "thin"},
                    "tree_paths": ["src/app.py"],
                }
            ],
        )
    )

    blocker_titles = {blocker.title for blocker in plan.setup_blockers}
    risk_titles = {risk.title for risk in plan.risk_notes}

    assert "README signal is weak or missing" in blocker_titles
    assert "Environment example not found" in blocker_titles
    assert "Treat low-confidence analysis as a map, not a verdict" in risk_titles


def test_empty_evidence_still_returns_actionable_report():
    plan = build_codebase_guide(
        _result(
            detected_stack={},
            entry_points=[],
            folder_map=[],
            raw_evidence=[],
            confidence_score=None,
        )
    )

    assert plan.overview
    assert plan.week_plan
    assert plan.evidence_summary["allowed_path_count"] == 0


def test_onboarding_wrapper_matches_codebase_guide_for_compatibility():
    result = _result()

    assert build_onboarding_plan(result) == build_codebase_guide(result)
