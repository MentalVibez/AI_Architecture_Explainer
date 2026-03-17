"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { submitAnalysis } from "@/lib/api";

export default function RepoUrlForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { job_id } = await submitAnalysis(url.trim());
      router.push(`/analyze?job_id=${job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 w-full">
      <div className="flex gap-2">
        <input
          type="url"
          placeholder="https://github.com/owner/repo"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          className="flex-1 px-4 py-3 rounded-lg bg-[#0a0a0a] border border-[#1e1e1e] text-[#e8e0d4]
                     placeholder-[#3a3a3a] focus:outline-none focus:border-[#7cb9c8] font-mono text-[13px]
                     transition-colors"
        />
        <button
          type="submit"
          disabled={loading || !url}
          className="px-6 py-3 rounded-lg bg-[#c8a96e] hover:bg-[#d4b87a] text-[#0a0a0a]
                     disabled:opacity-40 disabled:cursor-not-allowed font-mono text-[12px]
                     tracking-wider transition-colors"
        >
          {loading ? "Submitting…" : "Analyze →"}
        </button>
      </div>
      {error && <p className="font-mono text-[12px] text-[#c84b4b] text-left">{error}</p>}
    </form>
  );
}
