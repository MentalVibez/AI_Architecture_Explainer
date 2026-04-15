"use client";

import clsx from "clsx";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { submitAnalysis } from "@/lib/api";
import { useRepoWorkspace } from "@/components/workspace/RepoWorkspaceProvider";
import { normalizeRepoWorkspace } from "@/lib/repo-workspace";

export default function RepoUrlForm() {
  const router = useRouter();
  const { activeRepo, setActiveRepo } = useRepoWorkspace();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (activeRepo?.url && activeRepo.url !== url) {
      setUrl(activeRepo.url);
    }
  }, [activeRepo, url]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const normalized = normalizeRepoWorkspace({ url });
    if (normalized) {
      setActiveRepo(normalized);
    }

    try {
      const { job_id } = await submitAnalysis(url.trim());
      router.push(`/analyze?job_id=${job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex w-full flex-col gap-3">
      <div className="flex flex-col gap-3 sm:flex-row">
        <input
          type="url"
          placeholder="Paste a public GitHub repository URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          className={clsx(
            "flex-1 min-w-0 rounded-2xl border bg-[#07101d] px-4 py-3.5",
            "font-mono text-[13px] text-[#f2f7ff] placeholder-[#7082a5]",
            "focus:outline-none focus:border-[#4d7cff] focus:ring-4 focus:ring-[#4d7cff]/10",
            "border-white/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]",
          )}
        />
        <button
          type="submit"
          disabled={loading || !url}
          className="rounded-2xl bg-[#4d7cff] px-6 py-3.5 text-[#f8fbff] shadow-[0_14px_30px_rgba(77,124,255,0.28)]
                     hover:bg-[#6894ff] disabled:opacity-40 disabled:cursor-not-allowed
                     font-mono text-[12px] tracking-[0.18em] uppercase sm:min-w-[10.5rem]"
        >
          {loading ? "Running…" : "Open Atlas"}
        </button>
      </div>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="break-all font-mono text-[11px] text-[#7e92b7] sm:break-normal">
          Try: <span className="text-[#dce8ff]">https://github.com/vercel/next.js</span>
        </p>
        <p className="font-mono text-[11px] text-[#5f7397]">
          Public repos only. Architecture summary usually returns in under 2 minutes.
        </p>
      </div>
      {error && <p className="font-mono text-[12px] text-[#ff8d8d] text-left">{error}</p>}
    </form>
  );
}
