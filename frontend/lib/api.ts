import type { AnalyzeResponse, AnalysisResult, JobStatusResponse } from "./types";

// API_URL resolution:
// - Server components: use API_URL (private, set to internal service address in prod)
// - Client components: use NEXT_PUBLIC_API_URL (exposed to browser)
// Fallback to localhost for local dev in both cases.
function getApiUrl(): string {
  if (typeof window === "undefined") {
    // Server-side: prefer the private API_URL env var
    return process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  }
  // Client-side: must use the public env var
  return process.env.NEXT_PUBLIC_API_URL ?? "";
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${getApiUrl()}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
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
