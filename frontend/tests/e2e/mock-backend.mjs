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
    "- The codebase appears structured for developer onboarding and architecture review workflows.",
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

  sendJson(res, 404, { detail: "Not found" });
});

server.listen(8000, "127.0.0.1", () => {
  console.log("mock backend listening on http://127.0.0.1:8000");
});
