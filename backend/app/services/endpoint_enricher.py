"""
LLM enrichment for raw extracted routes.

Takes an EndpointMap (deterministic output) + stack context.
Returns grouped, described, annotated endpoint map.

The stack profile context lets the LLM describe routes accurately
without re-inferring the framework from scratch.
"""
import json
import logging

from app.llm.anthropic_provider import AnthropicProvider
from app.services.route_extractor import EndpointMap

logger = logging.getLogger(__name__)

_provider: AnthropicProvider | None = None


def _get_provider() -> AnthropicProvider:
    global _provider
    if _provider is None:
        _provider = AnthropicProvider()
    return _provider


def _build_prompt(endpoint_map: EndpointMap, insights: str = "") -> str:
    routes_text = "\n".join(
        f"  {r.method:8} {r.path}"
        + (f"  ← params: {', '.join(r.params)}" if r.params else "")
        + f"  [{r.source_file}]"
        for r in endpoint_map.endpoints
    )

    if not routes_text:
        routes_text = "  No routes extracted via static analysis."

    return f"""You are analyzing API endpoints for a {endpoint_map.framework} application.

Stack context:
  Framework:  {endpoint_map.framework} ({endpoint_map.framework_confidence} confidence)
  Strategy:   {endpoint_map.parse_strategy}
{f'  Notes: {insights}' if insights else ''}

Extracted routes:
{routes_text}

Files scanned: {', '.join(endpoint_map.files_scanned) or 'none'}

Return ONLY valid JSON (no markdown, no backticks):
{{
  "groups": [
    {{
      "name": "Resource group name (e.g. Users, Authentication, Products)",
      "description": "What this group of endpoints does",
      "endpoints": [
        {{
          "method": "GET",
          "path": "/users/{{id}}",
          "description": "Fetch a single user by ID",
          "params": ["id"],
          "auth_likely": true,
          "notes": "optional short note"
        }}
      ]
    }}
  ],
  "summary": "1-2 sentence API overview",
  "api_style": "REST|GraphQL|RPC|Mixed|Unknown",
  "auth_pattern": "JWT|Session|API Key|OAuth|Unknown|None detected",
  "warnings": ["any caveats about coverage or accuracy"]
}}

Rules:
- Group related endpoints (CRUD for same resource, auth flows, etc.)
- If no routes found, return empty groups and explain in warnings
- auth_likely = true if path contains /auth, /login, /token, or uses headers
- Respect the framework context — don't guess what you already know
- Max 8 groups"""


_EMPTY_RESULT = {
    "groups": [],
    "summary": "No API endpoints could be extracted from this repository.",
    "api_style": "Unknown",
    "auth_pattern": "Unknown",
}


async def enrich_endpoint_map(endpoint_map: EndpointMap, insights: str = "") -> dict:
    if not endpoint_map.endpoints and not endpoint_map.files_scanned:
        return {
            **_EMPTY_RESULT,
            "warnings": endpoint_map.warnings + [
                "No route files found in expected locations for this framework.",
                "Repository may use a non-standard structure or dynamic routing.",
            ],
        }

    provider = _get_provider()
    text = await provider.generate_text(_build_prompt(endpoint_map, insights))
    cleaned = text.strip().replace("```json", "").replace("```", "").strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON for endpoint enrichment, using fallback")
        result = {
            **_EMPTY_RESULT,
            "warnings": ["LLM returned malformed JSON — showing raw endpoint list only."],
        }

    # Surface any extractor warnings into the result
    if endpoint_map.warnings:
        result.setdefault("warnings", [])
        result["warnings"] = endpoint_map.warnings + result["warnings"]

    return result
