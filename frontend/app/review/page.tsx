"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { getReviewResult, getReviewStatus, submitReview } from "@/lib/api";
import type { ReviewFinding, ReviewResult, ReviewStatusResponse } from "@/lib/types";
import { useRepoWorkspace } from "@/components/workspace/RepoWorkspaceProvider";
import { normalizeRepoWorkspace } from "@/lib/repo-workspace";
import RecentRuns from "@/components/workspace/RecentRuns";

type JobStatus = "idle" | "queued" | "running" | "completed" | "failed";

const POLL_INTERVAL_MS = 5000;
const MAX_POLLS = 120;

const SEVERITY_COLOR: Record<string, string> = {
  critical: "#ff7f96",
  high: "#ffb067",
  medium: "#ffd98f",
  low: "#8ea3c7",
  info: "#6d7f9f",
};
const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"] as const;
const SEVERITY_LABEL: Record<string, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
};

const REVIEW_POINTS = [
  "Evidence-backed scoring across security, testing, reliability, and maintainability",
  "Deterministic rules and adapters first, not purely model-generated opinions",
  "Confidence and depth labels surfaced directly in the report",
  "Human-readable findings that point to actual remediation work",
] as const;

const REVIEW_PHASE_STEPS = [
  {
    key: "queue",
    title: "Queue the review",
    detail: "Reserve the job and prepare the repo for the deeper scan.",
  },
  {
    key: "analysis",
    title: "Run the scan",
    detail: "Gather evidence, score the repo, and assemble findings.",
  },
  {
    key: "complete",
    title: "Publish the report",
    detail: "Return the scorecard and action-oriented findings view.",
  },
] as const;

function scoreColor(value: number) {
  if (value >= 70) return "#35c58b";
  if (value >= 50) return "#ffcb6b";
  return "#ff8d8d";
}

function phaseLabel(phase: ReviewStatusResponse["phase"] | undefined) {
  if (phase === "queue") return "In queue";
  if (phase === "analysis") return "Running scan";
  if (phase === "complete") return "Report ready";
  if (phase === "failed") return "Failed";
  return "Tracking";
}

function reviewPhaseIndex(phase: ReviewStatusResponse["phase"] | undefined) {
  if (phase === "complete") return 2;
  if (phase === "analysis") return 1;
  return 0;
}

export default function ReviewPage() {
  const searchParams = useSearchParams();
  const { activeRepo, setActiveRepo, addRecentRun } = useRepoWorkspace();
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [status, setStatus] = useState<JobStatus>("idle");
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [jobMeta, setJobMeta] = useState<ReviewStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const activeJobId = useRef<string | null>(null);
  const pollTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (pollTimeout.current) clearTimeout(pollTimeout.current);
    };
  }, []);

  useEffect(() => {
    const repo = searchParams.get("repo");
    if (repo && !url) {
      setUrl(`https://github.com/${repo}`);
      return;
    }

    if (!url && activeRepo?.url) {
      setUrl(activeRepo.url);
    }
  }, [activeRepo, searchParams, url]);

  useEffect(() => {
    const resultId = searchParams.get("result_id");
    if (!resultId || result) {
      return;
    }

    let cancelled = false;

    async function loadResult() {
      try {
        const data = await getReviewResult(resultId);
        if (cancelled) {
          return;
        }

        setResult(data);
        setStatus("completed");
        setError(null);
      } catch (err) {
        if (cancelled) {
          return;
        }

        setError(err instanceof Error ? err.message : "Failed to load review result.");
      }
    }

    void loadResult();

    return () => {
      cancelled = true;
    };
  }, [result, searchParams]);

  useEffect(() => {
    if (!result) {
      return;
    }

    const normalized = normalizeRepoWorkspace({ url: result.repo_url, provider: "github" });
    if (!normalized) {
      return;
    }

    addRecentRun({
      id: result.result_id,
      kind: "review",
      repo: normalized.repo,
      href: `/review?result_id=${encodeURIComponent(result.result_id)}&repo=${encodeURIComponent(normalized.repo)}`,
      title: result.verdict_label
        ? `${result.verdict_label} review result`
        : "Review result",
      completedAt: result.completed_at ?? result.created_at,
    });
  }, [addRecentRun, result]);

  async function pollStatus(jobId: string, polls = 0) {
    if (polls >= MAX_POLLS) {
      setError("Review timed out waiting for result.");
      setStatus("failed");
      activeJobId.current = null;
      return;
    }

    try {
      const data = await getReviewStatus(jobId);
      if (activeJobId.current !== jobId) return;

      setJobMeta(data);
      setStatus(data.status);

      if (data.status === "completed" && data.result_id) {
        setResult(await getReviewResult(data.result_id));
        activeJobId.current = null;
        return;
      }

      if (data.status === "failed") {
        setError(data.error_message ?? data.status_detail ?? "Review failed.");
        activeJobId.current = null;
        return;
      }
    } catch {
      if (activeJobId.current !== jobId) return;
    }

    pollTimeout.current = setTimeout(() => {
      void pollStatus(jobId, polls + 1);
    }, POLL_INTERVAL_MS);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (pollTimeout.current) clearTimeout(pollTimeout.current);
    activeJobId.current = null;
    setError(null);
    setResult(null);
    setJobMeta(null);
    setStatus("queued");
    const normalized = normalizeRepoWorkspace({ url });
    if (normalized) {
      setActiveRepo(normalized);
    }

    try {
      const data = await submitReview(url, branch || undefined);
      activeJobId.current = data.job_id;
      void pollStatus(data.job_id);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to submit review.";
      setError(message.includes("429") ? "Rate limited. Please try again later." : message);
      setStatus("idle");
    }
  }

  return (
    <div className="page-shell">
      <section className="page-hero">
        <div className="hero-grid">
          <div>
            <div className="mb-5 flex flex-wrap items-center gap-3">
              <span className="rounded-full border border-[#c5b3ff]/25 bg-[#c5b3ff]/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.24em] text-[#d8cbff]">
                Tool 04
              </span>
              <span className="rounded-full border border-white/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-[#6d7f9f]">
                Public repos
              </span>
            </div>

            <h1 className="hero-title">
              Review engineering risk
              <br />
              with evidence instead of vibes.
            </h1>

            <p className="hero-copy mt-6">
              Review is the risk lens of the product. It runs a deeper pass over a public repository,
              scores operational quality, and returns confidence-aware findings you can act on.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              {REVIEW_POINTS.map((point) => (
                <div key={point} className="surface-note">
                  <p className="surface-note-copy mt-0">{point}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="panel-strong rounded-[28px] p-6">
            <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#d8cbff]">
                  Review a repository
                </p>
                <p className="mt-2 max-w-md text-sm leading-relaxed text-[#8ea3c7]">
                  Submit a public GitHub repository and wait for the scorecard plus findings.
                </p>
              </div>
              <Link href="/" className="font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:text-white">
                Open Atlas
              </Link>
            </div>

            <form onSubmit={handleSubmit} className="mt-5 space-y-3">
              <input
                type="text"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://github.com/owner/repo"
                required
                className="w-full rounded-2xl border border-white/10 bg-[#07101d] px-4 py-3.5 font-mono text-[13px] text-[#f5f8ff] placeholder-[#7082a5] focus:border-[#c5b3ff]/40 focus:outline-none"
              />
              <div className="flex flex-col gap-3 sm:flex-row">
                <input
                  type="text"
                  value={branch}
                  onChange={(event) => setBranch(event.target.value)}
                  placeholder="Optional branch name"
                  className="min-w-0 flex-1 rounded-2xl border border-white/10 bg-[#07101d] px-4 py-3.5 font-mono text-[13px] text-[#f5f8ff] placeholder-[#7082a5] focus:border-[#c5b3ff]/40 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={status === "queued" || status === "running"}
                  className="rounded-2xl bg-[#c5b3ff] px-6 py-3.5 font-mono text-[12px] uppercase tracking-[0.18em] text-[#0a1220] hover:bg-[#d5c7ff] disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {status === "queued" || status === "running" ? "Reviewing…" : "Run Review"}
                </button>
              </div>
            </form>

            <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#6d7f9f]">Current constraints</p>
              <div className="mt-3 space-y-2 text-sm leading-relaxed text-[#94a8cb]">
                <p>Public GitHub repositories only.</p>
                <p>Confidence reflects the depth of evidence available, not just a raw score.</p>
                <p>Longer reviews are normal on larger repositories.</p>
              </div>
            </div>

            <RecentRuns />

            {status !== "idle" && (
              <div className="mt-5 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#6d7f9f]">Job status</p>
                <p className="mt-2 font-mono text-[11px] text-[#dce8ff]">
                  {jobMeta?.status_detail ??
                    (status === "queued"
                      ? "Queued and waiting to start."
                      : status === "running"
                      ? "Cloning and analyzing repository."
                      : status === "completed"
                      ? "Completed."
                      : "Failed.")}
                </p>
                {jobMeta && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <JobPill label={phaseLabel(jobMeta.phase)} />
                    {jobMeta.duration_seconds > 0 && (
                      <JobPill label={`${jobMeta.duration_seconds}s elapsed`} />
                    )}
                    {jobMeta.next_poll_seconds && (
                      <JobPill label={`poll ${jobMeta.next_poll_seconds}s`} />
                    )}
                    {jobMeta.retryable !== null && (
                      <JobPill label={jobMeta.retryable ? "retryable" : "inspect before retry"} />
                    )}
                  </div>
                )}
                {jobMeta?.suggested_action && (
                  <p className="mt-3 text-sm leading-relaxed text-[#94a8cb]">
                    {jobMeta.suggested_action}
                  </p>
                )}
              </div>
            )}

            {error && <p className="mt-4 font-mono text-[11px] text-[#ff8d8d]">{error}</p>}
          </div>
        </div>
      </section>

      {(status === "queued" || status === "running") && (
        <section className="pb-10">
          <div className="panel rounded-[28px] p-6">
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">Running review</p>
            <h2 className="mt-3 text-2xl font-semibold text-[#f5f8ff]">
              Building the scorecard and gathering findings.
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-[#94a8cb]">
              This usually takes 30 to 120 seconds depending on repository size and adapter coverage.
            </p>
            {jobMeta && <ReviewProgressPanel jobMeta={jobMeta} />}
          </div>
        </section>
      )}

      {result && <ReviewResultPanel result={result} />}
    </div>
  );
}

function ScoreBar({ label, value }: { label: string; value: number | null }) {
  const pct = value ?? 0;
  const color = scoreColor(pct);
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-[#6d7f9f]">
          {label.replace(/_/g, " ")}
        </span>
        <span className="font-mono text-[11px]" style={{ color }}>
          {value ?? "—"}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function ReviewResultPanel({ result }: { result: ReviewResult }) {
  const { setActiveRepo } = useRepoWorkspace();
  const overall = result.overall_score ?? 0;
  const overallColor = scoreColor(overall);
  const severityGroups = SEVERITY_ORDER.map((severity) => ({
    severity,
    findings: result.findings.filter((finding) => finding.severity === severity),
  })).filter((group) => group.findings.length > 0);
  const priorityActions = dedupeStrings(
    result.findings
      .filter((finding) => finding.severity === "critical" || finding.severity === "high")
      .map((finding) => finding.suggested_fix)
      .filter(Boolean),
  ).slice(0, 5);

  useEffect(() => {
    const normalized = normalizeRepoWorkspace({ url: result.repo_url, provider: "github" });
    if (normalized) {
      setActiveRepo(normalized);
    }
  }, [result.repo_url, setActiveRepo]);

  return (
    <section className="space-y-6 pb-20">
      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        <div className="panel-strong rounded-[28px] p-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#d8cbff]">Review result</p>
          <h2 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-[#f5f8ff] break-all">{result.repo_url}</h2>
          <div className="mt-6 flex flex-col items-start gap-3 sm:flex-row sm:items-end sm:gap-4">
            <p className="text-6xl font-semibold leading-none" style={{ color: overallColor }}>
              {result.overall_score ?? "—"}
            </p>
            <div className="pb-1">
              <p className="font-mono text-[12px] uppercase tracking-[0.18em] text-[#dce8ff]">
                {result.verdict_label ?? "Unknown verdict"}
              </p>
              <p className="mt-1 text-sm text-[#94a8cb]">
                {result.production_suitable ? "Production suitable" : "Not production suitable"}
              </p>
            </div>
          </div>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <Stat label="Confidence" value={result.confidence_label ?? "—"} />
            <Stat label="Depth" value={result.depth_level?.replace(/_/g, " ") ?? "—"} />
            <Stat label="Branch" value={result.branch || "main"} />
            <Stat label="Commit" value={result.commit ?? "latest"} />
            <Stat
              label="Duration"
              value={result.duration_seconds ? `${result.duration_seconds}s` : "—"}
            />
          </div>

          {result.anti_gaming_verdict && result.anti_gaming_verdict !== "likely_honest" && (
            <div className="mt-5 rounded-2xl border border-[#ffcb6b]/25 bg-[#ffcb6b]/10 p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#ffd98f]">Anti-gaming note</p>
              <p className="mt-2 text-sm leading-relaxed text-[#f3ddb0]">
                {result.anti_gaming_verdict.replace(/_/g, " ")}
              </p>
            </div>
          )}
        </div>

        <div className="panel rounded-[28px] p-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">Scorecard</p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {Object.entries(result.scores).map(([key, value]) => (
              <ScoreBar key={key} label={key} value={value} />
            ))}
          </div>
        </div>
      </div>

      {result.summary && (
        <div className="grid gap-4 md:grid-cols-2">
          <SummaryCard title="Technical summary" body={result.summary.developer} accent="#4d7cff" />
          <SummaryCard title="Manager summary" body={result.summary.manager} accent="#c5b3ff" />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="panel rounded-[24px] p-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#d8cbff]">
            Do first
          </p>
          {priorityActions.length > 0 ? (
            <div className="mt-4 space-y-3">
              {priorityActions.map((action, index) => (
                <div key={`${index}-${action}`} className="flex items-start gap-3">
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-[#c5b3ff]/25 bg-[#c5b3ff]/10 font-mono text-[10px] text-[#e1d7ff]">
                    {index + 1}
                  </span>
                  <p className="text-sm leading-relaxed text-[#d7e4ff]">{action}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-4 text-sm leading-relaxed text-[#94a8cb]">
              No critical or high-severity fixes were surfaced in this report.
            </p>
          )}
        </div>

        <div className="panel rounded-[24px] p-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#6d7f9f]">
            Severity overview
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {SEVERITY_ORDER.map((severity) => {
              const count = result.findings.filter((finding) => finding.severity === severity).length;
              const color = SEVERITY_COLOR[severity];
              return (
                <div key={severity} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em]" style={{ color }}>
                    {SEVERITY_LABEL[severity]}
                  </p>
                  <p className="mt-2 text-2xl font-semibold text-[#f5f8ff]">{count}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {result.findings && result.findings.length > 0 && (
        <div>
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">Findings</p>
              <h3 className="mt-2 text-2xl font-semibold text-[#f5f8ff]">
                {result.findings.length} evidence-backed issues and recommendations
              </h3>
            </div>
          </div>
          <div className="space-y-5">
            {severityGroups.map((group) => (
              <SeverityGroup
                key={group.severity}
                severity={group.severity}
                findings={group.findings}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function SummaryCard({
  title,
  body,
  accent,
}: {
  title: string;
  body: string;
  accent: string;
}) {
  return (
    <div className="panel rounded-[24px] p-5">
      <p className="font-mono text-[10px] uppercase tracking-[0.2em]" style={{ color: accent }}>
        {title}
      </p>
      <p className="mt-3 text-sm leading-relaxed text-[#d7e4ff]">{body}</p>
    </div>
  );
}

function FindingCard({ finding }: { finding: ReviewFinding }) {
  const [open, setOpen] = useState(false);
  const color = SEVERITY_COLOR[finding.severity] ?? "#8ea3c7";

  return (
    <div className="panel rounded-[24px] p-5">
      <button onClick={() => setOpen((value) => !value)} className="flex w-full items-start gap-3 text-left">
        <span
          className="rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.16em]"
          style={{ color, borderColor: `${color}40`, backgroundColor: `${color}12` }}
        >
          {finding.severity}
        </span>
        <div className="min-w-0 flex-1">
          <h4 className="text-lg font-semibold text-[#f5f8ff]">{finding.title}</h4>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.18em] text-[#6d7f9f]">
            {finding.category} · {finding.rule_id}
          </p>
        </div>
        <span className="font-mono text-[11px] text-[#c2d3f2]">{open ? "Collapse" : "Expand"}</span>
      </button>

      {open && (
        <div className="mt-4 border-t border-white/10 pt-4">
          <p className="text-sm leading-relaxed text-[#d7e4ff]">{finding.summary}</p>
          {finding.why_it_matters && (
            <p className="mt-3 text-sm leading-relaxed text-[#94a8cb]">
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-[#6d7f9f]">Why it matters</span>
              <br />
              {finding.why_it_matters}
            </p>
          )}
          {finding.suggested_fix && (
            <p className="mt-3 text-sm leading-relaxed text-[#94a8cb]">
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-[#6d7f9f]">Suggested fix</span>
              <br />
              {finding.suggested_fix}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function SeverityGroup({
  severity,
  findings,
}: {
  severity: string;
  findings: ReviewFinding[];
}) {
  const color = SEVERITY_COLOR[severity] ?? "#8ea3c7";

  return (
    <section>
      <div className="mb-3 flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <span
            className="rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.16em]"
            style={{ color, borderColor: `${color}40`, backgroundColor: `${color}12` }}
          >
            {SEVERITY_LABEL[severity] ?? severity}
          </span>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[#6d7f9f]">
            {findings.length} findings
          </p>
        </div>
      </div>
      <div className="space-y-3">
        {findings.map((finding) => (
          <FindingCard key={finding.id} finding={finding} />
        ))}
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#6d7f9f]">{label}</p>
      <p className="mt-2 font-mono text-[12px] text-[#dce8ff]">{value}</p>
    </div>
  );
}

function JobPill({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 font-mono text-[10px] text-[#b7c8e8]">
      {label}
    </span>
  );
}

function ReviewProgressPanel({ jobMeta }: { jobMeta: ReviewStatusResponse }) {
  const activeStep = reviewPhaseIndex(jobMeta.phase);

  return (
    <div className="mt-5 space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {REVIEW_PHASE_STEPS.map((step, index) => {
          const isDone = index < activeStep;
          const isActive = index === activeStep;

          return (
            <div
              key={step.key}
              className="rounded-[22px] border p-4"
              style={{
                borderColor: isDone || isActive ? "rgba(197,179,255,0.3)" : "rgba(255,255,255,0.1)",
                background: isDone || isActive ? "rgba(197,179,255,0.08)" : "rgba(255,255,255,0.03)",
              }}
            >
              <div className="flex items-center gap-3">
                <span
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border font-mono text-[10px]"
                  style={{
                    borderColor: isDone || isActive ? "rgba(197,179,255,0.34)" : "rgba(255,255,255,0.12)",
                    color: isDone ? "#0a1220" : "#efe7ff",
                    backgroundColor: isDone ? "#c5b3ff" : isActive ? "rgba(197,179,255,0.16)" : "transparent",
                  }}
                >
                  {isDone ? "✓" : index + 1}
                </span>
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#efe7ff]">
                  {step.title}
                </p>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-[#94a8cb]">{step.detail}</p>
            </div>
          );
        })}
      </div>

      <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-4">
        <div className="flex flex-wrap gap-2">
          <JobPill label={phaseLabel(jobMeta.phase)} />
          {jobMeta.duration_seconds > 0 && (
            <JobPill label={`${jobMeta.duration_seconds}s elapsed`} />
          )}
          {jobMeta.next_poll_seconds && (
            <JobPill label={`next poll ${jobMeta.next_poll_seconds}s`} />
          )}
        </div>
        <p className="mt-3 text-sm leading-relaxed text-[#d7e4ff]">{jobMeta.status_detail}</p>
        {jobMeta.suggested_action && (
          <p className="mt-2 text-sm leading-relaxed text-[#94a8cb]">{jobMeta.suggested_action}</p>
        )}
      </div>
    </div>
  );
}

function dedupeStrings(items: string[]): string[] {
  return [...new Set(items)];
}
