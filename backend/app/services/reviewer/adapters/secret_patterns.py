"""
Offline secret pattern scanner. No network dependency. No external binary.

Scans file content for credential patterns using regex.
Category: secrets — contributes to security_augmented depth level.

Design laws:
  - High confidence only for vendor-specific patterns (AWS, GitHub, Stripe, etc.)
  - Medium for generic assignment patterns
  - Allowlist checked FIRST — placeholder values never emit findings
  - .env.example and docs directories suppressed
  - No false positives on test fixtures with obvious dummy values

Signal value:
  Tutorial and weak repos are far more likely to have copied API keys
  from tutorials, committed tokens, or sloppy .env files.
  Strong production repos use pre-commit hooks and CI secret scanning.
  This is one of the cleanest offline separators between the two.
"""
import re
import time
from pathlib import Path

from .base import AdapterResult, AdapterStatus, ToolAdapter, ToolIssue

# ── Patterns ──────────────────────────────────────────────────────────────────

PATTERNS: list[dict] = [
    # Vendor-specific — HIGH confidence (format-constrained)
    {"code": "SECRET-AWS-ACCESS-KEY",    "severity": "critical", "confidence": "high",
     "regex": r"(?<![A-Z0-9])(AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])",
     "message": "Possible AWS access key ID detected"},

    {"code": "SECRET-GITHUB-TOKEN",      "severity": "critical", "confidence": "high",
     "regex": r"gh[pousr]_[A-Za-z0-9]{36}",
     "message": "Possible GitHub personal access token detected"},

    {"code": "SECRET-GITHUB-OAUTH",      "severity": "critical", "confidence": "high",
     "regex": r"gho_[A-Za-z0-9]{36}",
     "message": "Possible GitHub OAuth token detected"},

    {"code": "SECRET-STRIPE-KEY",        "severity": "critical", "confidence": "high",
     "regex": r"sk_live_[0-9a-zA-Z]{24,}",
     "message": "Possible Stripe live secret key detected"},

    {"code": "SECRET-SLACK-TOKEN",       "severity": "high",     "confidence": "high",
     "regex": r"xox[bpsa]-[0-9]{10,13}-[0-9]{10,13}-[0-9a-zA-Z]{24,}",
     "message": "Possible Slack API token detected"},

    {"code": "SECRET-PRIVATE-KEY",       "severity": "critical", "confidence": "high",
     "regex": r"-----BEGIN (RSA|EC|OPENSSH|PGP|DSA) PRIVATE KEY-----",
     "message": "Private key header detected in file"},

    {"code": "SECRET-GOOGLE-API",        "severity": "high",     "confidence": "high",
     "regex": r"AIza[0-9A-Za-z\-_]{35}",
     "message": "Possible Google API key detected"},

    {"code": "SECRET-SENDGRID",          "severity": "high",     "confidence": "high",
     "regex": r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}",
     "message": "Possible SendGrid API key detected"},

    # Generic assignment patterns — MEDIUM confidence (noisy but real signal)
    {"code": "SECRET-HARDCODED-AWS-SECRET", "severity": "high",  "confidence": "medium",
     "regex": r"""(?i)(aws_secret_access_key|aws_secret_key)\s*[=:]\s*["']([A-Za-z0-9/+=]{40})["']""",
     "message": "Possible hardcoded AWS secret access key"},

    {"code": "SECRET-HARDCODED-ASSIGNMENT", "severity": "medium", "confidence": "medium",
     "regex": r"""(?i)(secret_key|api_key|api_secret|auth_token|access_token|private_key)\s*[=:]\s*["']([A-Za-z0-9_\-/+=]{16,80})["']""",
     "message": "Possible hardcoded secret-like assignment detected"},

    {"code": "SECRET-PASSWORD-ASSIGN",   "severity": "medium",  "confidence": "low",
     "regex": r"""(?i)(password|passwd|db_password|database_password)\s*[=:]\s*["']([^"']{8,80})["']""",
     "message": "Possible hardcoded password assignment detected"},
]

# ── Sensitive filenames ───────────────────────────────────────────────────────

SENSITIVE_FILENAMES = {
    ".env", ".env.production", ".env.staging", ".env.local",
    "credentials.json", "service-account.json", "serviceaccount.json",
    "id_rsa", "id_ed25519", "id_ecdsa",
    "secrets.yml", "secrets.yaml",
    "firebase-adminsdk.json",
}

SENSITIVE_EXTENSIONS = {".pem", ".p12", ".pfx", ".key", ".jks", ".cer"}

# ── Allowlist — never emit findings for these ─────────────────────────────────

PLACEHOLDER_PATTERNS = [
    r"your[_-]api[_-]key",
    r"your[_-]secret",
    r"your[_-]token",
    r"changeme",
    r"placeholder",
    r"example[_-]key",
    r"<.*>",                          # template placeholders
    r"\$\{.*\}",                      # shell var references
    r"xxxx",
    r"1234567890",
    r"0000000000",
    r"test[_-]?key",
    r"dummy[_-]?key",
    r"fake[_-]?key",
    r"my[_-]?api[_-]?key",
    r"some[_-]?secret",
    r"insert[_-]?here",
]

PLACEHOLDER_RE = re.compile("|".join(PLACEHOLDER_PATTERNS), re.IGNORECASE)

SKIP_DIRS = {
    "node_modules", ".next", "dist", "build", ".venv", "venv",
    "vendor", "__pycache__", ".git", "coverage", "docs", "doc",
    "tests", "test", "spec", "fixtures", "examples", "__mocks__",
}

# Skip .env.example — it's supposed to have placeholder keys
SKIP_FILENAMES = {
    ".env.example", ".env.sample", ".env.template",
    "README.md", "README.rst", "CHANGELOG.md",
}

MAX_FILE_SIZE_BYTES = 512 * 1024   # skip files > 512KB
MAX_FILES_TO_SCAN = 500            # don't scan every file in huge repos


class SecretPatternsAdapter(ToolAdapter):
    tool_name = "secret_patterns"
    supported_ecosystems = ["all"]
    timeout_seconds = 60

    # Always available — no external binary needed
    def is_available(self) -> bool:
        return True

    def run(self, repo_path: str) -> AdapterResult:
        t0 = time.monotonic()
        issues: list[ToolIssue] = []
        files_scanned = 0
        root = Path(repo_path)

        compiled = [(p, re.compile(p["regex"])) for p in PATTERNS]

        for path in root.rglob("*"):
            if files_scanned >= MAX_FILES_TO_SCAN:
                break
            if not path.is_file():
                continue

            # Skip paths in excluded directories
            parts = set(path.relative_to(root).parts)
            if parts & SKIP_DIRS:
                continue
            if path.name in SKIP_FILENAMES:
                continue

            rel = str(path.relative_to(root))

            # Check for sensitive filenames directly
            if path.name in SENSITIVE_FILENAMES or path.suffix in SENSITIVE_EXTENSIONS:
                # Only flag if it's not in a docs/example directory
                if not any(d in rel.lower() for d in ("doc", "example", "sample", "template")):
                    issues.append(ToolIssue(
                        tool=self.tool_name,
                        rule_code="SECRET-SENSITIVE-FILE",
                        severity="high",
                        message=f"Sensitive file committed to repository: {path.name}",
                        file=rel, line=None, column=None,
                        symbol="sensitive-filename",
                        raw={"filename": path.name},
                        tags=["security", "secrets", "credential", "filename"],
                    ))
                continue

            # Only scan text-like files
            if path.suffix not in {
                ".py", ".js", ".ts", ".tsx", ".jsx", ".rb", ".go", ".rs",
                ".java", ".php", ".cs", ".cpp", ".c", ".h", ".yml", ".yaml",
                ".json", ".toml", ".cfg", ".ini", ".conf", ".sh", ".bash",
                ".env", ".properties", ".xml", ".tf", ".tfvars",
            }:
                continue

            try:
                if path.stat().st_size > MAX_FILE_SIZE_BYTES:
                    continue
                content = path.read_text(errors="ignore")
            except Exception:
                continue

            files_scanned += 1

            for line_num, line in enumerate(content.splitlines(), start=1):
                if PLACEHOLDER_RE.search(line):
                    continue  # allowlisted line

                for pattern_def, regex in compiled:
                    match = regex.search(line)
                    if not match:
                        continue

                    matched_value = match.group(0)
                    if PLACEHOLDER_RE.search(matched_value):
                        continue  # double-check the matched value itself

                    issues.append(ToolIssue(
                        tool=self.tool_name,
                        rule_code=pattern_def["code"],
                        severity=pattern_def["severity"],
                        message=f"{pattern_def['message']}: {rel}",
                        file=rel, line=line_num, column=match.start(),
                        symbol=pattern_def["code"],
                        raw={"pattern": pattern_def["code"], "confidence": pattern_def["confidence"]},
                        tags=["security", "secrets", "credential"],
                    ))
                    break  # one finding per line max

        duration = round(time.monotonic() - t0, 2)
        return AdapterResult(
            tool=self.tool_name,
            status=AdapterStatus.SUCCESS,
            issues=issues,
            duration_seconds=duration,
            files_scanned=files_scanned,
        )

    def normalize(self, raw_output: str) -> list[ToolIssue]:
        return []  # not used — run() returns issues directly
