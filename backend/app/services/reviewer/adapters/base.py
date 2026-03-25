"""
Adapter base contract. Every tool adapter must implement this interface.

Law: adapters are fact producers, not final truth.
They emit normalized ToolIssue objects. Rules and heuristics reason over them.
"""
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class AdapterStatus(str, Enum):
    SUCCESS = "success"
    TOOL_NOT_FOUND = "tool_not_found"
    EXECUTION_ERROR = "execution_error"
    PARSE_ERROR = "parse_error"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class ToolIssue:
    """
    Normalized output from any static analysis tool.
    All adapters must produce this shape — no exceptions.
    """
    tool: str
    rule_code: str
    severity: str            # internal normalized: critical/high/medium/low/info
    message: str
    file: str | None = None
    line: int | None = None
    column: int | None = None
    symbol: str | None = None  # human-readable rule name, e.g. "no-unused-vars"
    raw: dict = field(default_factory=dict)  # original tool output, unmodified
    tags: list[str] = field(default_factory=list)


@dataclass
class AdapterResult:
    """
    What an adapter run returns — issues plus execution metadata.
    Callers should always check status before using issues.
    """
    tool: str
    status: AdapterStatus
    issues: list[ToolIssue] = field(default_factory=list)
    error_message: str | None = None
    duration_seconds: float = 0.0
    files_scanned: int = 0


class ToolAdapter(ABC):
    """
    Base class for all static analysis tool adapters.

    Subclasses implement:
        is_available()      — can this tool run in the current environment?
        run(repo_path)      — execute the tool, return AdapterResult
        normalize(raw)      — convert tool-native output to list[ToolIssue]

    Subclasses declare:
        tool_name           — canonical identifier, e.g. "ruff"
        supported_ecosystems — e.g. ["python"]
        timeout_seconds     — kill switch for runaway tools
    """

    tool_name: str = ""
    supported_ecosystems: list[str] = []
    timeout_seconds: int = 60

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the tool binary is present and executable."""
        ...

    @abstractmethod
    def run(self, repo_path: str) -> AdapterResult:
        """
        Execute the tool against the repo. Must return AdapterResult.
        Must not raise — catch all errors and return AdapterStatus.*_ERROR.
        Must respect timeout_seconds.
        """
        ...

    @abstractmethod
    def normalize(self, raw_output: str) -> list[ToolIssue]:
        """
        Parse raw tool stdout/stderr into list[ToolIssue].
        Must not raise — return [] on parse failure.
        Must use _map_severity() to normalize severity values.
        """
        ...

    def _map_severity(self, tool_severity: str, rule_code: str = "") -> str:
        """
        Subclasses override or extend this to apply tool-specific severity mapping.
        Default: pass-through with safe fallback.
        """
        normalized = tool_severity.lower().strip()
        if normalized in ("critical", "high", "medium", "low", "info", "note"):
            return normalized if normalized != "note" else "info"
        return "medium"  # safe default for unknown severity values

    def _which(self, binary: str) -> bool:
        """Convenience: check if a binary is on PATH."""
        return shutil.which(binary) is not None

    def _run_subprocess(
        self, cmd: list[str], cwd: str
    ) -> tuple[int, str, str]:
        """
        Run a subprocess with timeout. Returns (returncode, stdout, stderr).
        Does not raise on non-zero exit — many linters exit non-zero when issues found.
        """
        try:
            result = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True,
                timeout=self.timeout_seconds,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", f"Tool timed out after {self.timeout_seconds}s"
        except FileNotFoundError:
            return -2, "", f"Binary not found: {cmd[0]}"
        except Exception as exc:
            return -3, "", str(exc)
