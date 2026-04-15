from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...exports.json_exporter import export as export_json
from ...exports.markdown_exporter import export as export_markdown
from ...service import ReviewError, run_review

router = APIRouter(prefix="/review", tags=["review"])


class ReviewRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    export_format: str = "json"


@router.post("/")
async def review_repo(req: ReviewRequest):
    try:
        report = await run_review(repo_url=req.repo_url, branch=req.branch)
    except ReviewError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": exc.code, "message": exc.message},
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if req.export_format == "markdown":
        return {"format": "markdown", "content": export_markdown(report)}

    return {
        "format": "json",
        "overall_score": report.meta.overall_score,
        "analysis_depth": report.depth.label,
        "report": report.model_dump(),
        "content": export_json(report),
    }
