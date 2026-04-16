import type {
  AnalyzeResponse,
  AnalysisResult,
  JobStatusResponse,
  OpsSnapshotResponse,
  RecentRunsResponse,
  ReviewJobSubmissionResponse,
  ReviewResult,
  ReviewStatusResponse,
} from "./types";

// API URL resolution:
// - Server components need an absolute URL, so they use API_URL/NEXT_PUBLIC_API_URL.
// - Client components should stay same-origin and let Next/Vercel rewrites forward /api/*
//   to the backend. This avoids stale baked-in public backend hosts.
export function getApiUrl(): string {
  if (typeof window === "undefined") {
    // Server-side: prefer the private API_URL env var.
    return process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  }
  // Client-side: use relative paths so deploys rely on current rewrites, not baked env URLs.
  return "";
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${getApiUrl()}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    if (res.status === 404 && body.includes("\"Application not found\"")) {
      throw new Error(
        "Backend application not found. Check the frontend rewrite target or Vercel API environment variables.",
      );
    }
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export async function submitAnalysis(repoUrl: string): Promise<AnalyzeResponse> {
  return apiFetch<AnalyzeResponse>("/api/analyze", {
    method: "POST",
    body: JSON.stringify({ repo_url: repoUrl }),
  });
}

export async function getJobStatus(jobId: number): Promise<JobStatusResponse> {
  return apiFetch<JobStatusResponse>(`/api/analyze/${jobId}`);
}

export async function getResult(resultId: number): Promise<AnalysisResult> {
  return apiFetch<AnalysisResult>(`/api/results/${resultId}`);
}

export async function getRecentRuns(limit = 8): Promise<RecentRunsResponse> {
  return apiFetch<RecentRunsResponse>(`/api/history/runs?limit=${limit}`);
}

export async function getOpsSnapshot(): Promise<OpsSnapshotResponse> {
  return apiFetch<OpsSnapshotResponse>("/api/ops/summary");
}

export async function submitReview(repoUrl: string, branch?: string): Promise<ReviewJobSubmissionResponse> {
  return apiFetch<ReviewJobSubmissionResponse>("/api/review/", {
    method: "POST",
    body: JSON.stringify({ repo_url: repoUrl, branch: branch || null }),
  });
}

export async function getReviewStatus(jobId: string): Promise<ReviewStatusResponse> {
  return apiFetch<ReviewStatusResponse>(`/api/review/${jobId}`);
}

export async function getReviewResult(resultId: string): Promise<ReviewResult> {
  return apiFetch<ReviewResult>(`/api/review/results/${resultId}`);
}
