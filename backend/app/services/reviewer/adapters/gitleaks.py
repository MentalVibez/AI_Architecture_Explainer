"""
Gitleaks adapter. Detects committed secrets and credentials.

Why this creates strong separation:
  Tutorial/weak repos are far more likely to contain:
    - copied API keys from tutorials
    - hardcoded tokens
    - .env files accidentally committed
    - password strings in config examples

  Production-grade repos have pre-commit hooks and secret scanning in CI.
  This is one of the cleanest separators between real engineering discipline
  and code that "looks fine."

When gitleaks binary is not installed, returns TOOL_NOT_FOUND cleanly.
"""
import json
import time

from .base import AdapterResult, AdapterStatus, ToolAdapter, ToolIssue
from .severity_map import normalize_gitleaks


class GitleaksAdapter(ToolAdapter):
    tool_name = "gitleaks"
    supported_ecosystems = ["all"]
    timeout_seconds = 90

    def is_available(self) -> bool:
        return self._which("gitleaks")

    def run(self, repo_path: str) -> AdapterResult:
        if not self.is_available():
            return AdapterResult(
                tool=self.tool_name,
                status=AdapterStatus.TOOL_NOT_FOUND,
                error_message="gitleaks not found on PATH",
            )

        cmd = [
            "gitleaks", "detect", "--source", ".", "--report-format", "json",
            "--report-path", "/dev/stdout", "--no-git", "--exit-code", "0",
        ]
        t0 = time.monotonic()
        rc, stdout, stderr = self._run_subprocess(cmd, cwd=repo_path)
        duration = round(time.monotonic() - t0, 2)

        if rc == -1:
            return AdapterResult(tool=self.tool_name, status=AdapterStatus.TIMEOUT,
                                 error_message=stderr, duration_seconds=duration)

        if not stdout.strip() or stdout.strip() == "null":
            return AdapterResult(tool=self.tool_name, status=AdapterStatus.SUCCESS,
                                 duration_seconds=duration)

        issues = self.normalize(stdout)
        return AdapterResult(tool=self.tool_name, status=AdapterStatus.SUCCESS,
                             issues=issues, duration_seconds=duration)

    def normalize(self, raw_output: str) -> list[ToolIssue]:
        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        issues = []
        for item in data:
            rule_id = item.get("RuleID", "unknown")
            issues.append(ToolIssue(
                tool=self.tool_name,
                rule_code=rule_id,
                severity=normalize_gitleaks(rule_id),
                message=f"Secret pattern matched: {item.get('Description', rule_id)}",
                file=item.get("File"),
                line=item.get("StartLine"),
                column=item.get("StartColumn"),
                symbol=rule_id,
                raw=item,
                tags=["security", "secrets", "credentials"],
            ))
        return issues
