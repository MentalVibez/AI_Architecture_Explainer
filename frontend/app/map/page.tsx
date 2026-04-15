"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { getApiUrl } from "@/lib/api";
import { useRepoWorkspace } from "@/components/workspace/RepoWorkspaceProvider";
import { buildRepoUrl, normalizeRepoWorkspace } from "@/lib/repo-workspace";

const ACCENT = "#7ec8ff";

interface ProfileUsed {
  framework: string;
  framework_confidence: string;
  from_profile: boolean;
  detected_backend: string[];
  detected_frontend: string[];
}

interface Endpoint {
  method: string;
  path: string;
  description: string;
  params: string[];
  auth_likely: boolean;
  notes?: string;
}

interface EndpointGroup {
  name: string;
  description: string;
  endpoints: Endpoint[];
}

interface MapResult {
  repo: string;
  profile_used: ProfileUsed;
  groups: EndpointGroup[];
  summary: string;
  api_style: string;
  auth_pattern: string;
  files_scanned: string[];
  raw_endpoint_count: number;
  warnings: string[];
  duration_ms: number;
}

const PHASES = [
  { id: "profile", label: "Profile stack", detail: "Read manifests and derive the most likely framework." },
  { id: "extract", label: "Extract routes", detail: "Scan targeted files for framework-aware route patterns." },
  { id: "shape", label: "Shape output", detail: "Group the API surface into something a human can read." },
] as const;

const SAMPLE_REPOS = [
  "tiangolo/fastapi",
  "django/django",
  "expressjs/express",
  "vercel/next.js",
] as const;
const QUICK_HINTS = [
  "Best for repos where you want to confirm routes before reading code by hand.",
  "Works fastest when the framework is detectable from manifests and file structure.",
  "Pairs well with Atlas first and Review immediately after.",
] as const;

const METHOD_COLORS: Record<string, string> = {
  GET: "#35c58b",
  POST: "#4d7cff",
  PUT: "#ffcb6b",
  PATCH: "#ffd98f",
  DELETE: "#ff8d8d",
  ANY: "#8ea3c7",
};

function parseRepoInput(raw: string): { owner: string; repo: string } | null {
  const trimmed = raw.trim().replace(/\/$/, "");
  const urlMatch = trimmed.match(/github\.com\/([^/\s]+)\/([^/\s]+)/);
  if (urlMatch) return { owner: urlMatch[1], repo: urlMatch[2] };
  const shortMatch = trimmed.match(/^([a-zA-Z0-9_-]+)\/([a-zA-Z0-9_.-]+)$/);
  if (shortMatch) return { owner: shortMatch[1], repo: shortMatch[2] };
  return null;
}

function confidenceColor(value: string) {
  if (value === "high") return "#35c58b";
  if (value === "speculative") return "#ffcb6b";
  return "#8ea3c7";
}

function MethodBadge({ method }: { method: string }) {
  const color = METHOD_COLORS[method.toUpperCase()] ?? METHOD_COLORS.ANY;
  return (
    <span
      className="shrink-0 rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.16em]"
      style={{ color, borderColor: `${color}35`, backgroundColor: `${color}10` }}
    >
      {method.toUpperCase()}
    </span>
  );
}

function PhaseTracker({ phase }: { phase: number }) {
  return (
    <div className="grid gap-3">
      {PHASES.map((item, index) => {
        const done = index < phase;
        const active = index === phase;
        return (
          <div key={item.id} className="panel rounded-2xl p-4">
            <div className="flex items-start gap-3">
              <div
                className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border"
                style={{
                  borderColor: done || active ? ACCENT : "rgba(255,255,255,0.12)",
                  backgroundColor: done ? ACCENT : active ? "rgba(126,200,255,0.12)" : "transparent",
                  color: done ? "#08111f" : "#cfeaff",
                }}
              >
                {done ? "✓" : index + 1}
              </div>
              <div>
                <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#dce8ff]">{item.label}</p>
                <p className="mt-1 text-sm leading-relaxed text-[#94a8cb]">{item.detail}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EndpointCard({ endpoint }: { endpoint: Endpoint }) {
  return (
    <div className="border-b border-white/10 py-3 last:border-0">
      <div className="flex items-start gap-3">
        <MethodBadge method={endpoint.method} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-mono text-[12px] text-[#eff6ff] break-all">{endpoint.path}</p>
            {endpoint.auth_likely && (
              <span className="rounded-full border border-[#ffcb6b]/30 bg-[#ffcb6b]/10 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.16em] text-[#ffd98f]">
                auth
              </span>
            )}
          </div>
          {endpoint.description && (
            <p className="mt-1 text-sm leading-relaxed text-[#95a9cb]">{endpoint.description}</p>
          )}
          {endpoint.notes && <p className="mt-1 font-mono text-[10px] text-[#6d7f9f]">{endpoint.notes}</p>}
        </div>
      </div>
    </div>
  );
}

function GroupCard({ group }: { group: EndpointGroup }) {
  const [open, setOpen] = useState(true);

  return (
    <div className="panel rounded-[24px] p-5">
      <button onClick={() => setOpen((value) => !value)} className="flex w-full flex-col items-start gap-3 text-left sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-[#f4f8ff]">{group.name}</h3>
          {group.description && <p className="mt-2 text-sm leading-relaxed text-[#94a8cb]">{group.description}</p>}
        </div>
        <div className="shrink-0 text-left sm:text-right">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#6d7f9f]">
            {group.endpoints.length} endpoints
          </p>
          <p className="mt-1 font-mono text-[11px] text-[#cfeaff]">{open ? "Collapse" : "Expand"}</p>
        </div>
      </button>

      {open && (
        <div className="mt-4 border-t border-white/10 pt-4">
          {group.endpoints.map((endpoint, index) => (
            <EndpointCard key={`${group.name}-${index}`} endpoint={endpoint} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function MapPage() {
  const searchParams = useSearchParams();
  const { activeRepo, setActiveRepo } = useRepoWorkspace();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState(-1);
  const [result, setResult] = useState<MapResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const phaseRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const repo = searchParams.get("repo");
    if (repo) {
      setInput(repo);
      return;
    }

    if (!input && activeRepo?.repo) {
      setInput(activeRepo.repo);
    }
  }, [activeRepo, input, searchParams]);

  useEffect(() => {
    if (loading) {
      setPhase(0);
      let current = 0;
      phaseRef.current = setInterval(() => {
        current += 1;
        if (current < PHASES.length) setPhase(current);
      }, 1400);
    } else if (!result) {
      setPhase(-1);
    }

    return () => {
      if (phaseRef.current) clearInterval(phaseRef.current);
    };
  }, [loading, result]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setResult(null);

    const parsed = parseRepoInput(input);
    if (!parsed) {
      setError("Enter a GitHub URL or owner/repo, for example `tiangolo/fastapi`.");
      return;
    }

    setLoading(true);
    try {
      setActiveRepo({
        repo: `${parsed.owner}/${parsed.repo}`,
        url: buildRepoUrl(`${parsed.owner}/${parsed.repo}`),
        provider: "github",
      });

      const response = await fetch(`${getApiUrl()}/api/map/${parsed.owner}/${parsed.repo}`, {
        headers: { "Content-Type": "application/json" },
      });
      if (!response.ok) {
        const body = await response.text();
        throw new Error(`API error ${response.status}: ${body}`);
      }
      const data: MapResult = await response.json();
      setPhase(PHASES.length);
      setResult(data);
      const normalized = normalizeRepoWorkspace({ repo: data.repo, provider: "github" });
      if (normalized) {
        setActiveRepo(normalized);
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : "Something went wrong.");
    } finally {
      setLoading(false);
      if (phaseRef.current) clearInterval(phaseRef.current);
    }
  }

  const confColor = confidenceColor(result?.profile_used.framework_confidence ?? "");

  return (
    <div className="page-shell">
      <section className="page-hero">
        <div className="hero-grid">
          <div>
            <div className="mb-5 flex flex-wrap items-center gap-3">
              <span className="rounded-full border border-[#7ec8ff]/25 bg-[#7ec8ff]/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.24em] text-[#cfeaff]">
                Tool 03
              </span>
              <span className="hero-kicker">
                API surface workspace
              </span>
            </div>

            <h1 className="hero-title">
              Map the API surface
              <br />
              before you read every route by hand.
            </h1>

            <p className="hero-copy mt-6">
              Map uses the stack profile to choose better extraction patterns, then shapes the
              output into grouped endpoint clusters. It is the fast “what does this backend expose?”
              layer of the product.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              <div className="surface-note">
                <p className="surface-note-title">Input</p>
                <p className="surface-note-copy">Public GitHub repository URL or `owner/repo`.</p>
              </div>
              <div className="surface-note">
                <p className="surface-note-title">Output</p>
                <p className="surface-note-copy">Framework, grouped endpoints, auth clues, API style, and scanned files.</p>
              </div>
            </div>
          </div>

          <div className="panel-strong rounded-[28px] p-6">
            <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#cfeaff]">Map a repository</p>
                <p className="mt-2 max-w-md text-sm leading-relaxed text-[#8ea3c7]">Start from one repo, then move into grouped endpoints and route context.</p>
              </div>
              <Link href="/review" className="font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:text-white">
                Open Review
              </Link>
            </div>

            <form onSubmit={handleSubmit} className="mt-5">
              <div className="flex flex-col gap-3 sm:flex-row">
                <input
                  type="text"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="tiangolo/fastapi or https://github.com/owner/repo"
                  className="min-w-0 flex-1 rounded-2xl border border-white/10 bg-[#07101d] px-4 py-3.5 font-mono text-[13px] text-[#f5f8ff] placeholder-[#7082a5] focus:border-[#7ec8ff]/40 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="rounded-2xl bg-[#7ec8ff] px-6 py-3.5 font-mono text-[12px] uppercase tracking-[0.18em] text-[#07131b] hover:bg-[#9bd6ff] disabled:cursor-not-allowed disabled:opacity-40 sm:min-w-[10rem]"
                >
                  {loading ? "Mapping…" : "Run Map"}
                </button>
              </div>
            </form>

            <div className="mt-4 flex flex-wrap gap-2">
              {SAMPLE_REPOS.map((repo) => (
                <button
                  key={repo}
                  onClick={() => setInput(repo)}
                  disabled={loading}
                  className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-[10px] text-[#b7c8e8] hover:text-white disabled:opacity-40"
                >
                  {repo}
                </button>
              ))}
            </div>

            {error && <p className="mt-4 font-mono text-[11px] text-[#ff8d8d]">{error}</p>}
          </div>
        </div>
      </section>

      {loading && (
        <section className="pb-12">
          <div className="grid gap-4 lg:grid-cols-[0.7fr_1.3fr]">
            <PhaseTracker phase={phase} />
            <div className="panel rounded-[28px] p-6">
              <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">Running map</p>
              <h2 className="mt-3 text-2xl font-semibold text-[#f5f8ff]">Resolving framework and extracting route structure.</h2>
              <p className="mt-3 text-sm leading-relaxed text-[#94a8cb]">
                The mapper is collecting the repo tree, choosing a parse profile, and shaping the output into grouped surface areas.
              </p>
            </div>
          </div>
        </section>
      )}

      {!loading && !result && !error && (
        <section className="pb-16">
          <div className="panel rounded-[28px] p-8">
            <div className="flex flex-col items-start gap-4 sm:flex-row sm:flex-wrap sm:items-end sm:justify-between">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">
                  Ready
                </p>
                <h2 className="mt-3 text-2xl font-semibold text-[#f5f8ff]">
                  Start with one repository and let Map tell you where the backend surface lives.
                </h2>
              </div>
              <Link
                href="/scout"
                className="rounded-full border border-white/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:text-white"
              >
                Need a repo first?
              </Link>
            </div>
            <div className="mt-6 grid gap-3 md:grid-cols-3">
              {QUICK_HINTS.map((hint) => (
                <div key={hint} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="text-sm leading-relaxed text-[#dce8ff]">{hint}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {!loading && !result && error && (
        <section className="pb-16">
          <div className="panel rounded-[28px] p-8 text-center">
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#ff8d8d]">Map failed</p>
            <h2 className="mt-3 text-2xl font-semibold text-[#f5f8ff]">
              Map couldn’t build a route view for this repo yet.
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-[#94a8cb]">{error}</p>
            <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
              <button
                type="button"
                onClick={() => setError(null)}
                className="rounded-full bg-[#7ec8ff] px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.16em] text-[#07131b]"
              >
                Try another repo
              </button>
              <Link
                href="/"
                className="rounded-full border border-white/10 px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2]"
              >
                Open Atlas
              </Link>
            </div>
          </div>
        </section>
      )}

      {result && !loading && (
        <section className="pb-20">
          <div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
            <div className="panel-strong rounded-[28px] p-6">
              <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#cfeaff]">Map result</p>
              <h2 className="mt-3 break-all text-3xl font-semibold tracking-[-0.03em] text-[#f5f8ff]">{result.repo}</h2>
              {result.summary && <p className="mt-4 text-[15px] leading-relaxed text-[#d8e5fb]">{result.summary}</p>}
              <div className="mt-6 grid gap-3 sm:grid-cols-2">
                <Metric label="Framework" value={result.profile_used.framework || "unknown"} color={confColor} />
                <Metric label="Confidence" value={result.profile_used.framework_confidence || "unknown"} color={confColor} />
                <Metric label="API style" value={result.api_style} />
                <Metric label="Auth pattern" value={result.auth_pattern} />
                <Metric label="Endpoints found" value={String(result.raw_endpoint_count)} color={ACCENT} />
                <Metric label="Duration" value={`${result.duration_ms} ms`} />
              </div>
            </div>

            <div className="panel rounded-[28px] p-6">
              <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">Detected stack</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {result.profile_used.detected_backend.map((value) => (
                  <Tag key={`backend-${value}`} label={value} color="#35c58b" />
                ))}
                {result.profile_used.detected_frontend.map((value) => (
                  <Tag key={`frontend-${value}`} label={value} color={ACCENT} />
                ))}
                {result.profile_used.detected_backend.length === 0 && result.profile_used.detected_frontend.length === 0 && (
                  <p className="text-sm text-[#94a8cb]">No strong framework signal was detected.</p>
                )}
              </div>

              <div className="mt-6 border-t border-white/10 pt-6">
                <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">Next actions</p>
                <div className="mt-3 flex flex-wrap gap-3">
                  <Link href={`/review?repo=${encodeURIComponent(result.repo)}`} className="rounded-full border border-white/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:text-white">
                    Review this repo
                  </Link>
                  <Link href="/" className="rounded-full border border-white/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:text-white">
                    Open Atlas
                  </Link>
                </div>
              </div>
            </div>
          </div>

          {result.warnings.length > 0 && (
            <div className="mt-4 panel rounded-[24px] p-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#ffd98f]">Warnings</p>
              <div className="mt-3 space-y-2">
                {result.warnings.map((warning) => (
                  <p key={warning} className="text-sm leading-relaxed text-[#f3ddb0]">{warning}</p>
                ))}
              </div>
            </div>
          )}

          <div className="mt-6 grid gap-4">
            {result.groups.length > 0 ? (
              result.groups.map((group) => <GroupCard key={group.name} group={group} />)
            ) : (
              <div className="panel rounded-[24px] p-6">
                <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#ffd98f]">
                  No endpoints found
                </p>
                <h3 className="mt-3 text-xl font-semibold text-[#f5f8ff]">
                  Map didn’t find a route surface in the scanned files.
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-[#94a8cb]">
                  This can happen for libraries, frontends without backend routes, or repos that need deeper architecture context first.
                </p>
                <div className="mt-5 flex flex-wrap gap-3">
                  <Link
                    href="/"
                    className="rounded-full border border-white/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:text-white"
                  >
                    Open Atlas
                  </Link>
                  <Link
                    href={`/review?repo=${encodeURIComponent(result.repo)}`}
                    className="rounded-full border border-white/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:text-white"
                  >
                    Run Review
                  </Link>
                </div>
              </div>
            )}
          </div>

          {result.files_scanned.length > 0 && (
            <details className="mt-6 panel rounded-[24px] p-5">
              <summary className="cursor-pointer font-mono text-[11px] uppercase tracking-[0.18em] text-[#c2d3f2]">
                Files scanned ({result.files_scanned.length})
              </summary>
              <div className="mt-4 grid gap-2 sm:grid-cols-2">
                {result.files_scanned.map((file) => (
                  <p key={file} className="font-mono text-[11px] text-[#8ea3c7]">{file}</p>
                ))}
              </div>
            </details>
          )}
        </section>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#6d7f9f]">{label}</p>
      <p className="mt-2 font-mono text-[12px]" style={{ color: color ?? "#dce8ff" }}>
        {value}
      </p>
    </div>
  );
}

function Tag({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="rounded-full border px-2.5 py-1 font-mono text-[10px]"
      style={{ color, borderColor: `${color}35`, backgroundColor: `${color}12` }}
    >
      {label}
    </span>
  );
}
