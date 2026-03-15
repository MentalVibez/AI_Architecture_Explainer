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
