const STAGE_LABELS: Record<string, string> = {
  queued: "Queued and waiting to start…",
  running: "Collecting repository evidence and building the report…",
  completed: "Done. Redirecting to the workspace…",
};

const ANALYSIS_STEPS = [
  {
    key: "queued",
    title: "Queue the run",
    detail: "Reserve the job and prepare the workspace for analysis.",
  },
  {
    key: "running",
    title: "Collect evidence",
    detail: "Read manifests, tree structure, and high-signal files before any summary work.",
  },
  {
    key: "completed",
    title: "Assemble the report",
    detail: "Build the final architecture view and redirect into the results workspace.",
  },
] as const;

interface Props {
  status: string;
  elapsedSeconds?: number;
  slow?: boolean;
}

function getActiveStepIndex(status: string) {
  if (status === "completed") return 2;
  if (status === "running") return 1;
  return 0;
}

export default function LoadingAnalysis({
  status,
  elapsedSeconds = 0,
  slow = false,
}: Props) {
  const activeStep = getActiveStepIndex(status);

  return (
    <div className="panel-strong mx-auto w-full max-w-4xl rounded-[28px] p-6 sm:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#a9c2ff]">
            Atlas workspace
          </p>
          <p className="mt-2 text-sm leading-relaxed text-[#8ea3c7]">
            Deterministic analysis runs first, then the report is assembled for the final view.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-[#dbe7ff]">
            {status}
          </div>
          <div className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.18em] text-[#8ea3c7]">
            {elapsedSeconds}s elapsed
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-3">
        {ANALYSIS_STEPS.map((step, index) => {
          const isDone = index < activeStep;
          const isActive = index === activeStep;

          return (
            <div
              key={step.key}
              className="rounded-[22px] border p-4"
              style={{
                borderColor: isDone || isActive ? "rgba(77,124,255,0.28)" : "rgba(255,255,255,0.1)",
                background: isDone || isActive ? "rgba(77,124,255,0.08)" : "rgba(255,255,255,0.03)",
              }}
            >
              <div className="flex items-center gap-3">
                <span
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border font-mono text-[10px]"
                  style={{
                    borderColor: isDone || isActive ? "rgba(77,124,255,0.32)" : "rgba(255,255,255,0.12)",
                    color: isDone ? "#08111f" : "#dbe7ff",
                    backgroundColor: isDone ? "#4d7cff" : isActive ? "rgba(77,124,255,0.16)" : "transparent",
                  }}
                >
                  {isDone ? "✓" : index + 1}
                </span>
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#dbe7ff]">
                  {step.title}
                </p>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-[#8ea3c7]">{step.detail}</p>
            </div>
          );
        })}
      </div>

      <div className="mt-6 rounded-[24px] border border-white/10 bg-white/[0.03] p-4">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#6d7f9f]">
          Current status
        </p>
        <p className="mt-3 text-sm leading-relaxed text-[#d7e4ff]">
          {STAGE_LABELS[status] ?? status}
        </p>
        <p className="mt-2 text-sm leading-relaxed text-[#94a8cb]">
          {slow
            ? "Larger repositories can take a little longer while Atlas finishes evidence collection and report assembly."
            : "Atlas is still in the deterministic analysis pass before the final report view opens."}
        </p>
      </div>

      <div className="mt-6 space-y-6">
        <div className="skeleton h-4 w-40" />
        <div className="skeleton h-56 w-full rounded-[24px] sm:h-72" />

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-6">
            <div className="space-y-3">
              <div className="skeleton h-3 w-24" />
              <div className="skeleton h-3 w-full" />
              <div className="skeleton h-3 w-5/6" />
              <div className="skeleton h-3 w-4/6" />
              <div className="skeleton h-3 w-full" />
              <div className="skeleton h-3 w-3/4" />
            </div>
          </div>
          <div className="rounded-[24px] border border-white/10 bg-white/[0.03] p-6">
            <div className="space-y-3">
              <div className="skeleton h-3 w-28" />
              <div className="skeleton h-3 w-full" />
              <div className="skeleton h-3 w-4/5" />
              <div className="skeleton h-3 w-full" />
              <div className="skeleton h-3 w-2/3" />
              <div className="skeleton h-3 w-5/6" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
