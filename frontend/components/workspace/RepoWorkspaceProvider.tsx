"use client";

import { createContext, useContext, useEffect, useState } from "react";

import type {
  RepoWorkspace,
  RepoWorkspaceInput,
  WorkspaceRun,
  WorkspaceRunInput,
} from "@/lib/repo-workspace";
import {
  MAX_RECENT_REPOS,
  MAX_RECENT_RUNS,
  normalizeRepoWorkspace,
  normalizeRepoWorkspaceList,
  normalizeWorkspaceRunList,
} from "@/lib/repo-workspace";

const ACTIVE_REPO_KEY = "codebaseatlas.active-repo";
const RECENT_REPOS_KEY = "codebaseatlas.recent-repos";
const RECENT_RUNS_KEY = "codebaseatlas.recent-runs";

interface RepoWorkspaceContextValue {
  activeRepo: RepoWorkspace | null;
  recentRepos: RepoWorkspace[];
  recentRuns: WorkspaceRun[];
  setActiveRepo: (input: RepoWorkspaceInput) => void;
  addRecentRun: (input: WorkspaceRunInput) => void;
  clearActiveRepo: () => void;
}

const RepoWorkspaceContext = createContext<RepoWorkspaceContextValue | null>(null);

export function RepoWorkspaceProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [activeRepo, setActiveRepoState] = useState<RepoWorkspace | null>(null);
  const [recentRepos, setRecentRepos] = useState<RepoWorkspace[]>([]);
  const [recentRuns, setRecentRuns] = useState<WorkspaceRun[]>([]);

  useEffect(() => {
    const activeRaw = window.localStorage.getItem(ACTIVE_REPO_KEY);
    const recentRaw = window.localStorage.getItem(RECENT_REPOS_KEY);
    const runsRaw = window.localStorage.getItem(RECENT_RUNS_KEY);

    try {
      if (activeRaw) {
        const parsed = JSON.parse(activeRaw) as RepoWorkspaceInput;
        const normalized = normalizeRepoWorkspace(parsed);
        if (normalized) {
          setActiveRepoState(normalized);
        } else {
          window.localStorage.removeItem(ACTIVE_REPO_KEY);
        }
      }
    } catch {
      window.localStorage.removeItem(ACTIVE_REPO_KEY);
    }

    try {
      if (recentRaw) {
        const parsed = JSON.parse(recentRaw) as RepoWorkspaceInput[];
        setRecentRepos(normalizeRepoWorkspaceList(parsed).slice(0, MAX_RECENT_REPOS));
      }
    } catch {
      window.localStorage.removeItem(RECENT_REPOS_KEY);
    }

    try {
      if (runsRaw) {
        const parsed = JSON.parse(runsRaw) as WorkspaceRunInput[];
        setRecentRuns(normalizeWorkspaceRunList(parsed).slice(0, MAX_RECENT_RUNS));
      }
    } catch {
      window.localStorage.removeItem(RECENT_RUNS_KEY);
    }
  }, []);

  function setActiveRepo(input: RepoWorkspaceInput) {
    const normalized = normalizeRepoWorkspace(input);
    if (!normalized) {
      return;
    }

    setActiveRepoState(normalized);
    window.localStorage.setItem(ACTIVE_REPO_KEY, JSON.stringify(normalized));
    setRecentRepos((current) => {
      const next = normalizeRepoWorkspaceList([normalized, ...current]).slice(0, MAX_RECENT_REPOS);
      window.localStorage.setItem(RECENT_REPOS_KEY, JSON.stringify(next));
      return next;
    });
  }

  function addRecentRun(input: WorkspaceRunInput) {
    setRecentRuns((current) => {
      const next = normalizeWorkspaceRunList([input, ...current]).slice(0, MAX_RECENT_RUNS);
      window.localStorage.setItem(RECENT_RUNS_KEY, JSON.stringify(next));
      return next;
    });
  }

  function clearActiveRepo() {
    setActiveRepoState(null);
    window.localStorage.removeItem(ACTIVE_REPO_KEY);
  }

  return (
    <RepoWorkspaceContext.Provider
      value={{ activeRepo, recentRepos, recentRuns, setActiveRepo, addRecentRun, clearActiveRepo }}
    >
      {children}
    </RepoWorkspaceContext.Provider>
  );
}

export function useRepoWorkspace() {
  const context = useContext(RepoWorkspaceContext);
  if (!context) {
    throw new Error("useRepoWorkspace must be used within RepoWorkspaceProvider");
  }
  return context;
}
