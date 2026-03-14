"""Deterministically parses manifest files to extract dependency information."""
import json
from typing import Any


def parse_package_json(content: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}

    deps = {
        **data.get("dependencies", {}),
        **data.get("devDependencies", {}),
        **data.get("peerDependencies", {}),
    }
    return {
        "name": data.get("name"),
        "description": data.get("description"),
        "scripts": list(data.get("scripts", {}).keys()),
        "dependencies": list(deps.keys()),
    }


def parse_requirements_txt(content: str) -> list[str]:
    packages = []
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("-"):
            pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0].strip()
            if pkg:
                packages.append(pkg.lower())
    return packages


def parse_pyproject_toml(content: str) -> dict[str, Any]:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    try:
        data = tomllib.loads(content)
    except Exception:
        return {}

    project = data.get("project", {})
    deps_raw = project.get("dependencies", [])
    deps = [d.split("[")[0].split(">=")[0].split("==")[0].strip().lower() for d in deps_raw]

    return {
        "name": project.get("name"),
        "dependencies": deps,
    }
