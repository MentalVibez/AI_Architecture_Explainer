"""
Parses manifest files: pyproject.toml, requirements.txt, package.json, Dockerfile.
"""
import json
from pathlib import Path
from ..models import RepoFacts

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


def collect(facts: RepoFacts, repo_path: str) -> None:
    root = Path(repo_path)

    pyproject = root / "pyproject.toml"
    if pyproject.exists() and tomllib:
        try:
            facts.manifests.pyproject_toml = tomllib.loads(pyproject.read_text())
        except Exception:
            pass

    req_txt = root / "requirements.txt"
    if req_txt.exists():
        try:
            facts.manifests.requirements_txt = [
                l.strip() for l in req_txt.read_text().splitlines()
                if l.strip() and not l.startswith("#")
            ]
        except Exception:
            pass

    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            facts.manifests.package_json = json.loads(pkg_json.read_text())
        except Exception:
            pass

    dockerfile = root / "Dockerfile"
    if dockerfile.exists():
        try:
            facts.manifests.dockerfile = dockerfile.read_text(errors="ignore")
        except Exception:
            pass
