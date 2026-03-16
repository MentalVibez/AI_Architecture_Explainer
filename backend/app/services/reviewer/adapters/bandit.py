"""
Bandit adapter. Runs `bandit -r -f json` and normalizes output.

Bandit uses a severity × confidence matrix, which we map to Atlas internal severity.
"""
import json
import time
from .base import ToolAdapter, ToolIssue, AdapterResult, AdapterStatus
from .severity_map import normalize_bandit


class BanditAdapter(ToolAdapter):
    tool_name = "bandit"
    supported_ecosystems = ["python"]
    timeout_seconds = 60

    def is_available(self) -> bool:
        return self._which("bandit")

    def run(self, repo_path: str) -> AdapterResult:
        if not self.is_available():
            return AdapterResult(tool=self.tool_name, status=AdapterStatus.TOOL_NOT_FOUND,
                                 error_message="bandit not found on PATH")

        cmd = [
            "bandit", "-r", "-f", "json",
            "--exclude", ".venv,venv,node_modules,dist,build,tests",
            ".",
        ]
        t0 = time.monotonic()
        rc, stdout, stderr = self._run_subprocess(cmd, cwd=repo_path)
        duration = round(time.monotonic() - t0, 2)

        if rc == -1:
            return AdapterResult(tool=self.tool_name, status=AdapterStatus.TIMEOUT,
                                 error_message=stderr, duration_seconds=duration)

        # Bandit exits 1 when issues found — expected
        if not stdout.strip():
            return AdapterResult(tool=self.tool_name,
                                 status=AdapterStatus.SUCCESS if rc in (0, 1) else AdapterStatus.EXECUTION_ERROR,
                                 error_message=stderr, duration_seconds=duration)

        issues = self.normalize(stdout)
        return AdapterResult(
            tool=self.tool_name,
            status=AdapterStatus.SUCCESS,
            issues=issues,
            duration_seconds=duration,
        )

    def normalize(self, raw_output: str) -> list[ToolIssue]:
        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return []

        results = data.get("results", [])
        issues = []
        for item in results:
            severity = item.get("issue_severity", "MEDIUM")
            confidence = item.get("issue_confidence", "MEDIUM")
            test_id = item.get("test_id", "")
            test_name = item.get("test_name", "")

            issues.append(ToolIssue(
                tool=self.tool_name,
                rule_code=test_id,
                severity=normalize_bandit(severity, confidence),
                message=item.get("issue_text", ""),
                file=item.get("filename"),
                line=item.get("line_number"),
                column=None,
                symbol=test_name,
                raw=item,
                tags=["security"] + (["subprocess"] if "subprocess" in test_name else []),
            ))

        return issues
