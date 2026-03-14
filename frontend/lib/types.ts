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

export interface AnalysisResult {
  id: number;
  job_id: number;
  repo_snapshot_sha: string | null;
  detected_stack: {
    frontend: string[];
    backend: string[];
    database: string[];
    infra: string[];
    testing: string[];
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
