import { createServer } from "node:http";

let pollCount = 0;
let reviewPollCount = 0;

const reviewResult = {
  result_id: "review-result-789",
  share_slug: "review-share-slug",
  job_id: "review-job-789",
  repo_url: "https://github.com/MentalVibez/ai-agent-orchestrator",
  commit: "abcdef1",
  branch: "main",
  created_at: new Date().toISOString(),
  completed_at: new Date().toISOString(),
  duration_seconds: 18,
  ruleset_version: "test-ruleset",
  depth_level: "structural_plus",
  confidence_label: "high",
  overall_score: 84,
  verdict_label: "Promising foundation",
  production_suitable: true,
  anti_gaming_verdict: "likely_honest",
  scores: {
    security: 82,
    testing: 80,
    maintainability: 88,
    reliability: 83,
    operations: 79,
    developer_experience: 90,
  },
  findings: [
    {
      id: "finding-1",
      rule_id: "ops-healthcheck",
      title: "Healthchecks are present but tracing is still missing",
      category: "operations",
      severity: "medium",
      summary: "The repo exposes health endpoints but does not show tracing coverage.",
      why_it_matters: "Incident diagnosis will take longer without request-level traces.",
      suggested_fix: "Add Sentry or OpenTelemetry tracing for the critical request path.",
    },
    {
      id: "finding-2",
      rule_id: "tests-ci",
      title: "CI verifies the backend path",
      category: "testing",
      severity: "low",
      summary: "Pytest coverage is wired into CI for the backend changes.",
      why_it_matters: "Regression risk is lower when route protection is covered in CI.",
      suggested_fix: "Extend the suite with user-facing flow tests for Scout, Map, and Review.",
    },
  ],
  summary: {
    developer: "The repository has a solid baseline with clear route coverage and deploy hygiene.",
    manager: "This project shows good operational discipline with a few observability gaps left to close.",
    hiring: "Strong signal for product-minded full-stack engineering work.",
  },
  error_code: null,
  error_message: null,
};

const scoutResult = {
  query: "MentalVibez/ai-agent-orchestrator",
  total: 1,
  tldr: "One strong repository matched the query with high quality and relevance.",
  repos: [
    {
      id: "repo-1",
      platform: "github",
      full_name: "MentalVibez/ai-agent-orchestrator",
      owner: "MentalVibez",
      description: "Agent orchestration framework for coordinating AI workflows.",
      url: "https://github.com/MentalVibez/ai-agent-orchestrator",
      language: "TypeScript",
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2026-01-15T00:00:00Z",
      scores: { quality_score: 86, relevance_score: 91, overall_score: 89 },
      verdict: "HIGHLY_RECOMMENDED",
      ai_insight: "Strong fit for multi-agent workflow exploration with an active maintenance profile.",
      risks: ["Tracing not detected"],
      signals: [
        { label: "README verified", type: "good", verified: true },
        { label: "Recent updates", type: "good", verified: true },
      ],
      evidence: {
        stars: 4200,
        forks: 380,
        days_since_update: 7,
        has_license: true,
        license_name: "MIT",
        readme_verified: true,
        is_fork: false,
        is_archived: false,
        is_template: false,
        open_issues: 12,
        topic_matches: ["agents", "orchestration"],
        matched_terms: ["ai", "agent"],
        noise_flags: [],
      },
    },
  ],
};

const mapResult = {
  repo: "MentalVibez/ai-agent-orchestrator",
  profile_used: {
    framework: "fastapi",
    framework_confidence: "high",
    from_profile: true,
    detected_backend: ["FastAPI"],
    detected_frontend: ["Next.js"],
  },
  groups: [
    {
      name: "Health & Status",
      description: "Operational endpoints for liveness and readiness.",
      endpoints: [
        {
          method: "GET",
          path: "/health",
          description: "Returns overall API health.",
          params: [],
          auth_likely: false,
        },
        {
          method: "GET",
          path: "/ready",
          description: "Returns readiness for the serving path.",
          params: [],
          auth_likely: false,
        },
      ],
    },
  ],
  summary: "The API surface is centered on operational status and analysis workflows.",
  api_style: "REST",
  auth_pattern: "Bearer or session cookie",
  files_scanned: ["backend/app/main.py", "backend/app/api/routes_health.py"],
  raw_endpoint_count: 2,
  warnings: [],
  duration_ms: 142,
};

const devcontainerResponse = {
  devcontainer_id: "devcontainer-123",
  job_id: 123,
  version_number: 1,
  config: {
    name: "atlas-dev-python",
    image: "mcr.microsoft.com/devcontainers/python:3.11",
    features: {
      "ghcr.io/devcontainers/features/github-cli:1": {},
    },
    postCreateCommand: "pip install -r requirements.txt",
    remoteUser: "vscode",
  },
  repo_url: "https://github.com/MentalVibez/ai-agent-orchestrator",
  created_at: new Date().toISOString(),
};

const result = {
  id: 456,
  job_id: 123,
  repo_snapshot_sha: "mock-sha-1234567",
  detected_stack: {
    frontend: [
      {
        name: "Next.js 14",
        evidence: ["package.json -> next@14.2.35"],
        confidence: 0.98,
      },
    ],
    backend: [
      {
        name: "FastAPI",
        evidence: ["backend/app/main.py"],
        confidence: 0.96,
      },
    ],
    database: [
      {
        name: "Supabase Postgres",
        evidence: ["DATABASE_URL", "asyncpg"],
        confidence: 0.91,
      },
    ],
    infra: [
      {
        name: "Railway",
        evidence: ["backend/railway.toml"],
        confidence: 0.89,
      },
      {
        name: "Vercel",
        evidence: ["frontend/vercel.json"],
        confidence: 0.89,
      },
    ],
    testing: [
      {
        name: "Pytest",
        evidence: ["backend/tests"],
        confidence: 0.92,
      },
    ],
  },
  dependencies: {
    npm: ["next", "react", "mermaid"],
    python: ["fastapi", "sqlalchemy", "anthropic"],
  },
  entry_points: ["frontend/app/page.tsx", "backend/app/main.py"],
  folder_map: [
    { path: "frontend/app", role: "Next.js App Router pages" },
    { path: "frontend/components", role: "UI building blocks" },
    { path: "backend/app/api", role: "FastAPI HTTP routes" },
    {
      path: "backend/app/services",
      role: "analysis orchestration and LLM summarization",
    },
  ],
  diagram_mermaid: [
    "flowchart TD",
    "  Browser --> NextFrontend",
    "  NextFrontend --> FastAPI",
    "  FastAPI --> GitHubAPI",
    "  FastAPI --> Anthropic",
    "  FastAPI --> SQLite",
  ].join("\n"),
  developer_summary: [
    "SYSTEM OVERVIEW",
    "- Next.js frontend submits repository URLs and polls for job status.",
    "- FastAPI orchestrates deterministic parsing before LLM last-mile summarization.",
    "- Results combine stack detection, dependency evidence, and Mermaid architecture output.",
  ].join("\n"),
  hiring_manager_summary: [
    "PROJECT SIGNAL",
    "- This project demonstrates full-stack product thinking across frontend, backend, and deployment.",
    "- It shows clear separation between deterministic analysis and LLM-generated explanation.",
    "- The codebase appears structured for developer guidance and architecture review workflows.",
  ].join("\n"),
  confidence_score: 0.87,
  caveats: ["Mocked backend response used for Playwright smoke coverage."],
  raw_evidence: [
    {
      repo: { owner: "MentalVibez", name: "ai-agent-orchestrator" },
      tree_paths: [
        "frontend/app/page.tsx",
        "backend/app/main.py",
        "backend/app/services/summary_service.py",
        "frontend/components/RepoUrlForm.tsx",
      ],
    },
  ],
  setup_risk: {
    scan_state: "found",
    score: 24,
    level: "low",
    confidence: 0.86,
    missing_env_vars: [],
    env_example_present: true,
    likely_start_commands: ["npm run dev", "uvicorn app.main:app"],
    required_services: ["postgres"],
    detected_manifests: ["package.json", "pyproject.toml"],
    risks: [],
    scan_errors: [],
  },
  debug_readiness: {
    scan_state: "found",
    score: 35,
    level: "medium",
    confidence: 0.82,
    logging: { scan_state: "found", framework: "stdlib_logging", print_only_detected: false },
    error_handling: { scan_state: "found", framework: "fastapi" },
    health_checks: { scan_state: "found", routes_found: ["/health"] },
    tracing: { scan_state: "not_found", sentry_found: false, otel_found: false },
    test_harness: { scan_state: "found", frameworks: ["pytest", "playwright"] },
    risks: [
      {
        category: "observability",
        reason: "Tracing was not detected in the mocked repository.",
        rule: "tracing_not_detected",
        evidence: [{ source_file: "<repo_root>", rule: "tracing_not_detected" }],
      },
    ],
    scan_errors: [],
  },
  change_risk: {
    scan_state: "found",
    score: 42,
    level: "medium",
    confidence: 0.81,
    ci: {
      scan_state: "found",
      platforms: ["github_actions"],
      has_test_gate: true,
      has_lint_gate: true,
    },
    test_gates: {
      scan_state: "found",
      frameworks: ["pytest", "playwright"],
      has_coverage: false,
    },
    migration_risk: {
      scan_state: "not_found",
      migration_paths: [],
      has_migration_tests: false,
    },
    blast_radius_hotspots: [
      {
        path: "backend/app/services/analysis_pipeline.py",
        category: "core",
        reason: "Central analysis orchestration affects Atlas result generation.",
      },
    ],
    risky_to_change: ["backend/app/services/analysis_pipeline.py"],
    risks: [],
    scan_errors: [],
  },
  analysis_tier: "static",
  runtime_verified: false,
  tier_disclosure:
    "This analysis is based on static code inspection only. It detects structure, configuration, and likely risk signals from files and manifests. It does not execute code, run tests, or verify runtime behavior. Findings represent likely conditions, not confirmed facts.",
  created_at: new Date().toISOString(),
};

const codebaseGuide = {
  result_id: 456,
  repo_label: "MentalVibez/ai-agent-orchestrator",
  overview:
    "Use this guide to understand MentalVibez/ai-agent-orchestrator through Next.js 14, FastAPI, and Supabase Postgres.",
  week_plan: [
    {
      phase: "System map",
      title: "Build the mental model before editing",
      goal: "Understand the app boundary and entry points.",
      actions: ["Read the project summary.", "Open frontend/app/page.tsx.", "Open backend/app/main.py."],
    },
    {
      phase: "Execution flow",
      title: "Trace one real workflow",
      goal: "Follow a request through the frontend and API.",
      actions: ["Use the diagram and reading path together."],
    },
  ],
  reading_path: [
    {
      path: "frontend/app/page.tsx",
      reason: "Runtime entry point detected by Atlas.",
      confidence: 0.92,
    },
    {
      path: "backend/app/main.py",
      reason: "Runtime entry point detected by Atlas.",
      confidence: 0.92,
    },
  ],
  concepts: [
    {
      name: "Next.js 14",
      explanation: "Atlas detected Next.js 14 in the frontend layer.",
      evidence: ["package.json -> next@14.2.35"],
    },
  ],
  starter_tasks: [
    {
      title: "Improve project understanding documentation",
      why_safe: "Documentation changes help future readers and usually avoid runtime risk.",
      suggested_checks: ["Preview the changed documentation."],
      related_paths: [],
    },
  ],
  risk_notes: [
    {
      title: "Avoid broad architectural rewrites until the flow is clear",
      guidance: "Start by tracing behavior and changing isolated docs, tests, or small UI pieces.",
      related_paths: ["backend/app/main.py"],
    },
  ],
  mentor_questions: [
    "What is the safest first workflow to trace from UI/API entry to persistence or external calls?",
  ],
  team_questions: [
    "What is the most important workflow to trace from UI/API entry to persistence or external calls?",
  ],
  setup_blockers: [
    {
      title: "Environment example not found",
      severity: "medium",
      guidance: "Confirm required environment variables with a maintainer before running services.",
    },
  ],
  evidence_summary: {
    allowed_path_count: 4,
    entry_point_count: 2,
    folder_signal_count: 4,
    caveat_count: 1,
    confidence_score: 0.87,
  },
};

function sendJson(res, status, payload) {
  const body = Buffer.from(JSON.stringify(payload));
  res.writeHead(status, {
    "Access-Control-Allow-Origin": "http://127.0.0.1:3000",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
    "Content-Length": body.length,
  });
  res.end(body);
}

const server = createServer((req, res) => {
  const path = new URL(req.url ?? "/", "http://127.0.0.1:8000").pathname;

  if (req.method === "OPTIONS") {
    res.writeHead(200, {
      "Access-Control-Allow-Origin": "http://127.0.0.1:3000",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Content-Length": "0",
    });
    res.end();
    return;
  }

  if (req.method === "GET" && path === "/health") {
    sendJson(res, 200, { status: "ok", service: "mock-atlas-backend" });
    return;
  }

  if (req.method === "POST" && path === "/api/analyze") {
    pollCount = 0;
    sendJson(res, 200, { job_id: 123, status: "queued" });
    return;
  }

  if (req.method === "GET" && path === "/api/analyze/123") {
    pollCount += 1;
    if (pollCount < 2) {
      sendJson(res, 200, {
        job_id: 123,
        status: "running",
        phase: "analysis",
        status_detail: "Collecting repository evidence and assembling the Atlas workspace.",
        result_id: null,
        error_message: null,
        duration_seconds: 1,
        next_poll_seconds: 2,
        created_at: new Date().toISOString(),
        completed_at: null,
      });
      return;
    }

    sendJson(res, 200, {
      job_id: 123,
      status: "completed",
      phase: "complete",
      status_detail: "Completed successfully.",
      result_id: 456,
      error_message: null,
      duration_seconds: 2,
      next_poll_seconds: null,
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    });
    return;
  }

  if (req.method === "GET" && path === "/api/results/456") {
    sendJson(res, 200, result);
    return;
  }

  if (req.method === "GET" && path === "/api/results/456/onboarding") {
    sendJson(res, 200, codebaseGuide);
    return;
  }

  if (req.method === "GET" && path === "/api/results/456/guide") {
    sendJson(res, 200, codebaseGuide);
    return;
  }

  if (req.method === "POST" && path === "/api/devcontainer/123/generate") {
    sendJson(res, 200, devcontainerResponse);
    return;
  }

  if (req.method === "POST" && path === "/api/review/") {
    reviewPollCount = 0;
    sendJson(res, 202, {
      job_id: "review-job-789",
      status: "queued",
      message: "Review queued. Poll for status.",
    });
    return;
  }

  if (req.method === "GET" && path === "/api/review/review-job-789") {
    reviewPollCount += 1;
    if (reviewPollCount < 2) {
      sendJson(res, 200, {
        job_id: "review-job-789",
        status: "running",
        phase: "analysis",
        status_detail: "Gathering evidence and building the scorecard.",
        result_id: null,
        error_code: null,
        error_message: null,
        duration_seconds: 5,
        next_poll_seconds: 1,
        retryable: null,
        suggested_action: "Keep polling until the report is ready.",
        created_at: new Date().toISOString(),
        completed_at: null,
      });
      return;
    }

    sendJson(res, 200, {
      job_id: "review-job-789",
      status: "completed",
      phase: "complete",
      status_detail: "Completed successfully in about 18 seconds.",
      result_id: "review-result-789",
      error_code: null,
      error_message: null,
      duration_seconds: 18,
      next_poll_seconds: null,
      retryable: null,
      suggested_action: null,
      created_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
    });
    return;
  }

  if (req.method === "GET" && path === "/api/review/results/review-result-789") {
    sendJson(res, 200, reviewResult);
    return;
  }

  if (req.method === "POST" && path === "/api/scout/search") {
    sendJson(res, 200, scoutResult);
    return;
  }

  if (req.method === "GET" && path === "/api/map/MentalVibez/ai-agent-orchestrator") {
    sendJson(res, 200, mapResult);
    return;
  }

  sendJson(res, 404, { detail: "Not found" });
});

server.listen(8000, "127.0.0.1", () => {
  console.log("mock backend listening on http://127.0.0.1:8000");
});
