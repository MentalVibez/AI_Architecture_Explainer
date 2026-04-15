"use client";

import { useEffect } from "react";

import type { RepoWorkspaceInput } from "@/lib/repo-workspace";
import { useRepoWorkspace } from "@/components/workspace/RepoWorkspaceProvider";

export default function WorkspaceSync(props: RepoWorkspaceInput) {
  const { setActiveRepo } = useRepoWorkspace();

  useEffect(() => {
    setActiveRepo(props);
  }, [props, setActiveRepo]);

  return null;
}
