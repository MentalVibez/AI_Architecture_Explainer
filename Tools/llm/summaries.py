"""
LLM summary generation with confidence-calibrated language.

Key law: summary language must not outrun evidence.
When confidence is Low (no adapters ran), the hiring summary cannot 
claim "solid engineering discipline" — that requires adapter signal.
It should instead say "surface signals suggest..." or "structural 
signals indicate..." to reflect the actual evidence level.
"""
import json
import logging
from .contract import LLMReportInput, LLMSummaryOutput, build_llm_input
from .trace import build_deterministic_trace, SummaryTrace
from ..models.report import ReviewSummary

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a code review assistant. You receive structured analysis findings only.

STRICT RULES:
- Only reference issues present in the provided findings
- Never invent problems not in the findings  
- Verdict and scores are already determined — do not override them
- Each summary: max 3 sentences
- hiring_summary: professional senior-engineer debrief tone
- If confidence_label is "Low", qualify claims: use "structural signals suggest" not "demonstrates"

Return ONLY valid JSON:
{
  "developer_summary": "...",
  "manager_summary": "...",
  "hiring_summary": "...",
  "top_risks": ["...", "...", "..."],
  "strengths": ["...", "...", "..."]
}"""


def _validate_output(output: LLMSummaryOutput, llm_input: LLMReportInput) -> list[str]:
    violations = []
    known_categories = {f.category for f in llm_input.findings}
    known_titles = {f.title.lower() for f in llm_input.findings}
    for risk in output.top_risks:
        words = set(risk.lower().split())
        category_words = {w for cat in known_categories for w in cat.split("-")}
        title_words = {w for title in known_titles for w in title.split() if len(w) > 4}
        if not (words & (category_words | title_words)) and len(risk) > 20:
            violations.append(f"ungrounded risk: '{risk[:60]}'")
    return violations


def _confidence_qualifier(llm_input: LLMReportInput) -> str:
    """Returns appropriate epistemic qualifier based on confidence level."""
    if llm_input.confidence_label == "High":
        return "demonstrates"
    elif llm_input.confidence_label == "Medium":
        return "shows signals of"
    else:
        return "shows structural signals of"  # Low confidence — no adapter data


def _build_sentences(llm_input: LLMReportInput) -> dict[str, str]:
    """
    Build summary strings. Must stay in sync with build_deterministic_trace().
    Language is calibrated to confidence level — lower confidence = more hedged claims.
    """
    sc = llm_input.scorecard_summary
    findings = llm_input.findings
    critical_count = sum(1 for f in findings if f.severity == "critical")
    high_count = sum(1 for f in findings if f.severity == "high")
    verdict = llm_input.verdict_label
    testing = sc.get("testing", 100)
    security = sc.get("security", 100)
    qualifier = _confidence_qualifier(llm_input)

    # Developer summary
    if critical_count > 0:
        dev = f"This repository has {critical_count} critical finding(s) requiring immediate attention before deployment."
    elif high_count > 0:
        cats = list({f.category for f in findings if f.severity == "high"})[:2]
        dev = f"This repository has {high_count} high-severity finding(s) in {', '.join(cats)}."
    else:
        dev = f"This repository is {verdict.lower()} with no critical issues detected."
    if testing < 50:
        dev += " Testing coverage is critically insufficient."
    elif security < 65:
        dev += " Security posture requires attention before production use."

    # Manager summary
    if not llm_input.production_suitable:
        gap_areas = [k for k, t in [("testing",50),("security",65),("reliability",65)] if sc.get(k,100)<t]
        mgr = f"This repository is {verdict.lower()}."
        if gap_areas:
            mgr += f" Elevated delivery risk in {', '.join(gap_areas)}."
        mgr += " A hardening sprint is recommended before further onboarding."
    else:
        mgr = f"This repository is {verdict.lower()} with manageable technical debt."
        mgr += " No blockers for planned delivery."

    # Hiring summary — language calibrated to confidence
    weak = [k for k, v in sc.items() if v < 55]
    strong = [k for k, v in sc.items() if v >= 75]

    if weak:
        hire = f"This repository {qualifier} implementation capability but lacks discipline in {', '.join(weak[:2]).replace('_', ' ')}."
        if testing < 40:
            hire += " Absence of testing is a significant signal for a hiring evaluation."
    else:
        if llm_input.confidence_label == "Low":
            # Low confidence: structural signals only, be explicit about the limitation
            hire = f"Structural signals suggest this repository has basic engineering hygiene in place."
            if not llm_input.adapters_ran:
                hire += " Static analysis was not available — deeper quality assessment requires tool output."
        else:
            hire = f"This repository {qualifier} solid engineering discipline across {', '.join(strong[:3]).replace('_', ' ')}."

    return {"developer": dev, "manager": mgr, "hiring": hire}


def _deterministic_fallback(
    llm_input: LLMReportInput,
    findings: list | None = None,
) -> tuple[ReviewSummary, SummaryTrace]:
    sentences = _build_sentences(llm_input)
    trace = build_deterministic_trace(llm_input, findings or [], llm_input.scorecard_summary)
    summary = ReviewSummary(
        developer=sentences["developer"],
        manager=sentences["manager"],
        hiring=sentences["hiring"],
        trace=trace.to_dict(),
    )
    return summary, trace


async def generate_summaries(
    report,
    overall_score: int,
    findings: list,
    confidence_label: str = "Low",
    adapters_ran: bool = False,
) -> ReviewSummary:
    llm_input = build_llm_input(
        report, overall_score, findings,
        confidence_label=confidence_label,
        adapters_ran=adapters_ran,
    )
    try:
        import httpx
        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 600,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": json.dumps(llm_input.model_dump())}],
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers={"anthropic-version": "2023-06-01", "content-type": "application/json"},
            )
        if resp.status_code != 200:
            summary, _ = _deterministic_fallback(llm_input, findings)
            return summary

        raw = resp.json()["content"][0]["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        output = LLMSummaryOutput(**json.loads(raw))
        violations = _validate_output(output, llm_input)
        if violations:
            logger.warning("LLM validation: %d violation(s) — falling back", len(violations))
            summary, _ = _deterministic_fallback(llm_input, findings)
            return summary

        trace = SummaryTrace(generation_method="llm_validated", validated=True)
        return ReviewSummary(
            developer=output.developer_summary,
            manager=output.manager_summary,
            hiring=output.hiring_summary,
            trace=trace.to_dict(),
        )
    except Exception as exc:
        logger.warning("LLM failed: %s — using fallback", exc)
        summary, _ = _deterministic_fallback(llm_input, findings)
        return summary
