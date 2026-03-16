from fastapi import FastAPI
from .api.routes.review import router as review_router

app = FastAPI(
    title="Codebase Atlas — Review Engine",
    description="Evidence-backed repository review: deterministic rules, tool adapters, architecture heuristics.",
    version="0.1.0",
)

app.include_router(review_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "atlas-reviewer", "ruleset_version": "2026.03"}
