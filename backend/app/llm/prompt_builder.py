"""Builds prompts for each LLM task in the analysis pipeline."""

import json
from typing import Any

# Hard caps to prevent token blowout
_MAX_TREE_PATHS = 60
_MAX_README_CHARS = 1500
_MAX_DEPS = 40


def _flatten_stack(raw_stack: dict) -> dict:
    """Flatten detected_stack to simple name lists for LLM input.

    Handles both the new rich format ({name, evidence, confidence}) and the
    legacy string format so old stored results don't break.
    """
    return {
        cat: [d["name"] if isinstance(d, dict) else d for d in items]
        for cat, items in raw_stack.items()
    }


def _safe_evidence(evidence: dict[str, Any]) -> str:
    """Return a token-safe JSON snapshot of the evidence dict."""
    safe = {
        "repo": evidence.get("repo", {}),
        "detected_stack": _flatten_stack(evidence.get("detected_stack", {})),
        "npm_dependencies": evidence.get("npm_dependencies", [])[:_MAX_DEPS],
        "python_dependencies": evidence.get("python_dependencies", [])[:_MAX_DEPS],
        "fetched_files": evidence.get("fetched_files", []),
        "tree_paths": evidence.get("tree_paths", [])[:_MAX_TREE_PATHS],
        "readme": (evidence.get("readme") or "")[:_MAX_README_CHARS],
    }
    return json.dumps(safe, indent=2)


def build_developer_summary_prompt(evidence: dict[str, Any]) -> str:
    return f"""You are analyzing a GitHub repository. \
You have been given structured evidence from static analysis.

Generate a Technical View summary based ONLY on the evidence provided.
Do NOT invent components, files, or services not supported by the evidence.

Evidence:
{_safe_evidence(evidence)}

Format your response as a presentation slide — clear section headings followed by bullet points.
Use bullet character • for every bullet point. Do NOT use dashes.
Keep each bullet concise (one idea per bullet). No prose paragraphs.

Sections to cover:
What This Project Does
• What this project appears to do

Stack & Frameworks
• Detected technologies and frameworks

Architecture
• Key architectural patterns observed

Entry Points & Responsibilities
• Main components and what they own

Infrastructure
• Deployment or infra clues if present (omit section if none)

Confidence Notes
• Note any areas where evidence is weak or uncertain"""


def build_hiring_manager_summary_prompt(evidence: dict[str, Any]) -> str:
    return f"""You are analyzing a GitHub repository for a non-technical audience.

Generate a Non-Technical View summary based ONLY on the evidence provided.
Write as if presenting a slide at a board meeting or conference. No jargon.
If you must use a technical term, explain it in plain English immediately after.

Evidence:
{_safe_evidence(evidence)}

Format your response as a presentation slide — clear section headings followed by bullet points.
Use bullet character • for every bullet point. Do NOT use dashes.
Keep each bullet concise (one idea per bullet). No prose paragraphs.

Sections to cover:
What This Project Does
• What the project does in plain business terms

Skills Demonstrated
• Technical capabilities this project shows

Complexity
• Simple / Moderate / Complex — with one-line justification

Standout Points
• What is most impressive or notable

Business Context
• Any relevant business or market context you can infer (omit if none)

Be honest about uncertainty. Do not overstate."""


def build_devcontainer_prompt(evidence: dict[str, Any]) -> str:
    stack = _flatten_stack(evidence.get("detected_stack", {}))
    npm_deps = evidence.get("npm_dependencies", [])[:_MAX_DEPS]
    py_deps = evidence.get("python_dependencies", [])[:_MAX_DEPS]
    tree_paths = evidence.get("tree_paths", [])[:_MAX_TREE_PATHS]
    readme_snippet = (evidence.get("readme") or "")[:_MAX_README_CHARS]
    repo = evidence.get("repo", {})
    repo_name = f"{repo.get('owner', 'repo')}/{repo.get('name', 'project')}"

    # Surface env-var hints: any .env.example file in the tree is a signal
    env_hints = [p for p in tree_paths if ".env" in p.split("/")[-1].lower()]

    return f"""You are a senior DevOps engineer generating a production-quality \
.devcontainer/devcontainer.json for the GitHub repository {repo_name}.

Use ONLY the evidence below. Do NOT invent dependencies or services that are not \
supported by the evidence.

=== EVIDENCE ===
Stack (deterministic):
{json.dumps(stack, indent=2)}

Python dependencies:
{json.dumps(py_deps)}

NPM dependencies:
{json.dumps(npm_deps)}

Files in repo (sample):
{json.dumps(tree_paths)}

Env-related files detected:
{json.dumps(env_hints)}

README excerpt:
{readme_snippet}
=== END EVIDENCE ===

Generate a devcontainer.json with these rules:
1. Choose the most specific official devcontainer base image for the primary language.
   Prefer mcr.microsoft.com/devcontainers/* images.
2. Add ghcr.io/devcontainers/features/* entries only for tools the evidence confirms are needed.
   Always include git. Include docker-in-docker only if a Dockerfile or docker-compose.yml is present.
3. Write a postCreateCommand that installs exactly the dependencies shown in evidence
   (e.g., `pip install -r requirements.txt`, `npm ci`). Chain with `&&`. Skip steps with no evidence.
4. For containerEnv: include only environment variables the project clearly needs
   (inferred from README setup instructions or .env file names). Use "${{localEnv:VAR_NAME}}"
   so the developer's local shell value is forwarded. Omit if no evidence.
5. forwardPorts: include only ports the stack clearly uses (e.g., 3000 for Next.js, 8000 for FastAPI).
6. customizations.vscode.extensions: include language-appropriate extensions only.
   Do not add extensions for languages not in the stack.
7. remoteUser: always "vscode".
8. name: short slug derived from the repo name."""


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
