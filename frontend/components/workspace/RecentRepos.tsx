"use client";

import { useRepoWorkspace } from "@/components/workspace/RepoWorkspaceProvider";

export default function RecentRepos() {
  const { recentRepos, setActiveRepo } = useRepoWorkspace();

  if (recentRepos.length === 0) {
    return null;
  }

  return (
    <div className="mt-5 border-t border-white/10 pt-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">
          Recent repos
        </p>
        <p className="hidden font-mono text-[10px] text-[#5f7397] sm:block">
          Click one to reuse it in Atlas.
        </p>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {recentRepos.map((repo) => (
          <button
            key={repo.repo}
            type="button"
            onClick={() => setActiveRepo(repo)}
            className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-[10px] text-[#b7c8e8] hover:border-[#4d7cff]/30 hover:text-white"
          >
            {repo.repo}
          </button>
        ))}
      </div>
    </div>
  );
}
