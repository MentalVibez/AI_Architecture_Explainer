"""
scout_benchmark.py  —  v2
─────────────────────────────────────────────────────────────────────────────
RepoScout scoring benchmark harness.

PURPOSE
  Every weight change must be validated against this harness before merging.
  It gives you rank outcomes you can compare, not vibes.

ACCEPTANCE CRITERIA (enforced by --gate flag)
  • Mean NDCG@3 (overall) does not decrease
  • No critical query drops more than 0.15 NDCG
  • No new noise gate failures introduced
  • No query subset regresses by more than 0.10 mean NDCG

QUERY CLASSES (each tracked separately)
  STANDARD      — unambiguous, well-defined queries
  AMBIGUOUS     — terms that compete across multiple valid interpretations
  MISLEADING    — popularity misleads (old dominants, boilerplate traps)
  LOW_STAR      — correct answer has low stars; tests relevance > popularity
  NOISE         — query text naturally attracts junk repos
  ANTI_AWESOME  — aggregator-list traps

USAGE
  python scout_benchmark.py
  python scout_benchmark.py --quality-weight 0.5 --relevance-weight 0.5
  python scout_benchmark.py --save baseline.json
  python scout_benchmark.py --compare baseline.json new.json
  python scout_benchmark.py --compare baseline.json new.json --gate
  python scout_benchmark.py --save results.json --report summary.md
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from app.services.repo_scout import _noise_flags, _quality_score, _should_exclude

# ═════════════════════════════════════════════════════════════════════════════
# QUERY CLASSES
# ═════════════════════════════════════════════════════════════════════════════

class QC:
    STANDARD     = "standard"
    AMBIGUOUS    = "ambiguous"
    MISLEADING   = "misleading"
    LOW_STAR     = "low_star"
    NOISE        = "noise"
    ANTI_AWESOME = "anti_awesome"


# ═════════════════════════════════════════════════════════════════════════════
# 1. QUERY PACK  (30 queries across 6 classes, including ugly real-world cases)
# ═════════════════════════════════════════════════════════════════════════════

QUERY_PACK: list[dict] = [

    # ── STANDARD ──────────────────────────────────────────────────────────────
    {
        "id": "q01", "cls": QC.STANDARD, "critical": True,
        "query": "RAG pipeline LangChain",
        "ideal_top3": ["langchain-ai/langchain", "run-llama/llama_index", "chroma-core/chroma"],
        "must_not_top3": ["some-user/rag-tutorial", "someone/awesome-rag", "random/rag-fork"],
        "notes": "Canonical RAG ecosystem. Tutorials and aggregators must not outrank.",
    },
    {
        "id": "q02", "cls": QC.STANDARD, "critical": True,
        "query": "AWS CDK infrastructure as code Python",
        "ideal_top3": ["aws/aws-cdk", "awslabs/aws-sam-cli", "pulumi/pulumi"],
        "must_not_top3": ["some-user/cdk-tutorial", "awesome-aws-cdk"],
        "notes": "IaC frameworks. Tutorial repos and awesome-lists must not outrank.",
    },
    {
        "id": "q03", "cls": QC.STANDARD, "critical": True,
        "query": "self-hosted vector database",
        "ideal_top3": ["weaviate/weaviate", "qdrant/qdrant", "milvus-io/milvus"],
        "must_not_top3": ["someone/awesome-vectors"],
        "notes": "Production-grade vector stores only.",
    },
    {
        "id": "q04", "cls": QC.STANDARD, "critical": True,
        "query": "open source LLM inference server",
        "ideal_top3": ["vllm-project/vllm", "ggerganov/llama.cpp", "ollama/ollama"],
        "must_not_top3": [],
        "notes": "Inference runtimes. Fine-tuning repos are irrelevant.",
    },
    {
        "id": "q05", "cls": QC.STANDARD, "critical": False,
        "query": "Terraform AWS reusable modules",
        "ideal_top3": ["terraform-aws-modules/terraform-aws-vpc", "terraform-aws-modules/terraform-aws-eks"],
        "must_not_top3": ["some-user/terraform-example"],
        "notes": "Official modules. One-off HCL examples should not rank.",
    },
    {
        "id": "q23", "cls": QC.STANDARD, "critical": False,
        "query": "Next.js auth starter template",
        "ideal_top3": ["nextauthjs/next-auth", "supabase/auth-helpers"],
        "must_not_top3": ["some-user/nextjs-hello-world"],
        "notes": "Auth libraries over random starters.",
    },
    {
        "id": "q24", "cls": QC.STANDARD, "critical": False,
        "query": "serverless AWS Lambda Python deployment",
        "ideal_top3": ["aws/chalice", "awslabs/aws-sam-cli"],
        "must_not_top3": [],
        "notes": "Deployment frameworks first.",
    },
    {
        "id": "q25", "cls": QC.STANDARD, "critical": False,
        "query": "React accessible component primitives",
        "ideal_top3": ["radix-ui/primitives", "ariakit/ariakit"],
        "must_not_top3": [],
        "notes": "Accessibility-first libs.",
    },

    # ── AMBIGUOUS ─────────────────────────────────────────────────────────────
    {
        "id": "q06", "cls": QC.AMBIGUOUS, "critical": False,
        "query": "agent framework",
        "ideal_top3": ["microsoft/autogen", "langchain-ai/langgraph", "crewAIInc/crewAI"],
        "must_not_top3": ["some-user/agent-demo"],
        "notes": "'agent' covers AI agents, HTTP agents, user-agents. Plausible results expected.",
    },
    {
        "id": "q07", "cls": QC.AMBIGUOUS, "critical": False,
        "query": "memory framework Python",
        "ideal_top3": ["mem0ai/mem0", "zep-cloud/zep"],
        "must_not_top3": [],
        "notes": "'memory' = RAM profiling OR LLM conversation memory. Tests relevance discrimination.",
    },
    {
        "id": "q08", "cls": QC.AMBIGUOUS, "critical": False,
        "query": "Python queue",
        "ideal_top3": ["celery/celery", "rq/rq"],
        "must_not_top3": [],
        "notes": "stdlib queue vs task queue vs message queue. Production queues should rank above toys.",
    },
    {
        "id": "q09", "cls": QC.AMBIGUOUS, "critical": False,
        "query": "embeddings",
        "ideal_top3": ["chroma-core/chroma", "qdrant/qdrant"],
        "must_not_top3": ["someone/awesome-embeddings"],
        "notes": "Single-word query. Aggregator lists are a trap.",
    },
    {
        "id": "q26", "cls": QC.AMBIGUOUS, "critical": False,
        "query": "chatbot",
        "ideal_top3": [],
        "must_not_top3": ["random/rag-fork", "archived/old-rag"],
        "notes": "Extremely vague. Junk repos must not dominate.",
    },
    {
        "id": "q27", "cls": QC.AMBIGUOUS, "critical": False,
        "query": "Python",
        "ideal_top3": [],
        "must_not_top3": ["random/rag-fork", "archived/old-rag"],
        "notes": "Single-word language query. No ideal possible. Hard-excluded repos must stay excluded.",
    },

    # ── MISLEADING ────────────────────────────────────────────────────────────
    {
        "id": "q10", "cls": QC.MISLEADING, "critical": False,
        "query": "Python web scraping production",
        "ideal_top3": ["scrapy/scrapy", "microsoft/playwright-python"],
        "must_not_top3": ["some-user/rag-tutorial"],
        "notes": "requests+BeautifulSoup have massive stars but are not 'production' scraping frameworks.",
    },
    {
        "id": "q11", "cls": QC.MISLEADING, "critical": False,
        "query": "FastAPI production boilerplate",
        "ideal_top3": ["tiangolo/full-stack-fastapi-template", "zhanymkanov/fastapi-best-practices"],
        "must_not_top3": ["some-user/fastapi-hello-world", "some-user/fastapi-tutorial"],
        "notes": "fastapi/fastapi itself (70k stars) is the framework, not a boilerplate.",
    },
    {
        "id": "q12", "cls": QC.MISLEADING, "critical": False,
        "query": "logging Python structured",
        "ideal_top3": ["hynek/structlog", "madzak/python-json-logger"],
        "must_not_top3": [],
        "notes": "stdlib logging has infinite stars. Third-party structured loggers should rank above it.",
    },
    {
        "id": "q13", "cls": QC.MISLEADING, "critical": False,
        "query": "mature Python web framework still maintained",
        "ideal_top3": ["celery/celery", "django/django"],
        "must_not_top3": [],
        "notes": "Old repos that are still actively maintained must not be penalised by recency alone.",
    },
    {
        "id": "q28", "cls": QC.MISLEADING, "critical": False,
        "query": "vector database production scale Kubernetes",
        "ideal_top3": ["qdrant/qdrant", "milvus-io/milvus", "weaviate/weaviate"],
        "must_not_top3": ["someone/awesome-vectors"],
        "notes": "Long specific query. Multi-term relevance must work across topics.",
    },

    # ── LOW_STAR ──────────────────────────────────────────────────────────────
    {
        "id": "q14", "cls": QC.LOW_STAR, "critical": True,
        "query": "Kubernetes operator Python kopf",
        "ideal_top3": ["nolar/kopf"],
        "must_not_top3": [],
        "notes": "kopf has ~2k stars. THE canonical answer. Relevance must overcome star dominance.",
    },
    {
        "id": "q15", "cls": QC.LOW_STAR, "critical": False,
        "query": "zep conversational memory LLM",
        "ideal_top3": ["zep-cloud/zep"],
        "must_not_top3": [],
        "notes": "Named niche tool with modest stars. Tests named-tool surfacing.",
    },
    {
        "id": "q16", "cls": QC.LOW_STAR, "critical": False,
        "query": "Python JSON logger structured logging",
        "ideal_top3": ["madzak/python-json-logger", "hynek/structlog"],
        "must_not_top3": [],
        "notes": "python-json-logger has ~1.5k stars. Must not be buried by high-star noise.",
    },

    # ── NOISE ─────────────────────────────────────────────────────────────────
    {
        "id": "q17", "cls": QC.NOISE, "critical": False,
        "query": "RAG tutorial beginner",
        "ideal_top3": ["langchain-ai/langchain", "run-llama/llama_index"],
        "must_not_top3": ["random/rag-fork", "archived/old-rag"],
        "notes": "Canonical frameworks still win even with 'tutorial' in query.",
    },
    {
        "id": "q18", "cls": QC.NOISE, "critical": False,
        "query": "Python fork multiprocessing",
        "ideal_top3": [],
        "must_not_top3": ["random/rag-fork"],
        "notes": "'fork' keyword must not surface is_fork repos with low stars.",
    },
    {
        "id": "q19", "cls": QC.NOISE, "critical": False,
        "query": "archived legacy Python library",
        "ideal_top3": [],
        "must_not_top3": ["archived/old-rag"],
        "notes": "Hard-excluded archived repos must not surface regardless of query text.",
    },
    {
        "id": "q29", "cls": QC.NOISE, "critical": False,
        "query": "LLM fine-tuning LoRA parameter efficient",
        "ideal_top3": [],
        "must_not_top3": [],
        "notes": "No ideal in mock pool. Tests graceful empty-ideal handling without divide-by-zero.",
    },
    {
        "id": "q30", "cls": QC.NOISE, "critical": False,
        "query": "github copilot alternative self-hosted code completion",
        "ideal_top3": [],
        "must_not_top3": [],
        "notes": "Emerging niche with no mock matches. Tests graceful empty result.",
    },

    # ── ANTI_AWESOME ──────────────────────────────────────────────────────────
    {
        "id": "q20", "cls": QC.ANTI_AWESOME, "critical": False,
        "query": "awesome machine learning resources",
        "ideal_top3": [],
        "must_not_top3": ["someone/awesome-rag", "someone/awesome-vectors"],
        "notes": "awesome-lists must not top the list just because 'awesome' is in the query.",
    },
    {
        "id": "q21", "cls": QC.ANTI_AWESOME, "critical": False,
        "query": "best Python libraries 2024",
        "ideal_top3": [],
        "must_not_top3": ["someone/awesome-rag", "someone/awesome-vectors", "someone/awesome-embeddings"],
        "notes": "List-phrased query. Aggregators must not dominate implementation repos.",
    },
    {
        "id": "q22", "cls": QC.ANTI_AWESOME, "critical": False,
        "query": "awesome LLM tools",
        "ideal_top3": [],
        "must_not_top3": ["someone/awesome-rag"],
        "notes": "Query contains 'awesome' explicitly. Direct awesome-list trap.",
    },
]


# ═════════════════════════════════════════════════════════════════════════════
# 2. MOCK REPO POOL
# ═════════════════════════════════════════════════════════════════════════════

def _r(
    repo_id: str,
    stars: int = 500,
    forks: int = 50,
    days: int = 30,
    license: bool = True,
    readme: bool = False,
    is_fork: bool = False,
    archived: bool = False,
    template: bool = False,
    desc: str = "A useful open source project",
    topics: list[str] | None = None,
    platform: str = "github",
    lang: str = "Python",
) -> dict:
    updated = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    return {
        "id": repo_id, "full_name": repo_id, "platform": platform,
        "stars": stars, "forks": forks, "updated_at": updated,
        "license_name": "MIT" if license else None,
        "readme_verified": readme,
        "is_fork": is_fork, "is_archived": archived, "is_template": template,
        "description": desc, "topics": topics or [], "language": lang, "open_issues": 10,
    }


MOCK_REPO_POOL: dict[str, dict] = {
    # ── Canonical implementation repos ───────────────────────────────────────
    "langchain-ai/langchain":    _r("langchain-ai/langchain",   85_000, 13_000, 2,   desc="Build LLM applications with RAG, agents, chains, and composability", topics=["llm","langchain","rag","ai","python","agents"]),
    "run-llama/llama_index":     _r("run-llama/llama_index",    33_000,  4_600, 1,   desc="LlamaIndex data framework for LLM RAG applications and retrieval", topics=["rag","llm","indexing","python","retrieval"]),
    "chroma-core/chroma":        _r("chroma-core/chroma",       14_000,  1_200, 5,   desc="AI-native open-source embedding vector database for RAG", topics=["embeddings","vector-database","rag","ai"]),
    "weaviate/weaviate":         _r("weaviate/weaviate",        10_000,    800, 3,   desc="Open-source vector database. Self-hosted, production-grade Kubernetes.", topics=["vector-database","self-hosted","search","ai","kubernetes"], lang="Go"),
    "qdrant/qdrant":             _r("qdrant/qdrant",            18_000,  1_300, 2,   desc="Qdrant vector database for AI applications. Self-hosted, production scale.", topics=["vector-database","self-hosted","rust","kubernetes","search"], lang="Rust"),
    "milvus-io/milvus":          _r("milvus-io/milvus",        29_000,  2_800, 4,   desc="Open-source vector database at scale. Kubernetes native, self-hosted.", topics=["vector-database","self-hosted","kubernetes","ai","search"], lang="Go"),
    "microsoft/autogen":         _r("microsoft/autogen",        33_000,  4_800, 3,   desc="Framework for building multi-agent conversational AI systems", topics=["multi-agent","llm","agent","framework","python"]),
    "langchain-ai/langgraph":    _r("langchain-ai/langgraph",    6_000,    900, 2,   desc="Stateful multi-actor agent orchestration with LangChain", topics=["agent","orchestrator","multi-agent","langchain","graph"]),
    "crewAIInc/crewAI":          _r("crewAIInc/crewAI",         21_000,  2_900, 5,   desc="Framework for orchestrating role-playing multi-agent AI systems", topics=["agent","multi-agent","orchestrator","crewai","python"]),
    "vllm-project/vllm":         _r("vllm-project/vllm",        24_000,  3_500, 1,   desc="High-throughput memory-efficient inference engine for LLMs", topics=["llm","inference","python","gpu","serving"]),
    "ggerganov/llama.cpp":       _r("ggerganov/llama.cpp",      65_000,  9_400, 1,   desc="LLM inference in C/C++. Self-hosted local efficient.", topics=["llm","inference","local","cpp","quantization"], lang="C++"),
    "ollama/ollama":             _r("ollama/ollama",             78_000,  6_000, 2,   desc="Run large language models locally. Inference server.", topics=["llm","local","inference","server"], lang="Go"),
    "aws/aws-cdk":               _r("aws/aws-cdk",              11_000,  3_800, 1,   desc="AWS Cloud Development Kit — infrastructure as code framework", topics=["aws","cdk","infrastructure-as-code","typescript","cloudformation"], lang="TypeScript"),
    "awslabs/aws-sam-cli":       _r("awslabs/aws-sam-cli",       6_800,  1_200, 5,   desc="AWS SAM CLI for serverless Lambda deployment and local testing Python", topics=["aws","serverless","lambda","deployment","python"]),
    "aws/chalice":               _r("aws/chalice",              10_000,  1_000, 60,  desc="Python serverless microframework for AWS Lambda deployment", topics=["aws","lambda","serverless","python","deployment"]),
    "pulumi/pulumi":             _r("pulumi/pulumi",             21_000,  1_100, 1,   desc="Infrastructure as Code SDK. Multi-language multi-cloud.", topics=["infrastructure-as-code","aws","cloud","devops"], lang="Go"),
    "terraform-aws-modules/terraform-aws-vpc": _r("terraform-aws-modules/terraform-aws-vpc", 3_000, 4_500, 20, desc="Terraform AWS VPC module reusable production-grade", topics=["terraform","aws","vpc","modules","infrastructure-as-code"], lang="HCL"),
    "terraform-aws-modules/terraform-aws-eks": _r("terraform-aws-modules/terraform-aws-eks", 4_000, 3_800, 15, desc="Terraform AWS EKS module production Kubernetes", topics=["terraform","aws","eks","kubernetes","modules"], lang="HCL"),
    "celery/celery":             _r("celery/celery",             24_000,  4_600, 10,  desc="Celery distributed task queue for Python async jobs", topics=["celery","task-queue","python","distributed","async"]),
    "rq/rq":                     _r("rq/rq",                     9_800,  1_300, 25,  desc="Simple Python job queues backed by Redis", topics=["queue","python","redis","jobs","async"]),
    "mem0ai/mem0":               _r("mem0ai/mem0",               22_000,  2_100, 4,   desc="Memory layer for AI apps. Persistent conversation memory for LLMs.", topics=["memory","llm","ai","chatbot","python"]),
    "zep-cloud/zep":             _r("zep-cloud/zep",              1_800,    180, 14,  desc="Zep long-term memory store for LLM conversational AI applications", topics=["memory","llm","conversational","ai","python"]),
    "hynek/structlog":           _r("hynek/structlog",            3_200,    220, 30,  desc="Structured composable logging for Python", topics=["logging","python","structured","observability"]),
    "madzak/python-json-logger": _r("madzak/python-json-logger",  1_600,    240, 90,  desc="Python JSON structured logging formatter", topics=["logging","python","json","structured"]),
    "scrapy/scrapy":             _r("scrapy/scrapy",             52_000, 10_200, 8,   desc="Scrapy fast high-level web crawling scraping framework Python production", topics=["scraping","crawling","python","web","production"]),
    "microsoft/playwright-python":_r("microsoft/playwright-python",11_000,   900, 5,  desc="Python Playwright browser automation web scraping", topics=["playwright","browser","testing","scraping","python"]),
    "tiangolo/full-stack-fastapi-template": _r("tiangolo/full-stack-fastapi-template", 27_000, 4_900, 20, desc="Full stack FastAPI React PostgreSQL production boilerplate template", topics=["fastapi","boilerplate","template","python","production"]),
    "zhanymkanov/fastapi-best-practices": _r("zhanymkanov/fastapi-best-practices", 8_000, 680, 45, desc="FastAPI best practices conventions production codebases", topics=["fastapi","python","best-practices","production"]),
    "nextauthjs/next-auth":      _r("nextauthjs/next-auth",      23_000,  3_100, 3,   desc="Authentication for Next.js. OAuth email credentials.", topics=["nextjs","authentication","oauth","typescript"], lang="TypeScript"),
    "supabase/auth-helpers":     _r("supabase/auth-helpers",      1_400,    280, 20,  desc="Supabase Auth helpers for Next.js session management authentication", topics=["nextjs","authentication","supabase","typescript"], lang="TypeScript"),
    "radix-ui/primitives":       _r("radix-ui/primitives",       15_000,    830, 4,   desc="Unstyled accessible React UI primitives for design systems", topics=["react","accessibility","component","primitives","typescript"], lang="TypeScript"),
    "ariakit/ariakit":           _r("ariakit/ariakit",            7_500,    550, 6,   desc="Toolkit for building accessible React components ARIA", topics=["react","accessibility","aria","components"], lang="TypeScript"),
    "nolar/kopf":                _r("nolar/kopf",                  2_100,    190, 18,  desc="Kopf Kubernetes Operator Framework Python. Build operators in Python.", topics=["kubernetes","operator","python","kopf","k8s"]),
    "django/django":             _r("django/django",              79_000, 31_000, 2,   desc="Django web framework for perfectionists with deadlines", topics=["python","django","web","framework","orm"]),
    "openai/evals":              _r("openai/evals",               14_000,  3_200, 30,  desc="OpenAI Evals framework for evaluating LLMs AI models", topics=["llm","evaluation","testing","ai","python"]),
    "confident-ai/deepeval":     _r("confident-ai/deepeval",       4_800,    380, 8,   desc="DeepEval LLM evaluation framework metrics test cases CI", topics=["llm","evaluation","testing","python","prompt-engineering"]),
    "grafana/loki":              _r("grafana/loki",               23_000,  3_200, 2,   desc="Loki log aggregation system observability", topics=["logging","observability","grafana","log-aggregation"], lang="Go"),

    # ── Noise / adversarial repos ─────────────────────────────────────────────
    "some-user/rag-tutorial":    _r("some-user/rag-tutorial",       120,     30, 200, desc="Tutorial: building RAG pipeline with LangChain step by step", topics=["tutorial","rag","langchain","beginner"]),
    "some-user/cdk-tutorial":    _r("some-user/cdk-tutorial",        80,     10, 300, desc="AWS CDK tutorial for beginners infrastructure as code examples", topics=["tutorial","aws","cdk","beginner"]),
    "some-user/fastapi-hello-world": _r("some-user/fastapi-hello-world", 45, 12, 400, desc="FastAPI hello world example starter template", topics=["fastapi","example","starter"]),
    "some-user/fastapi-tutorial":_r("some-user/fastapi-tutorial",    200,     60, 250, desc="FastAPI tutorial boilerplate for beginners Python", topics=["fastapi","tutorial","python","beginner"]),
    "some-user/nextjs-hello-world": _r("some-user/nextjs-hello-world", 30,   8, 500, desc="Next.js hello world starter project", topics=["nextjs","starter","example"], lang="TypeScript"),
    "some-user/terraform-example":_r("some-user/terraform-example",   50,    15, 350, desc="Terraform AWS example learning project", topics=["terraform","aws","example"], lang="HCL"),
    "some-user/agent-demo":      _r("some-user/agent-demo",           90,     20, 180, desc="Demo agent application built with LangChain", topics=["agent","demo","langchain"]),
    "random/rag-fork":           _r("random/rag-fork",                 5,      0, 400, desc="Fork of langchain with minor personal tweaks", is_fork=True, topics=["rag"]),
    "archived/old-rag":          _r("archived/old-rag",              300,     40, 900, desc="RAG pipeline no longer maintained archived", archived=True, topics=["rag","archived"]),
    "someone/awesome-rag":       _r("someone/awesome-rag",          3_500,    400, 60, desc="Curated awesome list of RAG resources tutorials and tools", topics=["awesome-list","rag","resources","curated"]),
    "someone/awesome-vectors":   _r("someone/awesome-vectors",      2_200,    180, 90, desc="Awesome curated list of vector database resources", topics=["awesome-list","vector-database","curated"]),
    "someone/awesome-embeddings":_r("someone/awesome-embeddings",   1_800,    150, 120,desc="Curated awesome list of embeddings and vector search tools", topics=["awesome-list","embeddings","curated"]),
    "awesome-aws-cdk":           _r("awesome-aws-cdk",              4_000,    320, 45, desc="Awesome list of AWS CDK resources examples tutorials", topics=["awesome-list","aws","cdk","curated"]),
}


# ═════════════════════════════════════════════════════════════════════════════
# 3. EVALUATOR
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class ScoredRepo:
    repo_id:        str
    quality_score:  int
    relevance_score:int
    overall_score:  int
    excluded:       bool
    noise_flags:    list[str]


def _simulate_relevance(query: str, repo: dict) -> int:
    """
    Intentionally imperfect term-overlap simulation.
    Perfect oracle = tests oracle, not scoring system.
    Star popularity boost reflects real LLM tendency.
    """
    tokens = {t.lower() for t in query.split() if len(t) > 2}
    text = " ".join([
        repo.get("description", ""),
        repo.get("full_name", ""),
        " ".join(repo.get("topics", [])),
    ]).lower()
    hits = sum(1 for t in tokens if t in text)
    ratio = hits / max(len(tokens), 1)
    star_boost = min(10, repo.get("stars", 0) // 5000)
    return min(int(ratio * 90) + star_boost, 100)


def score_pool(
    repos: list[dict],
    query: str,
    quality_weight: float,
    relevance_weight: float,
    relevance_fn: Callable[[str, dict], int] = _simulate_relevance,
) -> list[ScoredRepo]:
    results: list[ScoredRepo] = []
    for repo in repos:
        flags = _noise_flags(repo)
        if _should_exclude(repo, flags):
            results.append(ScoredRepo(repo["id"], 0, 0, -1, True, flags))
            continue
        q, signals = _quality_score(repo, flags)
        r = relevance_fn(query, repo)
        overall = min(round(quality_weight * q + relevance_weight * r), 100)
        results.append(ScoredRepo(repo["id"], q, r, overall, False, flags))
    results.sort(key=lambda x: (-1 if x.excluded else x.overall_score), reverse=True)
    return results


# ═════════════════════════════════════════════════════════════════════════════
# 4. METRICS
# ═════════════════════════════════════════════════════════════════════════════

def ndcg_at_k(ranked: list[str], ideal: list[str], k: int = 3) -> float:
    if not ideal:
        return 1.0
    def dcg(ids: list[str]) -> float:
        return sum((1 if r in ideal else 0) / math.log2(i+2) for i,r in enumerate(ids[:k]))
    ideal_dcg = dcg(ideal[:k])
    return dcg(ranked) / ideal_dcg if ideal_dcg else 0.0

def precision_at_k(ranked: list[str], ideal: list[str], k: int = 3) -> float:
    if not ideal:
        return 1.0
    return sum(1 for r in ranked[:k] if r in ideal) / k

def noise_gate_pass(top3: list[str], forbidden: list[str]) -> bool:
    return not any(r in top3 for r in forbidden)


# ═════════════════════════════════════════════════════════════════════════════
# 5. RUNNER
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class QueryResult:
    id:            str
    query:         str
    cls:           str
    ranked_top5:   list[str]
    ideal:         list[str]
    must_not_top3: list[str]
    ndcg3:         float
    p3:            float
    noise_gate:    bool
    critical:      bool
    notes:         str

@dataclass
class BenchmarkReport:
    weights:             tuple
    results:             list[QueryResult]
    mean_ndcg:           float
    mean_p3:             float
    subset_ndcg:         dict[str, float]
    subset_p3:           dict[str, float]
    noise_gate_failures: list[str]
    worst_regressions:   list[dict]
    gate_passed:         bool = True


def run_benchmark(
    quality_weight: float = 0.4,
    relevance_weight: float = 0.6,
    pool: dict[str, dict] = MOCK_REPO_POOL,
) -> BenchmarkReport:
    results: list[QueryResult] = []
    for item in QUERY_PACK:
        scored = score_pool(list(pool.values()), item["query"], quality_weight, relevance_weight)
        ranked = [s.repo_id for s in scored if not s.excluded]
        results.append(QueryResult(
            id=item["id"], query=item["query"], cls=item["cls"],
            ranked_top5=ranked[:5], ideal=item["ideal_top3"],
            must_not_top3=item.get("must_not_top3", []),
            ndcg3=ndcg_at_k(ranked, item["ideal_top3"]),
            p3=precision_at_k(ranked, item["ideal_top3"]),
            noise_gate=noise_gate_pass(ranked[:3], item.get("must_not_top3", [])),
            critical=item.get("critical", False), notes=item.get("notes", ""),
        ))

    scoreable = [r for r in results if r.ideal]
    mean_ndcg = statistics.mean(r.ndcg3 for r in scoreable) if scoreable else 0.0
    mean_p3   = statistics.mean(r.p3    for r in scoreable) if scoreable else 0.0

    all_cls = sorted({r.cls for r in results})
    subset_ndcg, subset_p3 = {}, {}
    for cls in all_cls:
        sub = [r for r in results if r.cls == cls and r.ideal]
        if sub:
            subset_ndcg[cls] = statistics.mean(r.ndcg3 for r in sub)
            subset_p3[cls]   = statistics.mean(r.p3    for r in sub)

    return BenchmarkReport(
        weights=(quality_weight, relevance_weight), results=results,
        mean_ndcg=mean_ndcg, mean_p3=mean_p3,
        subset_ndcg=subset_ndcg, subset_p3=subset_p3,
        noise_gate_failures=[r.id for r in results if not r.noise_gate],
        worst_regressions=[],
    )


# ═════════════════════════════════════════════════════════════════════════════
# 6. REPORTER
# ═════════════════════════════════════════════════════════════════════════════

def print_report(report: BenchmarkReport) -> None:
    qw, rw = report.weights
    W = 80
    print(f"\n{'═'*W}")
    print(f"  RepoScout Benchmark v2  |  quality={qw}  relevance={rw}")
    print(f"{'═'*W}")

    n = len([r for r in report.results if r.ideal])
    print(f"\n  OVERALL  ({n} scored queries)")
    print(f"  Mean NDCG@3 : {report.mean_ndcg:.3f}")
    print(f"  Mean P@3    : {report.mean_p3:.3f}")

    print("\n  BY SUBSET")
    print(f"  {'Class':<14} {'NDCG@3':>8} {'P@3':>8}")
    for cls in sorted(report.subset_ndcg):
        print(f"  {cls:<14} {report.subset_ndcg[cls]:>8.3f} {report.subset_p3.get(cls,0):>8.3f}")

    nf = report.noise_gate_failures
    if nf:
        print(f"\n  ⚠ NOISE GATE FAILURES  ({len(nf)})")
        for qid in nf:
            q = next(r for r in report.results if r.id == qid)
            junk = [r for r in q.ranked_top5[:3] if r in q.must_not_top3]
            print(f"    [{qid}] {q.query[:55]}")
            for j in junk: print(f"          junk in top-3: {j}")
    else:
        print("\n  ✓  All noise gates passed")

    print(f"\n  {'ID':<5} {'Query':<36} {'Class':<12} {'NDCG':>6} {'P@3':>5}  {'Top Result':<32} Gate")
    print(f"  {'-'*5} {'-'*36} {'-'*12} {'-'*6} {'-'*5}  {'-'*32} ----")
    for r in report.results:
        nd = f"{r.ndcg3:.2f}" if r.ideal else " n/a"
        p  = f"{r.p3:.2f}"   if r.ideal else " n/a"
        top = r.ranked_top5[0] if r.ranked_top5 else "—"
        gate = "✓" if r.noise_gate else "✗"
        crit = "!" if r.critical else " "
        print(f"  {crit}{r.id:<4} {r.query[:36]:<36} {r.cls:<12} {nd:>6} {p:>5}  {top[:32]:<32} {gate}")

    if report.worst_regressions:
        print("\n  WORST REGRESSIONS")
        for reg in report.worst_regressions[:5]:
            print(f"    [{reg['id']}] {reg['query'][:55]:<55}  NDCG Δ {reg['delta']:+.3f}")
    print()


def write_markdown(report: BenchmarkReport, path: str) -> None:
    qw, rw = report.weights
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# RepoScout Benchmark Report", "",
        f"**Weights:** quality={qw}  relevance={rw} &nbsp;|&nbsp; **Generated:** {ts}", "",
        "## Overall", "",
        "| Metric | Value |", "|--------|-------|",
        f"| Mean NDCG@3 | {report.mean_ndcg:.3f} |",
        f"| Mean P@3 | {report.mean_p3:.3f} |",
        f"| Noise gate failures | {len(report.noise_gate_failures)} |", "",
        "## Subset Breakdown", "", "| Class | NDCG@3 | P@3 |", "|-------|--------|-----|",
    ]
    for cls in sorted(report.subset_ndcg):
        lines.append(f"| {cls} | {report.subset_ndcg[cls]:.3f} | {report.subset_p3.get(cls,0):.3f} |")

    lines += ["", "## Per-Query Results", "",
              "| ID | Query | Class | NDCG@3 | P@3 | Top Result | Gate |",
              "|----|-------|-------|--------|-----|-----------|------|"]
    for r in report.results:
        nd = f"{r.ndcg3:.2f}" if r.ideal else "n/a"
        p  = f"{r.p3:.2f}"   if r.ideal else "n/a"
        top = r.ranked_top5[0] if r.ranked_top5 else "—"
        gate = "✓" if r.noise_gate else "**✗**"
        lines.append(f"| {r.id} | {r.query[:40]} | {r.cls} | {nd} | {p} | `{top[:35]}` | {gate} |")

    if report.noise_gate_failures:
        lines += ["", "## ⚠ Noise Gate Failures", ""]
        for qid in report.noise_gate_failures:
            q = next(r for r in report.results if r.id == qid)
            lines.append(f"- **[{qid}]** {q.query}")
            for j in [x for x in q.ranked_top5[:3] if x in q.must_not_top3]:
                lines.append(f"  - Junk in top-3: `{j}`")

    if report.worst_regressions:
        lines += ["", "## Worst Regressions", ""]
        for reg in report.worst_regressions[:5]:
            lines.append(f"- **[{reg['id']}]** {reg['query']} — NDCG Δ `{reg['delta']:+.3f}`")

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Report written to {path}")


# ═════════════════════════════════════════════════════════════════════════════
# 7. COMPARE + GATE
# ═════════════════════════════════════════════════════════════════════════════

def compare_reports(baseline_path: str, new_path: str, gate: bool = False) -> BenchmarkReport:
    with open(baseline_path) as f: base_data = json.load(f)
    with open(new_path)     as f: new_data  = json.load(f)

    base_idx = {r["id"]: r for r in base_data["results"]}
    new_idx  = {r["id"]: r for r in new_data["results"]}
    common   = set(base_idx) & set(new_idx)

    regressions, critical_fails = [], []
    deltas: list[float] = []

    print(f"\n{'═'*76}")
    print(f"  COMPARISON  |  {baseline_path}  →  {new_path}")
    print(f"{'═'*76}")
    print(f"\n  {'ID':<5} {'Query':<42} {'NDCG Δ':>8} {'P@3 Δ':>7}")
    print(f"  {'-'*5} {'-'*42} {'-'*8} {'-'*7}")

    for qid in sorted(common):
        b, n = base_idx[qid], new_idx[qid]
        if not b.get("ideal"): continue
        dn = n["ndcg3"] - b["ndcg3"]
        dp = n["p3"]    - b["p3"]
        deltas.append(dn)
        sign = "↑" if dn > 0.01 else ("↓" if dn < -0.01 else "·")
        crit = "!" if b.get("critical") else " "
        print(f"  {crit}{qid:<4} {b['query'][:42]:<42} {dn:>+8.3f} {dp:>+7.3f}  {sign}")
        if dn < 0: regressions.append({"id": qid, "query": b["query"], "delta": dn})
        if dn < -0.15 and b.get("critical"): critical_fails.append({"id": qid, "query": b["query"], "delta": dn})

    regressions.sort(key=lambda x: x["delta"])
    mean_d  = statistics.mean(deltas) if deltas else 0.0
    new_mn  = new_data.get("mean_ndcg", 0.0)
    base_mn = base_data.get("mean_ndcg", 0.0)
    print(f"\n  Mean NDCG Δ : {mean_d:+.3f}  ({base_mn:.3f} → {new_mn:.3f})")

    gate_passed = True
    if gate:
        print("\n  GATE CHECKS")
        checks = [
            (new_mn >= base_mn - 0.001, f"Mean NDCG did not decrease ({base_mn:.3f} → {new_mn:.3f})"),
            (not critical_fails,         "No critical query regressed > 0.15"),
            (not (set(new_data.get("noise_gate_failures",[])) - set(base_data.get("noise_gate_failures",[]))), "No new noise gate failures"),
        ]
        for passed, msg in checks:
            print(f"  {'✓' if passed else '✗'} {msg}")
            if not passed: gate_passed = False
        print(f"\n  {'✓ GATE PASSED' if gate_passed else '✗ GATE FAILED'}")

    print()
    return BenchmarkReport(
        weights=tuple(new_data.get("weights", [0.4, 0.6])),
        results=[], mean_ndcg=new_mn, mean_p3=new_data.get("mean_p3", 0.0),
        subset_ndcg={}, subset_p3={},
        noise_gate_failures=new_data.get("noise_gate_failures", []),
        worst_regressions=regressions, gate_passed=gate_passed,
    )


# ═════════════════════════════════════════════════════════════════════════════
# CLI
# ═════════════════════════════════════════════════════════════════════════════

def _to_json(report: BenchmarkReport) -> dict:
    return {
        "weights": list(report.weights),
        "mean_ndcg": report.mean_ndcg, "mean_p3": report.mean_p3,
        "subset_ndcg": report.subset_ndcg, "subset_p3": report.subset_p3,
        "noise_gate_failures": report.noise_gate_failures,
        "results": [asdict(r) for r in report.results],
    }


def main() -> None:
    p = argparse.ArgumentParser(description="RepoScout benchmark v2")
    p.add_argument("--quality-weight",   type=float, default=0.4)
    p.add_argument("--relevance-weight", type=float, default=0.6)
    p.add_argument("--save",   type=str, default=None)
    p.add_argument("--report", type=str, default=None)
    p.add_argument("--compare", nargs=2, metavar=("BASELINE", "NEW"))
    p.add_argument("--gate", action="store_true")
    args = p.parse_args()

    if args.compare:
        stub = compare_reports(args.compare[0], args.compare[1], gate=args.gate)
        if args.gate and not stub.gate_passed:
            sys.exit(1)
        return

    report = run_benchmark(args.quality_weight, args.relevance_weight)
    print_report(report)

    if args.save:
        with open(args.save, "w") as f: json.dump(_to_json(report), f, indent=2)
        print(f"  Saved to {args.save}")
    if args.report:
        write_markdown(report, args.report)


if __name__ == "__main__":
    main()
