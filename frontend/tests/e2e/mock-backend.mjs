import { createServer } from "node:http";

let pollCount = 0;

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
        result_id: null,
        error_message: null,
      });
      return;
    }

    sendJson(res, 200, {
      job_id: 123,
      status: "completed",
      result_id: 456,
      error_message: null,
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

  sendJson(res, 404, { detail: "Not found" });
});

server.listen(8000, "127.0.0.1", () => {
  console.log("mock backend listening on http://127.0.0.1:8000");
});
