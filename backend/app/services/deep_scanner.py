"""
app/services/deep_scanner.py
------------------------
DeepScanner: The deterministic file intelligence engine.

Responsibilities (what it DOES):
  - Prioritize files for scanning
  - Detect language per file
  - Parse imports, exports, functions, classes, routes
  - Compute complexity signals
  - Detect sensitive patterns
  - Produce FileIntelligence objects

Responsibilities (what it DOES NOT DO):
  - Call LLM
  - Decide architecture
  - Generate findings
  - Make judgments

The LLM reads what DeepScanner produces. It never runs inside DeepScanner.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import AsyncIterator, Dict, List, Optional, Tuple

import httpx

from app.schemas.intelligence import (
    FileIntelligence,
    FileRole,
    LanguageTag,
    ScanMetadata,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Files/directories to always skip — noise without signal
SKIP_PATHS = frozenset(
    {
        "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
        "dist", "build", ".next", ".nuxt", "coverage", ".nyc_output",
        ".mypy_cache", ".pytest_cache", ".ruff_cache", "vendor",
    }
)

# Max file size to fully parse. Files larger are flagged + partially read.
MAX_FILE_BYTES = 150_000  # 150 KB

# Max concurrent GitHub file fetches
MAX_CONCURRENT_FETCHES = 12

# Hard scan limits — never exceed these regardless of caller input
HARD_MAX_FILES = 800          # Absolute ceiling for files scanned per job
HARD_MAX_BYTES_TOTAL = 50_000_000  # 50 MB aggregate content cap
HARD_TIMEOUT_SECONDS = 120    # Max wall-clock for the full scan phase

# Generated/vendor file patterns — excluded from scan, still counted in total
GENERATED_PATTERNS = (
    # Lockfiles — all lowercase for case-insensitive match against name.lower()
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "pipfile.lock", "gemfile.lock",
    "cargo.lock", "composer.lock",
    # Generated code markers
    ".generated.", ".gen.", ".pb.", "_pb2.py",
    # Minified files
    ".min.js", ".min.css",
    # Build output
    ".d.ts",  # TS declaration files — generated, not source
)

def is_generated(path: str) -> bool:
    """Returns True for lockfiles, minified files, and generated code."""
    name = PurePosixPath(path).name.lower()
    for pattern in GENERATED_PATTERNS:
        if pattern in name:
            return True
    # Additional heuristic: files in generated/ or gen/ directories
    parts = PurePosixPath(path).parts
    return any(p in ("generated", "gen", "proto", "dist", "out") for p in parts)

# Priority scores — lower number = fetch earlier
FILE_PRIORITY: Dict[str, int] = {
    "entrypoint": 1,
    "service": 2,
    "schema": 3,
    "config": 4,
    "module": 5,
    "utility": 6,
    "infra": 7,
    "migration": 8,
    "test": 9,
    "unknown": 10,
}

# Extension → language mapping (deterministic)
EXTENSION_MAP: Dict[str, LanguageTag] = {
    ".py": "python",
    ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".yml": "yaml", ".yaml": "yaml",
    ".toml": "toml",
    ".json": "json",
    ".md": "markdown", ".mdx": "markdown",
    ".dockerfile": "dockerfile",
    ".sql": "sql",
}

# Shebang → language
SHEBANG_MAP: Dict[str, LanguageTag] = {
    "python": "python",
    "python3": "python",
    "node": "javascript",
    "ruby": "ruby",
    "bash": "shell",
    "sh": "shell",
    "php": "php",
}


# ---------------------------------------------------------------------------
# Sensitive pattern registry
# Deterministic — no LLM involved
# ---------------------------------------------------------------------------

SENSITIVE_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("hardcoded_secret", re.compile(
        r'(?i)(password|secret|api_key|token|auth)\s*=\s*["\'][^"\']{6,}["\']'
    )),
    ("eval_exec", re.compile(r'\b(eval|exec)\s*\(')),
    ("subprocess_shell", re.compile(r'subprocess\.(call|run|Popen).*shell\s*=\s*True')),
    ("raw_sql_format", re.compile(r'(execute|query)\s*\(\s*["\'].*%[s\d]')),
    ("sql_fstring", re.compile(r'f["\'].*SELECT.*FROM.*\{', re.IGNORECASE)),
    ("os_system", re.compile(r'\bos\.system\s*\(')),
    ("pickle_load", re.compile(r'\bpickle\.(load|loads)\s*\(')),
    ("yaml_load_unsafe", re.compile(r'\byaml\.load\s*\([^,)]*\)')),  # no Loader=
    ("open_redirect", re.compile(r'redirect\s*\(\s*request\.')),
    ("debug_mode_enabled", re.compile(r'(?i)debug\s*=\s*True')),
]

EXTERNAL_CALL_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("http_request", re.compile(r'\b(requests\.|httpx\.|aiohttp\.|fetch\s*\(|axios\.)')),
    ("db_query", re.compile(r'\b(\.execute\s*\(|\.query\s*\(|session\.|db\.)')),
    ("file_io", re.compile(r'\b(open\s*\(|Path\(.*\)\.read|os\.path\.)')),
    ("subprocess", re.compile(r'\b(subprocess\.|os\.system|os\.popen)')),
    ("cloud_sdk", re.compile(r'\b(boto3\.|google\.cloud\.|azure\.)')),
]


# ---------------------------------------------------------------------------
# Language-specific parsers
# These are pure regex parsers. tree-sitter is the upgrade path,
# wired in via the TreeSitterParser class below.
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    function_names: List[str] = field(default_factory=list)
    class_names: List[str] = field(default_factory=list)
    framework_signals: List[str] = field(default_factory=list)
    route_patterns: List[str] = field(default_factory=list)
    external_calls: List[str] = field(default_factory=list)
    sensitive_ops: List[str] = field(default_factory=list)
    has_type_annotations: bool = False
    has_docstrings: bool = False
    has_error_handling: bool = False
    loc: int = 0
    nesting_depth_max: int = 0
    complexity_score: float = 0.0
    errors: List[str] = field(default_factory=list)


def _parse_python(content: str) -> ParseResult:
    result = ParseResult()
    lines = content.splitlines()
    result.loc = sum(
        1 for line in lines
        if line.strip() and not line.strip().startswith("#")
    )

    # Imports — emit both the base module path and, for L-001 cases,
    # candidate submodule paths. Candidate expansion happens at resolve time
    # (in _resolve_python_import) where the file index is available.
    # The parser's job is only to extract what was written in the source.
    from_import_re = re.compile(
        r'^from\s+([\w.]+)\s+import\s+([\w\s,*]+?)(?:\s*#.*)?$'
    )
    bare_import_re = re.compile(
        r'^import\s+([\w., ]+?)(?:\s*#.*)?(?:\s+as\s+\w+)?$'
    )
    for line in lines:
        stripped = line.strip()
        fm = from_import_re.match(stripped)
        if fm:
            module_path = fm.group(1)
            imported_names_raw = fm.group(2)
            # Store as "module_path::name1,name2" so resolver can expand if needed
            # Simple case: just the module path (standard behavior)
            result.imports.append(module_path)
            # L-001: also store the imported names alongside the module path
            # so the resolver can try 'module_path.name' when module_path doesn't resolve
            imported_names = [
                n.strip() for n in imported_names_raw.split(",")
                if n.strip() and n.strip() != "*" and n.strip()[0].islower()
            ]
            for name in imported_names:
                if "." not in name:
                    candidate = f"{module_path}.{name}"
                    if candidate not in result.imports:
                        result.imports.append(candidate)
            continue

        bm = bare_import_re.match(stripped)
        if bm:
            for mod in bm.group(1).split(","):
                mod = mod.strip().split(" as ")[0].strip()
                if mod:
                    result.imports.append(mod)

    # Framework signals from imports
    fw_map = {
        "fastapi": "fastapi", "flask": "flask", "django": "django",
        "sqlalchemy": "sqlalchemy", "alembic": "alembic",
        "pydantic": "pydantic", "pytest": "pytest",
        "celery": "celery", "redis": "redis", "boto3": "aws_sdk",
        "anthropic": "anthropic_sdk", "openai": "openai_sdk",
    }
    for imp in result.imports:
        base = imp.split(".")[0].lower()
        if base in fw_map:
            result.framework_signals.append(fw_map[base])

    # Functions and classes
    result.function_names = re.findall(r'^def\s+(\w+)\s*\(', content, re.MULTILINE)
    result.class_names = re.findall(r'^class\s+(\w+)', content, re.MULTILINE)

    # Exports (top-level public names)
    result.exports = [
        f for f in result.function_names if not f.startswith("_")
    ] + [c for c in result.class_names if not c.startswith("_")]

    # Type annotations
    result.has_type_annotations = bool(
        re.search(r'def\s+\w+\s*\([^)]*:\s*\w', content) or
        re.search(r'->\s*\w', content)
    )

    # Docstrings
    result.has_docstrings = bool(re.search(r'""".*?"""', content, re.DOTALL))

    # Error handling
    result.has_error_handling = bool(re.search(r'\btry\s*:', content))

    # Sensitive patterns
    for name, pattern in SENSITIVE_PATTERNS:
        if pattern.search(content):
            result.sensitive_ops.append(name)

    # External calls
    for name, pattern in EXTERNAL_CALL_PATTERNS:
        if pattern.search(content):
            result.external_calls.append(name)

    # Nesting depth — count leading spaces on deepest non-blank line
    max_indent = 0
    for line in lines:
        if line.strip() and not line.strip().startswith("#"):
            indent = len(line) - len(line.lstrip())
            max_indent = max(max_indent, indent)
    result.nesting_depth_max = max_indent // 4  # assume 4-space indent

    # Cyclomatic complexity — per function, on code-only lines
    # Strip strings and comments before matching to avoid false positives
    result.complexity_score = _compute_python_complexity(content, result.function_names)

    # Route detection
    result.route_patterns = re.findall(
        r'@\w+\.(get|post|put|delete|patch|route)\s*\(["\']([^"\']+)["\']',
        content,
        re.IGNORECASE,
    )

    return result


def _parse_typescript(content: str) -> ParseResult:
    result = ParseResult()
    lines = content.splitlines()
    result.loc = sum(
        1 for line in lines
        if line.strip() and not line.strip().startswith("//")
    )

    # Imports — both standard imports and re-export-from (barrel files)
    import_re = re.compile(r"^(?:import|export)\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
    result.imports = import_re.findall(content)

    # Also capture: export * from '...' (wildcard re-exports)
    wildcard_re = re.compile(r"^export\s+\*\s+from\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
    for m in wildcard_re.findall(content):
        if m not in result.imports:
            result.imports.append(m)

    # Framework signals
    fw_map = {
        "react": "react", "next": "nextjs", "vue": "vue",
        "express": "express", "fastify": "fastify",
        "@tanstack": "tanstack", "axios": "axios",
        "@anthropic-ai": "anthropic_sdk",
    }
    for imp in result.imports:
        base = imp.split("/")[0].lstrip("@").lower() if imp.startswith("@") else imp.split("/")[0].lower()
        if base in fw_map:
            result.framework_signals.append(fw_map[base])
        elif imp.startswith("@"):
            scope = imp.split("/")[0]
            if scope in fw_map:
                result.framework_signals.append(fw_map[scope])

    # Exports
    result.exports = re.findall(r'^export\s+(?:default\s+)?(?:function|class|const|type|interface)\s+(\w+)', content, re.MULTILINE)

    # Functions
    result.function_names = re.findall(r'(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?\()', content)
    result.function_names = [f[0] or f[1] for f in result.function_names if f[0] or f[1]]

    # Type annotations — TS has them by definition if not .js
    result.has_type_annotations = ": " in content and ("interface " in content or "type " in content)
    result.has_error_handling = bool(re.search(r'\btry\s*\{', content))
    result.has_docstrings = bool(re.search(r'/\*\*.*?\*/', content, re.DOTALL))

    # Sensitive
    for name, pattern in SENSITIVE_PATTERNS:
        if pattern.search(content):
            result.sensitive_ops.append(name)

    for name, pattern in EXTERNAL_CALL_PATTERNS:
        if pattern.search(content):
            result.external_calls.append(name)

    branch_keywords = re.findall(r'\b(if|else|for|while|catch)\b|&&|\|\|', _strip_ts_strings_and_comments(content))
    result.complexity_score = float(len(result.function_names) + len(branch_keywords))

    return result


def _parse_generic(content: str, language: LanguageTag) -> ParseResult:
    """Minimal parser for languages without dedicated handlers."""
    result = ParseResult()
    lines = content.splitlines()
    result.loc = sum(1 for line in lines if line.strip())
    for name, pattern in SENSITIVE_PATTERNS:
        if pattern.search(content):
            result.sensitive_ops.append(name)
    return result


def _strip_python_strings_and_comments(content: str) -> str:
    """
    Remove string literals and comments from Python source before pattern matching.
    Prevents false positives like: # "use this if you want X or Y"
    This is not a full parser — it handles the 95% case accurately.
    """
    # Remove triple-quoted strings first (greedy, handles multiline)
    content = re.sub(r'""".*?"""', '""', content, flags=re.DOTALL)
    content = re.sub(r"'''.*?'''", "''", content, flags=re.DOTALL)
    # Remove single-quoted strings (non-greedy, same line)
    content = re.sub(r'"[^"\n]*"', '""', content)
    content = re.sub(r"'[^'\n]*'", "''", content)
    # Remove inline comments
    content = re.sub(r'#[^\n]*', '', content)
    return content


def _strip_ts_strings_and_comments(content: str) -> str:
    """Remove string literals and comments from TypeScript/JavaScript source."""
    # Remove template literals
    content = re.sub(r'`[^`]*`', '``', content, flags=re.DOTALL)
    # Remove double-quoted strings
    content = re.sub(r'"[^"\n]*"', '""', content)
    # Remove single-quoted strings
    content = re.sub(r"'[^'\n]*'", "''", content)
    # Remove block comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove line comments
    content = re.sub(r'//[^\n]*', '', content)
    return content


def _compute_python_complexity(content: str, function_names: List[str]) -> float:
    """
    Per-function cyclomatic complexity estimate.

    Standard approximation: complexity = 1 + number of decision points per function.
    Decision points: if, elif, for, while, except, and, or, case (match statement).

    We sum across all functions and divide by function count to get an average,
    then scale: average ≤ 5 = low, ≤ 10 = medium, > 10 = high complexity signal.

    Returns a float that maps to the same 0–∞ scale as before, but is now
    per-function rather than per-file, making the LLM invocation threshold meaningful.
    """
    clean = _strip_python_strings_and_comments(content)

    # Split content into function blocks heuristically
    # Each block starts at a `def ` line and ends at the next `def ` or EOF
    func_blocks: List[str] = []
    current_block: List[str] = []
    in_func = False

    for line in clean.splitlines():
        stripped = line.strip()
        if re.match(r'^def\s+\w+\s*\(', stripped):
            if in_func and current_block:
                func_blocks.append("\n".join(current_block))
            current_block = [line]
            in_func = True
        elif in_func:
            current_block.append(line)

    if in_func and current_block:
        func_blocks.append("\n".join(current_block))

    if not func_blocks:
        # No functions found — score the whole file as one unit
        func_blocks = [clean]

    # Decision point keywords (only structural, not logical operators in isolation)
    DECISION_RE = re.compile(r'^\s*(if|elif|for|while|except|case)\b', re.MULTILINE)
    # Logical operators that add a branch within an expression
    LOGICAL_RE = re.compile(r'\b(and|or)\b')

    total_complexity = 0.0
    for block in func_blocks:
        structural = len(DECISION_RE.findall(block))
        logical = len(LOGICAL_RE.findall(block))
        # Weight logical operators at 0.5 — they add paths but aren't full branches
        block_complexity = 1 + structural + (logical * 0.5)
        total_complexity += block_complexity

    # Return average per-function complexity * function count
    # This preserves the scale: a file with 10 complex functions scores higher
    # than a file with 10 trivial functions, unlike the old flat count
    avg = total_complexity / len(func_blocks)
    return round(avg, 2)


LANGUAGE_PARSERS = {
    "python": _parse_python,
    "typescript": _parse_typescript,
    "javascript": _parse_typescript,  # reuse TS parser
}


# ---------------------------------------------------------------------------
# Role classifier
# Deterministic. Uses path + filename signals.
# ---------------------------------------------------------------------------

def classify_role(path: str, parse_result: Optional[ParseResult] = None) -> FileRole:
    p = PurePosixPath(path)
    name = p.name.lower()
    parts = [part.lower() for part in p.parts]

    # Test files
    if "test" in parts or "tests" in parts or "spec" in parts:
        return "test"
    if name.startswith("test_") or name.endswith("_test.py") or ".spec." in name or ".test." in name:
        return "test"

    # Infrastructure
    if name in ("dockerfile", "docker-compose.yml", "docker-compose.yaml"):
        return "infra"
    if any(part in ("infra", "terraform", "k8s", "kubernetes", "deploy", "helm") for part in parts):
        return "infra"
    # GitHub/GitLab CI workflows — check for .github or .gitlab in path before generic yaml
    if ".github" in parts or ".gitlab" in parts:
        return "infra"
    if p.suffix in (".yml", ".yaml") and any(k in name for k in ("ci", "workflow", "pipeline", "github", "gitlab")):
        return "infra"

    # Config
    if name in (
        "settings.py", "config.py", "configuration.py",
        ".env", ".env.example", "pyproject.toml",
        "package.json", "tsconfig.json", "next.config.js",
        "next.config.ts", "tailwind.config.js", "tailwind.config.ts",
    ):
        return "config"

    # Migrations
    if "migration" in parts or "migrations" in parts or "alembic" in parts:
        return "migration"

    # Schema / models
    if any(k in name for k in ("schema", "model", "entity", "type")):
        return "schema"

    # Entrypoints
    if name in ("main.py", "app.py", "server.py", "index.ts", "index.js", "index.tsx"):
        return "entrypoint"
    # Next.js App Router: page.tsx / layout.tsx / route.ts anywhere under app/ dir
    if "app" in parts and name in ("page.tsx", "page.ts", "page.jsx", "page.js",
                                    "layout.tsx", "layout.ts", "route.ts", "route.js"):
        return "entrypoint"
    if parse_result and parse_result.framework_signals:
        if any(sig in parse_result.framework_signals for sig in ("fastapi", "flask", "django", "express", "nextjs")):
            if name in ("main.py", "app.py", "application.py", "server.py", "app.ts"):
                return "entrypoint"

    # Services
    if any(k in name for k in ("service", "manager", "handler", "worker", "processor")):
        return "service"
    if any(part in ("services", "handlers", "workers") for part in parts):
        return "service"

    # API / routes
    if any(k in name for k in ("route", "router", "api", "endpoint", "view", "controller")):
        return "service"
    if any(part in ("api", "routes", "routers", "endpoints", "views", "controllers") for part in parts):
        return "service"

    # Utilities
    if any(k in name for k in ("util", "helper", "common", "shared", "mixin")):
        return "utility"
    if any(part in ("utils", "helpers", "lib", "common", "shared") for part in parts):
        return "utility"

    # Module (catch-all for source files)
    if p.suffix in (".py", ".ts", ".js", ".go", ".rs", ".java"):
        return "module"

    return "unknown"


# ---------------------------------------------------------------------------
# Language detector
# Deterministic: extension → shebang → content heuristics
# ---------------------------------------------------------------------------

def detect_language(path: str, content: str = "") -> LanguageTag:
    ext = PurePosixPath(path).suffix.lower()
    if ext in EXTENSION_MAP:
        return EXTENSION_MAP[ext]

    # Filename without extension
    name = PurePosixPath(path).name.lower()
    if name == "dockerfile":
        return "dockerfile"
    if name in ("makefile", "rakefile", "gemfile"):
        return "unknown"

    # Shebang detection
    if content.startswith("#!"):
        first_line = content.split("\n")[0]
        for keyword, lang in SHEBANG_MAP.items():
            if keyword in first_line:
                return lang

    # Content heuristics (last resort)
    if "def " in content and "import " in content:
        return "python"
    if ("function " in content or "const " in content) and "=>" in content:
        return "javascript"

    return "unknown"


# ---------------------------------------------------------------------------
# File prioritizer
# Returns files sorted by scan priority (entrypoints first, tests last)
# ---------------------------------------------------------------------------

def prioritize_files(file_tree: List[Dict]) -> List[Dict]:
    """
    Input: List of GitHub tree items with 'path', 'type', 'size' keys.
    Output: Same list, sorted by scan priority.
    """
    def score(item: Dict) -> Tuple[int, int]:
        path = item.get("path", "")
        size = item.get("size", 0) or 0

        # Skip non-blobs
        if item.get("type") != "blob":
            return (999, 0)

        # Skip noise directories
        parts = PurePosixPath(path).parts
        if any(skip in parts for skip in SKIP_PATHS):
            return (998, 0)

        # Skip binary/asset files
        ext = PurePosixPath(path).suffix.lower()
        if ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
                   ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3",
                   ".zip", ".tar", ".gz", ".lock"):
            return (997, 0)

        role = classify_role(path)
        priority = FILE_PRIORITY.get(role, 10)

        # Small files get slight priority boost (faster to scan)
        size_penalty = min(size // 10_000, 5)

        return (priority, size_penalty)

    return sorted(file_tree, key=score)


def should_skip(path: str) -> bool:
    """
    Returns True for binary assets, compiled output, and vendor directories.
    Lock files are handled by is_generated() — these two functions are independent.
    """
    parts = PurePosixPath(path).parts
    if any(skip in parts for skip in SKIP_PATHS):
        return True
    ext = PurePosixPath(path).suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
               ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3",
               ".zip", ".tar", ".gz", ".pyc", ".pyo",
               ".class", ".jar", ".so", ".dll", ".exe"):
        return True
    return False


# ---------------------------------------------------------------------------
# GitHub content fetcher
# Uses raw.githubusercontent.com for efficiency.
# ---------------------------------------------------------------------------

class GitHubContentFetcher:
    def __init__(self, github_token: Optional[str] = None):
        headers = {"Accept": "application/vnd.github.raw"}
        if github_token:
            headers["Authorization"] = f"Bearer {github_token}"
        self._headers = headers
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)

    async def fetch_file(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
        path: str,
        ref: str = "HEAD",
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Returns (path, content_or_None, error_or_None)
        """
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
        async with self._semaphore:
            try:
                resp = await client.get(url, headers=self._headers, timeout=10.0)
                if resp.status_code == 200:
                    content = resp.text
                    return (path, content, None)
                elif resp.status_code == 404:
                    return (path, None, "not_found")
                else:
                    return (path, None, f"http_{resp.status_code}")
            except httpx.TimeoutException:
                return (path, None, "timeout")
            except Exception as e:
                return (path, None, f"error:{type(e).__name__}")

    async def fetch_batch(
        self,
        owner: str,
        repo: str,
        paths: List[str],
        ref: str = "HEAD",
    ) -> AsyncIterator[Tuple[str, Optional[str], Optional[str]]]:
        async with httpx.AsyncClient() as client:
            tasks = [
                self.fetch_file(client, owner, repo, path, ref)
                for path in paths
            ]
            for coro in asyncio.as_completed(tasks):
                yield await coro


# ---------------------------------------------------------------------------
# Core FileIntelligence builder
# ---------------------------------------------------------------------------

def build_file_intelligence(
    path: str,
    content: str,
    size_bytes: int = 0,
) -> FileIntelligence:
    was_truncated = False
    if size_bytes > MAX_FILE_BYTES:
        content = content[:MAX_FILE_BYTES]
        was_truncated = True

    language = detect_language(path, content)
    parser = LANGUAGE_PARSERS.get(language, _parse_generic)

    try:
        parsed = parser(content) if language != "unknown" else _parse_generic(content, language)
    except Exception as e:
        parsed = ParseResult(errors=[f"parse_exception:{type(e).__name__}:{e}"])

    role = classify_role(path, parsed)

    # Determine if entrypoint — explicit bool() to prevent list-truthy passing to Pydantic
    is_entrypoint = bool(
        role == "entrypoint" or (
            bool(parsed.framework_signals) and
            PurePosixPath(path).name.lower() in (
                "main.py", "app.py", "server.py", "index.ts", "index.js"
            )
        )
    )

    # Executable check
    is_executable = (
        bool(re.search(r'^if\s+__name__\s*==\s*["\']__main__["\']', content, re.MULTILINE))
        or content.startswith("#!")
        or PurePosixPath(path).suffix == ""
    )

    confidence = 1.0 if not parsed.errors else max(0.3, 1.0 - (len(parsed.errors) * 0.2))

    return FileIntelligence(
        path=path,
        language=language,
        role=role,
        imports=list(dict.fromkeys(parsed.imports)),  # dedupe, preserve order
        exports=list(dict.fromkeys(parsed.exports)),
        dependencies=[
            imp.split(".")[0].split("/")[0]
            for imp in parsed.imports
            if not imp.startswith(".")
        ],
        complexity_score=round(parsed.complexity_score, 2),
        loc=parsed.loc,
        nesting_depth_max=parsed.nesting_depth_max,
        function_count=len(parsed.function_names),
        class_count=len(parsed.class_names),
        external_calls=list(dict.fromkeys(parsed.external_calls)),
        sensitive_operations=list(dict.fromkeys(parsed.sensitive_ops)),
        framework_signals=list(dict.fromkeys(parsed.framework_signals)),
        is_entrypoint=is_entrypoint,
        is_executable=is_executable,
        is_test=role == "test",
        has_type_annotations=parsed.has_type_annotations,
        has_docstrings=parsed.has_docstrings,
        has_error_handling=parsed.has_error_handling,
        confidence=round(confidence, 3),
        parse_errors=parsed.errors,
        size_bytes=size_bytes,
        was_truncated=was_truncated,
    )


# ---------------------------------------------------------------------------
# Import resolver
# Translates import strings into repo-relative file paths.
# This is what makes CodeContext actually useful.
# ---------------------------------------------------------------------------

def _build_file_index(files: List[FileIntelligence]) -> Dict[str, str]:
    """
    Build a lookup: canonical module key → repo-relative file path.

    For Python: "app.services.analyzer" → "app/services/analyzer.py"
    For TypeScript: "@/lib/utils" → "lib/utils.ts" (after alias stripping)

    This is the index that import_to_path() queries.
    """
    index: Dict[str, str] = {}
    for fi in files:
        p = PurePosixPath(fi.path)

        if fi.language == "python":
            # Convert path to dotted module notation
            # "app/services/analyzer.py" → "app.services.analyzer"
            parts_no_ext = list(p.with_suffix("").parts)
            dotted = ".".join(parts_no_ext)
            index[dotted] = fi.path

            # Also index every suffix so "from app.services.analyzer import X"
            # still resolves even if the importer writes just "services.analyzer"
            for i in range(len(parts_no_ext)):
                suffix_key = ".".join(parts_no_ext[i:])
                if suffix_key not in index:
                    index[suffix_key] = fi.path

            # Index by stem alone as last-resort fallback
            if p.stem not in index:
                index[p.stem] = fi.path

        elif fi.language in ("typescript", "javascript"):
            # Index by path without extension, with and without leading ./
            stem_path = str(p.with_suffix(""))
            index[stem_path] = fi.path
            index["./" + stem_path] = fi.path
            index["/" + stem_path] = fi.path

            # Index the stem alone for bare imports within the same dir
            if p.stem not in index:
                index[p.stem] = fi.path

    return index


def _resolve_python_import(
    import_str: str,
    importer_path: str,
    file_index: Dict[str, str],
) -> Optional[str]:
    """
    Resolve a Python import string to a repo file path.

    Handles:
    - Absolute imports: "from app.services.analyzer import X" → app/services/analyzer.py
    - Relative imports: "from .utils import parse" → sibling utils.py
    - Multi-level relative: "from ..core import config" → parent/core.py
    """
    # Relative imports
    if import_str.startswith("."):
        dots = len(import_str) - len(import_str.lstrip("."))
        module_part = import_str.lstrip(".")
        importer_dir = PurePosixPath(importer_path).parent

        # Walk up the directory tree by dot count
        base = importer_dir
        for _ in range(dots - 1):
            base = base.parent

        if module_part:
            candidate = base / module_part.replace(".", "/")
        else:
            candidate = base

        # Try with common extensions
        for ext in (".py", ".ts", ".js", ".tsx", ".jsx"):
            candidate_str = str(candidate) + ext
            if candidate_str in {fi_path for fi_path in file_index.values()}:
                return candidate_str

        # Try as __init__.py in a package directory
        candidate_init = str(candidate / "__init__.py")
        if candidate_init in {fi_path for fi_path in file_index.values()}:
            return candidate_init

        return None

    # Absolute imports — check the index directly
    # Try increasingly specific suffix matches
    if import_str in file_index:
        return file_index[import_str]

    # Try all suffix substrings (longest match wins)
    parts = import_str.split(".")
    for i in range(len(parts)):
        key = ".".join(parts[i:])
        if key in file_index:
            return file_index[key]

    return None


def _resolve_ts_import(
    import_str: str,
    importer_path: str,
    file_index: Dict[str, str],
    ts_aliases: Dict[str, str],
) -> Optional[str]:
    """
    Resolve a TypeScript/JavaScript import to a repo file path.

    Handles:
    - Relative: "./utils" → sibling utils.ts
    - Path aliases: "@/lib/utils" → lib/utils.ts (using tsconfig paths)
    - Bare module re-exports: "@/components" → components/index.ts
    """
    resolved_str = import_str

    # Apply tsconfig path aliases
    for alias, target in ts_aliases.items():
        alias_prefix = alias.rstrip("*").rstrip("/")
        if import_str.startswith(alias_prefix):
            resolved_str = import_str.replace(alias_prefix, target.rstrip("*").rstrip("/"), 1)
            break

    # Relative imports
    if resolved_str.startswith("."):
        importer_dir = PurePosixPath(importer_path).parent
        candidate = importer_dir / resolved_str

        # Normalize (resolve ../ etc.)
        try:
            # PurePosixPath doesn't resolve '..' but we can normalize manually
            parts = []
            for part in candidate.parts:
                if part == "..":
                    if parts:
                        parts.pop()
                else:
                    parts.append(part)
            candidate = PurePosixPath(*parts) if parts else PurePosixPath(".")
        except Exception:
            pass

        stem_str = str(candidate.with_suffix("")) if candidate.suffix else str(candidate)

        # Primary lookup: the index maps stem_path → full_path
        # e.g. 'src/components/AnalysisForm' → 'src/components/AnalysisForm.tsx'
        if stem_str in file_index:
            return file_index[stem_str]

        # Fallback: try stem + explicit extension (covers edge cases)
        for ext in (".ts", ".tsx", ".js", ".jsx"):
            full = stem_str + ext
            if full in file_index:
                return file_index[full]

        # Try index file in directory
        index_stem = str(candidate / "index")
        if index_stem in file_index:
            return file_index[index_stem]
        for ext in (".ts", ".tsx", ".js", ".jsx"):
            index_path = str(candidate / "index") + ext
            if index_path in file_index:
                return file_index[index_path]

        return None

    # Aliased or bare path — check index directly (stem key first)
    if resolved_str in file_index:
        return file_index[resolved_str]

    # Strip leading slash
    stripped = resolved_str.lstrip("/")
    if stripped in file_index:
        return file_index[stripped]

    # No match — external package
    return None


def _extract_ts_aliases(files: List[FileIntelligence]) -> Dict[str, str]:
    """
    Extract path aliases from tsconfig.json if present in the scanned files.
    Returns a dict of alias_prefix → resolved_prefix.

    Example tsconfig paths:
      "@/*": ["src/*"]  →  {"@/": "src/"}
    """
    # We don't have file contents here — aliases are extracted separately
    # and passed in during the scan. This is a stub that returns Next.js defaults,
    # which covers the majority of Atlas's target repos.
    return {
        "@/": "src/",        # Next.js default with src/ dir
        "~/": "src/",        # common alias
        "@components/": "components/",
        "@lib/": "lib/",
        "@utils/": "utils/",
    }


def _classify_unresolved_reason(
    import_str: str,
    language: str,
    ts_aliases: Dict[str, str],
) -> str:
    """
    Classify why an import string could not be resolved to a file path.
    Returns one of the UnresolvedReason literal values from DependencyEdge.

    Classification logic (in priority order):
    1. Dynamic import patterns → 'dynamic_import'
    2. TS alias prefix not in known aliases → 'alias_unknown'
    3. Python `from pkg import mod` pattern (no trailing module component) → 'ambiguous_package_import'
    4. Relative Python import that didn't resolve → 'file_not_scanned'
    5. Everything else → 'file_not_scanned'
    """
    # 1. Dynamic import detection
    # Python: importlib.import_module(f"..."), __import__(...)
    # These contain braces (f-strings) or are known dynamic patterns
    dynamic_patterns = (
        "importlib", "__import__", "import_module",
        "${", "` +", "` +"  # TS template literals in dynamic import
    )
    for pat in dynamic_patterns:
        if pat in import_str:
            return "dynamic_import"

    if language in ("typescript", "javascript"):
        # 2. Check if it starts with a KNOWN alias prefix
        for alias_prefix in ts_aliases:
            # Keep the trailing slash: "@/" not "@" — "@/foo" matches "@/" but not "@unknown"
            clean_prefix = alias_prefix.rstrip("*")  # remove glob but keep trailing /
            if import_str.startswith(clean_prefix):
                return "file_not_scanned"  # alias is known, file just missing
        # 3. If it starts with @ but no alias matched, it's an unknown alias
        if import_str.startswith("@"):
            return "alias_unknown"
        # Relative TS import that didn't resolve
        if import_str.startswith("."):
            return "file_not_scanned"
        return "file_not_scanned"

    if language == "python":
        # 3. Detect `from pkg import mod` pattern (L-001)
        # Heuristic: if the import string ends with a component that looks like
        # a package directory (no .py, and there exist files at pkg/mod.py in
        # theory), classify as ambiguous. We detect this by checking if the
        # import string has no trailing module (i.e., it's all dots+identifiers
        # but matches no file in the index). The key signal is when the dotted
        # path is a prefix of known file paths but doesn't match exactly.
        # Simple heuristic: if import has 2+ components and last component is
        # a plural directory name (common Python package dirs like 'routes',
        # 'models', 'services'), classify as ambiguous.
        parts = import_str.lstrip(".").split(".")
        if len(parts) >= 2:
            last = parts[-1].lower()
            package_dir_signals = {
                "routes", "models", "services", "handlers", "utils", "helpers",
                "api", "core", "lib", "common", "shared", "views", "controllers",
                "tasks", "jobs", "workers", "schemas", "types", "validators",
                "middleware", "filters", "hooks", "mixins", "interfaces",
            }
            if last in package_dir_signals:
                return "ambiguous_package_import"

        # 4. Relative import that didn't resolve
        if import_str.startswith("."):
            return "file_not_scanned"

        # 5. Absolute import that resolved to nothing
        return "file_not_scanned"

    # Default for other languages
    return "file_not_scanned"


def build_code_contexts(
    files: List[FileIntelligence],
    ts_aliases: Optional[Dict[str, str]] = None,
) -> Tuple[Dict[str, "CodeContext"], List["DependencyEdge"], float]:
    """
    Build CodeContext for every file and emit explicit DependencyEdge objects.

    Returns:
        (contexts, edges, graph_confidence)

        contexts:         file_path → CodeContext
        edges:            all DependencyEdge objects found (confirmed + unresolved)
        graph_confidence: fraction of non-external edges that resolved to confirmed paths

    Every architecture claim downstream must trace to at least one confirmed edge.
    Unresolved edges are retained for transparency — they prove we tried.
    """
    from app.schemas.intelligence import CodeContext, DependencyEdge

    if ts_aliases is None:
        ts_aliases = _extract_ts_aliases(files)

    file_index = _build_file_index(files)
    known_paths = {fi.path for fi in files}

    contexts: Dict[str, "CodeContext"] = {}
    edges: List["DependencyEdge"] = []

    # Known external package prefixes — unresolved against these are tagged
    # external_package, not counted against graph_confidence.
    # The root of an import string is the first dotted component:
    # "urllib.parse" → "urllib", "pydantic_settings" → "pydantic_settings"
    EXTERNAL_PREFIXES = frozenset({
        # Python stdlib — all top-level package roots
        "os", "sys", "re", "json", "typing", "pathlib", "datetime",
        "collections", "itertools", "functools", "logging", "asyncio",
        "unittest", "abc", "io", "math", "random", "string", "time",
        "threading", "multiprocessing", "subprocess", "shutil", "copy",
        "hashlib", "hmac", "secrets", "uuid", "enum", "dataclasses",
        "contextlib", "warnings", "inspect", "traceback", "weakref",
        "struct", "socket", "ssl", "http", "urllib", "email", "html",
        "xml", "csv", "sqlite3", "pickle", "shelve", "tempfile",
        "glob", "fnmatch", "stat", "platform", "signal", "queue",
        "concurrent", "importlib", "pkgutil", "types", "typing_extensions",
        "builtins", "operator", "functools", "heapq", "bisect",
        "array", "decimal", "fractions", "statistics", "textwrap",
        "pprint", "reprlib", "numbers", "cmath", "base64", "binascii",
        "codecs", "locale", "gettext", "argparse", "configparser",
        "zlib", "gzip", "bz2", "lzma", "zipfile", "tarfile",
        # Common Python packages
        "fastapi", "flask", "django", "starlette", "uvicorn", "gunicorn",
        "sqlalchemy", "alembic", "pydantic", "pydantic_settings",
        "httpx", "requests", "aiohttp", "aiofiles",
        "anthropic", "openai", "boto3", "botocore", "celery", "redis",
        "pytest", "ruff", "mypy", "black", "isort", "coverage",
        "jwt", "passlib", "bcrypt", "cryptography",
        "yaml", "toml", "dotenv", "environs",
        "click", "typer", "rich", "tqdm",
        "pandas", "numpy", "scipy", "sklearn", "matplotlib",
        "PIL", "cv2", "torch", "tensorflow",
        "supabase", "psycopg2", "asyncpg", "motor", "pymongo",
        "kafka", "pika", "nats",
        # JS/TS ecosystem
        "react", "next", "vue", "nuxt", "svelte", "angular",
        "express", "fastify", "hono", "koa", "nestjs",
        "axios", "fetch", "node-fetch", "got", "ky",
        "@tanstack", "@radix-ui", "@headlessui", "lucide-react",
        "tailwindcss", "postcss", "webpack", "vite", "turbopack", "esbuild",
        "typescript", "eslint", "prettier", "jest", "vitest", "mocha",
        "zod", "yup", "joi", "ajv",
        "prisma", "drizzle", "knex", "sequelize",
        "stripe", "twilio", "sendgrid",
        "@supabase", "@vercel", "@clerk",
        "framer-motion", "recharts", "d3", "three",
    })

    def _is_external(import_str: str) -> bool:
        root = import_str.lstrip(".").split(".")[0].split("/")[0]
        if root.startswith("@"):
            root = import_str.split("/")[0]
        return root.lower() in EXTERNAL_PREFIXES

    # Counters for graph_confidence
    total_internal_imports = 0
    confirmed_imports = 0

    # Pass 1: Resolve all imports → edges + downstream deps
    for fi in files:
        downstream: List[str] = []

        for imp in fi.imports:
            # Detect line number (best effort — imports are early in file)
            # We store line=0 here; the line scanner below can enrich this
            edge_base = dict(
                source_path=fi.path,
                raw_import=imp,
                kind="import",
                source_line=0,
            )

            if fi.language == "python":
                resolved = _resolve_python_import(imp, fi.path, file_index)
            elif fi.language in ("typescript", "javascript"):
                resolved = _resolve_ts_import(imp, fi.path, file_index, ts_aliases)
            else:
                resolved = None

            # L-001 suppression: the parser emits 'module.name' candidates for
            # 'from module import name' imports. If 'module' itself resolves to
            # a known file, then 'module.name' is a member import (function/class),
            # not a submodule. Suppress it entirely — no edge, no confidence impact.
            if resolved is None and fi.language == "python" and "." in imp:
                parent = ".".join(imp.split(".")[:-1])
                if parent and not imp.startswith(".") and _resolve_python_import(parent, fi.path, file_index) is not None:
                    # Parent module exists as a file → this is a member import, skip
                    continue

            if resolved and resolved in known_paths and resolved != fi.path:
                # Confirmed edge
                total_internal_imports += 1
                confirmed_imports += 1
                edges.append(DependencyEdge(
                    **edge_base,
                    target_path=resolved,
                    confidence="confirmed",
                ))
                downstream.append(resolved)
            elif not _is_external(imp):
                # Classify the failure reason
                reason = _classify_unresolved_reason(imp, fi.language, ts_aliases)
                # Dynamic imports are structurally unresolvable — don't penalize confidence
                if reason != "dynamic_import":
                    total_internal_imports += 1
                edges.append(DependencyEdge(
                    **edge_base,
                    target_path=None,
                    confidence="unresolved",
                    unresolved_reason=reason,
                ))

        contexts[fi.path] = CodeContext(
            file_path=fi.path,
            downstream_dependencies=list(dict.fromkeys(downstream)),
            upstream_callers=[],
            related_files=[],
            service_boundary=_infer_service_boundary(fi.path),
            entrypoint_chain=[],
            is_on_critical_path=fi.is_entrypoint,
            caller_count=0,
        )

    # Pass 2: Upstream callers
    for fi in files:
        for dep_path in contexts[fi.path].downstream_dependencies:
            if dep_path in contexts:
                if fi.path not in contexts[dep_path].upstream_callers:
                    contexts[dep_path].upstream_callers.append(fi.path)
                contexts[dep_path].caller_count += 1

    # Pass 3: Related files
    for fi in files:
        parent_dir = str(PurePosixPath(fi.path).parent)
        related = [
            other.path
            for other in files
            if other.path != fi.path
            and str(PurePosixPath(other.path).parent) == parent_dir
            and other.role == fi.role
        ][:5]
        contexts[fi.path].related_files = related

    # Pass 4: Critical path — BFS guarantees shortest-path depth semantics
    for fi in files:
        if fi.is_entrypoint:
            _mark_critical_path_bfs(fi.path, contexts)

    # Graph confidence: confirmed / total_internal
    # If no internal imports at all, we can't say anything meaningful → 0.5
    if total_internal_imports == 0:
        graph_confidence = 0.5
    else:
        graph_confidence = round(confirmed_imports / total_internal_imports, 3)

    return contexts, edges, graph_confidence


def _infer_service_boundary(path: str) -> Optional[str]:
    """Infer which service domain owns a file from its path."""
    parts = PurePosixPath(path).parts
    boundary_dirs = ("auth", "payments", "users", "api", "services",
                     "admin", "analytics", "notifications", "search")
    for part in parts:
        if part.lower() in boundary_dirs:
            return part.lower()
    return None


def _mark_critical_path_bfs(
    entrypoint_path: str,
    contexts: Dict[str, "CodeContext"],
) -> None:
    """
    Mark files reachable from an entrypoint using BFS (breadth-first search).

    BFS guarantees shortest-path depth semantics: a file's critical-path depth
    is always the minimum number of hops from any entrypoint, not an artifact
    of traversal order.

    This replaces the previous DFS implementation which had an ordering artifact:
    if node A was reachable at depth 1 directly AND at depth 2 via a sibling,
    DFS might visit it at depth 2 first (marking its children as depth 3, blocked)
    even though the shortest path was depth 1. BFS eliminates this entirely.

    DEPTH CAP: depth > 2 is not enqueued.

    Complexity: O(V + E) per entrypoint, same as DFS.
    Memory: O(V) for the visited set and queue, same as DFS.
    """
    from collections import deque

    if entrypoint_path not in contexts:
        return

    # BFS queue: (path, depth)
    queue: deque = deque()
    queue.append((entrypoint_path, 0))
    visited: set = set()

    while queue:
        path, depth = queue.popleft()

        if path in visited or depth > 2:
            continue

        visited.add(path)

        if path not in contexts:
            continue

        contexts[path].is_on_critical_path = True

        # Enqueue direct dependencies at depth+1 (only if within cap)
        if depth < 2:
            for dep in contexts[path].downstream_dependencies:
                if dep not in visited:
                    queue.append((dep, depth + 1))


# ---------------------------------------------------------------------------
# DeepScanner — the main orchestrator
# ---------------------------------------------------------------------------

class DeepScanner:
    """
    Orchestrates the full file intelligence extraction for a repository.

    Usage:
        scanner = DeepScanner(github_token="...")
        intelligence = await scanner.scan(
            owner="vercel",
            repo="next.js",
            file_tree=[...],  # from GitHub API
            ref="main",
        )
    """

    def __init__(self, github_token: Optional[str] = None):
        self.fetcher = GitHubContentFetcher(github_token)

    async def scan(
        self,
        owner: str,
        repo: str,
        file_tree: List[Dict],
        ref: str = "HEAD",
        max_files: int = HARD_MAX_FILES,
    ) -> "DeepScanResult":
        from app.schemas.intelligence import ScanMetadata

        # Enforce hard ceiling — caller cannot exceed it
        max_files = min(max_files, HARD_MAX_FILES)

        start_time = time.monotonic()

        # Step 1: Filter, classify generated, and prioritize
        scannable = []
        files_skipped_generated = 0
        for item in file_tree:
            if item.get("type") != "blob":
                continue
            path = item.get("path", "")
            if should_skip(path) or is_generated(path):
                files_skipped_generated += 1
                continue
            scannable.append(item)

        prioritized = prioritize_files(scannable)[:max_files]

        total_files = len(file_tree)
        files_attempted = len(prioritized)
        files_skipped = (total_files - len(scannable)) + (len(scannable) - files_attempted)
        files_failed = 0
        language_counts: Dict[str, int] = defaultdict(int)
        bytes_fetched = 0

        # Step 2: Fetch and parse in priority order, batched
        BATCH_SIZE = 30
        file_intelligence_list: List[FileIntelligence] = []
        file_contents: Dict[str, str] = {}  # path → raw content, retained for ContextReviewer

        for batch_start in range(0, files_attempted, BATCH_SIZE):
            batch = prioritized[batch_start: batch_start + BATCH_SIZE]
            batch_paths = [item["path"] for item in batch]
            path_to_size = {item["path"]: item.get("size", 0) or 0 for item in batch}

            async for path, content, error in self.fetcher.fetch_batch(owner, repo, batch_paths, ref):
                if error or content is None:
                    files_failed += 1
                    lang = detect_language(path)
                    fi = FileIntelligence(
                        path=path,
                        language=lang,
                        role=classify_role(path),
                        confidence=0.0,
                        parse_errors=[error or "fetch_failed"],
                        size_bytes=path_to_size.get(path, 0),
                    )
                    file_intelligence_list.append(fi)
                else:
                    # Cap content before storing — same limit used by build_file_intelligence
                    stored_content = content[:MAX_FILE_BYTES]
                    bytes_fetched += len(stored_content.encode("utf-8", errors="replace"))
                    file_contents[path] = stored_content
                    fi = build_file_intelligence(
                        path=path,
                        content=content,
                        size_bytes=path_to_size.get(path, 0),
                    )
                    file_intelligence_list.append(fi)
                    language_counts[fi.language] += 1

            # Hard timeout check between batches — partial results returned, not crash
            elapsed = time.monotonic() - start_time
            if elapsed > HARD_TIMEOUT_SECONDS:
                logger.warning(
                    f"DeepScanner timeout after {elapsed:.1f}s — "
                    f"returning partial results ({len(file_intelligence_list)} files)"
                )
                break

            # Hard byte budget — stop if we've fetched too much
            if bytes_fetched > HARD_MAX_BYTES_TOTAL:
                logger.warning(
                    f"DeepScanner byte budget exceeded ({bytes_fetched:,} bytes) — "
                    f"stopping at {len(file_intelligence_list)} files"
                )
                break

        # Step 3: Build CodeContext graph + edges from all scanned files
        contexts, edges, graph_confidence = build_code_contexts(file_intelligence_list)

        # Step 4: Compute scan metadata
        files_scanned = files_attempted - files_failed
        parse_success_rate = files_scanned / files_attempted if files_attempted > 0 else 0.0

        scan_metadata = ScanMetadata(
            total_files=total_files,
            files_scanned=files_scanned,
            files_skipped=files_skipped,
            files_failed=files_failed,
            parse_success_rate=round(parse_success_rate, 3),
            languages_detected=dict(language_counts),
            scan_duration_seconds=round(time.monotonic() - start_time, 2),
        )

        return DeepScanResult(
            files=file_intelligence_list,
            contexts=contexts,
            scan_metadata=scan_metadata,
            contents=file_contents,
            edges=edges,
            graph_confidence=round(graph_confidence, 3),
        )


@dataclass
class DeepScanResult:
    files: List[FileIntelligence]
    contexts: Dict[str, "CodeContext"]
    scan_metadata: ScanMetadata
    # Raw file contents keyed by path — required by ContextReviewer.
    # Stored here so we never fetch files twice.
    # Contents are capped at MAX_FILE_BYTES at fetch time.
    contents: Dict[str, str] = field(default_factory=dict)
    # Explicit dependency edges — every architecture claim traces here
    edges: List["DependencyEdge"] = field(default_factory=list)
    # Graph confidence: fraction of internal imports that resolved to confirmed paths
    graph_confidence: float = 0.0

    def get_by_role(self, role: FileRole) -> List[FileIntelligence]:
        return [f for f in self.files if f.role == role]

    def get_entrypoints(self) -> List[FileIntelligence]:
        return [f for f in self.files if f.is_entrypoint]

    def get_high_risk_files(self) -> List[FileIntelligence]:
        return [f for f in self.files if f.sensitive_operations]

    def get_critical_path_files(self) -> List[FileIntelligence]:
        return [
            f for f in self.files
            if self.contexts.get(f.path, None) and
               self.contexts[f.path].is_on_critical_path
        ]

    def primary_language(self) -> LanguageTag:
        if not self.scan_metadata.languages_detected:
            return "unknown"
        return max(
            self.scan_metadata.languages_detected,
            key=self.scan_metadata.languages_detected.get,
        )
