"""Orchestrates the full repo analysis pipeline."""
import logging
from typing import Any

from app.core.config import settings
from app.services import framework_detector, github_service, manifest_parser

logger = logging.getLogger(__name__)

# Filenames to always attempt to fetch (matched by basename, not full path)
PRIORITY_FILENAMES = {
    "README.md",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Dockerfile",
    "docker-compose.yml",
    "vercel.json",
    "next.config.js",
    "next.config.ts",
    "tsconfig.json",
    "main.py",
    "app.py",
    "manage.py",
    "server.js",
    "index.js",
}

# Search for priority files up to this many directory levels deep
_MAX_PRIORITY_DEPTH = 2


async def run_analysis(owner: str, repo: str) -> tuple[dict[str, Any], Any]:
    """
    Run full analysis pipeline.
    Returns (evidence_dict, intel_result|None).
    intel_result is a PipelineResult from intelligence_pipeline.py — caller
    is responsible for persisting it to the DB.
    """
    metadata = await github_service.get_repo_metadata(owner, repo)
    default_branch = metadata.get("default_branch", "HEAD")

    tree = await github_service.get_repo_tree(owner, repo, default_branch)

    # Run the deep intelligence pipeline (non-blocking — errors logged, not raised)
    intel_result = None
    try:
        from app.services.intelligence_pipeline import IntelligencePipeline, PipelineConfig
        _config = PipelineConfig(
            github_token=getattr(settings, "github_token", None),
            anthropic_api_key=settings.anthropic_api_key,
        )
        intel_result = await IntelligencePipeline(_config).run(
            f"https://github.com/{owner}/{repo}", tree, ref=default_branch
        )
        if not intel_result.succeeded:
            logger.warning(
                "Intelligence pipeline incomplete for %s/%s: %s",
                owner, repo, intel_result.stage_errors,
            )
    except Exception:
        logger.exception("Intelligence pipeline failed for %s/%s — continuing without it", owner, repo)

    tree_paths = [item["path"] for item in tree if item["type"] == "blob"]

    # Collect priority file paths: match by basename at depth <= _MAX_PRIORITY_DEPTH
    # This handles monorepos where manifests live in subdirectories (e.g. frontend/package.json)
    priority_paths = [
        p for p in tree_paths
        if p.split("/")[-1] in PRIORITY_FILENAMES and p.count("/") <= _MAX_PRIORITY_DEPTH
    ]

    file_contents: dict[str, str] = {}
    for path in priority_paths:
        content = await github_service.get_file_content(owner, repo, path)
        if content:
            file_contents[path] = content

    # Parse manifests — accumulate across all found instances (monorepo support)
    npm_deps: list[str] = []
    python_deps: list[str] = []

    for path, content in file_contents.items():
        filename = path.split("/")[-1]
        if filename == "package.json":
            pkg = manifest_parser.parse_package_json(content)
            npm_deps = list(dict.fromkeys(npm_deps + pkg.get("dependencies", [])))
        elif filename == "requirements.txt":
            new_deps = manifest_parser.parse_requirements_txt(content)
            python_deps = list(dict.fromkeys(python_deps + new_deps))
        elif filename == "pyproject.toml":
            pyproj = manifest_parser.parse_pyproject_toml(content)
            python_deps = list(dict.fromkeys(python_deps + pyproj.get("dependencies", [])))

    detected_stack = framework_detector.detect_stack(tree_paths, npm_deps, python_deps)

    # Use the shallowest README found (most likely the root one)
    readme_path = min(
        (p for p in file_contents if p.split("/")[-1] == "README.md"),
        key=lambda p: p.count("/"),
        default=None,
    )

    evidence = {
        "repo": {"owner": owner, "name": repo, "default_branch": default_branch},
        "detected_stack": detected_stack,
        "npm_dependencies": npm_deps,
        "python_dependencies": python_deps,
        "tree_paths": tree_paths[:200],  # cap for context safety
        "fetched_files": list(file_contents.keys()),
        "readme": file_contents.get(readme_path, "") if readme_path else "",
    }
    return evidence, intel_result


async def run_stack_analysis(owner: str, repo: str) -> dict[str, Any]:
    """Lightweight variant: fetch tree + detect stack only, no intelligence pipeline.

    Use this for endpoints that need stack/framework info but not full analysis
    (e.g. /api/map). Completes in ~5s vs 60-120s for run_analysis.
    """
    metadata = await github_service.get_repo_metadata(owner, repo)
    default_branch = metadata.get("default_branch", "HEAD")
    tree = await github_service.get_repo_tree(owner, repo, default_branch)
    tree_paths = [item["path"] for item in tree if item["type"] == "blob"]

    priority_paths = [
        p for p in tree_paths
        if p.split("/")[-1] in PRIORITY_FILENAMES and p.count("/") <= _MAX_PRIORITY_DEPTH
    ]

    file_contents: dict[str, str] = {}
    for path in priority_paths:
        content = await github_service.get_file_content(owner, repo, path)
        if content:
            file_contents[path] = content

    npm_deps: list[str] = []
    python_deps: list[str] = []
    for path, content in file_contents.items():
        filename = path.split("/")[-1]
        if filename == "package.json":
            pkg = manifest_parser.parse_package_json(content)
            npm_deps = list(dict.fromkeys(npm_deps + pkg.get("dependencies", [])))
        elif filename == "requirements.txt":
            new_deps = manifest_parser.parse_requirements_txt(content)
            python_deps = list(dict.fromkeys(python_deps + new_deps))
        elif filename == "pyproject.toml":
            pyproj = manifest_parser.parse_pyproject_toml(content)
            python_deps = list(dict.fromkeys(python_deps + pyproj.get("dependencies", [])))

    detected_stack = framework_detector.detect_stack(tree_paths, npm_deps, python_deps)

    return {
        "repo": {"owner": owner, "name": repo, "default_branch": default_branch},
        "detected_stack": detected_stack,
        "npm_dependencies": npm_deps,
        "python_dependencies": python_deps,
        "tree_paths": tree_paths[:200],
        "fetched_files": list(file_contents.keys()),
    }
