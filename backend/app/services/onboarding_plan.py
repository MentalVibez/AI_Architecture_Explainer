from __future__ import annotations

from typing import Any

from app.models.analysis_result import AnalysisResult
from app.schemas.onboarding import (
    CodebaseGuideResponse,
    ConceptNote,
    ReadingPathItem,
    RiskNote,
    SetupBlocker,
    StarterTask,
    WeekPlanItem,
)


def build_codebase_guide(result: AnalysisResult) -> CodebaseGuideResponse:
    evidence = _first_evidence(result.raw_evidence)
    repo = evidence.get("repo", {}) if isinstance(evidence.get("repo"), dict) else {}
    repo_label = _repo_label(repo)
    allowed_paths = _allowed_paths(result, evidence)
    reading_path = _build_reading_path(result, allowed_paths)
    stack_names = _stack_names(result.detected_stack)
    blockers = _setup_blockers(result, evidence)
    team_questions = _team_questions(result, stack_names, blockers)

    return CodebaseGuideResponse(
        result_id=result.id,
        repo_label=repo_label,
        overview=_overview(repo_label, stack_names, result.confidence_score),
        week_plan=_week_plan(reading_path, blockers),
        reading_path=reading_path,
        concepts=_concepts(result.detected_stack),
        starter_tasks=_starter_tasks(result, allowed_paths, blockers),
        risk_notes=_risk_notes(result, allowed_paths),
        mentor_questions=team_questions,
        team_questions=team_questions,
        setup_blockers=blockers,
        evidence_summary={
            "allowed_path_count": len(allowed_paths),
            "entry_point_count": len(result.entry_points or []),
            "folder_signal_count": len(result.folder_map or []),
            "caveat_count": len(result.caveats or []),
            "confidence_score": result.confidence_score,
        },
    )


def build_onboarding_plan(result: AnalysisResult) -> CodebaseGuideResponse:
    """Compatibility wrapper for callers using the original feature name."""
    return build_codebase_guide(result)


def _first_evidence(raw_evidence: Any) -> dict[str, Any]:
    if isinstance(raw_evidence, list) and raw_evidence and isinstance(raw_evidence[0], dict):
        return raw_evidence[0]
    return {}


def _repo_label(repo: dict[str, Any]) -> str | None:
    owner = repo.get("owner")
    name = repo.get("name")
    if isinstance(owner, str) and isinstance(name, str) and owner and name:
        return f"{owner}/{name}"
    return None


def _allowed_paths(result: AnalysisResult, evidence: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for path in result.entry_points or []:
        if isinstance(path, str) and path:
            paths.add(path)
    for item in result.folder_map or []:
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            paths.add(item["path"])
    for key in ("tree_paths", "fetched_files"):
        values = evidence.get(key, [])
        if isinstance(values, list):
            paths.update(path for path in values if isinstance(path, str) and path)
    return paths


def _build_reading_path(result: AnalysisResult, allowed_paths: set[str]) -> list[ReadingPathItem]:
    items: list[ReadingPathItem] = []
    seen: set[str] = set()

    for path in result.entry_points or []:
        if path in allowed_paths:
            _append_reading_item(items, seen, path, "Runtime entry point detected by Atlas.", 0.92)

    for item in result.folder_map or []:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        role = item.get("role")
        if isinstance(path, str) and path in allowed_paths:
            reason = str(role) if role else "High-signal folder from the Atlas folder map."
            _append_reading_item(items, seen, path, reason, 0.78)

    for candidate in sorted(allowed_paths):
        lowered = candidate.lower()
        if lowered.endswith("readme.md"):
            _append_reading_item(
                items, seen, candidate, "Project orientation and setup context.", 0.7
            )
        elif "test" in lowered and len(items) < 8:
            _append_reading_item(
                items,
                seen,
                candidate,
                "Tests show expected behavior and the safest validation boundaries.",
                0.64,
            )

    return items[:8]


def _append_reading_item(
    items: list[ReadingPathItem],
    seen: set[str],
    path: str,
    reason: str,
    confidence: float,
) -> None:
    if path in seen:
        return
    seen.add(path)
    items.append(ReadingPathItem(path=path, reason=reason, confidence=confidence))


def _stack_names(stack: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(stack, dict):
        return names
    for values in stack.values():
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
            elif isinstance(item, str):
                names.append(item)
    return names


def _concepts(stack: Any) -> list[ConceptNote]:
    if not isinstance(stack, dict):
        return []
    concepts: list[ConceptNote] = []
    for category, values in stack.items():
        if not isinstance(values, list):
            continue
        for item in values[:2]:
            name = item.get("name") if isinstance(item, dict) else item
            if not isinstance(name, str) or not name:
                continue
            evidence = item.get("evidence", []) if isinstance(item, dict) else []
            concepts.append(
                ConceptNote(
                    name=name,
                    explanation=(
                        f"Atlas detected {name} in the {category} layer. "
                        "Use the evidence to understand its runtime role, boundaries, "
                        "and likely change impact."
                    ),
                    evidence=[e for e in evidence if isinstance(e, str)][:3],
                )
            )
    return concepts[:6]


def _setup_blockers(result: AnalysisResult, evidence: dict[str, Any]) -> list[SetupBlocker]:
    paths = {p.lower() for p in _allowed_paths(result, evidence)}
    blockers: list[SetupBlocker] = []
    if not any(path.endswith("readme.md") for path in paths) and not evidence.get("readme"):
        blockers.append(SetupBlocker(
            title="README signal is weak or missing",
            severity="medium",
            guidance="Ask for the expected local setup path before spending time guessing.",
        ))
    if not any(".env.example" in path or ".env.sample" in path for path in paths):
        blockers.append(SetupBlocker(
            title="Environment example not found",
            severity="medium",
            guidance=(
                "Confirm required environment variables with a maintainer "
                "before running services."
            ),
        ))
    if not any("test" in path or "pytest" in path or "playwright" in path for path in paths):
        blockers.append(SetupBlocker(
            title="Test entry point is unclear",
            severity="low",
            guidance="Identify the smallest reliable test command before changing behavior.",
        ))
    if not any(".github/workflows" in path for path in paths):
        blockers.append(SetupBlocker(
            title="CI workflow not visible in evidence",
            severity="low",
            guidance="Do not assume automated checks exist; ask which commands gate pull requests.",
        ))
    return blockers


def _week_plan(
    reading_path: list[ReadingPathItem],
    blockers: list[SetupBlocker],
) -> list[WeekPlanItem]:
    first_paths = [item.path for item in reading_path[:3]]
    return [
        WeekPlanItem(
            phase="System map",
            title="Build the mental model before editing",
            goal=(
                "Understand what the repo appears to do, where execution starts, "
                "and how confident the evidence is."
            ),
            actions=[
                "Read the project summary and confidence caveats.",
                *[f"Open {path}." for path in first_paths],
            ],
        ),
        WeekPlanItem(
            phase="Execution flow",
            title="Trace one real workflow end to end",
            goal="Follow one request, job, or user action through the main modules.",
            actions=[
                "Use the diagram and reading path together.",
                "Record unclear service boundaries for team review.",
            ],
        ),
        WeekPlanItem(
            phase="Change guidance",
            title="Choose a safe contribution path",
            goal="Make the first change in an area with clear validation and low blast radius.",
            actions=[
                "Choose a documentation, test, or isolated UI cleanup task.",
                "Run the smallest available checks before opening a pull request.",
                *[f"Resolve blocker: {blocker.title}." for blocker in blockers[:2]],
            ],
        ),
    ]


def _starter_tasks(
    result: AnalysisResult,
    allowed_paths: set[str],
    blockers: list[SetupBlocker],
) -> list[StarterTask]:
    tasks = [
        StarterTask(
            title="Improve project understanding documentation",
            why_safe="Documentation changes help future readers and usually avoid runtime risk.",
            suggested_checks=[
                "Preview the changed documentation.",
                "Ask a maintainer to verify setup commands.",
            ],
            related_paths=_pick_paths(allowed_paths, ["readme", "docs"])[:2],
        ),
        StarterTask(
            title="Add or tighten a small test around existing behavior",
            why_safe=(
                "Tests help any developer learn expected behavior without changing "
                "product logic first."
            ),
            suggested_checks=[
                "Run the targeted test command.",
                "Confirm the test fails for the intended reason before fixing.",
            ],
            related_paths=_pick_paths(allowed_paths, ["test", "spec"])[:2],
        ),
    ]
    if result.caveats:
        tasks.append(StarterTask(
            title="Clarify an Atlas caveat with a maintainer",
            why_safe="Resolving uncertainty improves the guide before anyone edits risky areas.",
            suggested_checks=[
                "Compare the caveat against the referenced files.",
                "Record the maintainer answer in project docs.",
            ],
            related_paths=[],
        ))
    if blockers:
        tasks.append(StarterTask(
            title="Document the missing setup step",
            why_safe=(
                "Setup fixes are high-leverage and easy to review when scoped "
                "to verified commands."
            ),
            suggested_checks=[
                "Run the documented command locally.",
                "Have another developer follow the updated step.",
            ],
            related_paths=_pick_paths(allowed_paths, ["readme", "docs"])[:2],
        ))
    return tasks[:4]


def _risk_notes(result: AnalysisResult, allowed_paths: set[str]) -> list[RiskNote]:
    notes = [
        RiskNote(
            title="Avoid broad architectural rewrites until the flow is clear",
            guidance=(
                "Start by tracing behavior and changing isolated docs, "
                "tests, or small UI pieces."
            ),
            related_paths=_pick_paths(allowed_paths, ["main", "app", "server"])[:3],
        )
    ]
    if result.confidence_score is not None and result.confidence_score < 0.65:
        notes.append(RiskNote(
            title="Treat low-confidence analysis as a map, not a verdict",
            guidance=(
                "Confirm entry points and service boundaries with a maintainer "
                "before editing core code."
            ),
            related_paths=[],
        ))
    if result.caveats:
        notes.append(RiskNote(
            title="Review caveats before selecting a task",
            guidance="Atlas caveats mark places where evidence was incomplete or ambiguous.",
            related_paths=[],
        ))
    return notes


def _team_questions(
    result: AnalysisResult,
    stack_names: list[str],
    blockers: list[SetupBlocker],
) -> list[str]:
    questions = [
        (
            "What is the most important workflow to trace from UI/API entry "
            "to persistence or external calls?"
        ),
        "Which modules are high-risk or owner-reviewed before changes merge?",
        "What command set should pass before opening a pull request?",
    ]
    if stack_names:
        questions.append(
            f"Which detected stack pieces are most central to this project: "
            f"{', '.join(stack_names[:4])}?"
        )
    if blockers:
        questions.append(
            "Who owns the missing setup or test documentation surfaced by this guide?"
        )
    if result.caveats:
        questions.append(
            "Which Atlas caveats are known limitations versus real documentation gaps?"
        )
    return questions[:6]


def _pick_paths(paths: set[str], needles: list[str]) -> list[str]:
    matches = [
        path for path in sorted(paths)
        if any(needle in path.lower() for needle in needles)
    ]
    return matches


def _overview(repo_label: str | None, stack_names: list[str], confidence: float | None) -> str:
    subject = repo_label or "this repository"
    stack = ", ".join(stack_names[:4]) if stack_names else "the detected project structure"
    if confidence is None:
        confidence_text = (
            "Atlas did not attach a confidence score, so verify the path with a maintainer."
        )
    elif confidence >= 0.85:
        confidence_text = "Atlas confidence is high enough to use this as a practical first pass."
    elif confidence >= 0.65:
        confidence_text = (
            "Atlas confidence is moderate, so confirm important boundaries before editing."
        )
    else:
        confidence_text = (
            "Atlas confidence is low, so treat this as orientation rather than authority."
        )
    return f"Use this guide to understand {subject} through {stack}. {confidence_text}"
