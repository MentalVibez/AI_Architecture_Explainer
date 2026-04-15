from fastapi import FastAPI
from .api.routes.review import router as review_router

app = FastAPI(
    title="Codebase Atlas — Review Compatibility Shell",
    description="Thin standalone shell over the canonical backend reviewer service.",
    version="0.1.0",
)

app.include_router(review_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "atlas-reviewer-compat",
        "canonical_service": "app.services.reviewer.service",
        "ruleset_version": "2026.03",
    }
