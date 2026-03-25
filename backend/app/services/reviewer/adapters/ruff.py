"""
Ruff adapter. Runs `ruff check --output-format=json` and normalizes output.

Ruff JSON output per issue:
{
  "code": "F401",
  "message": "...",
  "filename": "src/main.py",
  "location": { "row": 12, "column": 1 },
  "end_location": { "row": 12, "column": 10 },
  "fix": null,
  "noqa_row": null,
  "url": "https://docs.astral.sh/ruff/rules/F401"
}
"""
import json
import time

from .base import AdapterResult, AdapterStatus, ToolAdapter, ToolIssue
from .severity_map import normalize_ruff

RUFF_TAGS: dict[str, list[str]] = {
    "F": ["correctness", "pyflakes"],
    "E": ["style", "pycodestyle"],
    "W": ["style", "pycodestyle"],
    "N": ["naming"],
    "S": ["security"],
    "C": ["complexity"],
    "B": ["bugbear", "correctness"],
    "ANN": ["annotations", "typing"],
    "ERA": ["dead-code"],
    "RUF": ["ruff"],
}

SKIP_DIRS = [
    "--exclude", ".venv,venv,node_modules,.next,dist,build,__pycache__,.git"
]


class RuffAdapter(ToolAdapter):
    tool_name = "ruff"
    supported_ecosystems = ["python"]
    timeout_seconds = 45

    def is_available(self) -> bool:
        return self._which("ruff")

    def run(self, repo_path: str) -> AdapterResult:
        if not self.is_available():
            return AdapterResult(
                tool=self.tool_name,
                status=AdapterStatus.TOOL_NOT_FOUND,
                error_message="ruff not found on PATH",
            )

        cmd = ["ruff", "check", "--output-format=json", "--no-cache"] + SKIP_DIRS + ["."]
        t0 = time.monotonic()
        rc, stdout, stderr = self._run_subprocess(cmd, cwd=repo_path)
        duration = round(time.monotonic() - t0, 2)

        if rc == -1:
            return AdapterResult(tool=self.tool_name, status=AdapterStatus.TIMEOUT,
                                 error_message=stderr, duration_seconds=duration)
        if rc == -2:
            return AdapterResult(tool=self.tool_name, status=AdapterStatus.TOOL_NOT_FOUND,
                                 error_message=stderr, duration_seconds=duration)

        # Ruff exits 1 when issues are found — that is expected, not an error
        if not stdout.strip():
            if rc not in (0, 1):
                return AdapterResult(tool=self.tool_name, status=AdapterStatus.EXECUTION_ERROR,
                                     error_message=stderr or "empty output", duration_seconds=duration)
            return AdapterResult(tool=self.tool_name, status=AdapterStatus.SUCCESS,
                                 duration_seconds=duration)

        issues = self.normalize(stdout)
        return AdapterResult(
            tool=self.tool_name,
            status=AdapterStatus.SUCCESS if issues is not None else AdapterStatus.PARSE_ERROR,
            issues=issues or [],
            duration_seconds=duration,
        )

    def normalize(self, raw_output: str) -> list[ToolIssue]:
        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return []

        issues = []
        for item in data:
            code = item.get("code") or "UNKNOWN"
            prefix = code[:3].rstrip("0123456789")
            tags = RUFF_TAGS.get(prefix, []) + RUFF_TAGS.get(code[:1], [])
            tags = list(dict.fromkeys(tags))  # dedupe, preserve order

            issues.append(ToolIssue(
                tool=self.tool_name,
                rule_code=code,
                severity=normalize_ruff(code),
                message=item.get("message", ""),
                file=item.get("filename"),
                line=item.get("location", {}).get("row"),
                column=item.get("location", {}).get("column"),
                symbol=code,
                raw=item,
                tags=tags,
            ))

        return issues
