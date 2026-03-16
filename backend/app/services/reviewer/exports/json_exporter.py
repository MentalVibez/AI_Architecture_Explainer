from ..models.report import ReviewReport


def export(report: ReviewReport) -> str:
    return report.model_dump_json(indent=2)
