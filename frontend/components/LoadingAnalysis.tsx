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
    <div className="text-center space-y-4">
      <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
      <p className="text-gray-300">{STAGE_LABELS[status] ?? status}</p>
    </div>
  );
}
