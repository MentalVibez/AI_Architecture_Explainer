"use client";

import { useEffect } from "react";

import type { WorkspaceRunInput } from "@/lib/repo-workspace";
import { useRepoWorkspace } from "@/components/workspace/RepoWorkspaceProvider";

export default function WorkspaceRunSync(props: WorkspaceRunInput) {
  const { addRecentRun } = useRepoWorkspace();

  useEffect(() => {
    addRecentRun(props);
  }, [addRecentRun, props]);

  return null;
}
