"""
Score interpretation layer.

Converts numeric scores into stable semantic labels.
Band boundaries are calibrated to actual model output — not aspirational values.

Calibration record:
  2026.03 — ops band raised: "production-ready" threshold 80→88
             Rationale: tutorial repos with no CI/health/logging score ~83.
             83 should not read as "production-ready operational posture."
"""
from dataclasses import dataclass
from ..models.report import Scorecard


@dataclass
class ScoreBand:
    label: str
    min_score: int
    max_score: int
    developer_meaning: str
    manager_meaning: str
    hiring_meaning: str
    trust_recommendation: str
    color_hint: str


SCORE_BANDS: list[ScoreBand] = [
    ScoreBand(
        label="Strong",
        min_score=90, max_score=100,
        developer_meaning="Well-maintained with minor or no gaps. Suitable as architecture reference.",
        manager_meaning="Low delivery risk. Meets production standards.",
        hiring_meaning="Strong signal. Demonstrates disciplined engineering habits.",
        trust_recommendation="strong", color_hint="green",
    ),
    ScoreBand(
        label="Solid",
        min_score=75, max_score=89,
        developer_meaning="Generally healthy with notable gaps to address before scaling.",
        manager_meaning="Moderate delivery risk. Known gaps exist and are manageable.",
        hiring_meaning="Positive signal. Shows capability with some areas to probe in interview.",
        trust_recommendation="solid", color_hint="yellow",
    ),
    ScoreBand(
        label="Mixed",
        min_score=60, max_score=74,
        developer_meaning="Functional but carries real risk — gaps in testing, security, or architecture.",
        manager_meaning="Elevated delivery risk. Hardening sprint recommended before next milestone.",
        hiring_meaning="Moderate signal. Functional output but missing discipline indicators.",
        trust_recommendation="moderate", color_hint="orange",
    ),
    ScoreBand(
        label="Weak",
        min_score=40, max_score=59,
        developer_meaning="Significant structural or quality problems. Not ready for production use.",
        manager_meaning="High delivery risk. Requires focused remediation before onboarding contributors.",
        hiring_meaning="Limited signal. Shows effort but lacks production-readiness discipline.",
        trust_recommendation="limited", color_hint="red",
    ),
    ScoreBand(
        label="Critical concerns",
        min_score=0, max_score=39,
        developer_meaning="Serious multi-domain failures. Treat as foundational rebuild.",
        manager_meaning="Do not ship. Security, reliability, or architecture problems require immediate attention.",
        hiring_meaning="Insufficient signal. Output quality does not meet baseline production engineering standards.",
        trust_recommendation="none", color_hint="dark-red",
    ),
]

# Per-category bands — calibrated to actual scoring model output.
# Ops bands raised: "production-ready" now requires 88+ (previously 80+).
# This reflects: a repo missing CI+health+logging scores ~83, which should not
# read as "production-ready."
CATEGORY_BANDS: dict[str, list[tuple[int, int, str]]] = {
    "security": [
        (90, 100, "No significant vulnerabilities detected"),
        (70, 89,  "Minor security gaps — low risk with existing controls"),
        (50, 69,  "Notable security issues requiring attention"),
        (30, 49,  "Serious security gaps — not suitable for production without remediation"),
        (0,  29,  "Critical security failures — active risk"),
    ],
    "testing": [
        (80, 100, "Strong test coverage signals"),
        (60, 79,  "Partial test coverage — key paths may be unprotected"),
        (40, 59,  "Weak test coverage — regressions are a real risk"),
        (20, 39,  "Minimal testing — changes cannot be validated safely"),
        (0,  19,  "No meaningful test coverage"),
    ],
    "maintainability": [
        (80, 100, "Clean structure — easy to extend and review"),
        (65, 79,  "Generally readable with some complexity concentration"),
        (50, 64,  "Notable structural debt slowing development"),
        (30, 49,  "High structural debt — ownership and review are difficult"),
        (0,  29,  "Severe architectural problems"),
    ],
    "reliability": [
        (80, 100, "High reliability signals"),
        (65, 79,  "Mostly reliable with some gaps"),
        (50, 64,  "Reliability concerns that could surface under load or change"),
        (30, 49,  "Significant reliability risk"),
        (0,  29,  "Multiple failure vectors present"),
    ],
    # Ops bands raised from 80→88 for top tier.
    # Calibration: no-CI + no-health + no-logging → score ≈83.
    # 83 should read "operational basics in place" not "production-ready."
    "operational_readiness": [
        (88, 100, "Production-ready operational posture"),
        (70, 87,  "Operational basics in place — notable gaps for production deployment"),
        (50, 69,  "Operational gaps that would create friction in production"),
        (30, 49,  "Weak operational posture — not suitable for production"),
        (0,  29,  "Missing foundational operational controls"),
    ],
    "developer_experience": [
        (80, 100, "Excellent onboarding and contribution signals"),
        (65, 79,  "Good developer experience with minor gaps"),
        (50, 64,  "Noticeable friction for contributors"),
        (30, 49,  "Poor developer experience — onboarding is difficult"),
        (0,  29,  "Significant barriers to contribution"),
    ],
}


def interpret_overall(score: int) -> ScoreBand:
    for band in SCORE_BANDS:
        if band.min_score <= score <= band.max_score:
            return band
    return SCORE_BANDS[-1]


def interpret_category(category: str, score: int) -> str:
    bands = CATEGORY_BANDS.get(category, [])
    for lo, hi, label in bands:
        if lo <= score <= hi:
            return label
    return "No interpretation available"


@dataclass
class InterpretedReport:
    overall_score: int
    overall_band: ScoreBand
    category_interpretations: dict[str, str]
    trust_recommendation: str
    top_concern: str | None
    production_suitable: bool


def interpret_report(scorecard: Scorecard, overall: int, findings: list) -> InterpretedReport:
    band = interpret_overall(overall)
    category_interpretations = {
        cat: interpret_category(cat, getattr(scorecard, cat, 0))
        for cat in ["security","testing","maintainability","reliability",
                    "operational_readiness","developer_experience"]
    }
    top_concern = None
    for sev in ("critical", "high"):
        group = [f for f in findings if f.severity == sev]
        if group:
            top_concern = group[0].title
            break
    production_suitable = (
        band.trust_recommendation in ("strong", "solid")
        and scorecard.security >= 65
        and scorecard.testing >= 50
    )
    return InterpretedReport(
        overall_score=overall, overall_band=band,
        category_interpretations=category_interpretations,
        trust_recommendation=band.trust_recommendation,
        top_concern=top_concern,
        production_suitable=production_suitable,
    )
