"""
pip-audit adapter — hardened for repo shape variability.

Before running, checks whether the repo has an auditable Python
dependency manifest. Skips gracefully when it doesn't.

Handles:
  - repos with requirements.txt
  - repos with pyproject.toml (poetry/hatchling/setuptools)
  - repos with Pipfile
  - repos with no Python deps (skips with SKIPPED status)
"""
import json
import time
from pathlib import Path
from .base import ToolAdapter, ToolIssue, AdapterResult, AdapterStatus

CVE_KEYWORDS_HIGH    = ("remote code", "arbitrary code", "rce", "authentication bypass")
CVE_KEYWORDS_MEDIUM  = ("injection", "bypass", "escalation", "disclosure", "redirect", "forgery")


class PipAuditAdapter(ToolAdapter):
    tool_name = "pip_audit"
    supported_ecosystems = ["python"]
    timeout_seconds = 90

    def is_available(self) -> bool:
        return self._which("pip-audit")

    def _find_manifest(self, repo_path: str) -> tuple[str | None, list[str]]:
        """
        Returns (manifest_type, cmd_args) for the best available manifest.
        Returns (None, []) if no auditable manifest found.
        """
        root = Path(repo_path)

        # Priority 1: requirements.txt at root
        req = root / "requirements.txt"
        if req.exists() and req.stat().st_size > 10:
            return "requirements.txt", ["-r", str(req)]

        # Priority 2: pyproject.toml with dependency declarations
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            try:
                content = pyproject.read_text()
                if any(marker in content for marker in
                       ("[project]", "[tool.poetry.dependencies]", "[tool.pdm.dev-dependencies]")):
                    return "pyproject.toml", []  # pip-audit will auto-detect
            except Exception:
                pass

        # Priority 3: Pipfile
        pipfile = root / "Pipfile"
        if pipfile.exists():
            return "Pipfile", []

        return None, []

    def run(self, repo_path: str) -> AdapterResult:
        if not self.is_available():
            return AdapterResult(
                tool=self.tool_name,
                status=AdapterStatus.TOOL_NOT_FOUND,
                error_message="pip-audit not found on PATH",
            )

        manifest_type, extra_args = self._find_manifest(repo_path)
        if manifest_type is None:
            return AdapterResult(
                tool=self.tool_name,
                status=AdapterStatus.SKIPPED,
                error_message="No auditable Python dependency manifest found",
            )

        # Build command — avoid --disable-pip which causes issues on some envs
        if extra_args:  # requirements.txt mode — safer
            cmd = ["pip-audit", "--format=json", "--skip-editable"] + extra_args
        else:  # project mode — let pip-audit auto-detect
            cmd = ["pip-audit", "--format=json", "--skip-editable", "--local"]

        t0 = time.monotonic()
        rc, stdout, stderr = self._run_subprocess(cmd, cwd=repo_path)
        duration = round(time.monotonic() - t0, 2)

        if rc == -1:
            return AdapterResult(tool=self.tool_name, status=AdapterStatus.TIMEOUT,
                                 error_message=stderr, duration_seconds=duration)

        if rc not in (0, 1) or not stdout.strip():
            # Try to determine if this is a real error or just no deps found
            if "No dependencies found" in stderr or "0 known vulnerabilities found" in stdout:
                return AdapterResult(tool=self.tool_name, status=AdapterStatus.SUCCESS,
                                     duration_seconds=duration)
            # Usage error — likely unsupported project shape, skip cleanly
            if "usage:" in stderr.lower() or "error:" in stderr.lower()[:50]:
                return AdapterResult(
                    tool=self.tool_name,
                    status=AdapterStatus.SKIPPED,
                    error_message=f"pip-audit could not process {manifest_type}: unsupported project shape",
                    duration_seconds=duration,
                )
            return AdapterResult(tool=self.tool_name, status=AdapterStatus.EXECUTION_ERROR,
                                 error_message=stderr[:200], duration_seconds=duration)

        issues = self.normalize(stdout)
        return AdapterResult(tool=self.tool_name, status=AdapterStatus.SUCCESS,
                             issues=issues, duration_seconds=duration)

    def normalize(self, raw_output: str) -> list[ToolIssue]:
        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            return []

        dependencies = data if isinstance(data, list) else data.get("dependencies", [])
        issues = []

        for dep in dependencies:
            for vuln in dep.get("vulns", []):
                vuln_id   = vuln.get("id", "UNKNOWN")
                desc      = vuln.get("description", "")
                fix_vers  = vuln.get("fix_versions", [])
                severity  = self._infer_severity(desc)

                if not fix_vers:
                    # Unfixable low severity → info
                    if severity == "low":
                        severity = "info"

                issues.append(ToolIssue(
                    tool=self.tool_name,
                    rule_code=vuln_id,
                    severity=severity,
                    message=f"{dep.get('name','?')}=={dep.get('version','?')}: {desc[:120]}",
                    file="requirements.txt",
                    line=None, column=None, symbol=vuln_id,
                    raw={"dep": dep.get("name"), "version": dep.get("version"),
                         "vuln_id": vuln_id, "fix_versions": fix_vers},
                    tags=["security", "dependency", "cve"],
                ))

        return issues

    def _infer_severity(self, description: str) -> str:
        desc_lower = description.lower()
        if any(w in desc_lower for w in CVE_KEYWORDS_HIGH):
            return "high"
        if any(w in desc_lower for w in CVE_KEYWORDS_MEDIUM):
            return "medium"
        return "medium"  # conservative default for any known vuln
