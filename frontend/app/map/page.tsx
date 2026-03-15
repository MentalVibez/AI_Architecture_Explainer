"use client";

/**
 * app/map/page.tsx  —  API Endpoint Mapper (Tool 03)
 *
 * Submits owner/repo to GET /api/map/{owner}/{repo}.
 * Shows a phase tracker animation while the pipeline runs,
 * then renders grouped endpoint cards with METHOD badges.
 *
 * Accent: sage green #8ab58a
 */

import { useState, useEffect, useRef } from "react";

/* ── Accent colour ────────────────────────────────────────────────────────── */
const ACCENT = "#8ab58a";

/* ── Types ────────────────────────────────────────────────────────────────── */

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

/* ── Helpers ──────────────────────────────────────────────────────────────── */

const METHOD_COLORS: Record<string, string> = {
  GET:    "#6dba8a",
  POST:   "#7cb9c8",
  PUT:    "#c8a96e",
  PATCH:  "#c8a96e",
  DELETE: "#b86a6a",
  ANY:    "#5a5a5a",
};

function parseRepoInput(raw: string): { owner: string; repo: string } | null {
  const trimmed = raw.trim().replace(/\/$/, "");
  // Full URL: https://github.com/owner/repo
  const urlMatch = trimmed.match(/github\.com\/([^/\s]+)\/([^/\s]+)/);
  if (urlMatch) return { owner: urlMatch[1], repo: urlMatch[2] };
  // Short form: owner/repo
  const shortMatch = trimmed.match(/^([a-zA-Z0-9_-]+)\/([a-zA-Z0-9_.-]+)$/);
  if (shortMatch) return { owner: shortMatch[1], repo: shortMatch[2] };
  return null;
}

function getApiUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

/* ── PHASES ───────────────────────────────────────────────────────────────── */

const PHASES = [
  { id: "profile",   label: "Stack Profile",      detail: "Detecting framework from manifests" },
  { id: "extract",   label: "Route Extraction",    detail: "Scanning source files for endpoints" },
  { id: "enrich",    label: "LLM Enrichment",      detail: "Grouping and describing endpoints" },
];

/* ── MethodBadge ──────────────────────────────────────────────────────────── */

function MethodBadge({ method }: { method: string }) {
  const color = METHOD_COLORS[method.toUpperCase()] ?? METHOD_COLORS.ANY;
  return (
    <span
      className="font-mono text-[10px] tracking-widest px-2 py-0.5 rounded border font-medium shrink-0"
      style={{ color, borderColor: `${color}40`, backgroundColor: `${color}10` }}
    >
      {method.toUpperCase()}
    </span>
  );
}

/* ── EndpointCard ─────────────────────────────────────────────────────────── */

function EndpointCard({ ep }: { ep: Endpoint }) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-[#111] last:border-0">
      <MethodBadge method={ep.method} />
      <div className="flex-1 min-w-0">
        <span className="font-mono text-[12px] text-[#c8c0b8] break-all">{ep.path}</span>
        {ep.description && (
          <p className="font-sans text-[12px] text-[#4a4a4a] mt-0.5 leading-relaxed">
            {ep.description}
          </p>
        )}
        {ep.notes && (
          <p className="font-mono text-[10px] text-[#3a3a3a] mt-0.5">{ep.notes}</p>
        )}
      </div>
      {ep.auth_likely && (
        <span className="font-mono text-[9px] tracking-widest text-[#c8a96e] border border-[#c8a96e30] px-1.5 py-0.5 rounded shrink-0">
          AUTH
        </span>
      )}
    </div>
  );
}

/* ── GroupCard ────────────────────────────────────────────────────────────── */

function GroupCard({ group }: { group: EndpointGroup }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="border border-[#1a1a1a] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-4
                   hover:bg-[#0e0e0e] transition-colors text-left"
      >
        <div>
          <span className="font-sans font-semibold text-[13px] text-[#c8c0b8]">{group.name}</span>
          {group.description && (
            <p className="font-mono text-[11px] text-[#3a3a3a] mt-0.5">{group.description}</p>
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-4">
          <span className="font-mono text-[10px] text-[#2a2a2a]">
            {group.endpoints.length} endpoint{group.endpoints.length !== 1 ? "s" : ""}
          </span>
          <span className="text-[#2a2a2a] text-[11px]">{open ? "▲" : "▼"}</span>
        </div>
      </button>
      {open && (
        <div className="px-5 border-t border-[#1a1a1a]">
          {group.endpoints.map((ep, i) => (
            <EndpointCard key={i} ep={ep} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ── PhaseTracker ─────────────────────────────────────────────────────────── */

function PhaseTracker({ phase }: { phase: number }) {
  return (
    <div className="flex flex-col gap-3 w-full max-w-sm">
      {PHASES.map((p, i) => {
        const done    = i < phase;
        const active  = i === phase;
        const pending = i > phase;
        return (
          <div key={p.id} className="flex items-start gap-3">
            <div
              className="w-5 h-5 rounded-full border flex items-center justify-center shrink-0 mt-0.5 transition-all duration-300"
              style={{
                borderColor: done || active ? ACCENT : "#2a2a2a",
                backgroundColor: done ? ACCENT : "transparent",
              }}
            >
              {done ? (
                <span className="text-[10px] text-[#0a0a0a]">✓</span>
              ) : active ? (
                <span className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: ACCENT }} />
              ) : null}
            </div>
            <div>
              <p
                className="font-mono text-[11px] tracking-widest transition-colors"
                style={{ color: done ? ACCENT : active ? "#c8c0b8" : "#2a2a2a" }}
              >
                {p.label}
              </p>
              {(active || done) && (
                <p className="font-mono text-[10px] text-[#3a3a3a] mt-0.5">{p.detail}</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Page ─────────────────────────────────────────────────────────────────── */

export default function MapPage() {
  const [input, setInput]     = useState("");
  const [loading, setLoading] = useState(false);
  const [phase, setPhase]     = useState(-1);
  const [result, setResult]   = useState<MapResult | null>(null);
  const [error, setError]     = useState<string | null>(null);
  const phaseRef              = useRef<ReturnType<typeof setInterval> | null>(null);

  // Simulate phase progression during the API call
  useEffect(() => {
    if (loading) {
      setPhase(0);
      let current = 0;
      phaseRef.current = setInterval(() => {
        current += 1;
        if (current < PHASES.length) setPhase(current);
        else if (phaseRef.current) clearInterval(phaseRef.current);
      }, 1800);
    } else {
      if (phaseRef.current) clearInterval(phaseRef.current);
      if (!result) setPhase(-1);
    }
    return () => { if (phaseRef.current) clearInterval(phaseRef.current); };
  }, [loading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setResult(null);

    const parsed = parseRepoInput(input);
    if (!parsed) {
      setError("Enter a GitHub URL or owner/repo (e.g. tiangolo/fastapi)");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(
        `${getApiUrl()}/api/map/${parsed.owner}/${parsed.repo}`,
        { headers: { "Content-Type": "application/json" } },
      );
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`API error ${res.status}: ${body}`);
      }
      const data: MapResult = await res.json();
      setPhase(PHASES.length); // all done
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const confidence = result?.profile_used.framework_confidence ?? "";
  const confidenceColor =
    confidence === "high"       ? ACCENT :
    confidence === "speculative" ? "#c8a96e" : "#5a5a5a";

  return (
    <div className="max-w-5xl mx-auto px-6">

      {/* ── Header ───────────────────────────────────────────────────── */}
      <section className="pt-20 pb-14 border-b border-[#1a1a1a]">
        <div className="flex items-center gap-3 mb-6">
          <span className="font-mono text-[10px] tracking-[0.3em] uppercase" style={{ color: ACCENT }}>
            Tool 03
          </span>
          <span className="h-px bg-[#1e1e1e] w-8" />
          <span className="font-mono text-[10px] tracking-widest text-[#2a2a2a] uppercase">
            API Endpoint Mapper
          </span>
        </div>

        <h1 className="font-serif text-5xl sm:text-6xl leading-[0.95] tracking-[-0.02em] text-[#e8e0d4] mb-5">
          Map the API.<br />
          <em className="not-italic" style={{ color: ACCENT }}>Understand</em> the surface.
        </h1>

        <p className="font-sans text-[#5a5a5a] text-base leading-relaxed max-w-xl mb-10">
          Atlas detects the framework, selects framework-targeted regex patterns, extracts
          every route, then uses Claude to group and describe the API surface — without
          guessing what it already knows.
        </p>

        {/* Input form */}
        <form onSubmit={handleSubmit} className="flex flex-col gap-3 max-w-xl">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="tiangolo/fastapi  or  https://github.com/owner/repo"
              required
              disabled={loading}
              className="flex-1 px-4 py-3 rounded-lg bg-[#111] border border-[#1e1e1e]
                         text-white placeholder-[#2a2a2a] focus:outline-none focus:border-[#8ab58a]
                         font-mono text-[13px] disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-6 py-3 rounded-lg font-mono text-[12px] tracking-widest uppercase
                         disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              style={{
                backgroundColor: ACCENT,
                color: "#0a0a0a",
              }}
            >
              {loading ? "Mapping…" : "Map API"}
            </button>
          </div>
          {error && <p className="text-red-400 font-mono text-[12px]">{error}</p>}
        </form>

        {/* Sample repos */}
        <div className="mt-5 flex flex-wrap gap-2">
          {[
            "tiangolo/fastapi",
            "django/django",
            "expressjs/express",
            "nextjs/next.js",
          ].map((r) => (
            <button
              key={r}
              onClick={() => setInput(r)}
              disabled={loading}
              className="px-3 py-1.5 rounded font-mono text-[11px] text-[#3a3a3a]
                         border border-[#1e1e1e] hover:border-[#2a2a2a] hover:text-[#5a5a5a]
                         transition-colors disabled:opacity-40"
            >
              {r}
            </button>
          ))}
        </div>
      </section>

      {/* ── Loading phase tracker ─────────────────────────────────────── */}
      {loading && (
        <section className="py-16 flex flex-col items-center gap-8">
          <PhaseTracker phase={phase} />
          <p className="font-mono text-[11px] text-[#2a2a2a] tracking-widest">
            Fetching repo tree · scanning for routes · enriching with Claude
          </p>
        </section>
      )}

      {/* ── Results ───────────────────────────────────────────────────── */}
      {result && !loading && (
        <section className="py-12">

          {/* Profile context bar */}
          <div className="border border-[#1a1a1a] rounded-lg px-5 py-4 mb-8 flex flex-wrap gap-x-8 gap-y-2">
            <MetaStat label="Framework" value={result.profile_used.framework || "unknown"} color={confidenceColor} />
            <MetaStat label="Confidence" value={confidence} color={confidenceColor} />
            <MetaStat label="API style" value={result.api_style} />
            <MetaStat label="Auth pattern" value={result.auth_pattern} />
            <MetaStat label="Endpoints found" value={String(result.raw_endpoint_count)} color={ACCENT} />
            <MetaStat label="Files scanned" value={String(result.files_scanned.length)} />
            <MetaStat label="Duration" value={`${result.duration_ms} ms`} />
          </div>

          {/* Summary */}
          {result.summary && (
            <p className="font-sans text-[#5a5a5a] text-sm leading-relaxed mb-8 max-w-2xl">
              {result.summary}
            </p>
          )}

          {/* Stack context */}
          {(result.profile_used.detected_backend.length > 0 || result.profile_used.detected_frontend.length > 0) && (
            <div className="mb-6 flex flex-wrap gap-2">
              {result.profile_used.detected_backend.map((fw) => (
                <Chip key={fw} label={fw} color={ACCENT} />
              ))}
              {result.profile_used.detected_frontend.map((fw) => (
                <Chip key={fw} label={fw} color="#7cb9c8" />
              ))}
            </div>
          )}

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <div className="mb-8 border border-[#c8a96e20] rounded-lg px-4 py-3 space-y-1">
              {result.warnings.map((w, i) => (
                <p key={i} className="font-mono text-[11px] text-[#c8a96e]">{w}</p>
              ))}
            </div>
          )}

          {/* Endpoint groups */}
          {result.groups.length > 0 ? (
            <div className="flex flex-col gap-3">
              {result.groups.map((group, i) => (
                <GroupCard key={i} group={group} />
              ))}
            </div>
          ) : (
            <div className="border border-[#1a1a1a] rounded-lg p-8 text-center">
              <p className="font-mono text-[12px] text-[#3a3a3a]">
                No API endpoints found in the expected locations for this framework.
              </p>
            </div>
          )}

          {/* Files scanned */}
          {result.files_scanned.length > 0 && (
            <details className="mt-8">
              <summary className="font-mono text-[11px] tracking-widest text-[#2a2a2a] uppercase cursor-pointer hover:text-[#4a4a4a]">
                Files scanned ({result.files_scanned.length})
              </summary>
              <ul className="mt-3 space-y-1 ml-4">
                {result.files_scanned.map((f) => (
                  <li key={f} className="font-mono text-[11px] text-[#3a3a3a]">{f}</li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}
    </div>
  );
}

/* ── Small helpers ────────────────────────────────────────────────────────── */

function MetaStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <p className="font-mono text-[9px] tracking-widest text-[#2a2a2a] uppercase mb-0.5">{label}</p>
      <p className="font-mono text-[12px]" style={{ color: color ?? "#6a6a6a" }}>{value}</p>
    </div>
  );
}

function Chip({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="font-mono text-[10px] tracking-wider px-2.5 py-1 rounded border"
      style={{ color, borderColor: `${color}30`, backgroundColor: `${color}08` }}
    >
      {label}
    </span>
  );
}
