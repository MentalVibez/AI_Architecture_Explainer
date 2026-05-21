"use client";

import type { CodebaseGuide } from "@/lib/types";
import { guideToMarkdown } from "@/lib/guide-to-markdown";

interface Props {
  guide: CodebaseGuide;
  repoLabel?: string | null;
}

export default function DownloadGuideButton({ guide, repoLabel }: Props) {
  function handleDownload() {
    const markdown = guideToMarkdown(guide, repoLabel);
    const blob = new Blob([markdown], { type: "text/markdown; charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "ONBOARDING.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <button
      onClick={handleDownload}
      className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-[#8a9bbf] transition-colors hover:border-white/20 hover:text-[#c5d0e8]"
    >
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
        <path
          d="M6 1v6M3.5 5L6 7.5 8.5 5M2 9.5h8"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      Download ONBOARDING.md
    </button>
  );
}
