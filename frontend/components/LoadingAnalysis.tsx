const STAGE_LABELS: Record<string, string> = {
  queued: "Queued — waiting to start…",
  running: "Fetching and analyzing repository…",
  completed: "Done — redirecting…",
};

interface Props {
  status: string;
}

export default function LoadingAnalysis({ status }: Props) {
  return (
    <div className="space-y-6 w-full max-w-4xl mx-auto">
      {/* Skeleton: header bar */}
      <div className="flex items-center gap-4">
        <div className="skeleton h-4 w-32" />
        <div className="skeleton h-4 w-48" />
      </div>

      {/* Skeleton: diagram box */}
      <div className="skeleton h-64 w-full rounded-xl" />

      {/* Skeleton: two summary cards side by side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-3 border border-[#1a1a1a] rounded-lg p-6">
          <div className="skeleton h-3 w-24" />
          <div className="skeleton h-3 w-full" />
          <div className="skeleton h-3 w-5/6" />
          <div className="skeleton h-3 w-4/6" />
          <div className="skeleton h-3 w-full" />
          <div className="skeleton h-3 w-3/4" />
        </div>
        <div className="space-y-3 border border-[#1a1a1a] rounded-lg p-6">
          <div className="skeleton h-3 w-28" />
          <div className="skeleton h-3 w-full" />
          <div className="skeleton h-3 w-4/5" />
          <div className="skeleton h-3 w-full" />
          <div className="skeleton h-3 w-2/3" />
          <div className="skeleton h-3 w-5/6" />
        </div>
      </div>

      {/* Status label */}
      <p className="font-mono text-[11px] tracking-wider text-[#3a3a3a] text-center">
        {STAGE_LABELS[status] ?? status}
      </p>
    </div>
  );
}
