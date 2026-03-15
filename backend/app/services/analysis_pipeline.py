"""Orchestrates the full repo analysis pipeline."""
from typing import Any

from app.services import framework_detector, github_service, manifest_parser

# Files to always attempt to fetch
PRIORITY_FILES = [
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
]


async def run_analysis(owner: str, repo: str) -> dict[str, Any]:
    """Run full analysis pipeline and return structured evidence."""
    metadata = await github_service.get_repo_metadata(owner, repo)
    default_branch = metadata.get("default_branch", "HEAD")

    tree = await github_service.get_repo_tree(owner, repo, default_branch)
    tree_paths = [item["path"] for item in tree if item["type"] == "blob"]

    # Fetch priority files
    file_contents: dict[str, str] = {}
    for path in PRIORITY_FILES:
        if path in tree_paths:
            content = await github_service.get_file_content(owner, repo, path)
            if content:
                file_contents[path] = content

    # Parse manifests
    npm_deps: list[str] = []
    python_deps: list[str] = []

    if "package.json" in file_contents:
        pkg = manifest_parser.parse_package_json(file_contents["package.json"])
        npm_deps = pkg.get("dependencies", [])

    if "requirements.txt" in file_contents:
        python_deps = manifest_parser.parse_requirements_txt(file_contents["requirements.txt"])
    elif "pyproject.toml" in file_contents:
        pyproj = manifest_parser.parse_pyproject_toml(file_contents["pyproject.toml"])
        python_deps = pyproj.get("dependencies", [])

    detected_stack = framework_detector.detect_stack(tree_paths, npm_deps, python_deps)

    return {
        "repo": {"owner": owner, "name": repo, "default_branch": default_branch},
        "detected_stack": detected_stack,
        "npm_dependencies": npm_deps,
        "python_dependencies": python_deps,
        "tree_paths": tree_paths[:200],  # cap for context safety
        "fetched_files": list(file_contents.keys()),
        "readme": file_contents.get("README.md", ""),
    }
