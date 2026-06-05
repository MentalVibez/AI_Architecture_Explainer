/**
 * Admin dashboard — server component only.
 * ADMIN_API_KEY is read at render time and never sent to the browser.
 */
import type { Metadata } from "next";
import type { OpsSnapshotResponse } from "@/lib/types";

export const metadata: Metadata = {
  title: "Admin — Atlas",
  robots: { index: false, follow: false },
};

// Revalidate every 30 seconds so the page stays fresh without full SSR on every hit
export const revalidate = 30;

async function fetchOpsSnapshot(): Promise<OpsSnapshotResponse | null> {
  const apiUrl =
    process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const adminKey = process.env.ADMIN_API_KEY ?? "";

  if (!adminKey) return null;

  try {
    const res = await fetch(`${apiUrl}/api/ops/summary`, {
      headers: { "x-atlas-admin-key": adminKey },
      next: { revalidate: 30 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    steady: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    active: "bg-blue-500/15 text-blue-300 border-blue-500/30",
    watch: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    ok: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    stale: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    missing: "bg-red-500/15 text-red-300 border-red-500/30",
  };
  const cls = styles[status] ?? "bg-white/10 text-white/60 border-white/10";
  return (
    <span className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest ${cls}`}>
      {status}
    </span>
  );
}

// ── Stat tile ─────────────────────────────────────────────────────────────────

function Tile({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#a9c2ff]">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-[#f5f8ff]">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-white/40">{sub}</p>}
    </div>
  );
}

// ── Queue section ─────────────────────────────────────────────────────────────

function QueueSection({ label, q }: { label: string; q: OpsSnapshotResponse["atlas"] }) {
  return (
    <div>
      <p className="mb-3 font-mono text-[10px] uppercase tracking-widest text-[#a9c2ff]">{label}</p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Queued" value={q.queued} />
        <Tile label="Running" value={q.running} />
        <Tile label="Done 24h" value={q.completed_last_24h} />
        <Tile label="Failed 24h" value={q.failed_last_24h} />
      </div>
      {q.average_duration_seconds != null && (
        <p className="mt-2 text-xs text-white/40">
          Avg duration: {q.average_duration_seconds.toFixed(1)}s
          {q.oldest_queued_seconds != null &&
            ` · Oldest queued: ${q.oldest_queued_seconds}s`}
        </p>
      )}
    </div>
  );
}

// ── LLM usage ─────────────────────────────────────────────────────────────────

function LLMSection({ llm }: { llm: OpsSnapshotResponse["llm_usage"] }) {
  if (!llm) return null;
  return (
    <div>
      <p className="mb-3 font-mono text-[10px] uppercase tracking-widest text-[#a9c2ff]">
        LLM usage (last {llm.window_hours}h)
      </p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="API calls" value={llm.total_calls} />
        <Tile label="Input tokens" value={llm.total_input_tokens.toLocaleString()} />
        <Tile label="Output tokens" value={llm.total_output_tokens.toLocaleString()} />
        <Tile
          label="Est. cost"
          value={`$${llm.estimated_cost_usd.toFixed(4)}`}
          sub="Claude Sonnet pricing"
        />
      </div>
      {llm.by_stage.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-xl border border-white/8">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-white/8 text-[#a9c2ff]">
                {["Stage", "Calls", "Input", "Output", "Avg ms"].map((h) => (
                  <th key={h} className="px-3 py-2 font-mono font-normal tracking-wide">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {llm.by_stage.map((s) => (
                <tr key={s.stage} className="border-b border-white/5 text-white/70 last:border-0">
                  <td className="px-3 py-2 font-mono text-[11px]">{s.stage}</td>
                  <td className="px-3 py-2">{s.calls}</td>
                  <td className="px-3 py-2">{s.input_tokens.toLocaleString()}</td>
                  <td className="px-3 py-2">{s.output_tokens.toLocaleString()}</td>
                  <td className="px-3 py-2">{s.avg_duration_ms.toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Workers ───────────────────────────────────────────────────────────────────

function WorkerSection({ workers }: { workers: OpsSnapshotResponse["workers"] }) {
  return (
    <div>
      <div className="mb-3 flex items-center gap-3">
        <p className="font-mono text-[10px] uppercase tracking-widest text-[#a9c2ff]">Workers</p>
        <StatusBadge status={workers.status} />
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Tile label="Fresh" value={workers.fresh_count} />
        <Tile label="Stale" value={workers.stale_count} />
        <Tile label="Queues" value={workers.active_queues.join(", ") || "—"} />
      </div>
      {workers.workers.length > 0 && (
        <div className="mt-4 space-y-2">
          {workers.workers.map((w) => (
            <div
              key={w.worker_id}
              className="flex items-center justify-between rounded-xl border border-white/8 bg-white/[0.02] px-4 py-2.5 text-xs"
            >
              <span className="font-mono text-white/70">{w.hostname} · pid {w.process_id}</span>
              <span className="text-white/40">{w.age_seconds}s ago</span>
              <StatusBadge status={w.fresh ? "ok" : "stale"} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Recent failures ───────────────────────────────────────────────────────────

function FailuresSection({ failures }: { failures: OpsSnapshotResponse["recent_failures"] }) {
  if (!failures.length) return null;
  return (
    <div>
      <p className="mb-3 font-mono text-[10px] uppercase tracking-widest text-[#a9c2ff]">
        Recent failures
      </p>
      <div className="space-y-2">
        {failures.map((f, i) => (
          <div
            key={i}
            className="rounded-xl border border-red-500/15 bg-red-500/5 px-4 py-3 text-xs"
          >
            <div className="flex items-center gap-2">
              <span className="font-mono text-red-300/80 uppercase tracking-wide text-[10px]">{f.kind}</span>
              <span className="font-medium text-white/80">{f.repo}</span>
              <span className="ml-auto text-white/30">{f.completed_at?.split("T")[0]}</span>
            </div>
            {f.error_message && (
              <p className="mt-1.5 text-white/50 font-mono text-[11px] truncate">{f.error_message}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default async function AdminPage() {
  const snap = await fetchOpsSnapshot();

  if (!snap) {
    return (
      <div className="page-shell pt-24 flex flex-col items-center justify-center gap-4">
        <p className="font-mono text-[10px] uppercase tracking-widest text-[#a9c2ff]">Admin</p>
        <p className="text-white/50">
          {process.env.ADMIN_API_KEY
            ? "Unable to reach the backend. Check API_URL."
            : "Set ADMIN_API_KEY in your environment to enable this dashboard."}
        </p>
      </div>
    );
  }

  return (
    <div className="page-shell pt-14 space-y-8">
      <header className="panel-strong rounded-[32px] p-6 sm:p-8">
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-full border border-[#4d7cff]/25 bg-[#4d7cff]/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.24em] text-[#a9c2ff]">
            Admin
          </span>
          <StatusBadge status={snap.status} />
        </div>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-[#f5f8ff]">
          Ops Dashboard
        </h1>
        {snap.attention_message && (
          <p className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/8 px-4 py-3 text-sm text-amber-200">
            {snap.attention_message}
          </p>
        )}
        <p className="mt-2 text-xs text-white/30">
          Generated {new Date(snap.generated_at).toLocaleTimeString()} · auto-refreshes every 30s
        </p>
      </header>

      <div className="space-y-6">
        <section className="panel rounded-[28px] p-6">
          <QueueSection label="Atlas queue" q={snap.atlas} />
        </section>

        <section className="panel rounded-[28px] p-6">
          <QueueSection label="Review queue" q={snap.review} />
        </section>

        <section className="panel rounded-[28px] p-6">
          <WorkerSection workers={snap.workers} />
        </section>

        {snap.llm_usage && (
          <section className="panel rounded-[28px] p-6">
            <LLMSection llm={snap.llm_usage} />
          </section>
        )}

        {snap.recent_failures.length > 0 && (
          <section className="panel rounded-[28px] p-6">
            <FailuresSection failures={snap.recent_failures} />
          </section>
        )}
      </div>
    </div>
  );
}
