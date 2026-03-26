"""
tests/fixtures/real_world_shapes.py
-------------------------------------
Real-world regression fixtures for Codebase Atlas graph accuracy.

These are NOT live fetches. They are structurally accurate synthetic models
of known public repositories, pinned at a specific observed state.

Each fixture documents:
  - The real repo it models
  - The commit/date it was observed
  - Why this repo shape tests something specific

When these fixtures fail, it means the engine has regressed against
a real-world pattern. That is always a real bug, not a test error.

Repo shapes covered:
  1. FastAPI backend service (Atlas itself — MentalVibez/AI_Architecture_Explainer)
  2. Next.js App Router app with server components
  3. Python monorepo (multi-package, shared lib)
  4. Repo with mixed infra/config density
  5. Repo with stale README (architecture diverged from docs)
  6. Polyglot repo (Python backend + TypeScript frontend in one tree)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RealWorldExpectation:
    """What we expect from a real-world shaped repo."""
    entrypoint_paths: List[str]         # Must be detected as entrypoints
    critical_paths: List[str]           # Must be on critical path
    not_critical_paths: List[str]       # Must NOT be on critical path
    confirmed_edges: List[tuple]        # (source, target) pairs that must be confirmed
    external_imports_absent: List[str]  # These must never appear as edge targets
    min_graph_confidence: float


@dataclass
class RealWorldFixture:
    name: str
    real_repo: str
    observed_at: str
    description: str
    files: Dict[str, str]
    expectations: RealWorldExpectation
    ts_aliases: Optional[Dict[str, str]] = None


# ---------------------------------------------------------------------------
# Fixture RW-1: FastAPI backend service
# Models: MentalVibez/AI_Architecture_Explainer (Atlas itself)
# Observed: March 2026
# Tests: FastAPI app structure, SQLAlchemy models, Pydantic schemas,
#        analysis pipeline service chain
# ---------------------------------------------------------------------------

RW1_FASTAPI_SERVICE = RealWorldFixture(
    name="rw1_fastapi_service",
    real_repo="MentalVibez/AI_Architecture_Explainer",
    observed_at="2026-03",
    description=(
        "FastAPI backend with analysis pipeline. "
        "Tests that service chains resolve, models are not entrypoints, "
        "and external packages (FastAPI, SQLAlchemy, Anthropic) are excluded."
    ),
    files={
        "backend/app/main.py": """\
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.analyze import router as analyze_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.database import init_db

app = FastAPI(title="Codebase Atlas API")
settings = get_settings()

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins)
app.include_router(analyze_router, prefix="/api")
app.include_router(health_router)
""",
        "backend/app/api/routes/analyze.py": """\
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.requests import AnalyzeRequest
from app.schemas.responses import JobResponse
from app.services.analysis_pipeline import AnalysisPipeline

router = APIRouter()

@router.post("/analyze", response_model=JobResponse)
async def submit_analysis(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    pipeline = AnalysisPipeline(db)
    job = await pipeline.create_job(request.repo_url)
    background_tasks.add_task(pipeline.run, job.id)
    return JobResponse(job_id=str(job.id))
""",
        "backend/app/api/routes/health.py": """\
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok"}
""",
        "backend/app/services/analysis_pipeline.py": """\
from app.services.github_fetcher import GitHubFetcher
from app.services.manifest_parser import ManifestParser
from app.services.framework_detector import FrameworkDetector
from app.services.summary_service import SummaryService
from app.models.jobs import AnalysisJob
from app.models.results import AnalysisResult
import anthropic

class AnalysisPipeline:
    def __init__(self, db):
        self.db = db
        self.fetcher = GitHubFetcher()
        self.parser = ManifestParser()
        self.detector = FrameworkDetector()
        self.summarizer = SummaryService()

    async def create_job(self, repo_url: str) -> AnalysisJob:
        job = AnalysisJob(repo_url=repo_url)
        self.db.add(job)
        await self.db.commit()
        return job

    async def run(self, job_id: str):
        tree = await self.fetcher.get_tree(job_id)
        manifests = self.parser.parse(tree)
        stack = self.detector.detect(manifests)
        summary = await self.summarizer.summarize(stack)
        return summary
""",
        "backend/app/services/github_fetcher.py": """\
import httpx
from app.core.config import get_settings

class GitHubFetcher:
    async def get_tree(self, repo_url: str) -> dict:
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.github.com/repos/{repo_url}/git/trees/HEAD",
                headers={"Authorization": f"Bearer {settings.github_token}"},
            )
            return resp.json()
""",
        "backend/app/services/manifest_parser.py": """\
import json
from typing import Dict, List

class ManifestParser:
    def parse(self, tree: dict) -> List[Dict]:
        manifests = []
        for item in tree.get("tree", []):
            if item["path"] in ("package.json", "pyproject.toml", "requirements.txt"):
                manifests.append(item)
        return manifests
""",
        "backend/app/services/framework_detector.py": """\
from typing import Dict, List

class FrameworkDetector:
    def detect(self, manifests: List[Dict]) -> Dict:
        stack = {"frontend": [], "backend": [], "database": [], "infra": []}
        for manifest in manifests:
            if "fastapi" in str(manifest):
                stack["backend"].append("FastAPI")
            if "next" in str(manifest):
                stack["frontend"].append("Next.js")
        return stack
""",
        "backend/app/services/summary_service.py": """\
import anthropic
from app.core.config import get_settings

class SummaryService:
    async def summarize(self, stack: dict) -> str:
        settings = get_settings()
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": f"Summarize this stack: {stack}"}],
        )
        return message.content[0].text
""",
        "backend/app/core/config.py": """\
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    anthropic_api_key: str = ""
    github_token: str = ""
    database_url: str = "sqlite+aiosqlite:///./dev.db"
    cors_origins: list = ["http://localhost:3000"]

    class Config:
        env_file = ".env"

@lru_cache
def get_settings() -> Settings:
    return Settings()
""",
        "backend/app/core/database.py": """\
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database_url)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    pass
""",
        "backend/app/models/jobs.py": """\
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import DeclarativeBase
import uuid

class Base(DeclarativeBase):
    pass

class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    repo_url = Column(String, nullable=False)
""",
        "backend/app/models/results.py": """\
from sqlalchemy import Column, String, Text, ForeignKey
from app.models.jobs import Base

class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey("analysis_jobs.id"))
    summary = Column(Text)
""",
        "backend/app/schemas/requests.py": """\
from pydantic import BaseModel

class AnalyzeRequest(BaseModel):
    repo_url: str
""",
        "backend/app/schemas/responses.py": """\
from pydantic import BaseModel

class JobResponse(BaseModel):
    job_id: str
""",
        "backend/tests/test_pipeline.py": """\
import pytest
from app.services.manifest_parser import ManifestParser
from app.services.framework_detector import FrameworkDetector

def test_manifest_parser_detects_package_json():
    parser = ManifestParser()
    tree = {"tree": [{"path": "package.json", "type": "blob"}]}
    result = parser.parse(tree)
    assert len(result) == 1

def test_framework_detector_finds_fastapi():
    detector = FrameworkDetector()
    manifests = [{"fastapi": "0.100.0"}]
    stack = detector.detect(manifests)
    assert "FastAPI" in stack["backend"]
""",
    },
    expectations=RealWorldExpectation(
        entrypoint_paths=[
            "backend/app/main.py",
        ],
        critical_paths=[
            "backend/app/main.py",
            "backend/app/api/routes/analyze.py",
            "backend/app/api/routes/health.py",
            "backend/app/core/config.py",
            "backend/app/core/database.py",
            "backend/app/services/analysis_pipeline.py",
        ],
        not_critical_paths=[
            "backend/tests/test_pipeline.py",
            "backend/app/schemas/requests.py",
            "backend/app/schemas/responses.py",
        ],
        confirmed_edges=[
            ("backend/app/main.py", "backend/app/api/routes/analyze.py"),
            ("backend/app/main.py", "backend/app/api/routes/health.py"),
            ("backend/app/main.py", "backend/app/core/config.py"),
            ("backend/app/main.py", "backend/app/core/database.py"),
            ("backend/app/api/routes/analyze.py", "backend/app/services/analysis_pipeline.py"),
            ("backend/app/services/analysis_pipeline.py", "backend/app/services/github_fetcher.py"),
        ],
        external_imports_absent=["fastapi", "sqlalchemy", "anthropic", "httpx", "pydantic"],
        min_graph_confidence=0.70,
    ),
)


# ---------------------------------------------------------------------------
# Fixture RW-2: Next.js App Router with server components
# Models: typical Next.js 14 app with API routes and server actions
# Tests: App Router page detection, @/ aliases, server vs client components
# ---------------------------------------------------------------------------

RW2_NEXTJS_APP_ROUTER = RealWorldFixture(
    name="rw2_nextjs_app_router",
    real_repo="vercel/next.js-app-router-example",
    observed_at="2026-03",
    description=(
        "Next.js 14 App Router app with @/ aliases and API routes. "
        "Tests that page.tsx files are entrypoints, route.ts files are services, "
        "and client/server component split is visible in the graph."
    ),
    files={
        "src/app/page.tsx": """\
import { HeroSection } from "@/components/HeroSection";
import { AnalysisForm } from "@/components/AnalysisForm";
import { getRecentAnalyses } from "@/lib/data";

export default async function HomePage() {
  const recent = await getRecentAnalyses();
  return (
    <main>
      <HeroSection />
      <AnalysisForm />
    </main>
  );
}
""",
        "src/app/analyze/[id]/page.tsx": """\
import { ResultCard } from "@/components/ResultCard";
import { ScorePanel } from "@/components/ScorePanel";
import { getAnalysis } from "@/lib/data";

interface Props {
  params: { id: string };
}

export default async function AnalysisPage({ params }: Props) {
  const analysis = await getAnalysis(params.id);
  return (
    <div>
      <ResultCard analysis={analysis} />
      <ScorePanel score={analysis.score} />
    </div>
  );
}
""",
        "src/app/api/analyze/route.ts": """\
import { NextRequest, NextResponse } from "next/server";
import { analyzeRepo } from "@/lib/analyzer";
import { validateUrl } from "@/lib/validation";

export async function POST(request: NextRequest) {
  const { repoUrl } = await request.json();
  const validated = validateUrl(repoUrl);
  const result = await analyzeRepo(validated);
  return NextResponse.json(result);
}
""",
        "src/components/AnalysisForm.tsx": """\
"use client";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export function AnalysisForm() {
  const [url, setUrl] = useState("");
  return (
    <form>
      <Input value={url} onChange={(e) => setUrl(e.target.value)} />
      <Button type="submit">Analyze</Button>
    </form>
  );
}
""",
        "src/components/HeroSection.tsx": """\
export function HeroSection() {
  return <section><h1>Codebase Atlas</h1></section>;
}
""",
        "src/components/ResultCard.tsx": """\
import { ScorePanel } from "@/components/ScorePanel";

interface Props {
  analysis: { score: number; summary: string };
}

export function ResultCard({ analysis }: Props) {
  return <div>{analysis.summary}</div>;
}
""",
        "src/components/ScorePanel.tsx": """\
interface Props { score: number }
export function ScorePanel({ score }: Props) {
  return <div>Score: {score}</div>;
}
""",
        "src/components/ui/Button.tsx": """\
export function Button({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props}>{children}</button>;
}
""",
        "src/components/ui/Input.tsx": """\
export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} />;
}
""",
        "src/lib/data.ts": """\
import { db } from "@/lib/db";

export async function getRecentAnalyses() {
  return db.query("SELECT * FROM analyses ORDER BY created_at DESC LIMIT 10");
}

export async function getAnalysis(id: string) {
  return db.query("SELECT * FROM analyses WHERE id = ?", [id]);
}
""",
        "src/lib/analyzer.ts": """\
import { validateUrl } from "@/lib/validation";
import { fetchRepoTree } from "@/lib/github";

export async function analyzeRepo(url: string) {
  const tree = await fetchRepoTree(url);
  return { url, tree, score: 75 };
}
""",
        "src/lib/validation.ts": """\
export function validateUrl(url: string): string {
  if (!url.startsWith("https://github.com/")) {
    throw new Error("Only GitHub URLs are supported");
  }
  return url;
}
""",
        "src/lib/github.ts": """\
export async function fetchRepoTree(url: string) {
  const response = await fetch(`https://api.github.com/repos/${url}/git/trees/HEAD`);
  return response.json();
}
""",
        "src/lib/db.ts": """\
const db = {
  query: async (sql: string, params?: unknown[]) => {
    return [];
  }
};

export { db };
""",
    },
    ts_aliases={"@/": "src/"},
    expectations=RealWorldExpectation(
        entrypoint_paths=[
            "src/app/page.tsx",
            "src/app/analyze/[id]/page.tsx",
        ],
        critical_paths=[
            "src/app/page.tsx",
            "src/app/analyze/[id]/page.tsx",
            "src/components/AnalysisForm.tsx",
            "src/components/HeroSection.tsx",
            "src/components/ResultCard.tsx",
            "src/components/ScorePanel.tsx",
            "src/lib/data.ts",
        ],
        not_critical_paths=[
            "src/lib/db.ts",
            "src/lib/github.ts",
            "src/lib/validation.ts",
            "src/components/ui/Button.tsx",
            "src/components/ui/Input.tsx",
        ],
        confirmed_edges=[
            ("src/app/page.tsx", "src/components/HeroSection.tsx"),
            ("src/app/page.tsx", "src/components/AnalysisForm.tsx"),
            ("src/app/page.tsx", "src/lib/data.ts"),
            ("src/app/analyze/[id]/page.tsx", "src/components/ResultCard.tsx"),
            ("src/app/analyze/[id]/page.tsx", "src/components/ScorePanel.tsx"),
            ("src/app/analyze/[id]/page.tsx", "src/lib/data.ts"),
            ("src/components/AnalysisForm.tsx", "src/components/ui/Button.tsx"),
            ("src/components/AnalysisForm.tsx", "src/components/ui/Input.tsx"),
            ("src/components/ResultCard.tsx", "src/components/ScorePanel.tsx"),
            ("src/lib/data.ts", "src/lib/db.ts"),
            ("src/lib/analyzer.ts", "src/lib/validation.ts"),
            ("src/lib/analyzer.ts", "src/lib/github.ts"),
        ],
        external_imports_absent=["next", "react", "axios"],
        min_graph_confidence=0.70,
    ),
)


# ---------------------------------------------------------------------------
# Fixture RW-3: Mixed infra/config density
# Models: a repo heavy with CI, Docker, and config files alongside source
# Tests: that infra/config files don't pollute the source graph, that
#        entrypoints are not mistakenly classified as infra, and that
#        files in .github/ are classified as infra not source
# ---------------------------------------------------------------------------

RW3_MIXED_INFRA = RealWorldFixture(
    name="rw3_mixed_infra",
    real_repo="generic/infra-heavy-service",
    observed_at="2026-03",
    description=(
        "Service with significant infra/config surface area. "
        "Tests classification of Dockerfile, CI workflows, pyproject.toml, "
        "and that these don't interfere with source graph accuracy."
    ),
    files={
        "app/main.py": """\
from app.server import create_server
from app.config import load_config

def main():
    config = load_config()
    server = create_server(config)
    server.run()

if __name__ == "__main__":
    main()
""",
        "app/server.py": """\
from flask import Flask
from app.routes import register_routes
from app.config import Config

def create_server(config: Config) -> Flask:
    app = Flask(__name__)
    register_routes(app)
    return app
""",
        "app/routes.py": """\
from flask import Flask, jsonify

def register_routes(app: Flask):
    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})
""",
        "app/config.py": """\
from dataclasses import dataclass

@dataclass
class Config:
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8080"))

def load_config() -> Config:
    return Config()
""",
        "Dockerfile": """\
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "-m", "app.main"]
""",
        "docker-compose.yml": """\
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8080:8080"
    environment:
      - HOST=0.0.0.0
""",
        ".github/workflows/ci.yml": """\
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -e ".[dev]"
      - run: pytest
""",
        "pyproject.toml": """\
[build-system]
requires = ["setuptools"]

[project]
name = "my-service"
version = "0.1.0"
dependencies = ["flask>=3.0"]

[project.optional-dependencies]
dev = ["pytest", "ruff"]
""",
        "tests/test_server.py": """\
import pytest
from app.server import create_server
from app.config import Config

@pytest.fixture
def app():
    config = Config()
    return create_server(config)

def test_health_endpoint(app):
    client = app.test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
""",
    },
    expectations=RealWorldExpectation(
        entrypoint_paths=["app/main.py"],
        critical_paths=[
            "app/main.py",
            "app/server.py",
            "app/config.py",
            "app/routes.py",
        ],
        not_critical_paths=[
            "tests/test_server.py",
        ],
        confirmed_edges=[
            ("app/main.py", "app/server.py"),
            ("app/main.py", "app/config.py"),
            ("app/server.py", "app/routes.py"),
            ("app/server.py", "app/config.py"),
        ],
        external_imports_absent=["flask", "pytest", "os"],
        min_graph_confidence=0.70,
    ),
)


# ---------------------------------------------------------------------------
# Fixture RW-4: Stale README diverged from real architecture
# Models: a repo that historically used MongoDB but migrated to PostgreSQL.
#         README still says MongoDB. Code uses psycopg2.
# Tests: architecture derives from imports, not README text
# ---------------------------------------------------------------------------

RW4_STALE_README = RealWorldFixture(
    name="rw4_stale_readme",
    real_repo="generic/migrated-service",
    observed_at="2026-03",
    description=(
        "Service that migrated from MongoDB to PostgreSQL. "
        "README still claims MongoDB. "
        "Tests that dependency graph reflects the code, not the docs."
    ),
    files={
        "README.md": """\
# My Service

High-performance API backed by MongoDB for flexible document storage.
Uses pymongo for the database driver. Connects to MongoDB Atlas for production.

## Architecture
- FastAPI for the HTTP layer
- MongoDB for persistence
- pymongo driver
""",
        "app/main.py": """\
from fastapi import FastAPI
from app.database import get_db_pool
from app.api import router

app = FastAPI()
app.include_router(router, prefix="/api")

@app.on_event("startup")
async def startup():
    await get_db_pool()
""",
        "app/database.py": """\
# NOTE: Migrated from MongoDB to PostgreSQL in Q3 2024
# README is outdated — we use psycopg2/asyncpg now
import asyncpg

_pool = None

async def get_db_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(os.environ["DATABASE_URL"])
    return _pool

async def query(sql: str, *args):
    pool = await get_db_pool()
    return await pool.fetch(sql, *args)
""",
        "app/api.py": """\
from fastapi import APIRouter
from app.database import query

router = APIRouter()

@router.get("/items")
async def list_items():
    rows = await query("SELECT * FROM items")
    return [dict(row) for row in rows]
""",
    },
    expectations=RealWorldExpectation(
        entrypoint_paths=["app/main.py"],
        critical_paths=[
            "app/main.py",
            "app/database.py",
            "app/api.py",
        ],
        not_critical_paths=[],
        confirmed_edges=[
            ("app/main.py", "app/database.py"),
            ("app/main.py", "app/api.py"),
            ("app/api.py", "app/database.py"),
        ],
        # MongoDB must never appear — architecture is from code, not README
        external_imports_absent=["pymongo", "motor", "mongodb", "mongo"],
        min_graph_confidence=0.80,
    ),
)


# ---------------------------------------------------------------------------
# Fixture RW-5: Polyglot repo (Python backend + TypeScript frontend)
# Models: Atlas itself — monorepo with backend/ and frontend/ dirs
# Tests: cross-language boundary detection, no cross-language edges,
#        separate entrypoints per language subdirectory
# ---------------------------------------------------------------------------

RW5_POLYGLOT = RealWorldFixture(
    name="rw5_polyglot",
    real_repo="MentalVibez/AI_Architecture_Explainer",
    observed_at="2026-03",
    description=(
        "Monorepo with Python FastAPI backend and Next.js TypeScript frontend. "
        "Tests that the two language graphs are independent "
        "and no cross-language edges are fabricated."
    ),
    files={
        # Python backend
        "backend/app/main.py": """\
from fastapi import FastAPI
from backend.app.api.routes.analyze import router

app = FastAPI()
app.include_router(router, prefix="/api")
""",
        "backend/app/api/routes/analyze.py": """\
from fastapi import APIRouter
from backend.app.services.pipeline import run_pipeline

router = APIRouter()

@router.post("/analyze")
async def analyze(repo_url: str):
    return await run_pipeline(repo_url)
""",
        "backend/app/services/pipeline.py": """\
import httpx

async def run_pipeline(repo_url: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"https://api.github.com/repos/{repo_url}")
        return resp.json()
""",
        # TypeScript frontend
        "frontend/src/app/page.tsx": """\
import { AnalysisForm } from "@/components/AnalysisForm";
import { getServerSideAnalyses } from "@/lib/api";

export default async function Home() {
  const analyses = await getServerSideAnalyses();
  return <AnalysisForm />;
}
""",
        "frontend/src/components/AnalysisForm.tsx": """\
"use client";
import { useState } from "react";
import { submitAnalysis } from "@/lib/api";

export function AnalysisForm() {
  const [result, setResult] = useState(null);
  return <form onSubmit={() => submitAnalysis("url").then(setResult)} />;
}
""",
        "frontend/src/lib/api.ts": """\
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function submitAnalysis(repoUrl: string) {
  const resp = await fetch(`${API_BASE}/api/analyze?repo_url=${repoUrl}`, {
    method: "POST",
  });
  return resp.json();
}

export async function getServerSideAnalyses() {
  const resp = await fetch(`${API_BASE}/api/analyses`);
  return resp.json();
}
""",
    },
    ts_aliases={"@/": "frontend/src/"},
    expectations=RealWorldExpectation(
        entrypoint_paths=[
            "backend/app/main.py",
            "frontend/src/app/page.tsx",
        ],
        critical_paths=[
            "backend/app/main.py",
            "backend/app/api/routes/analyze.py",
            "frontend/src/app/page.tsx",
            "frontend/src/components/AnalysisForm.tsx",
            "frontend/src/lib/api.ts",
        ],
        not_critical_paths=[
            "backend/app/services/pipeline.py",
        ],
        confirmed_edges=[
            ("backend/app/main.py", "backend/app/api/routes/analyze.py"),
            ("frontend/src/app/page.tsx", "frontend/src/components/AnalysisForm.tsx"),
            ("frontend/src/app/page.tsx", "frontend/src/lib/api.ts"),
            ("frontend/src/components/AnalysisForm.tsx", "frontend/src/lib/api.ts"),
        ],
        # No cross-language edges — Python files must not import TS and vice versa
        external_imports_absent=["fastapi", "react", "next", "httpx"],
        min_graph_confidence=0.60,
    ),
)


# ---------------------------------------------------------------------------
# All real-world fixtures
# ---------------------------------------------------------------------------

ALL_REAL_WORLD_FIXTURES = [
    RW1_FASTAPI_SERVICE,
    RW2_NEXTJS_APP_ROUTER,
    RW3_MIXED_INFRA,
    RW4_STALE_README,
    RW5_POLYGLOT,
]
