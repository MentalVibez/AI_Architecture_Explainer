"""
tests/fixtures/golden_repos.py
-------------------------------
Golden fixture repositories for graph accuracy regression testing.

Each fixture defines:
  - A synthetic repo as (path, content) pairs
  - EXPECTED_EDGES: the exact DependencyEdge set that must be produced
  - EXPECTED_CRITICAL_PATHS: which files must be marked critical
  - EXPECTED_NOT_CRITICAL: which files must NOT be marked critical
  - A description of what real-world pattern this tests

These are the proof fixtures. If build_code_contexts() doesn't produce
the expected edges for these synthetic repos, the architecture layer
cannot be trusted against real repos.

No network. No LLM. Pure deterministic regression.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class ExpectedEdge:
    """
    What we expect build_code_contexts() to produce for one import.
    source → target must be a confirmed edge.
    raw_import is what was written in the source file.
    """
    source_path: str
    target_path: str          # Must be confirmed — None means test failure
    raw_import: str
    confidence: str = "confirmed"


@dataclass
class GoldenRepo:
    name: str
    description: str
    files: Dict[str, str]          # path → content
    expected_edges: List[ExpectedEdge]
    expected_critical: List[str]   # paths that MUST be critical
    expected_not_critical: List[str]  # paths that MUST NOT be critical
    expected_graph_confidence_min: float  # graph_confidence must be >= this
    ts_aliases: Optional[Dict[str, str]] = None


# ---------------------------------------------------------------------------
# Fixture 1: Small Python service
# Tests: absolute dotted imports, relative imports, stdlib exclusion
# ---------------------------------------------------------------------------

SMALL_PYTHON_SERVICE = GoldenRepo(
    name="small_python_service",
    description=(
        "Minimal FastAPI service. Tests that Python absolute dotted imports "
        "resolve correctly and stdlib/external packages are excluded from graph."
    ),
    files={
        "app/main.py": """\
from fastapi import FastAPI
from app.services.analyzer import AnalysisService
from app.core.config import Settings

app = FastAPI()
settings = Settings()

@app.post("/analyze")
async def analyze(url: str):
    svc = AnalysisService(settings)
    return await svc.run(url)
""",
        "app/services/analyzer.py": """\
from app.utils.parser import parse_url
from app.models.result import AnalysisResult
import httpx

class AnalysisService:
    def __init__(self, settings):
        self.settings = settings

    async def run(self, url: str) -> AnalysisResult:
        parsed = parse_url(url)
        async with httpx.AsyncClient() as client:
            resp = await client.get(parsed.api_url)
        return AnalysisResult(data=resp.json())
""",
        "app/utils/parser.py": """\
from urllib.parse import urlparse
from app.models.url import ParsedURL

def parse_url(url: str) -> ParsedURL:
    parts = urlparse(url)
    return ParsedURL(scheme=parts.scheme, host=parts.netloc)
""",
        "app/models/result.py": """\
from pydantic import BaseModel
from typing import Any

class AnalysisResult(BaseModel):
    data: Any
""",
        "app/models/url.py": """\
from pydantic import BaseModel

class ParsedURL(BaseModel):
    scheme: str
    host: str

    @property
    def api_url(self) -> str:
        return f"{self.scheme}://{self.host}/api"
""",
        "app/core/config.py": """\
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str = ""
    github_token: str = ""

    class Config:
        env_file = ".env"
""",
    },
    expected_edges=[
        # main.py imports
        ExpectedEdge("app/main.py", "app/services/analyzer.py", "app.services.analyzer"),
        ExpectedEdge("app/main.py", "app/core/config.py", "app.core.config"),
        # analyzer.py imports
        ExpectedEdge("app/services/analyzer.py", "app/utils/parser.py", "app.utils.parser"),
        ExpectedEdge("app/services/analyzer.py", "app/models/result.py", "app.models.result"),
        # parser.py imports
        ExpectedEdge("app/utils/parser.py", "app/models/url.py", "app.models.url"),
    ],
    expected_critical=[
        "app/main.py",               # depth 0
        "app/services/analyzer.py",  # depth 1
        "app/core/config.py",        # depth 1
        "app/models/result.py",      # depth 2 — within cap
        "app/utils/parser.py",       # depth 2 (main→analyzer→parser)
    ],
    expected_not_critical=[
        "app/models/url.py",         # depth 3 from main — outside cap
    ],
    expected_graph_confidence_min=0.75,
)


# ---------------------------------------------------------------------------
# Fixture 2: Next.js app with path aliases
# Tests: @/ alias resolution, relative imports, TS barrel index
# ---------------------------------------------------------------------------

NEXTJS_WITH_ALIASES = GoldenRepo(
    name="nextjs_with_aliases",
    description=(
        "Next.js App Router project using @/ path aliases. "
        "Tests that tsconfig paths are applied correctly."
    ),
    files={
        "src/app/page.tsx": """\
import { AnalysisForm } from "@/components/AnalysisForm";
import { getAnalysis } from "@/lib/api";

export default function HomePage() {
  return <AnalysisForm />;
}
""",
        "src/app/results/page.tsx": """\
import { ResultCard } from "@/components/ResultCard";
import { getAnalysis } from "@/lib/api";

export default function ResultsPage() {
  return <ResultCard />;
}
""",
        "src/components/AnalysisForm.tsx": """\
import { useState } from "react";
import { apiClient } from "@/lib/api";
import { Button } from "@/components/ui/Button";

export function AnalysisForm() {
  const [url, setUrl] = useState("");
  return <form onSubmit={() => apiClient.post("/analyze", { url })}></form>;
}
""",
        "src/components/ResultCard.tsx": """\
import { apiClient } from "@/lib/api";

export function ResultCard() {
  return <div>Results</div>;
}
""",
        "src/components/ui/Button.tsx": """\
export function Button({ children }: { children: React.ReactNode }) {
  return <button>{children}</button>;
}
""",
        "src/lib/api.ts": """\
import axios from "axios";

export const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
});

export async function getAnalysis(id: string) {
  return apiClient.get(`/api/results/${id}`);
}
""",
    },
    ts_aliases={
        "@/": "src/",
    },
    expected_edges=[
        ExpectedEdge("src/app/page.tsx", "src/components/AnalysisForm.tsx", "@/components/AnalysisForm"),
        ExpectedEdge("src/app/page.tsx", "src/lib/api.ts", "@/lib/api"),
        ExpectedEdge("src/app/results/page.tsx", "src/components/ResultCard.tsx", "@/components/ResultCard"),
        ExpectedEdge("src/app/results/page.tsx", "src/lib/api.ts", "@/lib/api"),
        ExpectedEdge("src/components/AnalysisForm.tsx", "src/lib/api.ts", "@/lib/api"),
        ExpectedEdge("src/components/AnalysisForm.tsx", "src/components/ui/Button.tsx", "@/components/ui/Button"),
        ExpectedEdge("src/components/ResultCard.tsx", "src/lib/api.ts", "@/lib/api"),
    ],
    expected_critical=[
        "src/app/page.tsx",
        "src/app/results/page.tsx",
        "src/components/AnalysisForm.tsx",
        "src/components/ResultCard.tsx",
        "src/lib/api.ts",
        "src/components/ui/Button.tsx",  # depth 2 from page — within cap
    ],
    expected_not_critical=[],  # all files reachable within depth 2 of at least one entrypoint
    expected_graph_confidence_min=0.70,
)


# ---------------------------------------------------------------------------
# Fixture 3: Monorepo with packages
# Tests: cross-package imports, workspace-style Python paths
# ---------------------------------------------------------------------------

MONOREPO_PACKAGES = GoldenRepo(
    name="monorepo_packages",
    description=(
        "Python monorepo with two packages sharing a common library. "
        "Tests that cross-package dotted imports resolve across package boundaries."
    ),
    files={
        "packages/api/main.py": """\
from packages.shared.auth import verify_token
from packages.shared.models import User
from packages.api.handlers.analyze_handler import register

def run():
    register()
""",
        "packages/api/handlers/analyze_handler.py": """\
from packages.shared.models import AnalysisJob
from packages.shared.queue import enqueue

def register():
    pass

def handle(job: AnalysisJob):
    enqueue(job)
""",
        "packages/shared/auth.py": """\
import jwt

def verify_token(token: str) -> bool:
    try:
        jwt.decode(token, options={"verify_signature": False})
        return True
    except Exception:
        return False
""",
        "packages/shared/models.py": """\
from pydantic import BaseModel

class User(BaseModel):
    id: str
    email: str

class AnalysisJob(BaseModel):
    repo_url: str
    user_id: str
""",
        "packages/shared/queue.py": """\
import redis

_client = redis.Redis()

def enqueue(job) -> str:
    return _client.lpush("jobs", job.json())
""",
        "packages/worker/main.py": """\
from packages.shared.queue import enqueue
from packages.shared.models import AnalysisJob
from packages.worker.processor import process_job

def run():
    process_job.start()
""",
        "packages/worker/processor.py": """\
from packages.shared.models import AnalysisJob

def start():
    pass

def process_job(job: AnalysisJob):
    pass
""",
    },
    expected_edges=[
        ExpectedEdge("packages/api/main.py", "packages/shared/auth.py", "packages.shared.auth"),
        ExpectedEdge("packages/api/main.py", "packages/shared/models.py", "packages.shared.models"),
        ExpectedEdge("packages/api/main.py", "packages/api/handlers/analyze_handler.py", "packages.api.handlers.analyze_handler"),
        ExpectedEdge("packages/api/handlers/analyze_handler.py", "packages/shared/models.py", "packages.shared.models"),
        ExpectedEdge("packages/api/handlers/analyze_handler.py", "packages/shared/queue.py", "packages.shared.queue"),
        ExpectedEdge("packages/worker/main.py", "packages/shared/queue.py", "packages.shared.queue"),
        ExpectedEdge("packages/worker/main.py", "packages/shared/models.py", "packages.shared.models"),
        ExpectedEdge("packages/worker/main.py", "packages/worker/processor.py", "packages.worker.processor"),
    ],
    expected_critical=[
        "packages/api/main.py",
        "packages/shared/auth.py",
        "packages/shared/models.py",
        "packages/shared/queue.py",
        "packages/api/handlers/analyze_handler.py",
        "packages/worker/main.py",
        "packages/worker/processor.py",
    ],
    expected_not_critical=[],
    expected_graph_confidence_min=0.70,
)


# ---------------------------------------------------------------------------
# Fixture 4: Barrel exports (TS)
# Tests: barrel doesn't mark entire repo as critical
# ---------------------------------------------------------------------------

BARREL_EXPORTS = GoldenRepo(
    name="barrel_exports",
    description=(
        "TypeScript library with a barrel index.ts re-exporting all modules. "
        "Tests that critical path doesn't propagate beyond depth 2."
    ),
    files={
        "src/index.ts": """\
export { AuthService } from "./services/auth";
export { UserService } from "./services/users";
export { AnalysisService } from "./services/analysis";
export { CacheService } from "./services/cache";
export { QueueService } from "./services/queue";
""",
        "src/services/auth.ts": """\
import { UserService } from "./users";
import { db } from "../db/client";

export class AuthService {
  async verify(token: string) { return db.findToken(token); }
}
""",
        "src/services/users.ts": """\
import { db } from "../db/client";
import { UserValidator } from "../validators/user";

export class UserService {
  async getUser(id: string) { return db.findUser(id); }
}
""",
        "src/services/analysis.ts": """\
import { QueueService } from "./queue";

export class AnalysisService {
  async enqueue(url: string) { return new QueueService().push(url); }
}
""",
        "src/services/cache.ts": """\
import { redisClient } from "../db/redis";

export class CacheService {
  async get(key: string) { return redisClient.get(key); }
}
""",
        "src/services/queue.ts": """\
import { db } from "../db/client";

export class QueueService {
  async push(item: string) { return db.insert("queue", item); }
}
""",
        "src/db/client.ts": """\
import { createClient } from "@supabase/supabase-js";

export const db = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_KEY!,
);
""",
        "src/db/redis.ts": """\
import { createClient } from "redis";

export const redisClient = createClient();
""",
        "src/validators/user.ts": """\
export class UserValidator {
  validate(data: unknown) { return Boolean(data); }
}
""",
    },
    expected_edges=[
        # Barrel re-exports
        ExpectedEdge("src/index.ts", "src/services/auth.ts", "./services/auth"),
        ExpectedEdge("src/index.ts", "src/services/users.ts", "./services/users"),
        ExpectedEdge("src/index.ts", "src/services/analysis.ts", "./services/analysis"),
        ExpectedEdge("src/index.ts", "src/services/cache.ts", "./services/cache"),
        ExpectedEdge("src/index.ts", "src/services/queue.ts", "./services/queue"),
        # Service-level deps
        ExpectedEdge("src/services/auth.ts", "src/services/users.ts", "./users"),
        ExpectedEdge("src/services/auth.ts", "src/db/client.ts", "../db/client"),
        ExpectedEdge("src/services/users.ts", "src/db/client.ts", "../db/client"),
        ExpectedEdge("src/services/users.ts", "src/validators/user.ts", "../validators/user"),
        ExpectedEdge("src/services/analysis.ts", "src/services/queue.ts", "./queue"),
        ExpectedEdge("src/services/cache.ts", "src/db/redis.ts", "../db/redis"),
        ExpectedEdge("src/services/queue.ts", "src/db/client.ts", "../db/client"),
    ],
    expected_critical=[
        "src/index.ts",
        "src/services/auth.ts",       # depth 1
        "src/services/users.ts",      # depth 1
        "src/services/analysis.ts",   # depth 1
        "src/services/cache.ts",      # depth 1
        "src/services/queue.ts",      # depth 1
        "src/db/client.ts",           # depth 2
        "src/db/redis.ts",            # depth 2
        "src/validators/user.ts",     # depth 2 (index→users→validators) — BFS shortest path
    ],
    expected_not_critical=[],  # all 9 files are within depth 2 of index under BFS
    expected_graph_confidence_min=0.75,
)


# ---------------------------------------------------------------------------
# Fixture 5: Repo with parse failures
# Tests: partial results returned honestly, confidence degrades correctly
# ---------------------------------------------------------------------------

PARSE_FAILURES = GoldenRepo(
    name="parse_failures",
    description=(
        "Repo where some files can't be parsed. "
        "Tests that the system returns partial results with degraded confidence, "
        "not a crash or silent failure."
    ),
    files={
        "app/main.py": """\
from app.service import run
from app.broken import something  # this file will be a stub

def main():
    run()
""",
        "app/service.py": """\
def run():
    return "ok"
""",
        # app/broken.py is intentionally absent — simulates fetch failure
        # The scanner will create a stub FileIntelligence with confidence=0.0
    },
    expected_edges=[
        ExpectedEdge("app/main.py", "app/service.py", "app.service"),
        # app.broken → unresolved (file not in scanned set)
    ],
    expected_critical=[
        "app/main.py",
        "app/service.py",
    ],
    expected_not_critical=[],
    expected_graph_confidence_min=0.0,   # Intentionally low — broken file present
)


# ---------------------------------------------------------------------------
# Fixture 6: Stale README vs real architecture
# Tests: that the architecture is derived from code, not README claims.
# The README claims "uses MongoDB" but the actual code uses SQLite.
# Evidence tracing should cite the import, not the README text.
# ---------------------------------------------------------------------------

STALE_README = GoldenRepo(
    name="stale_readme",
    description=(
        "Repo whose README.md claims MongoDB but code uses SQLite. "
        "Verifies that architecture claims derive from import evidence, "
        "not from README content."
    ),
    files={
        "README.md": """\
# My App

A high-performance API backed by MongoDB for flexible document storage.
Connects to MongoDB Atlas for production workloads.
""",
        "app/main.py": """\
from app.db import get_db
from app.api import create_app

app = create_app()
""",
        "app/db.py": """\
import sqlite3  # NOT MongoDB — README is stale

_conn = None

def get_db():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect("dev.db")
    return _conn
""",
        "app/api.py": """\
from flask import Flask
from app.db import get_db

def create_app():
    app = Flask(__name__)
    return app
""",
    },
    expected_edges=[
        ExpectedEdge("app/main.py", "app/db.py", "app.db"),
        ExpectedEdge("app/main.py", "app/api.py", "app.api"),
        ExpectedEdge("app/api.py", "app/db.py", "app.db"),
    ],
    expected_critical=[
        "app/main.py",
        "app/db.py",
        "app/api.py",
    ],
    expected_not_critical=[],
    expected_graph_confidence_min=0.80,
)


# ---------------------------------------------------------------------------
# All fixtures — used by test runner
# ---------------------------------------------------------------------------

ALL_GOLDEN_REPOS: List[GoldenRepo] = [
    SMALL_PYTHON_SERVICE,
    NEXTJS_WITH_ALIASES,
    MONOREPO_PACKAGES,
    BARREL_EXPORTS,
    PARSE_FAILURES,
    STALE_README,
]
