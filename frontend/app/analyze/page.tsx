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
      <div className="text-center space-y-6 max-w-md px-4">
        <div className="font-mono text-[10px] tracking-[0.3em] text-[#b86a6a] uppercase">
          Analysis failed
        </div>
        <p className="font-sans text-[14px] text-[#4a4a4a] leading-relaxed">{error}</p>
        <a
          href="/"
          className="inline-block font-mono text-[12px] tracking-widest uppercase
                     px-5 py-2.5 border border-[#1e1e1e] text-[#4a4a4a] rounded
                     hover:border-[#2a2a2a] hover:text-[#6a6a6a] transition-colors"
        >
          Try again
        </a>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl px-6 space-y-4">
      <LoadingAnalysis status={status} />
      {slow && (
        <p className="font-mono text-[11px] text-[#2a2a2a] tracking-wider text-center">
          Large repos take longer — still working…
        </p>
      )}
    </div>
  );
}

export default function AnalyzePage() {
  return (
    <div className="min-h-[70vh] flex flex-col items-center justify-center py-20">
      <Suspense fallback={<LoadingAnalysis status="queued" />}>
        <AnalyzeInner />
      </Suspense>
    </div>
  );
}
