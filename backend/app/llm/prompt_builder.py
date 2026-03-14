"""Builds prompts for each LLM task in the analysis pipeline."""

import json
from typing import Any

# Hard caps to prevent token blowout
_MAX_TREE_PATHS = 60
_MAX_README_CHARS = 1500
_MAX_DEPS = 40


def _safe_evidence(evidence: dict[str, Any]) -> str:
    """Return a token-safe JSON snapshot of the evidence dict."""
    safe = {
        "repo": evidence.get("repo", {}),
        "detected_stack": evidence.get("detected_stack", {}),
        "npm_dependencies": evidence.get("npm_dependencies", [])[:_MAX_DEPS],
        "python_dependencies": evidence.get("python_dependencies", [])[:_MAX_DEPS],
        "fetched_files": evidence.get("fetched_files", []),
        "tree_paths": evidence.get("tree_paths", [])[:_MAX_TREE_PATHS],
        "readme": (evidence.get("readme") or "")[:_MAX_README_CHARS],
    }
    return json.dumps(safe, indent=2)


def build_developer_summary_prompt(evidence: dict[str, Any]) -> str:
    return f"""You are analyzing a GitHub repository. You have been given structured evidence from static analysis.

Generate a developer-facing architecture summary based ONLY on the evidence provided.
Do NOT invent components, files, or services not supported by the evidence.

Evidence:
{_safe_evidence(evidence)}

Write a clear, technical summary covering:
- What this project appears to do
- Detected stack and frameworks
- Key architectural patterns
- Entry points and component responsibilities
- Deployment/infra clues if present

Be specific and factual. Note uncertainty where evidence is weak."""


def build_hiring_manager_summary_prompt(evidence: dict[str, Any]) -> str:
    return f"""You are analyzing a GitHub repository for a non-technical hiring manager.

Generate a plain-English summary based ONLY on the evidence provided.
Avoid jargon where possible. Explain technical terms briefly if you must use them.

Evidence:
{_safe_evidence(evidence)}

Write a concise summary covering:
- What this project does (in business terms)
- What technical skills it demonstrates
- Likely complexity level (simple / moderate / complex)
- What stands out as impressive or notable
- Any relevant business context you can infer

Be honest about uncertainty. Do not overstate."""


def build_diagram_prompt(evidence: dict[str, Any]) -> str:
    return f"""You are generating a Mermaid architecture diagram for a GitHub repository.

Based on the evidence below, generate a valid Mermaid flowchart (graph TD) that shows:
- Major components and their roles
- Data/request flow between components
- External services if detected

Evidence:
{_safe_evidence(evidence)}

Return ONLY the raw Mermaid diagram text, starting with "graph TD".
Do not add markdown code fences. Do not add explanation."""
