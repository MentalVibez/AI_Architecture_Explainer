# CodebaseAtlas — Frontend

Next.js 14 (App Router) frontend for [CodebaseAtlas](../README.md).

**Live:** [www.codebaseatlas.com](https://www.codebaseatlas.com)

Paste a public GitHub URL → get an architecture diagram, dependency breakdown, and two audience-specific summaries:

- **Technical View** — stack, entry points, architectural patterns, and component responsibilities
- **Non-Technical View** — plain-English board-room summary: what the project does, skills demonstrated, complexity, and standout points

## Stack

- **Next.js 14** with App Router and TypeScript
- **Tailwind CSS** for styling
- **Mermaid** for architecture diagram rendering
- **lucide-react** for icons

## Key pages

| Route | File | Purpose |
|-------|------|---------|
| `/` | `app/page.tsx` | Homepage — URL input form + tool cards |
| `/scout` | `app/scout/page.tsx` | RepoScout — search and rank repositories |
| `/map` | `app/map/page.tsx` | API Endpoint Mapper |
| `/results/[id]` | `app/results/[id]/page.tsx` | Displays completed analysis |

## Key components

| Component | Purpose |
|-----------|---------|
| `RepoUrlForm` | Submits repo URL, redirects to polling page |
| `DiagramPanel` | Renders Mermaid architecture diagram |
| `DeveloperSummary` | Stack detection + Technical View (bullet-point presentation format) |
| `HiringManagerSummary` | Non-Technical View with confidence badge (bullet-point presentation format) |

## Running locally

```bash
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL
npm install
npm run dev
```

Requires the backend to be running at `http://localhost:8000`. See the [root quickstart](../README.md#quickstart).

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |
