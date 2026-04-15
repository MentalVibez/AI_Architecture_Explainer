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
          className="rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-2
                     hover:border-[#4d7cff]/30 hover:bg-[#4d7cff]/10 font-mono text-[11px]
                     text-[#a6b7d5] hover:text-[#eef4ff] disabled:opacity-40
                     disabled:cursor-not-allowed transition-colors"
        >
          {loading === label ? "Running…" : label}
        </button>
      ))}
    </div>
  );
}
