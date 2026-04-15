"use client";

import { useEffect, useState } from "react";

import { getOpsSnapshot } from "@/lib/api";
import type { OpsSnapshotResponse, QueueMetrics } from "@/lib/types";

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

export default function OpsSnapshot() {
  const [snapshot, setSnapshot] = useState<OpsSnapshotResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
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

  if (error || !snapshot) {
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
