export interface AnalyzeResponse {
  job_id: number;
  status: string;
}

export interface JobStatusResponse {
  job_id: number;
  status: "queued" | "running" | "completed" | "failed";
  result_id: number | null;
  error_message: string | null;
}

export interface ReviewJobSubmissionResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface ReviewStatusResponse {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  result_id: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ReviewFinding {
  id: string;
  rule_id: string;
  title: string;
  category: string;
  severity: string;
  summary: string;
  why_it_matters: string;
  suggested_fix: string;
}

export interface ReviewResult {
  result_id: string;
  job_id: string;
  repo_url: string;
  commit: string | null;
  branch: string;
  created_at: string;
  completed_at: string | null;
  ruleset_version: string | null;
  depth_level: string | null;
  confidence_label: string | null;
  overall_score: number | null;
  verdict_label: string | null;
  production_suitable: boolean;
  anti_gaming_verdict: string | null;
  scores: Record<string, number | null>;
  findings: ReviewFinding[];
  summary: { developer: string; manager: string; hiring: string } | null;
  error_code: string | null;
  error_message: string | null;
}

export interface StackItem {
  name: string;
  evidence: string[];
  confidence: number;
}

// detected_stack supports both the new rich format and legacy string format
// (old DB records may have string[] entries)
type StackCategory = (StackItem | string)[];

export interface AnalysisResult {
  id: number;
  job_id: number;
  repo_snapshot_sha: string | null;
  detected_stack: {
    frontend: StackCategory;
    backend: StackCategory;
    database: StackCategory;
    infra: StackCategory;
    testing: StackCategory;
  };
  dependencies: {
    npm?: string[];
    python?: string[];
  };
  entry_points: string[];
  folder_map: Array<{ path: string; role: string }>;
  diagram_mermaid: string | null;
  developer_summary: string | null;
  hiring_manager_summary: string | null;
  confidence_score: number | null;
  caveats: string[];
  raw_evidence: unknown[];
  created_at: string;
}

/** Normalize a stack category to always return StackItem objects. */
export function normalizeStackItems(items: StackCategory): StackItem[] {
  return items.map((item) =>
    typeof item === "string"
      ? { name: item, evidence: [], confidence: 0 }
      : item
  );
}
