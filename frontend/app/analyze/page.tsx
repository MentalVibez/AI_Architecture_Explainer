"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getJobStatus } from "@/lib/api";
import LoadingAnalysis from "@/components/LoadingAnalysis";

const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 3 * 60 * 1000; // 3 minutes

function AnalyzeInner() {
  const router = useRouter();
  const params = useSearchParams();
  const jobId = Number(params.get("job_id"));
  const [status, setStatus] = useState<string>("queued");
  const [error, setError] = useState<string | null>(null);
  const [slow, setSlow] = useState(false);
  const startTime = useRef(Date.now());

  useEffect(() => {
    if (!jobId) return;

    let timeoutId: ReturnType<typeof setTimeout>;

    const poll = async () => {
      const elapsed = Date.now() - startTime.current;

      if (elapsed > POLL_TIMEOUT_MS) {
        setError("Analysis is taking too long. The repo may be too large or the service is busy. Try again later.");
        return;
      }

      if (elapsed > 30_000) setSlow(true);

      try {
        const data = await getJobStatus(jobId);
        setStatus(data.status);

        if (data.status === "completed" && data.result_id) {
          router.push(`/results/${data.result_id}`);
          return;
        }
        if (data.status === "failed") {
          setError(data.error_message ?? "Analysis failed");
          return;
        }
        timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    };

    poll();
    return () => clearTimeout(timeoutId);
  }, [jobId, router]);

  if (error) {
    return (
      <div className="text-center space-y-4 max-w-md px-4">
        <p className="text-red-400">{error}</p>
        <a href="/" className="text-sm text-gray-400 underline">
          Try again
        </a>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <LoadingAnalysis status={status} />
      {slow && (
        <p className="text-xs text-gray-600 text-center">
          Large repos take longer — still working…
        </p>
      )}
    </div>
  );
}

export default function AnalyzePage() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-950 text-white">
      <Suspense fallback={<LoadingAnalysis status="queued" />}>
        <AnalyzeInner />
      </Suspense>
    </main>
  );
}
