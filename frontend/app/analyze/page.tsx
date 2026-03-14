"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getJobStatus } from "@/lib/api";
import LoadingAnalysis from "@/components/LoadingAnalysis";

const POLL_INTERVAL_MS = 2000;

function AnalyzeInner() {
  const router = useRouter();
  const params = useSearchParams();
  const jobId = Number(params.get("job_id"));
  const [status, setStatus] = useState<string>("queued");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
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
        setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    };

    poll();
  }, [jobId, router]);

  if (error) {
    return (
      <div className="text-center space-y-4">
        <p className="text-red-400 text-lg">{error}</p>
        <a href="/" className="text-sm text-gray-400 underline">
          Try again
        </a>
      </div>
    );
  }

  return <LoadingAnalysis status={status} />;
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
