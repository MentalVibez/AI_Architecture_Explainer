export type RepoProvider = "github" | "gitlab" | "unknown";
export type WorkspaceRunKind = "atlas" | "review";

export interface RepoWorkspace {
  repo: string;
  url: string;
  provider: RepoProvider;
}

export interface RepoWorkspaceInput {
  repo?: string | null;
  url?: string | null;
  provider?: RepoProvider | null;
}

export interface WorkspaceRun {
  id: string;
  kind: WorkspaceRunKind;
  repo: string;
  href: string;
  title: string;
  completedAt: string;
}

export interface WorkspaceRunInput {
  id?: string | null;
  kind?: WorkspaceRunKind | null;
  repo?: string | null;
  href?: string | null;
  title?: string | null;
  completedAt?: string | null;
}

export const MAX_RECENT_REPOS = 6;
export const MAX_RECENT_RUNS = 8;

const REPO_PATH = /^([a-zA-Z0-9._-]+)\/([a-zA-Z0-9._-]+)$/;

export function normalizeRepoWorkspace(input: RepoWorkspaceInput): RepoWorkspace | null {
  const parsedUrl = input.url ? parseRepoUrl(input.url) : null;

  if (parsedUrl) {
    return parsedUrl;
  }

  if (!input.repo) {
    return null;
  }

  const repo = input.repo.trim().replace(/\/+$/, "");
  if (!REPO_PATH.test(repo)) {
    return null;
  }

  const provider = input.provider ?? "github";
  return {
    repo,
    provider,
    url: buildRepoUrl(repo, provider),
  };
}

export function parseRepoUrl(raw: string): RepoWorkspace | null {
  const trimmed = raw.trim().replace(/\/+$/, "");
  if (!trimmed) {
    return null;
  }

  const parsed = safeParseUrl(trimmed);
  if (!parsed) {
    return null;
  }

  const segments = parsed.pathname.split("/").filter(Boolean);
  if (segments.length < 2) {
    return null;
  }

  const repo = `${segments[0]}/${segments[1]}`;
  if (!REPO_PATH.test(repo)) {
    return null;
  }

  const provider = detectProvider(parsed.hostname);
  return {
    repo,
    provider,
    url: buildRepoUrl(repo, provider),
  };
}

export function buildRepoUrl(repo: string, provider: RepoProvider = "github"): string {
  const host =
    provider === "gitlab"
      ? "https://gitlab.com"
      : provider === "unknown"
      ? "https://github.com"
      : "https://github.com";

  return `${host}/${repo}`;
}

export function isGithubRepo(workspace: RepoWorkspace | null | undefined): workspace is RepoWorkspace {
  return Boolean(workspace && workspace.provider === "github");
}

export function normalizeRepoWorkspaceList(items: RepoWorkspaceInput[]): RepoWorkspace[] {
  const seen = new Set<string>();
  const normalized: RepoWorkspace[] = [];

  for (const item of items) {
    const repo = normalizeRepoWorkspace(item);
    if (!repo || seen.has(repo.repo)) {
      continue;
    }

    seen.add(repo.repo);
    normalized.push(repo);
  }

  return normalized;
}

export function normalizeWorkspaceRun(input: WorkspaceRunInput): WorkspaceRun | null {
  const repo = input.repo?.trim().replace(/\/+$/, "");
  const href = input.href?.trim();
  const kind = input.kind ?? "atlas";
  const id = input.id?.trim();
  const title = input.title?.trim();
  const completedAt = input.completedAt?.trim() || new Date().toISOString();

  if (!repo || !REPO_PATH.test(repo) || !href || !id || !title) {
    return null;
  }

  return {
    id,
    kind,
    repo,
    href,
    title,
    completedAt,
  };
}

export function normalizeWorkspaceRunList(items: WorkspaceRunInput[]): WorkspaceRun[] {
  const seen = new Set<string>();
  const normalized: WorkspaceRun[] = [];

  for (const item of items) {
    const run = normalizeWorkspaceRun(item);
    if (!run) {
      continue;
    }

    const key = `${run.kind}:${run.id}`;
    if (seen.has(key)) {
      continue;
    }

    seen.add(key);
    normalized.push(run);
  }

  return normalized;
}

function detectProvider(hostname: string): RepoProvider {
  if (hostname.includes("github.com")) return "github";
  if (hostname.includes("gitlab.com")) return "gitlab";
  return "unknown";
}

function safeParseUrl(value: string): URL | null {
  try {
    return new URL(value);
  } catch {
    return null;
  }
}
