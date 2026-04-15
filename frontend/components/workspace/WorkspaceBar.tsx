"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { isGithubRepo } from "@/lib/repo-workspace";
import { useRepoWorkspace } from "@/components/workspace/RepoWorkspaceProvider";

const TOOL_LABELS: Record<string, string> = {
  "/": "Atlas",
  "/scout": "Scout",
  "/map": "Map",
  "/review": "Review",
};

export default function WorkspaceBar() {
  const pathname = usePathname();
  const { activeRepo, clearActiveRepo } = useRepoWorkspace();

  if (!activeRepo) {
    return null;
  }

  const currentTool = TOOL_LABELS[pathname] ?? "Workspace";
  const repoQuery = isGithubRepo(activeRepo)
    ? `?repo=${encodeURIComponent(activeRepo.repo)}`
    : "";

  return (
    <div className="border-b border-white/10 bg-[#07101d]/85 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0 flex flex-wrap items-center gap-3">
          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-[#6d7f9f]">
            {currentTool}
          </span>
          <span className="h-1 w-1 rounded-full bg-[#4d7cff]" />
          <p className="truncate font-mono text-[13px] text-[#f4f8ff]">{activeRepo.repo}</p>
          <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.16em] text-[#7f95ba]">
            {activeRepo.provider}
          </span>
        </div>

        <div className="flex w-full flex-col items-stretch gap-2 rounded-[20px] border border-white/10 bg-white/[0.03] p-2 sm:w-auto sm:flex-row sm:flex-wrap sm:items-center sm:gap-2 sm:rounded-full sm:p-1">
          <Link
            href="/"
            className="rounded-full px-3.5 py-2 text-center font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:bg-white/[0.04] hover:text-white"
          >
            Atlas
          </Link>
          <Link
            href={`/map${repoQuery}`}
            className="rounded-full px-3.5 py-2 text-center font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:bg-white/[0.04] hover:text-white"
          >
            Map
          </Link>
          <Link
            href={`/review${repoQuery}`}
            className="rounded-full px-3.5 py-2 text-center font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:bg-white/[0.04] hover:text-white"
          >
            Review
          </Link>
          <a
            href={activeRepo.url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-full px-3.5 py-2 text-center font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:bg-white/[0.04] hover:text-white"
          >
            Repo ↗
          </a>
          <button
            type="button"
            onClick={clearActiveRepo}
            className="rounded-full border border-white/10 bg-white/[0.02] px-3.5 py-2 text-center font-mono text-[11px] uppercase tracking-[0.16em] text-[#7f95ba] hover:border-white/15 hover:text-white"
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  );
}
