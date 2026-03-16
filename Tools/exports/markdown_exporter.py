from ..models.report import ReviewReport


def export(report: ReviewReport) -> str:
    sc = report.scorecard
    lines = [
        f"# Codebase Review: {report.repo.url}",
        f"> Commit: `{report.repo.commit}` · Ruleset: `{report.ruleset_version}`",
        "",
        "## Scorecard",
        "| Category | Score |",
        "|---|---|",
        f"| Security | {sc.security} |",
        f"| Reliability | {sc.reliability} |",
        f"| Maintainability | {sc.maintainability} |",
        f"| Testing | {sc.testing} |",
        f"| Operational Readiness | {sc.operational_readiness} |",
        f"| Developer Experience | {sc.developer_experience} |",
        "",
        "## Findings",
    ]
    for sev in ["critical", "high", "medium", "low"]:
        group = [f for f in report.findings if f.severity == sev]
        if not group:
            continue
        lines.append(f"\n### {sev.capitalize()}")
        for f in group:
            lines += [
                f"\n**{f.title}** `{f.id}`",
                f"_{f.summary}_",
                f"**Why it matters:** {f.why_it_matters}",
                f"**Fix:** {f.suggested_fix}",
            ]
            if f.evidence:
                lines.append("**Evidence:**")
                for ev in f.evidence:
                    lines.append(f"- `{ev.value}`")
    lines += ["", "## Priority Actions", ""]
    for i, action in enumerate(report.priority_actions, 1):
        lines.append(f"{i}. {action}")
    return "\n".join(lines)
