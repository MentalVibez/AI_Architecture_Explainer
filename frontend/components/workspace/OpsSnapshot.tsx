"use client";

import { useEffect, useState } from "react";

import { getOpsSnapshot } from "@/lib/api";
import type { LLMUsageStats, OpsSnapshotResponse, QueueMetrics } from "@/lib/types";

const STATUS_LABELS = {
  steady: "Steady",
  active: "Active",
  watch: "Needs attention",
} as const;

const STATUS_COLORS = {
  steady: "#35c58b",
  active: "#7ec8ff",
  watch: "#ffcb6b",
} as const;

const SHOW_OPS_SNAPSHOT = process.env.NEXT_PUBLIC_SHOW_OPS_SNAPSHOT === "true";

export default function OpsSnapshot() {
  const [snapshot, setSnapshot] = useState<OpsSnapshotResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!SHOW_OPS_SNAPSHOT) {
      return;
    }

    let cancelled = false;

    async function load() {
      try {
        const response = await getOpsSnapshot();
        if (!cancelled) {
          setSnapshot(response);
        }
      } catch {
        if (!cancelled) {
          setError(true);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  if (!SHOW_OPS_SNAPSHOT || error || !snapshot) {
    return null;
  }

  const statusColor = STATUS_COLORS[snapshot.status];

  return (
    <div className="panel rounded-[28px] p-5 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">
            Live system snapshot
          </p>
          <h3 className="mt-2 text-xl font-semibold text-[#f5f8ff]">
            Queue health without opening the logs.
          </h3>
        </div>
        <span
          className="rounded-full border px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em]"
          style={{ color: statusColor, borderColor: `${statusColor}40`, backgroundColor: `${statusColor}12` }}
        >
          {STATUS_LABELS[snapshot.status]}
        </span>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <OpsCard label="Atlas" metrics={snapshot.atlas} accent="#4d7cff" />
        <OpsCard label="Review" metrics={snapshot.review} accent="#c5b3ff" />
      </div>

      {snapshot.attention_message && (
        <div className="mt-5 rounded-2xl border border-[#ffcb6b]/30 bg-[#ffcb6b]/8 px-4 py-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#ffcb6b]">
            Worker attention
          </p>
          <p className="mt-2 text-sm leading-relaxed text-[#ffe7b0]">
            {snapshot.attention_message}
          </p>
        </div>
      )}

      {snapshot.llm_usage && snapshot.llm_usage.total_calls > 0 && (
        <LLMUsagePanel usage={snapshot.llm_usage} />
      )}

      {snapshot.recent_failures.length > 0 && (
        <div className="mt-5 border-t border-white/10 pt-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#ffd98f]">
            Recent failures
          </p>
          <div className="mt-3 space-y-3">
            {snapshot.recent_failures.map((failure, index) => (
              <div key={`${failure.kind}-${failure.repo}-${index}`} className="surface-note">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.16em] text-[#b7c8e8]">
                    {failure.kind}
                  </span>
                  <p className="text-sm font-semibold text-[#edf4ff]">{failure.repo}</p>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-[#94a8cb]">
                  {failure.error_message ?? "Job failed without a detailed error message."}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function OpsCard({
  label,
  metrics,
  accent,
}: {
  label: string;
  metrics: QueueMetrics;
  accent: string;
}) {
  return (
    <div className="surface-note">
      <p className="font-mono text-[10px] uppercase tracking-[0.18em]" style={{ color: accent }}>
        {label}
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <Metric label="Queued" value={String(metrics.queued)} />
        <Metric label="Running" value={String(metrics.running)} />
        <Metric label="Completed 24h" value={String(metrics.completed_last_24h)} />
        <Metric label="Failed 24h" value={String(metrics.failed_last_24h)} />
      </div>
      <p className="mt-4 text-sm leading-relaxed text-[#94a8cb]">
        {metrics.average_duration_seconds != null
          ? `Average completion time: ${metrics.average_duration_seconds}s over the last 24 hours.`
          : "No recent completed runs yet in the last 24 hours."}
      </p>
      {(metrics.oldest_queued_seconds != null || metrics.oldest_running_seconds != null) && (
        <p className="mt-2 text-sm leading-relaxed text-[#7f94b8]">
          {metrics.oldest_queued_seconds != null
            ? `Oldest queued job: ${metrics.oldest_queued_seconds}s. `
            : ""}
          {metrics.oldest_running_seconds != null
            ? `Longest running job: ${metrics.oldest_running_seconds}s.`
            : ""}
        </p>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[#6d7f9f]">{label}</p>
      <p className="mt-1 text-lg font-semibold text-[#edf4ff]">{value}</p>
    </div>
  );
}

function LLMUsagePanel({ usage }: { usage: LLMUsageStats }) {
  const totalTokens = usage.total_input_tokens + usage.total_output_tokens;

  return (
    <div className="mt-5 border-t border-white/10 pt-5">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#c5b3ff]">
          LLM Usage · last {usage.window_hours}h
        </p>
        <span className="font-mono text-[10px] text-[#6d7f9f]">
          ~${usage.estimated_cost_usd.toFixed(4)} estimated
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-4 mb-4">
        <Metric label="Total calls" value={String(usage.total_calls)} />
        <Metric label="Total tokens" value={fmtTokens(totalTokens)} />
        <Metric label="Input tokens" value={fmtTokens(usage.total_input_tokens)} />
        <Metric label="Output tokens" value={fmtTokens(usage.total_output_tokens)} />
      </div>

      {usage.by_stage.length > 0 && (
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[#6d7f9f] mb-3">
            By stage
          </p>
          <div className="space-y-2">
            {usage.by_stage.slice(0, 6).map((s) => {
              const stagePct = totalTokens > 0
                ? Math.round(((s.input_tokens + s.output_tokens) / totalTokens) * 100)
                : 0;
              return (
                <div key={s.stage} className="flex items-center gap-3">
                  <span className="font-mono text-[10px] text-[#8a9bbf] w-36 shrink-0 truncate">
                    {s.stage}
                  </span>
                  <div className="flex-1 h-1.5 bg-[#1a1a2e] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#c5b3ff] rounded-full"
                      style={{ width: `${stagePct}%` }}
                    />
                  </div>
                  <span className="font-mono text-[10px] text-[#6d7f9f] w-12 text-right shrink-0">
                    {fmtTokens(s.input_tokens + s.output_tokens)}
                  </span>
                  <span className="font-mono text-[10px] text-[#4a5568] w-10 text-right shrink-0">
                    {s.calls}×
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}
