# Codebase Atlas — Frontend

Next.js 14 (App Router) frontend for [Codebase Atlas](../README.md).

Paste a public GitHub URL → get an architecture diagram, dependency breakdown, and audience-specific summaries for developers and hiring managers.

## Stack

- **Next.js 14** with App Router and TypeScript
- **Tailwind CSS** for styling
- **Mermaid** for architecture diagram rendering
- **lucide-react** for icons

## Key pages

| Route | File | Purpose |
|-------|------|---------|
| `/` | `app/page.tsx` | Homepage — URL input form |
| `/analyze` | `app/analyze/page.tsx` | Polls job status while backend runs |
| `/results/[id]` | `app/results/[id]/page.tsx` | Displays completed analysis |

## Key components

| Component | Purpose |
|-----------|---------|
| `RepoUrlForm` | Submits repo URL, redirects to `/analyze` |
| `LoadingAnalysis` | Spinner + status label during polling |
| `DiagramPanel` | Renders Mermaid architecture diagram |
| `DeveloperSummary` | Shows stack, entry points, and developer narrative |
| `HiringManagerSummary` | Plain-English summary with confidence badge |

## Running locally

```bash
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL
npm install
npm run dev
```

Requires the backend to be running at `http://localhost:8000`. See the [backend README](../backend/README.md) or the [root quickstart](../README.md#quickstart).

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |
