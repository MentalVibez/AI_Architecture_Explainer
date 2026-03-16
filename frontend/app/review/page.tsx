"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

type JobStatus = "idle" | "queued" | "running" | "completed" | "failed";

interface ReviewResult {
  result_id: string;
  repo_url: string;
  commit: string | null;
  branch: string;
  overall_score: number | null;
  verdict_label: string | null;
  production_suitable: boolean;
  confidence_label: string | null;
  depth_level: string | null;
  anti_gaming_verdict: string | null;
  scores: Record<string, number | null>;
  findings: Finding[];
  summary: { developer: string; manager: string; hiring: string } | null;
  error_code: string | null;
  error_message: string | null;
}

interface Finding {
  id: string;
  rule_id: string;
  title: string;
  category: string;
  severity: string;
  summary: string;
  why_it_matters: string;
  suggested_fix: string;
}

const SEVERITY_COLOR: Record<string, string> = {
  critical: "#c84b4b",
  high: "#c8813a",
  medium: "#c8a96e",
  low: "#6a6a6a",
  info: "#3a3a3a",
};

export default function ReviewPage() {
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [_jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus>("idle");
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setStatus("queued");

    try {
      const res = await fetch(`${API_URL}/api/review/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: url, branch: branch || null }),
      });

      if (res.status === 429) {
        const data = await res.json();
        setError(data.detail?.message ?? "Rate limited. Please try again later.");
        setStatus("idle");
        return;
      }
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail?.message ?? "Failed to submit review.");
        setStatus("idle");
        return;
      }

      const data = await res.json();
      setJobId(data.job_id);
      setStatus("queued");
      pollStatus(data.job_id);
    } catch {
      setError("Network error. Is the backend running?");
      setStatus("idle");
    }
  }

  async function pollStatus(id: string) {
    const MAX_POLLS = 120; // 10 minutes at 5s intervals
    let polls = 0;

    const interval = setInterval(async () => {
      polls++;
      if (polls > MAX_POLLS) {
        clearInterval(interval);
        setError("Review timed out waiting for result.");
        setStatus("failed");
        return;
      }

      try {
        const res = await fetch(`${API_URL}/api/review/${id}`);
        if (!res.ok) return;
        const data = await res.json();

        setStatus(data.status);

        if (data.status === "completed" && data.result_id) {
          clearInterval(interval);
          const rRes = await fetch(`${API_URL}/api/review/results/${data.result_id}`);
          if (rRes.ok) setResult(await rRes.json());
        } else if (data.status === "failed") {
          clearInterval(interval);
          setError(data.error_message ?? "Review failed.");
        }
      } catch {
        // transient network error — keep polling
      }
    }, 5000);
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-16">
      {/* Header */}
      <div className="mb-12">
        <div className="flex items-center gap-3 mb-4">
          <span className="font-mono text-[10px] tracking-[0.3em] text-[#8ab58a] uppercase">
            Tool 04
          </span>
          <span className="h-px flex-1 bg-[#1a1a1a] max-w-[40px]" />
          <BetaBadge />
        </div>
        <h1 className="font-serif text-4xl sm:text-5xl text-[#e8e0d4] mb-4">
          Review
        </h1>
        <p className="font-sans text-[#5a5a5a] text-base leading-relaxed max-w-xl">
          Evidence-backed quality assessment for public GitHub repos. Deterministic
          rules, static analysis adapters, depth-aware scoring, and anti-gaming
          detection — no guesswork.
        </p>

        {/* Beta disclosure */}
        <div className="mt-6 border border-[#1e1e1e] rounded-lg p-4 font-mono text-[11px] text-[#4a4a4a] leading-relaxed space-y-1">
          <p><span className="text-[#8ab58a]">▸</span> Public GitHub repos only. Private repos return a clear error.</p>
          <p><span className="text-[#8ab58a]">▸</span> Score reflects analysis depth — the report shows structural, lint, or full toolchain coverage. Trust the confidence label.</p>
          <p><span className="text-[#8ab58a]">▸</span> Beta: results are calibrated but not perfect. The system tells you when confidence is low.</p>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="mb-10">
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://github.com/owner/repo"
            required
            className="flex-1 bg-[#0a0a0a] border border-[#1e1e1e] rounded-lg
                       px-4 py-3 font-mono text-[13px] text-[#e8e0d4]
                       placeholder-[#3a3a3a] focus:outline-none focus:border-[#8ab58a]
                       transition-colors"
          />
          <input
            type="text"
            value={branch}
            onChange={(e) => setBranch(e.target.value)}
            placeholder="branch (default: main)"
            className="w-48 bg-[#0a0a0a] border border-[#1e1e1e] rounded-lg
                       px-4 py-3 font-mono text-[13px] text-[#e8e0d4]
                       placeholder-[#3a3a3a] focus:outline-none focus:border-[#8ab58a]
                       transition-colors"
          />
          <button
            type="submit"
            disabled={status === "queued" || status === "running"}
            className="px-6 py-3 bg-[#8ab58a] text-[#0a0a0a] font-mono text-[12px]
                       tracking-wider rounded-lg hover:bg-[#9ac59a] transition-colors
                       disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {status === "queued" || status === "running" ? "Reviewing…" : "Review →"}
          </button>
        </div>
      </form>

      {/* Status */}
      {(status === "queued" || status === "running") && (
        <div className="border border-[#1a1a1a] rounded-lg p-6 text-center">
          <div className="font-mono text-[11px] text-[#4a4a4a] tracking-widest uppercase mb-2">
            {status === "queued" ? "Queued" : "Cloning + analysing…"}
          </div>
          <p className="font-mono text-[11px] text-[#3a3a3a]">
            This takes 30–120 seconds depending on repo size.
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="border border-[#c84b4b]/30 rounded-lg p-4 font-mono text-[12px] text-[#c84b4b]">
          {error}
        </div>
      )}

      {/* Result */}
      {result && <ReviewResult result={result} />}
    </div>
  );
}


/* ── Beta badge ──────────────────────────────────────────────────────────── */

function BetaBadge() {
  return (
    <span className="font-mono text-[9px] tracking-[0.2em] uppercase
                     px-2 py-0.5 border border-[#8ab58a]/40 text-[#8ab58a]
                     rounded bg-[#8ab58a]/5">
      Beta
    </span>
  );
}


/* ── Score display ───────────────────────────────────────────────────────── */

function ScoreBar({ label, value }: { label: string; value: number | null }) {
  const pct = value ?? 0;
  const color = pct >= 70 ? "#8ab58a" : pct >= 50 ? "#c8a96e" : "#c84b4b";
  return (
    <div>
      <div className="flex justify-between font-mono text-[11px] mb-1">
        <span className="text-[#5a5a5a] capitalize">{label.replace(/_/g, " ")}</span>
        <span style={{ color }}>{value ?? "—"}</span>
      </div>
      <div className="h-1 bg-[#1a1a1a] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}


/* ── Full result ─────────────────────────────────────────────────────────── */

function ReviewResult({ result }: { result: ReviewResult }) {
  const overallColor =
    (result.overall_score ?? 0) >= 70
      ? "#8ab58a"
      : (result.overall_score ?? 0) >= 50
      ? "#c8a96e"
      : "#c84b4b";

  return (
    <div className="space-y-8">
      {/* Overview */}
      <div className="border border-[#1a1a1a] rounded-lg p-6">
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <p className="font-mono text-[11px] text-[#3a3a3a] mb-1 truncate max-w-xs">
              {result.repo_url}
            </p>
            <div className="flex items-center gap-3 flex-wrap">
              <span
                className="font-serif text-5xl font-bold"
                style={{ color: overallColor }}
              >
                {result.overall_score ?? "—"}
              </span>
              <div>
                <p className="font-mono text-[13px] text-[#e8e0d4]">
                  {result.verdict_label ?? "—"}
                </p>
                <p className="font-mono text-[10px] text-[#3a3a3a]">
                  {result.production_suitable ? "production suitable" : "not production suitable"}
                </p>
              </div>
            </div>
          </div>
          <div className="text-right space-y-1">
            <p className="font-mono text-[10px] text-[#3a3a3a]">
              Confidence: <span className="text-[#5a5a5a]">{result.confidence_label ?? "—"}</span>
            </p>
            <p className="font-mono text-[10px] text-[#3a3a3a]">
              Depth: <span className="text-[#5a5a5a]">{result.depth_level?.replace(/_/g, " ") ?? "—"}</span>
            </p>
            {result.anti_gaming_verdict && result.anti_gaming_verdict !== "likely_honest" && (
              <p className="font-mono text-[10px] text-[#c8a96e]">
                ⚠ {result.anti_gaming_verdict.replace(/_/g, " ")}
              </p>
            )}
          </div>
        </div>

        {/* Score bars */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {Object.entries(result.scores).map(([k, v]) => (
            <ScoreBar key={k} label={k} value={v} />
          ))}
        </div>
      </div>

      {/* Summaries */}
      {result.summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <SummaryCard title="Developer" body={result.summary.developer} accent="#7cb9c8" />
          <SummaryCard title="Hiring Manager" body={result.summary.manager} accent="#c8a96e" />
        </div>
      )}

      {/* Findings */}
      {result.findings && result.findings.length > 0 && (
        <div>
          <h2 className="font-mono text-[11px] tracking-[0.3em] text-[#3a3a3a] uppercase mb-4">
            Findings ({result.findings.length})
          </h2>
          <div className="space-y-3">
            {result.findings.map((f) => (
              <FindingCard key={f.id} finding={f} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ title, body, accent }: { title: string; body: string; accent: string }) {
  return (
    <div className="border border-[#1a1a1a] rounded-lg p-5">
      <p className="font-mono text-[10px] tracking-widest uppercase mb-3" style={{ color: accent }}>
        {title}
      </p>
      <p className="font-sans text-[13px] text-[#8a8a8a] leading-relaxed">{body}</p>
    </div>
  );
}

function FindingCard({ finding }: { finding: Finding }) {
  const [open, setOpen] = useState(false);
  const color = SEVERITY_COLOR[finding.severity] ?? "#3a3a3a";
  return (
    <div className="border border-[#1a1a1a] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left px-4 py-3 flex items-center gap-3 hover:bg-[#0e0e0e] transition-colors"
      >
        <span
          className="font-mono text-[9px] tracking-wider uppercase px-1.5 py-0.5 border rounded flex-shrink-0"
          style={{ color, borderColor: color + "40" }}
        >
          {finding.severity}
        </span>
        <span className="font-mono text-[12px] text-[#c8c0b8] flex-1 text-left">{finding.title}</span>
        <span className="font-mono text-[10px] text-[#2a2a2a]">{finding.category}</span>
        <span className="font-mono text-[11px] text-[#2a2a2a] ml-2">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-2 border-t border-[#1a1a1a]">
          <p className="font-sans text-[12px] text-[#6a6a6a] mt-3">{finding.summary}</p>
          {finding.why_it_matters && (
            <p className="font-mono text-[11px] text-[#4a4a4a]">
              <span className="text-[#3a3a3a]">Why: </span>{finding.why_it_matters}
            </p>
          )}
          {finding.suggested_fix && (
            <p className="font-mono text-[11px] text-[#4a4a4a]">
              <span className="text-[#3a3a3a]">Fix: </span>{finding.suggested_fix}
            </p>
          )}
          <p className="font-mono text-[10px] text-[#2a2a2a]">{finding.rule_id}</p>
        </div>
      )}
    </div>
  );
}
