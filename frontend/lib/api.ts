import type { AnalyzeResponse, AnalysisResult, JobStatusResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
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
