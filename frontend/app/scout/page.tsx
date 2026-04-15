"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";

import { submitAnalysis } from "@/lib/api";
import { useRepoWorkspace } from "@/components/workspace/RepoWorkspaceProvider";

type Platform = "github" | "gitlab";
type SortBy = "stars" | "updated" | "best-match";
type Verdict = "HIGHLY_RECOMMENDED" | "RECOMMENDED" | "WORTH_CHECKING" | "AVOID";
type SigType = "good" | "warn" | "bad";

interface Signal {
  label: string;
  type: SigType;
  verified: boolean;
}

interface Scores {
  quality_score: number;
  relevance_score: number;
  overall_score: number;
}

interface Evidence {
  stars: number;
  forks: number;
  days_since_update: number | null;
  has_license: boolean;
  license_name: string | null;
  readme_verified: boolean;
  is_fork: boolean;
  is_archived: boolean;
  is_template: boolean;
  open_issues: number;
  topic_matches: string[];
  matched_terms: string[];
  noise_flags: string[];
}

interface Repo {
  id: string;
  platform: Platform;
  full_name: string;
  owner: string;
  description: string;
  url: string;
  language: string | null;
  created_at: string | null;
  updated_at: string | null;
  scores: Scores;
  verdict: Verdict;
  ai_insight: string;
  risks: string[];
  signals: Signal[];
  evidence: Evidence;
}

interface ScoutResponse {
  query: string;
  total: number;
  repos: Repo[];
  tldr: string;
}

const VERDICT_MAP: Record<Verdict, { label: string; color: string }> = {
  HIGHLY_RECOMMENDED: { label: "Top pick", color: "#35c58b" },
  RECOMMENDED: { label: "Recommended", color: "#35c58b" },
  WORTH_CHECKING: { label: "Worth checking", color: "#ffcb6b" },
  AVOID: { label: "Avoid", color: "#ff8d8d" },
};

const SAMPLE_QUERIES = [
  "nextjs starter auth",
  "rag pipeline langchain",
  "fastapi saas starter",
  "aws cdk infrastructure",
] as const;

const WORKFLOW_POINTS = [
  "Search GitHub and GitLab together",
  "Rank by quality and semantic relevance",
  "Suppress forks, mirrors, and low-signal noise",
  "Send the winner into Atlas with one click",
] as const;
const EMPTY_STATE_HINTS = [
  "Try broader technology terms instead of project names.",
  "Enable both GitHub and GitLab when the search space is thin.",
  "If you already know the repo, skip Scout and go straight to Atlas.",
] as const;

function fmtNum(n: number) {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

function scoreColor(value: number) {
  if (value >= 75) return "#35c58b";
  if (value >= 45) return "#ffcb6b";
  return "#ff8d8d";
}

function platformLabel(platform: Platform) {
  return platform === "github" ? "GitHub" : "GitLab";
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const color = scoreColor(value);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#7184a7]">
          {label}
        </span>
        <span className="font-mono text-[11px]" style={{ color }}>
          {value}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${value}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function EvidencePanel({ evidence }: { evidence: Evidence }) {
  const rows = [
    { label: "Stars", value: fmtNum(evidence.stars) },
    { label: "Forks", value: fmtNum(evidence.forks) },
    { label: "Updated", value: evidence.days_since_update != null ? `${evidence.days_since_update}d ago` : "unknown" },
    { label: "License", value: evidence.license_name ?? "none" },
    { label: "README", value: evidence.readme_verified ? "verified" : "unverified" },
    { label: "Issues", value: String(evidence.open_issues) },
  ] as const;

  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <div className="grid gap-2 sm:grid-cols-2">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-3">
            <span className="text-sm text-[#7f95ba]">{row.label}</span>
            <span className="font-mono text-[11px] text-[#deebff]">{row.value}</span>
          </div>
        ))}
      </div>
      {evidence.topic_matches.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {evidence.topic_matches.map((topic) => (
            <span
              key={topic}
              className="rounded-full border border-[#35c58b]/25 bg-[#35c58b]/10 px-2.5 py-1 font-mono text-[10px] text-[#8fe0b8]"
            >
              {topic}
            </span>
          ))}
        </div>
      )}
      {evidence.noise_flags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {evidence.noise_flags.map((flag) => (
            <span
              key={flag}
              className="rounded-full border border-[#ffcb6b]/25 bg-[#ffcb6b]/10 px-2.5 py-1 font-mono text-[10px] text-[#ffd98f]"
            >
              {flag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function RepoCard({ repo, rank }: { repo: Repo; rank: number }) {
  const router = useRouter();
  const { setActiveRepo } = useRepoWorkspace();
  const [showEvidence, setShowEvidence] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeErr, setAnalyzeErr] = useState("");
  const verdict = VERDICT_MAP[repo.verdict];

  async function handleAtlas() {
    setAnalyzeErr("");
    setAnalyzing(true);
    setActiveRepo({
      repo: repo.full_name,
      url: repo.url,
      provider: repo.platform,
    });

    try {
      const { job_id } = await submitAnalysis(repo.url);
      router.push(`/analyze?job_id=${job_id}`);
    } catch (error) {
      setAnalyzeErr(error instanceof Error ? error.message : "Failed to submit to Atlas.");
      setAnalyzing(false);
    }
  }

  return (
    <article className="panel rounded-[28px] p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3 sm:gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03] font-mono text-[11px] text-[#dce8ff]">
            #{rank}
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <a
                href={repo.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-lg font-semibold text-[#f5f8ff] hover:text-white"
              >
                {repo.full_name}
              </a>
              <span className="rounded-full border border-white/10 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.16em] text-[#7f95ba]">
                {platformLabel(repo.platform)}
              </span>
              <span
                className="rounded-full border px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.16em]"
                style={{ color: verdict.color, borderColor: `${verdict.color}40`, backgroundColor: `${verdict.color}12` }}
              >
                {verdict.label}
              </span>
            </div>
            <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.18em] text-[#6d7f9f]">
              {repo.owner} · {repo.language ?? "Unknown language"} · {repo.created_at ? new Date(repo.created_at).getFullYear() : "No year"}
            </p>
            {repo.description && (
              <p className="mt-3 text-sm leading-relaxed text-[#96aad0]">{repo.description}</p>
            )}
          </div>
        </div>

        <div className="self-start rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-center">
          <p className="text-3xl font-semibold leading-none" style={{ color: scoreColor(repo.scores.overall_score) }}>
            {repo.scores.overall_score}
          </p>
          <p className="mt-1 font-mono text-[9px] uppercase tracking-[0.2em] text-[#62779d]">overall</p>
        </div>
      </div>

      {repo.ai_insight && (
        <div className="mt-4 rounded-2xl border border-[#4d7cff]/20 bg-[#4d7cff]/10 p-4 text-sm leading-relaxed text-[#d7e4ff]">
          {repo.ai_insight}
        </div>
      )}

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <ScoreBar label="quality" value={repo.scores.quality_score} />
        <ScoreBar label="relevance" value={repo.scores.relevance_score} />
      </div>

      {repo.risks.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {repo.risks.map((risk) => (
            <span
              key={risk}
              className="rounded-full border border-[#ffcb6b]/25 bg-[#ffcb6b]/10 px-2.5 py-1 font-mono text-[10px] text-[#ffd98f]"
            >
              {risk}
            </span>
          ))}
        </div>
      )}

      {repo.signals.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {repo.signals.map((signal) => {
            const color =
              signal.type === "good" ? "#35c58b" : signal.type === "warn" ? "#ffcb6b" : "#ff8d8d";
            return (
              <span
                key={`${signal.label}-${signal.type}`}
                className="rounded-full border px-2.5 py-1 font-mono text-[10px]"
                style={{ color, borderColor: `${color}30`, backgroundColor: `${color}10` }}
              >
                {signal.verified ? signal.label : `~ ${signal.label}`}
              </span>
            );
          })}
        </div>
      )}

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-white/10 pt-5">
        <button
          onClick={() => setShowEvidence((value) => !value)}
          className="font-mono text-[11px] uppercase tracking-[0.16em] text-[#9ab0d4] hover:text-white"
        >
          {showEvidence ? "Hide evidence" : "Show evidence"}
        </button>
        <div className="flex flex-wrap items-center gap-3">
          <a
            href={repo.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-[11px] uppercase tracking-[0.16em] text-[#9ab0d4] hover:text-white"
          >
            Open repo ↗
          </a>
          <button
            onClick={handleAtlas}
            disabled={analyzing}
            className="rounded-full bg-[#4d7cff] px-4 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-white shadow-[0_12px_28px_rgba(77,124,255,0.25)] hover:bg-[#6794ff] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {analyzing ? "Opening…" : "Send to Atlas"}
          </button>
        </div>
      </div>

      {analyzeErr && <p className="mt-3 font-mono text-[11px] text-[#ff8d8d]">{analyzeErr}</p>}
      {showEvidence && <EvidencePanel evidence={repo.evidence} />}
    </article>
  );
}

export default function ScoutPage() {
  const [query, setQuery] = useState("");
  const [token, setToken] = useState("");
  const [github, setGithub] = useState(true);
  const [gitlab, setGitlab] = useState(true);
  const [sortBy, setSortBy] = useState<SortBy>("stars");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [result, setResult] = useState<ScoutResponse | null>(null);
  const [error, setError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);

  const handleScan = useCallback(async () => {
    if (!query.trim() || (!github && !gitlab)) return;
    setLoading(true);
    setResult(null);
    setError("");
    setStatus("Searching repositories and scoring results…");

    const platforms: Platform[] = [
      ...(github ? ["github" as const] : []),
      ...(gitlab ? ["gitlab" as const] : []),
    ];

    try {
      const res = await fetch("/api/scout/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          platforms,
          sort_by: sortBy,
          ...(token ? { github_token: token } : {}),
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Error ${res.status}`);
      }

      const data: ScoutResponse = await res.json();
      setResult(data);
      setHasSearched(true);
      setStatus(`${data.total} repositories ranked`);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unexpected search failure.");
      setStatus("");
    } finally {
      setLoading(false);
    }
  }, [github, gitlab, query, sortBy, token]);

  return (
    <div className="page-shell">
      <section className="page-hero">
        <div className="hero-grid">
          <div>
            <div className="mb-5 flex flex-wrap items-center gap-3">
              <span className="rounded-full border border-[#35c58b]/25 bg-[#35c58b]/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.24em] text-[#8fe0b8]">
                Tool 01
              </span>
              <span className="hero-kicker">
                Cross-repo discovery workspace
              </span>
            </div>

            <h1 className="hero-title">
              Search first.
              <br />
              Pick the right repo before you go deep.
            </h1>

            <p className="hero-copy mt-6">
              RepoScout is the front door for the product now. Search GitHub and GitLab,
              rank candidates by quality and relevance, then move the winner directly into
              Atlas for architecture analysis.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              {WORKFLOW_POINTS.map((point) => (
                <div key={point} className="surface-note">
                  <p className="surface-note-copy mt-0">{point}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="panel-strong rounded-[28px] p-6">
            <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#8fe0b8]">
                  RepoScout Query
                </p>
                <p className="mt-2 max-w-md text-sm leading-relaxed text-[#8ea3c7]">
                  Search both platforms, tune ranking, and pass the best result into Atlas.
                </p>
              </div>
              <Link
                href="/#analyze"
                className="font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:text-white"
              >
                Jump to Atlas
              </Link>
            </div>

            <div className="mt-5 flex flex-col gap-3 sm:flex-row">
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && !loading && void handleScan()}
                placeholder="e.g. nextjs auth starter or rag pipeline langchain"
                className="min-w-0 flex-1 rounded-2xl border border-white/10 bg-[#07101d] px-4 py-3.5 font-mono text-[13px] text-[#f5f8ff] placeholder-[#7082a5] focus:border-[#35c58b]/40 focus:outline-none"
              />
              <button
                onClick={() => void handleScan()}
                disabled={loading || !query.trim() || (!github && !gitlab)}
                className="rounded-2xl bg-[#35c58b] px-6 py-3.5 font-mono text-[12px] uppercase tracking-[0.18em] text-[#07131b] hover:bg-[#4bd495] disabled:cursor-not-allowed disabled:opacity-40 sm:min-w-[10rem]"
              >
                {loading ? "Searching…" : "Run Scout"}
              </button>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              {([
                { key: "github", label: "GitHub", value: github, toggle: setGithub },
                { key: "gitlab", label: "GitLab", value: gitlab, toggle: setGitlab },
              ] as const).map((item) => (
                <button
                  key={item.key}
                  onClick={() => item.toggle(!item.value)}
                  className={`rounded-full border px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.18em] ${
                    item.value
                      ? "border-[#35c58b]/35 bg-[#35c58b]/10 text-[#a2ebc6]"
                      : "border-white/10 bg-white/[0.02] text-[#8ea3c7]"
                  }`}
                >
                  {item.label}
                </button>
              ))}

              <select
                value={sortBy}
                onChange={(event) => setSortBy(event.target.value as SortBy)}
                className="w-full rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-[#dce8ff] outline-none sm:ml-auto sm:w-auto"
              >
                <option value="stars">Sort by stars</option>
                <option value="updated">Sort by updated</option>
                <option value="best-match">Sort by best match</option>
              </select>
            </div>

            <div className="mt-4">
              <input
                type="password"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                autoComplete="off"
                placeholder="Optional GitHub token to raise rate limits for public repo search"
                className="w-full rounded-2xl border border-white/10 bg-[#07101d] px-4 py-3 font-mono text-[12px] text-[#f5f8ff] placeholder-[#7082a5] focus:border-[#35c58b]/40 focus:outline-none"
              />
              <p className="mt-2 font-mono text-[10px] text-[#62779d]">
                Token is used for the current request only and is not stored.
              </p>
            </div>

            <div className="mt-5 flex flex-wrap gap-2">
              {SAMPLE_QUERIES.map((sample) => (
                <button
                  key={sample}
                  onClick={() => setQuery(sample)}
                  className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-[10px] text-[#b7c8e8] hover:text-white"
                >
                  {sample}
                </button>
              ))}
            </div>

            {(status || error) && (
              <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                {status && <p className="font-mono text-[11px] text-[#b7c8e8]">{status}</p>}
                {error && <p className="mt-1 font-mono text-[11px] text-[#ff8d8d]">{error}</p>}
              </div>
            )}
          </div>
        </div>
      </section>

      {result?.tldr && (
        <section className="pb-6">
          <div className="panel-strong rounded-[28px] p-6">
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#8fe0b8]">TLDR</p>
            <p className="mt-3 max-w-4xl text-[15px] leading-relaxed text-[#d8e5fb]">{result.tldr}</p>
          </div>
        </section>
      )}

      {result && result.repos.length > 0 && (
        <section className="pb-20">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">
                Ranked Results
              </p>
              <h2 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-[#f5f8ff]">
                {result.total} repositories for “{result.query}”
              </h2>
            </div>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#6d7f9f]">
              Overall score blends quality + relevance
            </p>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            {result.repos.map((repo, index) => (
              <RepoCard key={repo.id} repo={repo} rank={index + 1} />
            ))}
          </div>
        </section>
      )}

      {!loading && hasSearched && result && result.repos.length === 0 && !error && (
        <section className="pb-20">
          <div className="panel rounded-[28px] p-8 text-center">
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">No results</p>
            <h2 className="mt-3 text-2xl font-semibold text-[#f5f8ff]">Scout didn’t find strong matches yet.</h2>
            <p className="mt-3 text-sm leading-relaxed text-[#94a8cb]">
              Try broader search terms, enable both platforms, or search by technology rather than project name.
            </p>
            <div className="mt-6 grid gap-3 md:grid-cols-3 text-left">
              {EMPTY_STATE_HINTS.map((hint) => (
                <div key={hint} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="text-sm leading-relaxed text-[#dce8ff]">{hint}</p>
                </div>
              ))}
            </div>
            <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
              <Link
                href="/"
                className="rounded-full border border-white/10 px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:text-white"
              >
                Open Atlas
              </Link>
            </div>
          </div>
        </section>
      )}

      {!loading && !hasSearched && !error && (
        <section className="pb-20">
          <div className="panel rounded-[28px] p-8 text-center">
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">Ready</p>
            <h2 className="mt-3 text-2xl font-semibold text-[#f5f8ff]">Run a query to start the workflow.</h2>
            <p className="mt-3 text-sm leading-relaxed text-[#94a8cb]">
              RepoScout is most useful when you need to narrow a field before deeper architecture analysis.
            </p>
            <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
              <button
                type="button"
                onClick={() => setQuery(SAMPLE_QUERIES[0])}
                className="rounded-full bg-[#35c58b] px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.16em] text-[#07131b]"
              >
                Try a sample query
              </button>
              <Link
                href="/"
                className="rounded-full border border-white/10 px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:text-white"
              >
                Go to Atlas
              </Link>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
