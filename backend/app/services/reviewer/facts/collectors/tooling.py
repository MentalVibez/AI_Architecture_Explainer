"""
Detects tooling presence from the file tree — populates ToolingFacts boolean flags.
"""
from pathlib import Path
from ..models import RepoFacts

README_NAMES = {"README.md", "README.rst", "README.txt", "README"}
LICENSE_NAMES = {"LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE"}
ENV_EXAMPLE_NAMES = {".env.example", ".env.sample", ".env.template"}
LOCKFILE_NAMES = {
    "requirements.txt", "poetry.lock", "Pipfile.lock",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
}
CI_DIRS = {".github/workflows", ".circleci"}
CI_FILES = {".gitlab-ci.yml", "Jenkinsfile"}


def collect(facts: RepoFacts, repo_path: str) -> None:
    files_set = set(facts.structure.files)
    basenames = {Path(f).name for f in files_set}
    dirs_set = set(facts.structure.directories)

    facts.tooling.has_readme = bool(README_NAMES & basenames)
    facts.tooling.has_license = bool(LICENSE_NAMES & basenames)
    facts.tooling.has_env_example = bool(ENV_EXAMPLE_NAMES & basenames)
    facts.tooling.has_lockfile = bool(LOCKFILE_NAMES & basenames)
    facts.tooling.has_dockerfile = "Dockerfile" in basenames
    facts.tooling.has_github_actions = ".github/workflows" in dirs_set
    facts.tooling.has_ci = (
        any(ci in dirs_set for ci in CI_DIRS)
        or any(ci in basenames for ci in CI_FILES)
    )
    facts.tooling.has_tests = (
        any("test" in d.lower() or "spec" in d.lower() for d in dirs_set)
        or any(f.startswith("tests/") or f.startswith("test/") for f in files_set)
    )
    facts.tooling.has_linter = (
        bool({"ruff.toml", ".ruff.toml", ".eslintrc", ".eslintrc.js", ".eslintrc.json"} & basenames)
        or _pyproject_has(facts, "ruff")
    )
    facts.tooling.has_formatter = (
        bool({".prettierrc", ".prettierrc.json", "prettier.config.js"} & basenames)
        or _pyproject_has(facts, "black")
    )
    facts.tooling.has_type_checker = (
        bool({"mypy.ini", ".mypy.ini", "pyrightconfig.json"} & basenames)
        or _pyproject_has(facts, "mypy")
        or _pyproject_has(facts, "pyright")
    )


def _pyproject_has(facts: RepoFacts, tool: str) -> bool:
    return bool(facts.manifests.pyproject_toml and tool in str(facts.manifests.pyproject_toml))
