"""
app/services/context_reviewer.py
-----------------------------
ContextReviewer: The evidence-mandatory LLM-assisted code analysis layer.

Contract:
  Input:  FileIntelligence + CodeContext + repo summary subset
  Output: List[CodeFinding] — nothing else

Rules enforced:
  1. Every finding MUST have line_start, line_end, evidence_snippet
  2. LLM cannot produce a finding without citing specific lines
  3. No summaries, no suggestions here — only findings
  4. Findings are validated against the CodeFinding schema before returning
  5. If LLM output is invalid → log + discard, never crash

This is the boundary between deterministic and AI layers.
Everything the LLM sees was produced deterministically.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.schemas.intelligence import (
    CodeContext,
    CodeFinding,
    FileIntelligence,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scorecard deduction table
# Deterministic. LLM cannot modify these values.
# Tied directly to finding categories + severities.
# ---------------------------------------------------------------------------

SCORE_DEDUCTIONS: dict[str, dict[str, int]] = {
    "security": {
        "critical": -25,
        "high": -15,
        "medium": -8,
        "low": -3,
    },
    "performance": {
        "critical": -20,
        "high": -12,
        "medium": -6,
        "low": -2,
    },
    "reliability": {
        "critical": -20,
        "high": -12,
        "medium": -6,
        "low": -2,
    },
    "maintainability": {
        "critical": -15,
        "high": -8,
        "medium": -4,
        "low": -1,
    },
    "dead_code": {
        "critical": -5,
        "high": -4,
        "medium": -2,
        "low": -1,
    },
    "type_safety": {
        "critical": -10,
        "high": -6,
        "medium": -3,
        "low": -1,
    },
    "error_handling": {
        "critical": -15,
        "high": -10,
        "medium": -5,
        "low": -2,
    },
}

# Specific pattern overrides (deterministic findings bypass LLM entirely)
DETERMINISTIC_DEDUCTIONS: dict[str, int] = {
    "hardcoded_secret": -20,
    "eval_exec": -15,
    "subprocess_shell": -12,
    "raw_sql_format": -25,
    "sql_fstring": -25,
    "os_system": -10,
    "pickle_load": -15,
    "yaml_load_unsafe": -10,
    "open_redirect": -12,
    "debug_mode_enabled": -8,
}


# ---------------------------------------------------------------------------
# Deterministic finding generator
# Runs BEFORE the LLM. Flags known-bad patterns without AI involvement.
# ---------------------------------------------------------------------------

def generate_deterministic_findings(
    fi: FileIntelligence,
    file_content: str,
) -> list[CodeFinding]:
    """
    Generates findings from known patterns without any LLM involvement.
    These are the highest-confidence findings.
    """

    findings: list[CodeFinding] = []
    lines = file_content.splitlines()

    PATTERN_META: dict[str, tuple] = {
        "hardcoded_secret": (
            "security", "critical",
            "Hardcoded credential detected",
            "Credentials embedded in source code are exposed in version control and any deployment artifact. Use environment variables or a secrets manager.",
        ),
        "eval_exec": (
            "security", "high",
            "Dynamic code execution (eval/exec)",
            "eval() and exec() execute arbitrary code. If input is user-controlled, this is a remote code execution vulnerability.",
        ),
        "raw_sql_format": (
            "security", "critical",
            "SQL injection via string formatting",
            "Building SQL queries with % formatting is a textbook SQL injection vector. Use parameterized queries.",
        ),
        "sql_fstring": (
            "security", "critical",
            "SQL injection via f-string",
            "f-strings in SQL queries allow injection if any variable is user-controlled. Use parameterized queries.",
        ),
        "subprocess_shell": (
            "security", "high",
            "Shell injection risk (subprocess with shell=True)",
            "shell=True passes the command to the OS shell, enabling injection if any part of the command is user-controlled.",
        ),
        "os_system": (
            "security", "medium",
            "os.system() call",
            "os.system() spawns a shell. Prefer subprocess with a list of arguments and shell=False.",
        ),
        "pickle_load": (
            "security", "high",
            "Unsafe pickle deserialization",
            "pickle.load() can execute arbitrary code during deserialization. Never unpickle untrusted data.",
        ),
        "yaml_load_unsafe": (
            "security", "high",
            "Unsafe yaml.load() without Loader",
            "yaml.load() without an explicit Loader defaults to the unsafe loader. Use yaml.safe_load() or yaml.load(f, Loader=yaml.SafeLoader).",
        ),
        "debug_mode_enabled": (
            "reliability", "medium",
            "Debug mode enabled",
            "Debug mode exposes stack traces and internal state in production responses. This must be disabled in production.",
        ),
    }

    # Compile patterns locally
    from app.services.deep_scanner import SENSITIVE_PATTERNS
    pattern_map = {name: pat for name, pat in SENSITIVE_PATTERNS}

    for pattern_name in fi.sensitive_operations:
        if pattern_name not in PATTERN_META:
            continue
        if pattern_name not in pattern_map:
            continue

        category, severity, title, explanation = PATTERN_META[pattern_name]
        pat = pattern_map[pattern_name]

        # Find the exact lines
        for i, line in enumerate(lines, start=1):
            if pat.search(line):
                snippet = line.strip()
                if not snippet:
                    continue

                score_impact = DETERMINISTIC_DEDUCTIONS.get(
                    pattern_name,
                    SCORE_DEDUCTIONS.get(category, {}).get(severity, -5),
                )

                try:
                    finding = CodeFinding(
                        file_path=fi.path,
                        category=category,
                        severity=severity,
                        source="deterministic",
                        line_start=i,
                        line_end=i,
                        evidence_snippet=snippet[:300],  # cap to avoid bloat
                        title=title,
                        explanation=explanation,
                        score_impact=score_impact,
                        confidence=1.0,
                    )
                    findings.append(finding)
                except Exception as e:
                    logger.warning(f"Failed to construct finding for {pattern_name} in {fi.path}: {e}")

    return findings


# ---------------------------------------------------------------------------
# LLM review prompt builder
# Produces the exact context the LLM receives — nothing raw, nothing extra.
# ---------------------------------------------------------------------------

def build_review_prompt(
    fi: FileIntelligence,
    ctx: CodeContext,
    file_content: str,
    repo_summary: dict[str, Any],
    existing_findings: list[CodeFinding],
) -> str:
    """
    Builds a tightly scoped prompt for the LLM reviewer.

    The LLM gets:
    - The file content (truncated to relevant sections if large)
    - Structured context about callers + dependencies
    - Already-found deterministic issues (so it doesn't duplicate)
    - Strict output schema requirements

    The LLM does NOT get:
    - The full repo
    - Other files' content
    - Instruction to rewrite anything
    """

    # Truncate content for LLM context budget
    MAX_CONTENT_CHARS = 8_000
    content_for_llm = file_content
    was_truncated = len(file_content) > MAX_CONTENT_CHARS
    if was_truncated:
        # Keep the first and last portions — often the most signal-rich
        half = MAX_CONTENT_CHARS // 2
        content_for_llm = (
            file_content[:half]
            + f"\n\n... [TRUNCATED: {len(file_content) - MAX_CONTENT_CHARS} chars omitted] ...\n\n"
            + file_content[-half:]
        )

    already_flagged = [
        f"{f.line_start}-{f.line_end}: {f.title}"
        for f in existing_findings
    ]

    upstream_summary = ctx.upstream_callers[:5] if ctx.upstream_callers else ["(no callers detected)"]
    downstream_summary = ctx.downstream_dependencies[:5] if ctx.downstream_dependencies else ["(no dependencies detected)"]

    return f"""You are a code reviewer analyzing a single file in the context of a larger repository.

## File being reviewed
Path: {fi.path}
Language: {fi.language}
Role: {fi.role}
LOC: {fi.loc}
Is on critical path: {ctx.is_on_critical_path}
Called by {ctx.caller_count} other files

## Repository context
Primary language: {repo_summary.get('primary_language', 'unknown')}
Framework signals: {', '.join(repo_summary.get('framework_signals', [])) or 'none detected'}
Total files: {repo_summary.get('total_files', 'unknown')}

## This file's relationships
Upstream callers (files that call this):
{chr(10).join(f'  - {p}' for p in upstream_summary)}

Downstream dependencies (files this calls):
{chr(10).join(f'  - {p}' for p in downstream_summary)}

## Already-found issues (DO NOT duplicate these)
{chr(10).join(f'  - {f}' for f in already_flagged) or '  None yet'}

## File content
```{fi.language}
{content_for_llm}
```
{'[NOTE: Content was truncated due to file size]' if was_truncated else ''}

## Your task
Review this file for issues in these categories ONLY:
- dead_code: unreachable code, unused imports, unused variables/functions
- performance: N+1 queries, unnecessary loops, blocking I/O in async context
- reliability: missing error handling on external calls, unhandled exceptions
- error_handling: bare except clauses, swallowed exceptions, missing finally blocks
- maintainability: functions with 50+ LOC, deeply nested logic (5+ levels)
- type_safety: missing type annotations on public functions (Python/TypeScript only)

DO NOT flag:
- Style issues (use a linter for those)
- Anything already in the "Already-found issues" list
- Issues you cannot locate on a specific line

## Output format
Respond ONLY with a JSON array. Each element must have these exact fields:
{{
  "file_path": "{fi.path}",
  "category": "<one of the categories above>",
  "severity": "<low|medium|high|critical>",
  "line_start": <integer>,
  "line_end": <integer>,
  "evidence_snippet": "<exact code from the file, no paraphrasing>",
  "title": "<short descriptive title>",
  "explanation": "<why this is a problem, referencing the specific code>",
  "remediation": "<concrete fix suggestion>"
}}

If you find no issues, return an empty array: []
Return ONLY the JSON array. No markdown, no explanation, no preamble.
"""


# ---------------------------------------------------------------------------
# LLM response validator
# Strict. Invalid objects are logged and discarded, never silently corrupted.
# ---------------------------------------------------------------------------

def validate_llm_findings(
    raw_json: str,
    file_path: str,
) -> list[CodeFinding]:
    """
    Parses and validates LLM output.
    Discards any finding that doesn't meet the CodeFinding schema.
    Never raises — always returns a (possibly empty) list.
    """
    findings = []

    try:
        # Strip any markdown fences the LLM might add despite instructions
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        data = json.loads(cleaned)

        if not isinstance(data, list):
            logger.warning(f"LLM reviewer returned non-list for {file_path}: {type(data)}")
            return []

    except json.JSONDecodeError as e:
        logger.warning(f"LLM reviewer JSON parse failed for {file_path}: {e}")
        return []

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(f"Finding {i} for {file_path} is not a dict, skipping")
            continue

        # Force correct file path — LLM sometimes hallucinates this
        item["file_path"] = file_path
        item["source"] = "llm_assisted"

        # Compute score impact from the deduction table
        category = item.get("category", "maintainability")
        severity = item.get("severity", "low")
        item["score_impact"] = SCORE_DEDUCTIONS.get(category, {}).get(severity, -2)

        # Confidence is lower for LLM findings than deterministic ones
        item["confidence"] = 0.75

        try:
            finding = CodeFinding(**item)
            findings.append(finding)
        except Exception as e:
            logger.warning(f"Finding {i} for {file_path} failed validation: {e} — raw: {item}")

    return findings


# ---------------------------------------------------------------------------
# ContextReviewer — main class
# ---------------------------------------------------------------------------

class ContextReviewer:
    """
    Reviews files using deterministic patterns first, then LLM for deeper analysis.

    The LLM is only invoked if:
    1. The file is on the critical path, OR
    2. The file has >50 LOC and is not a test/config/migration, OR
    3. The file has sensitive operations detected

    This keeps LLM costs bounded while maximizing signal.
    """

    _SYSTEM_PROMPT = (
        "You are a precise code reviewer. "
        "You only report issues you can cite on specific lines. "
        "You always respond with valid JSON arrays and nothing else."
    )

    def __init__(
        self,
        anthropic_api_key: str,
        model: str = "claude-sonnet-4-6",
        enable_llm: bool = True,
    ):
        self.api_key = anthropic_api_key
        self.model = model
        self.enable_llm = enable_llm
        # Provider is instantiated once per reviewer instance
        if enable_llm and anthropic_api_key:
            from app.llm.anthropic_provider import AnthropicProvider
            self._provider: Any | None = AnthropicProvider(api_key=anthropic_api_key)
        else:
            self._provider = None

    def _should_invoke_llm(self, fi: FileIntelligence, ctx: CodeContext) -> bool:
        """Targeted LLM invocation — not every file, only high-signal ones."""
        if not self.enable_llm:
            return False

        # Always review critical path files
        if ctx.is_on_critical_path:
            return True

        # Skip tests, configs, migrations for LLM (deterministic is enough)
        if fi.role in ("test", "config", "migration", "infra"):
            return False

        # Review files with meaningful code and risk signals
        if fi.loc >= 50 and fi.sensitive_operations:
            return True

        # Review complex files regardless
        if fi.complexity_score >= 15:
            return True

        # Review highly-called files (high blast radius)
        if ctx.caller_count >= 3:
            return True

        return False

    async def review_file(
        self,
        fi: FileIntelligence,
        ctx: CodeContext,
        file_content: str,
        repo_summary: dict[str, Any],
    ) -> list[CodeFinding]:
        """
        Returns all findings for a single file.
        Deterministic findings always run. LLM is conditional.
        """
        # Phase 1: Deterministic findings (always)
        findings = generate_deterministic_findings(fi, file_content)

        # Phase 2: LLM-assisted findings (conditional)
        if self._should_invoke_llm(fi, ctx):
            llm_findings = await self._run_llm_review(
                fi, ctx, file_content, repo_summary, findings
            )
            # Deduplicate by line range overlap
            findings.extend(self._deduplicate(findings, llm_findings))

        return findings

    async def _run_llm_review(
        self,
        fi: FileIntelligence,
        ctx: CodeContext,
        file_content: str,
        repo_summary: dict[str, Any],
        existing_findings: list[CodeFinding],
    ) -> list[CodeFinding]:
        if self._provider is None:
            return []

        prompt = build_review_prompt(fi, ctx, file_content, repo_summary, existing_findings)

        try:
            raw = await self._provider.generate_text(prompt, system=self._SYSTEM_PROMPT)
            return validate_llm_findings(raw, fi.path)
        except Exception as e:
            logger.error(f"LLM review failed for {fi.path}: {type(e).__name__}: {e}")
            return []

    @staticmethod
    def _deduplicate(
        existing: list[CodeFinding],
        new_findings: list[CodeFinding],
    ) -> list[CodeFinding]:
        """Remove new findings that overlap with existing ones by line range."""
        existing_ranges = {
            (f.file_path, f.line_start, f.line_end)
            for f in existing
        }
        unique = []
        for f in new_findings:
            key = (f.file_path, f.line_start, f.line_end)
            if key not in existing_ranges:
                unique.append(f)
                existing_ranges.add(key)
        return unique

    async def review_repo(
        self,
        files: list[FileIntelligence],
        contexts: dict[str, CodeContext],
        file_contents: dict[str, str],
        repo_summary: dict[str, Any],
        max_concurrent: int = 5,
    ) -> list[CodeFinding]:
        """
        Reviews all files concurrently (bounded by semaphore).
        Returns the full findings list for the repository.
        """
        semaphore = __import__("asyncio").Semaphore(max_concurrent)

        async def review_with_semaphore(fi: FileIntelligence) -> list[CodeFinding]:
            async with semaphore:
                ctx = contexts.get(fi.path)
                content = file_contents.get(fi.path, "")
                if not ctx or not content:
                    return []
                return await self.review_file(fi, ctx, content, repo_summary)

        import asyncio
        tasks = [review_with_semaphore(fi) for fi in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_findings: list[CodeFinding] = []
        for r in results:
            if isinstance(r, list):
                all_findings.extend(r)
            elif isinstance(r, Exception):
                logger.error(f"Review task failed: {r}")

        return all_findings
