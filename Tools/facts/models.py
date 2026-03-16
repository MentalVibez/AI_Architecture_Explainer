from pydantic import BaseModel, Field
from typing import Any


class FileMetric(BaseModel):
    path: str
    line_count: int
    size_bytes: int


class RepoStructure(BaseModel):
    files: list[str] = Field(default_factory=list)
    directories: list[str] = Field(default_factory=list)
    max_depth: int = 0


class LanguageFacts(BaseModel):
    primary: list[str] = Field(default_factory=list)
    by_file_count: dict[str, int] = Field(default_factory=dict)


class ManifestFacts(BaseModel):
    pyproject_toml: dict[str, Any] | None = None
    requirements_txt: list[str] | None = None
    package_json: dict[str, Any] | None = None
    dockerfile: str | None = None
    docker_compose: dict[str, Any] | None = None


class ToolingFacts(BaseModel):
    has_ci: bool = False
    has_tests: bool = False
    has_linter: bool = False
    has_formatter: bool = False
    has_type_checker: bool = False
    has_lockfile: bool = False
    has_env_example: bool = False
    has_readme: bool = False
    has_license: bool = False
    has_dockerfile: bool = False
    has_github_actions: bool = False


class MetricFacts(BaseModel):
    large_files: list[FileMetric] = Field(default_factory=list)
    file_metrics: dict[str, FileMetric] = Field(default_factory=dict)
    test_file_count: int = 0
    source_file_count: int = 0
    router_file_count: int = 0
    total_file_count: int = 0


class AtlasContext(BaseModel):
    frameworks: list[str] = Field(default_factory=list)
    architecture_shape: str = "unknown"
    confidence: float = 0.0


class ToolIssue(BaseModel):
    tool: str
    external_id: str
    severity: str
    message: str
    file: str | None = None
    line: int | None = None
    rule_code: str | None = None


class ToolResults(BaseModel):
    ruff: list[ToolIssue] = Field(default_factory=list)
    bandit: list[ToolIssue] = Field(default_factory=list)
    mypy: list[ToolIssue] = Field(default_factory=list)
    eslint: list[ToolIssue] = Field(default_factory=list)
    npm_audit: list[ToolIssue] = Field(default_factory=list)
    gitleaks: list[ToolIssue] = Field(default_factory=list)
    hadolint: list[ToolIssue] = Field(default_factory=list)
    actionlint: list[ToolIssue] = Field(default_factory=list)


class RepoFacts(BaseModel):
    """
    Central fact store. Populated once by collectors.
    Treated as read-only during rule evaluation.
    """
    repo_url: str
    commit: str = ""
    structure: RepoStructure = Field(default_factory=RepoStructure)
    languages: LanguageFacts = Field(default_factory=LanguageFacts)
    manifests: ManifestFacts = Field(default_factory=ManifestFacts)
    tooling: ToolingFacts = Field(default_factory=ToolingFacts)
    metrics: MetricFacts = Field(default_factory=MetricFacts)
    atlas_context: AtlasContext = Field(default_factory=AtlasContext)
    tool_results: ToolResults = Field(default_factory=ToolResults)
