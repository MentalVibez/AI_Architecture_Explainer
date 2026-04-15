"use client";

import Link from "next/link";
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
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [statusDetail, setStatusDetail] = useState("");
  const startTime = useRef(Date.now());

  useEffect(() => {
    if (!jobId) return;

    let timeoutId: ReturnType<typeof setTimeout>;

    const poll = async () => {
      const elapsed = Date.now() - startTime.current;
      setElapsedSeconds(Math.floor(elapsed / 1000));

      if (elapsed > POLL_TIMEOUT_MS) {
        setError("Analysis is taking too long. The repo may be too large or the service is busy. Try again later.");
        return;
      }

      if (elapsed > 30_000) setSlow(true);

      try {
        const data = await getJobStatus(jobId);
        setStatus(data.status);
        setStatusDetail(data.status_detail);
        if (data.duration_seconds > 0) {
          setElapsedSeconds(data.duration_seconds);
        }

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

  if (!jobId) {
    return (
      <div className="panel mx-auto max-w-2xl rounded-[28px] p-8 text-center">
        <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-[#ffd98f]">
          Missing job
        </p>
        <h1 className="mt-3 text-3xl font-semibold text-[#f5f8ff]">
          Atlas needs a valid analysis job to continue.
        </h1>
        <p className="mt-4 text-sm leading-relaxed text-[#94a8cb]">
          Start from the Atlas form or send a repo from Scout so the workspace has a real job to track.
        </p>
        <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
          <Link
            href="/"
            className="rounded-full bg-[#4d7cff] px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.16em] text-white"
          >
            Open Atlas
          </Link>
          <Link
            href="/scout"
            className="rounded-full border border-white/10 px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2]"
          >
            Open Scout
          </Link>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel mx-auto max-w-2xl rounded-[28px] p-8 text-center">
        <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-[#ff8d8d]">
          Analysis failed
        </p>
        <h1 className="mt-3 text-3xl font-semibold text-[#f5f8ff]">Atlas couldn’t complete this run.</h1>
        <p className="mt-4 text-sm leading-relaxed text-[#94a8cb]">{error}</p>
        <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
          <Link
            href="/"
            className="rounded-full bg-[#4d7cff] px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.16em] text-white"
          >
            Try again
          </Link>
          <Link
            href="/review"
            className="rounded-full border border-white/10 px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2]"
          >
            Open Review
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-4xl px-6 space-y-4">
      <LoadingAnalysis status={status} elapsedSeconds={elapsedSeconds} slow={slow} />
      {statusDetail && (
        <p className="text-center text-sm leading-relaxed text-[#94a8cb]">{statusDetail}</p>
      )}
    </div>
  );
}

export default function AnalyzePage() {
  return (
    <div className="mx-auto flex min-h-[70vh] max-w-6xl flex-col items-center justify-center px-6 py-20">
      <div className="mb-6 text-center">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">Atlas job</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-[-0.03em] text-[#f5f8ff]">
          Building your repository workspace
        </h1>
      </div>
      <Suspense fallback={<LoadingAnalysis status="queued" elapsedSeconds={0} slow={false} />}>
        <AnalyzeInner />
      </Suspense>
    </div>
  );
}
