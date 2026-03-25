/**
 * app/scout/page.tsx  —  RepoScout tool page
 *
 * Drop into Atlas's existing frontend directory structure:
 *   frontend/app/scout/page.tsx
 *
 * Design language: inherits Atlas's globals.css tokens (DM Serif, DM Mono,
 * dark background, border-based layout). RepoScout accent = #c8a96e (amber).
 * Atlas accent = #7cb9c8 (teal). Both live in the same design system.
 *
 * The "Analyze with Atlas →" button on each card calls POST /api/analyze
 * and redirects to the Atlas results page — the existing Atlas API endpoint,
 * unchanged.
 *
 * API: POST /api/scout/search  (new backend route from REPOSCOUT_INTEGRATION.md)
 */

"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";

/* ── Types ────────────────────────────────────────────────────────────────── */

type Platform = "github" | "gitlab";
type SortBy   = "stars" | "updated" | "best-match";
type Verdict  = "HIGHLY_RECOMMENDED" | "RECOMMENDED" | "WORTH_CHECKING" | "AVOID";
type SigType  = "good" | "warn" | "bad";

interface Signal   { label: string; type: SigType; verified: boolean }
interface Scores   { quality_score: number; relevance_score: number; overall_score: number }
interface Evidence {
  stars: number; forks: number; days_since_update: number | null;
  has_license: boolean; license_name: string | null; readme_verified: boolean;
  is_fork: boolean; is_archived: boolean; is_template: boolean;
  open_issues: number; topic_matches: string[]; matched_terms: string[];
  noise_flags: string[];
}
interface Repo {
  id: string; platform: Platform; full_name: string; owner: string;
  description: string; url: string; language: string | null;
  created_at: string | null; updated_at: string | null;
  scores: Scores; verdict: Verdict; ai_insight: string;
  risks: string[]; signals: Signal[]; evidence: Evidence;
}
interface ScoutResponse { query: string; total: number; repos: Repo[]; tldr: string }

/* ── Helpers ─────────────────────────────────────────────────────────────── */

function fmtNum(n: number) { return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n); }

const VERDICT_MAP: Record<Verdict, { label: string; color: string }> = {
  HIGHLY_RECOMMENDED: { label: "✦ Top pick",       color: "#6dba8a" },
  RECOMMENDED:        { label: "✔ Recommended",     color: "#6dba8a" },
  WORTH_CHECKING:     { label: "◈ Worth checking",  color: "#c8a96e" },
  AVOID:              { label: "✘ Avoid",            color: "#b86a6a" },
};

/* ── ScoreBar ────────────────────────────────────────────────────────────── */

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color = value >= 75 ? "#6dba8a" : value >= 45 ? "#c8a96e" : "#b86a6a";
  return (
    <div className="mb-2">
      <div className="flex justify-between mb-0.5">
        <span className="font-mono text-[10px] tracking-widest text-[#3a3a3a] uppercase">{label}</span>
        <span className="font-mono text-[10px] font-medium" style={{ color }}>{value}</span>
      </div>
      <div className="h-px bg-[#1a1a1a] rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${value}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

/* ── EvidenceDrawer ──────────────────────────────────────────────────────── */

function EvidenceDrawer({ ev }: { ev: Evidence }) {
  const rows: { label: string; val: string; good?: boolean; bad?: boolean }[] = [
    { label: "Stars",       val: fmtNum(ev.stars),     good: ev.stars >= 100, bad: ev.stars < 10 },
    { label: "Forks",       val: fmtNum(ev.forks) },
    { label: "Last update", val: ev.days_since_update != null ? `${ev.days_since_update}d ago` : "unknown",
      good: (ev.days_since_update ?? 999) <= 90, bad: (ev.days_since_update ?? 0) > 365 },
    { label: "License",     val: ev.license_name ?? "None", good: ev.has_license, bad: !ev.has_license },
    { label: "README",      val: ev.readme_verified ? "Confirmed" : "Unverified", good: ev.readme_verified },
    { label: "Issues open", val: String(ev.open_issues) },
    { label: "Fork",        val: ev.is_fork ? "Yes" : "No", bad: ev.is_fork },
    { label: "Archived",    val: ev.is_archived ? "Yes" : "No", bad: ev.is_archived },
  ];
  const valColor = (r: typeof rows[0]) =>
    r.good ? "#6dba8a" : r.bad ? "#b86a6a" : "#4a4a4a";

  return (
    <div className="border border-[#1a1a1a] rounded p-4 mt-3 bg-[#080808]">
      <p className="font-mono text-[10px] tracking-[0.25em] text-[#2a2a2a] uppercase mb-3">Evidence</p>
      <div className="grid grid-cols-2 gap-x-8 gap-y-1.5 text-[11px] mb-3">
        {rows.map((r) => (
          <div key={r.label} className="flex justify-between">
            <span className="text-[#3a3a3a]">{r.label}</span>
            <span className="font-mono font-medium" style={{ color: valColor(r) }}>{r.val}</span>
          </div>
        ))}
      </div>
      {ev.topic_matches.length > 0 && (
        <p className="text-[10px] mb-1">
          <span className="text-[#2a2a2a]">Topic matches: </span>
          <span className="font-mono text-[#6dba8a]">{ev.topic_matches.join(", ")}</span>
        </p>
      )}
      {ev.noise_flags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {ev.noise_flags.map((f) => (
            <span key={f} className="font-mono text-[10px] px-1.5 py-0.5 border border-[#c8a96e]/20 text-[#c8a96e]/60 rounded">
              ⚠ {f}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── RepoCard ────────────────────────────────────────────────────────────── */

function RepoCard({ repo, rank }: { repo: Repo; rank: number }) {
  const router = useRouter();
  const [showEvidence, setShowEvidence] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeErr, setAnalyzeErr] = useState("");

  const overall  = repo.scores.overall_score;
  const scoreColor = overall >= 75 ? "#6dba8a" : overall >= 45 ? "#c8a96e" : "#b86a6a";
  const verdict  = VERDICT_MAP[repo.verdict];

  async function handleAtlas() {
    setAnalyzing(true); setAnalyzeErr("");
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/analyze`,
        { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ repo_url: repo.url }) }
      );
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail ?? `Atlas error ${res.status}`);
      }
      const { job_id } = await res.json();
      if (typeof job_id !== "string") throw new Error("Unexpected response from Atlas.");
      router.push(`/results/${job_id}`);
    } catch (e) {
      setAnalyzeErr(e instanceof Error ? e.message : "Failed to submit to Atlas.");
      setAnalyzing(false);
    }
  }

  return (
    <div className="border border-[#1a1a1a] rounded-lg overflow-hidden
                    hover:border-[#2a2a2a] transition-colors group">
      {/* Header */}
      <div className="flex items-start gap-4 p-5 border-b border-[#141414]">
        {/* Rank */}
        <div className={`w-8 h-8 flex items-center justify-center font-mono text-[11px] flex-shrink-0 rounded
          ${rank === 1 ? "bg-[#c8a96e] text-[#0a0a0a]"
          : rank === 2 ? "bg-[#5a5a5a] text-[#0a0a0a]"
          : rank === 3 ? "bg-[#7a5a3a] text-[#e8e0d4]"
          : "border border-[#1e1e1e] text-[#3a3a3a]"}`}
        >
          #{rank}
        </div>

        <div className="flex-1 min-w-0">
          <a href={repo.url} target="_blank" rel="noopener noreferrer"
             className="font-sans font-semibold text-[#e8e0d4] hover:text-white
                        truncate block transition-colors text-sm">
            {repo.full_name}
            <span className={`ml-2 font-mono text-[9px] tracking-widest px-1.5 py-0.5 rounded uppercase
              ${repo.platform === "github" ? "bg-[#1a1a1a] text-[#3a3a3a]" : "bg-orange-900/20 text-orange-500/60"}`}>
              {repo.platform === "github" ? "GH" : "GL"}
            </span>
          </a>
          <div className="font-mono text-[10px] text-[#3a3a3a] mt-0.5">
            {repo.owner} · {repo.language ?? "—"} · {repo.created_at ? new Date(repo.created_at).getFullYear() : "—"}
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <span className="font-mono text-[10px] tracking-wide" style={{ color: verdict.color }}>
              {verdict.label}
            </span>
          </div>
        </div>

        {/* Overall score */}
        <div className="text-center flex-shrink-0">
          <div className="font-serif text-3xl leading-none" style={{ color: scoreColor }}>{overall}</div>
          <div className="font-mono text-[9px] tracking-[0.2em] text-[#2a2a2a] uppercase mt-0.5">score</div>
        </div>
      </div>

      {/* Body */}
      <div className="p-5">
        {repo.description && (
          <p className="font-sans text-[12px] text-[#4a4a4a] leading-relaxed mb-3">{repo.description}</p>
        )}
        {repo.ai_insight && (
          <div className="border-l-2 border-[#c8a96e]/30 pl-3 font-sans text-[12px]
                          italic text-[#5a5a5a] leading-relaxed mb-4">
            {repo.ai_insight}
          </div>
        )}

        {/* Score bars */}
        <div className="mb-4">
          <ScoreBar label="Quality"   value={repo.scores.quality_score} />
          <ScoreBar label="Relevance" value={repo.scores.relevance_score} />
        </div>

        {/* Topic matches */}
        {repo.evidence.topic_matches.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {repo.evidence.topic_matches.map((t) => (
              <span key={t} className="font-mono text-[9px] px-1.5 py-0.5
                                       border border-[#c8a96e]/20 text-[#c8a96e]/70 rounded tracking-wider">
                {t}
              </span>
            ))}
          </div>
        )}

        {/* Risks */}
        {repo.risks.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-4">
            {repo.risks.map((r, i) => (
              <span key={i} className="font-mono text-[9px] px-1.5 py-0.5
                                       border border-[#c8a96e]/15 text-[#c8a96e]/50 rounded">
                ⚠ {r}
              </span>
            ))}
          </div>
        )}

        {/* Evidence toggle */}
        <button onClick={() => setShowEvidence((s) => !s)}
                className="font-mono text-[10px] text-[#2a2a2a] hover:text-[#4a4a4a]
                           underline underline-offset-2 transition-colors mb-1">
          {showEvidence ? "Hide evidence ↑" : "Show evidence ↓"}
        </button>
        {showEvidence && <EvidenceDrawer ev={repo.evidence} />}

        {/* CTA row */}
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-[#141414]">
          <a href={repo.url} target="_blank" rel="noopener noreferrer"
             className="font-mono text-[11px] text-[#c8a96e]/60 hover:text-[#c8a96e] transition-colors tracking-wider">
            View repo →
          </a>
          <div className="flex flex-col items-end gap-1">
            <button onClick={handleAtlas} disabled={analyzing}
                    className="font-mono text-[11px] px-3 py-1.5 border border-[#7cb9c8]/30
                               text-[#7cb9c8]/70 hover:text-[#7cb9c8] hover:border-[#7cb9c8]/60
                               disabled:opacity-40 transition-all rounded tracking-wider">
              {analyzing ? "Submitting…" : "Analyze with Atlas →"}
            </button>
            {analyzeErr && (
              <p className="font-mono text-[9px] text-[#b86a6a] max-w-[220px] text-right">{analyzeErr}</p>
            )}
          </div>
        </div>
      </div>

      {/* Signals footer */}
      {repo.signals.length > 0 && (
        <div className="flex flex-wrap gap-1 px-5 py-3 bg-[#060606] border-t border-[#141414]">
          {repo.signals.map((s, i) => (
            <span key={i} className={`font-mono text-[9px] px-1.5 py-0.5 border rounded tracking-wider
              ${s.type === "good" ? "border-[#6dba8a]/20 text-[#6dba8a]/60"
              : s.type === "warn" ? "border-[#c8a96e]/20 text-[#c8a96e]/60"
              : "border-[#b86a6a]/20 text-[#b86a6a]/60"}`}>
              {!s.verified && "〜"}{s.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Main page ───────────────────────────────────────────────────────────── */

export default function ScoutPage() {
  const [query,   setQuery]   = useState("");
  const [token,   setToken]   = useState("");
  const [github,  setGithub]  = useState(true);
  const [gitlab,  setGitlab]  = useState(true);
  const [sortBy,  setSortBy]  = useState<SortBy>("stars");
  const [loading, setLoading] = useState(false);
  const [progress,setProgress]= useState(0);
  const [status,  setStatus]  = useState("");
  const [result,  setResult]  = useState<ScoutResponse | null>(null);
  const [error,   setError]   = useState("");
  const [hasSearched, setHasSearched] = useState(false);

  const handleScan = useCallback(async () => {
    if (!query.trim() || (!github && !gitlab)) return;
    setLoading(true); setResult(null); setError(""); setProgress(10);
    const platforms: Platform[] = [...(github ? ["github" as const] : []), ...(gitlab ? ["gitlab" as const] : [])];

    try {
      setStatus("Scanning repositories…"); setProgress(30);
      const tick = setInterval(() => setProgress((p) => Math.min(p + 4, 75)), 700);
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/scout/search`,
        { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query, platforms, sort_by: sortBy, ...(token ? { github_token: token } : {}) }) }
      );
      clearInterval(tick);
      if (!res.ok) { const b = await res.json().catch(() => ({})); throw new Error(b.detail ?? `Error ${res.status}`); }
      setProgress(85); setStatus("Finalising AI scores…");
      await new Promise((r) => setTimeout(r, 300));
      const data: ScoutResponse = await res.json();
      setResult(data); setProgress(100); setStatus(`✦ ${data.total} repositories analysed`);
      setHasSearched(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "An unexpected error occurred.");
      setStatus(""); setProgress(0);
    } finally { setLoading(false); }
  }, [query, token, github, gitlab, sortBy]);

  return (
    <div className="max-w-6xl mx-auto px-6">

      {/* Tool header */}
      <section className="pt-16 pb-10 border-b border-[#1a1a1a]">
        <div className="flex items-center gap-3 mb-4">
          <span className="font-mono text-[10px] tracking-[0.3em] text-[#c8a96e] uppercase">Tool 01</span>
          <span className="h-px w-8 bg-[#1e1e1e]" />
        </div>
        <h1 className="font-serif text-5xl text-[#e8e0d4] mb-3">RepoScout</h1>
        <p className="font-sans text-[#5a5a5a] text-base leading-relaxed max-w-xl">
          Search GitHub and GitLab simultaneously. Credibility scores, noise suppression,
          intent-aware ranking. Then send the winner to Atlas for a deep dive.
        </p>
      </section>

      {/* Search panel */}
      <section className="py-10">
        <div className="border border-[#1a1a1a] rounded-lg p-6 bg-[#0c0c0c]">

          <div className="flex gap-3 mb-4">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !loading && handleScan()}
              placeholder='e.g. "RAG pipeline LangChain" or "AWS CDK infrastructure as code"'
              className="flex-1 bg-[#080808] border border-[#1e1e1e] rounded px-4 py-2.5
                         font-mono text-[13px] text-[#e8e0d4] placeholder-[#2a2a2a]
                         outline-none focus:border-[#c8a96e]/40 transition-colors"
            />
            <button
              onClick={handleScan}
              disabled={loading || !query.trim() || (!github && !gitlab)}
              className="px-6 py-2.5 bg-[#c8a96e] text-[#0a0a0a] font-mono text-[12px]
                         tracking-widest uppercase rounded hover:bg-[#d4b87a]
                         disabled:opacity-40 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
            >
              {loading ? "Scanning…" : "⌖ Scan"}
            </button>
          </div>

          <div className="flex flex-wrap gap-2 items-center mb-4">
            {([
              { id: "github", label: "GitHub", val: github, set: setGithub },
              { id: "gitlab", label: "GitLab", val: gitlab, set: setGitlab },
            ] as const).map((p) => (
              <button key={p.id} onClick={() => p.set(!p.val)}
                      className={`px-3 py-1 font-mono text-[11px] tracking-widest uppercase rounded border transition-colors
                        ${p.val
                          ? "border-[#c8a96e]/40 text-[#c8a96e]/80 bg-[#c8a96e]/5"
                          : "border-[#1a1a1a] text-[#3a3a3a] hover:border-[#2a2a2a]"}`}>
                {p.label}
              </button>
            ))}
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as SortBy)}
                    className="ml-auto bg-[#080808] border border-[#1a1a1a] rounded px-3 py-1
                               font-mono text-[11px] text-[#3a3a3a] outline-none">
              <option value="stars">Sort: Stars</option>
              <option value="updated">Sort: Updated</option>
              <option value="best-match">Sort: Best match</option>
            </select>
          </div>

          <input type="password" value={token} onChange={(e) => setToken(e.target.value)}
                 placeholder="GitHub token (optional — raises rate limit to 5,000 req/hr)"
                 autoComplete="off"
                 className="w-full bg-[#080808] border border-[#1a1a1a] rounded px-4 py-2
                            font-mono text-[11px] text-[#3a3a3a] placeholder-[#1e1e1e]
                            outline-none focus:border-[#c8a96e]/20 transition-colors" />
          <p className="font-mono text-[10px] text-[#1e1e1e] mt-1.5">
            Token used only for this request and never stored. github.com/settings/tokens — no scopes needed for public repos.
          </p>

          {loading && (
            <div className="mt-4">
              <div className="h-px bg-[#141414] rounded-full overflow-hidden">
                <div className="h-full bg-[#c8a96e] transition-all duration-300 rounded-full"
                     style={{ width: `${progress}%` }} />
              </div>
              <p className="font-mono text-[10px] text-[#2a2a2a] mt-1.5 italic">{status}</p>
            </div>
          )}
        </div>
      </section>

      {/* Error */}
      {error && (
        <div className="border border-[#b86a6a]/20 bg-[#b86a6a]/5 rounded p-3
                        font-mono text-[11px] text-[#b86a6a] mb-6">{error}</div>
      )}

      {/* TLDR */}
      {result?.tldr && (
        <div className="border border-[#c8a96e]/20 bg-[#c8a96e]/3 rounded-lg p-5 mb-8 relative">
          <span className="absolute -top-px right-4 font-mono text-[9px] tracking-[0.3em]
                           bg-[#c8a96e] text-[#0a0a0a] px-2 py-0.5 uppercase">
            TLDR
          </span>
          <p className="font-sans text-[13px] text-[#6a6a6a] leading-relaxed">{result.tldr}</p>
        </div>
      )}

      {/* Results */}
      {result && result.repos.length > 0 && (
        <section className="pb-20">
          <div className="flex justify-between items-center mb-5 flex-wrap gap-2">
            <h2 className="font-serif text-2xl text-[#e8e0d4]">
              <span className="text-[#c8a96e]">{result.total}</span> repositories
            </h2>
            <span className="font-mono text-[10px] text-[#2a2a2a] tracking-widest uppercase">
              Sorted by overall score
            </span>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {result.repos.map((repo, i) => (
              <RepoCard key={repo.id} repo={repo} rank={i + 1} />
            ))}
          </div>
        </section>
      )}

      {/* No results empty state */}
      {!loading && hasSearched && result && result.repos.length === 0 && !error && (
        <div className="text-center py-24">
          <div className="font-mono text-4xl mb-5 text-[#1e1e1e]">⌖</div>
          <p className="font-serif text-2xl text-[#3a3a3a] mb-2">
            No repositories found
          </p>
          <p className="font-sans text-[13px] text-[#2a2a2a] mb-8">
            for &ldquo;{result.query}&rdquo;
          </p>
          <ul className="font-mono text-[11px] text-[#2a2a2a] tracking-wider space-y-2 inline-block text-left">
            <li>→ Try broader or shorter search terms</li>
            <li>→ Switch from GitHub-only to both GitHub and GitLab</li>
            <li>→ Search by technology instead of project name</li>
            <li>→ Use English keywords — repo names are typically English</li>
          </ul>
        </div>
      )}

      {/* Initial empty state */}
      {!loading && !hasSearched && !error && (
        <div className="text-center py-24">
          <div className="font-mono text-5xl mb-4 text-[#1a1a1a]">⌖</div>
          <p className="font-sans text-[#2a2a2a]">Enter a query to begin scouting</p>
        </div>
      )}
    </div>
  );
}
