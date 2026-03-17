"use client";

import { useRouter } from "next/navigation";
import { submitAnalysis } from "@/lib/api";
import { useState } from "react";

const SAMPLES = [
  { label: "vercel/next.js", url: "https://github.com/vercel/next.js" },
  { label: "fastapi/fastapi", url: "https://github.com/fastapi/fastapi" },
  { label: "django/django", url: "https://github.com/django/django" },
  { label: "supabase/supabase", url: "https://github.com/supabase/supabase" },
];

export default function SampleRepos() {
  const router = useRouter();
  const [loading, setLoading] = useState<string | null>(null);

  const handleClick = async (url: string, label: string) => {
    setLoading(label);
    try {
      const { job_id } = await submitAnalysis(url);
      router.push(`/analyze?job_id=${job_id}`);
    } catch {
      setLoading(null);
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      {SAMPLES.map(({ label, url }) => (
        <button
          key={label}
          onClick={() => handleClick(url, label)}
          disabled={loading !== null}
          className="px-3 py-1.5 rounded border border-[#1e1e1e] bg-[#0a0a0a]
                     hover:border-[#2a2a2a] hover:bg-[#0e0e0e] font-mono text-[11px]
                     text-[#4a4a4a] hover:text-[#6a6a6a] disabled:opacity-40
                     disabled:cursor-not-allowed transition-colors"
        >
          {loading === label ? "Submitting…" : label}
        </button>
      ))}
    </div>
  );
}
