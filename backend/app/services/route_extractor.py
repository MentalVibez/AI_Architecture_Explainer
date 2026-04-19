"""
Route extractor service.

Without stack profile: guess the framework, parse generically, miss routes.
With stack profile:    know the framework with confidence, use targeted patterns.

Supported frameworks (via detected_stack["backend"]):
  FastAPI  → @app.get / @router.get / APIRouter decorators
  Flask    → @app.route / @blueprint.route
  Express  → app.get / router.get / app.use
  Django   → urls.py path() / re_path() / url()
  Next.js  → export function GET/POST/etc.
  Generic  → broad pattern scan when framework unknown/low confidence
"""
import asyncio
import re
from dataclasses import dataclass, field

from app.services import github_service

# ── Route patterns per framework ─────────────────────────────────────────────

FRAMEWORK_PATTERNS: dict[str, dict] = {
    "fastapi": {
        "file_patterns": [r"\.py$"],
        "route_re": [
            r'@(?:app|router)\.(?P<method>get|post|put|patch|delete|options|head)\s*\(\s*["\'](?P<path>[^"\']+)["\']',
            r'@(?:\w+)\.(?P<method>get|post|put|patch|delete)\s*\(\s*["\'](?P<path>[^"\']+)["\']',
        ],
        "interesting_dirs": ["app", "api", "routes", "routers", "src"],
        "interesting_files": ["main.py", "app.py", "router.py", "routes.py", "api.py"],
    },
    "flask": {
        "file_patterns": [r"\.py$"],
        "route_re": [
            r'@(?:app|bp|\w+)\.route\s*\(\s*["\'](?P<path>[^"\']+)["\'](?:.*?methods\s*=\s*\[(?P<methods>[^\]]+)\])?',
        ],
        "interesting_dirs": ["app", "views", "routes", "blueprints"],
        "interesting_files": ["app.py", "views.py", "routes.py"],
    },
    "express": {
        "file_patterns": [r"\.[jt]s$"],
        "route_re": [
            r'(?:app|router)\.(?P<method>get|post|put|patch|delete|use)\s*\(\s*["\`\'](?P<path>[^"\'`]+)["\`\']',
        ],
        "interesting_dirs": ["routes", "api", "src", "controllers"],
        "interesting_files": ["index.js", "app.js", "server.js", "routes.js"],
    },
    "django": {
        "file_patterns": [r"\.py$"],
        "route_re": [
            r'(?:path|re_path|url)\s*\(\s*["\'](?P<path>[^"\']+)["\']',
        ],
        "interesting_dirs": ["app", "apps", "core"],
        "interesting_files": ["urls.py"],
        "target_files": ["urls.py"],  # always scan any urls.py in the tree
    },
    "nextjs": {
        "file_patterns": [r"\.[jt]sx?$"],
        "route_re": [
            r'export\s+(?:async\s+)?function\s+(?P<method>GET|POST|PUT|PATCH|DELETE)\s*\(',
            r'export\s+(?:const|default)',
        ],
        "interesting_dirs": ["pages/api", "app/api", "src/pages/api"],
        "interesting_files": ["route.ts", "route.js"],
    },
    "generic": {
        "file_patterns": [r"\.(py|js|ts|go|rb|java)$"],
        "route_re": [
            r'(?:GET|POST|PUT|PATCH|DELETE)\s+["\']?(/[^\s"\']+)',
            r'["\']method["\'\s:]+["\'](?P<method>GET|POST|PUT|DELETE|PATCH)["\']',
        ],
        "interesting_dirs": ["routes", "api", "controllers", "handlers"],
        "interesting_files": [],
    },
}

# Normalize common framework name variants to FRAMEWORK_PATTERNS keys
FRAMEWORK_ALIASES: dict[str, str] = {
    "fastapi": "fastapi",
    "flask": "flask",
    "express": "express",
    "expressjs": "express",
    "next.js": "nextjs",
    "nextjs": "nextjs",
    "django": "django",
    "spring": "spring",
    "rails": "rails",
    "ruby on rails": "rails",
}


@dataclass
class RouteEndpoint:
    method: str
    path: str
    source_file: str
    line_number: int | None = None
    handler_name: str | None = None
    params: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Extract path params like {id} or :id
        raw = re.findall(r'\{(\w+)\}|:(\w+)', self.path)
        self.params = [p[0] or p[1] for p in raw]

    @property
    def display(self) -> str:
        return f"{self.method.upper():8} {self.path}"


@dataclass
class EndpointMap:
    repo: str
    framework: str
    framework_confidence: str
    framework_from_profile: bool
    endpoints: list[RouteEndpoint] = field(default_factory=list)
    files_scanned: list[str] = field(default_factory=list)
    parse_strategy: str = "generic"
    warnings: list[str] = field(default_factory=list)


def _normalize_framework(raw: str) -> str:
    return FRAMEWORK_ALIASES.get(raw.lower().strip(), "generic")


def _extract_routes_from_content(
    content: str, framework: str, filepath: str
) -> list[RouteEndpoint]:
    patterns_cfg = FRAMEWORK_PATTERNS.get(framework, FRAMEWORK_PATTERNS["generic"])
    routes: list[RouteEndpoint] = []

    for pattern_str in patterns_cfg["route_re"]:
        try:
            for i, line in enumerate(content.splitlines(), 1):
                match = re.search(pattern_str, line, re.IGNORECASE)
                if match:
                    groups = match.groupdict()
                    path = groups.get("path", "")
                    method = groups.get("method", "ANY")
                    methods_raw = groups.get("methods", "")

                    if not path or len(path) > 200:
                        continue

                    if methods_raw:
                        # Flask-style: methods=['GET', 'POST']
                        for m in re.findall(r"['\"](\w+)['\"]", methods_raw):
                            routes.append(RouteEndpoint(
                                method=m.upper(), path=path,
                                source_file=filepath, line_number=i,
                            ))
                    else:
                        routes.append(RouteEndpoint(
                            method=method.upper() if method else "ANY",
                            path=path, source_file=filepath, line_number=i,
                        ))
        except re.error:
            continue

    # Deduplicate same path+method in same file
    seen: set[tuple[str, str]] = set()
    unique: list[RouteEndpoint] = []
    for r in routes:
        key = (r.method, r.path)
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique


def _select_candidate_paths(tree: list[dict], framework: str) -> list[str]:
    cfg = FRAMEWORK_PATTERNS.get(framework, FRAMEWORK_PATTERNS["generic"])
    interesting_dirs = set(cfg.get("interesting_dirs", []))
    interesting_files = set(cfg.get("interesting_files", []))
    target_files = set(cfg.get("target_files", []))
    file_patterns: list[str] = cfg.get("file_patterns", [])

    candidate_paths: list[str] = []

    for item in tree:
        if item.get("type") != "blob":
            continue
        path: str = item["path"]
        name = path.split("/")[-1]
        parts = path.split("/")

        if name in target_files:
            if path not in candidate_paths:
                candidate_paths.insert(0, path)
            continue

        if len(parts) == 1 and name in interesting_files:
            if path not in candidate_paths:
                candidate_paths.append(path)
            continue

        in_interesting = any(p in interesting_dirs for p in parts[:-1])
        if in_interesting and any(re.search(pat, name) for pat in file_patterns):
            if path not in candidate_paths:
                candidate_paths.append(path)

    # Library-style repos often tuck examples and route demos under tests/examples/docs.
    if len(candidate_paths) < 8:
        for item in tree:
            if item.get("type") != "blob":
                continue
            path = item["path"]
            name = path.split("/")[-1]
            if name not in interesting_files:
                continue
            if path not in candidate_paths:
                candidate_paths.append(path)

    if not candidate_paths:
        broad_dirs = {"tests", "examples", "example", "demo", "docs", "docs_src", "src", "app", "api"}
        for item in tree:
            if item.get("type") != "blob":
                continue
            path = item["path"]
            name = path.split("/")[-1]
            parts = path.split("/")
            if any(re.search(pat, name) for pat in file_patterns) and any(p in broad_dirs for p in parts[:-1]):
                candidate_paths.append(path)

    if not candidate_paths:
        for item in tree:
            if item.get("type") != "blob":
                continue
            path = item["path"]
            name = path.split("/")[-1]
            if "/" not in path and any(re.search(pat, name) for pat in file_patterns):
                candidate_paths.append(path)

    return candidate_paths[:30]


async def extract_endpoints(
    owner: str,
    repo: str,
    framework: str = "generic",
    framework_confidence: str = "speculative",
    from_profile: bool = False,
) -> EndpointMap:
    """
    Main extraction entry point.
    framework + confidence come from the stack profile when available.
    Falls back to generic scan when confidence is low or framework unknown.
    Uses github_service (with GITHUB_TOKEN if configured) instead of raw httpx.
    """
    normalized = _normalize_framework(framework)
    use_framework = normalized
    warnings: list[str] = []

    if framework_confidence in ("speculative", "low") and normalized != "generic":
        warnings.append(
            f"Framework '{framework}' has {framework_confidence} confidence — "
            "using targeted patterns but results may be incomplete"
        )
    if normalized == "generic" or framework.lower() in ("unknown", ""):
        use_framework = "generic"
        if from_profile:
            warnings.append("Framework not determined by stack profile — using broad scan")

    cfg = FRAMEWORK_PATTERNS.get(use_framework, FRAMEWORK_PATTERNS["generic"])
    endpoint_map = EndpointMap(
        repo=f"{owner}/{repo}",
        framework=framework,
        framework_confidence=framework_confidence,
        framework_from_profile=from_profile,
        parse_strategy=use_framework,
        warnings=warnings,
    )

    try:
        async with github_service.create_github_client() as client:
            # Fetch the full recursive tree via github_service (uses GITHUB_TOKEN)
            tree = await github_service.get_repo_tree(owner, repo, client=client)
            candidate_paths = _select_candidate_paths(tree, use_framework)

            # Fetch and parse files concurrently with the same pooled client
            fetch_tasks = [
                github_service.get_file_content(owner, repo, path, client=client)
                for path in candidate_paths
            ]
            file_contents = await asyncio.gather(*fetch_tasks, return_exceptions=True)
    except github_service.GitHubError as exc:
        endpoint_map.warnings.append(f"Could not fetch repo tree: {exc}")
        return endpoint_map

    for path, content in zip(candidate_paths, file_contents, strict=False):
        if isinstance(content, Exception) or not content:
            continue
        endpoint_map.files_scanned.append(path)
        routes = _extract_routes_from_content(content, use_framework, path)
        endpoint_map.endpoints.extend(routes)

    endpoint_map.endpoints.sort(key=lambda r: (r.path, r.method))
    return endpoint_map
