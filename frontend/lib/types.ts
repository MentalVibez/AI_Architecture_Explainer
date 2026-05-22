export interface AnalyzeResponse {
  job_id: number;
  status: string;
}

export interface JobStatusResponse {
  job_id: number;
  status: "queued" | "running" | "completed" | "failed";
  phase: "queue" | "analysis" | "complete" | "failed" | "unknown";
  status_detail: string;
  result_id: number | null;
  error_message: string | null;
  duration_seconds: number;
  next_poll_seconds: number | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface RecentRunItem {
  id: string;
  kind: "atlas" | "review";
  repo: string;
  href: string;
  title: string;
  completed_at: string;
}

export interface RecentRunsResponse {
  items: RecentRunItem[];
}

export interface QueueMetrics {
  queued: number;
  running: number;
  completed_last_24h: number;
  failed_last_24h: number;
  average_duration_seconds: number | null;
  oldest_queued_seconds: number | null;
  oldest_running_seconds: number | null;
}

export interface RecentFailureItem {
  kind: "atlas" | "review";
  repo: string;
  error_message: string | null;
  completed_at: string | null;
}

export interface LLMStageMetrics {
  stage: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  avg_duration_ms: number;
}

export interface LLMUsageStats {
  window_hours: number;
  total_calls: number;
  total_input_tokens: number;
  total_output_tokens: number;
  estimated_cost_usd: number;
  avg_duration_ms: number | null;
  by_stage: LLMStageMetrics[];
}

export interface WorkerHeartbeat {
  worker_id: string;
  hostname: string;
  process_id: number;
  queues: string[];
  status: string;
  started_at: string;
  last_seen_at: string;
  age_seconds: number;
  fresh: boolean;
}

export interface WorkerStatus {
  status: "ok" | "stale" | "missing";
  fresh_count: number;
  stale_count: number;
  stale_after_seconds: number;
  active_queues: string[];
  workers: WorkerHeartbeat[];
}

export interface OpsSnapshotResponse {
  status: "steady" | "active" | "watch";
  attention_message: string | null;
  atlas: QueueMetrics;
  review: QueueMetrics;
  workers: WorkerStatus;
  recent_failures: RecentFailureItem[];
  llm_usage: LLMUsageStats | null;
  generated_at: string;
}

export interface ReviewJobSubmissionResponse {
  job_id: string;
  status: string;
  message: string;
}

export interface ReviewStatusResponse {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  phase: "queue" | "analysis" | "complete" | "failed" | "unknown";
  status_detail: string;
  result_id: string | null;
  error_code: string | null;
  error_message: string | null;
  duration_seconds: number;
  next_poll_seconds: number | null;
  retryable: boolean | null;
  suggested_action: string | null;
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
  share_slug: string | null;
  job_id: string;
  repo_url: string;
  commit: string | null;
  branch: string;
  created_at: string;
  completed_at: string | null;
  duration_seconds?: number | null;
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
  share_slug: string | null;
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

export interface WeekPlanItem {
  phase: string;
  title: string;
  goal: string;
  actions: string[];
}

export interface ReadingPathItem {
  path: string;
  reason: string;
  confidence: number;
}

export interface ConceptNote {
  name: string;
  explanation: string;
  evidence: string[];
}

export interface StarterTask {
  title: string;
  why_safe: string;
  suggested_checks: string[];
  related_paths: string[];
}

export interface RiskNote {
  title: string;
  guidance: string;
  related_paths: string[];
}

export interface SetupBlocker {
  title: string;
  severity: string;
  guidance: string;
}

export interface CodebaseGuide {
  result_id: number;
  repo_label: string | null;
  overview: string;
  week_plan: WeekPlanItem[];
  reading_path: ReadingPathItem[];
  concepts: ConceptNote[];
  starter_tasks: StarterTask[];
  risk_notes: RiskNote[];
  mentor_questions: string[];
  team_questions: string[];
  setup_blockers: SetupBlocker[];
  evidence_summary: Record<string, unknown>;
}

export type OnboardingPlan = CodebaseGuide;

export interface GraphFile {
  path: string;
  language: string;
  role: string;
  is_entrypoint: boolean;
  is_on_critical_path: boolean;
  loc: number;
  complexity_score: number;
  caller_count: number;
  sensitive_operations: string[];
  confidence: number;
  was_truncated: boolean;
}

export interface GraphEdge {
  source_path: string;
  target_path: string | null;
  raw_import: string;
  kind: string;
  confidence: string;
  unresolved_reason: string | null;
}

export interface AgentStepTrace {
  agent: string;
  messages: unknown[];
}

export interface AgentRunResponse {
  agent_run_id: number;
  status: string;
  architecture_narrative: string | null;
  mermaid_diagram: string | null;
  confidence: number | null;
  agent_trace: AgentStepTrace[] | null;
  created_at: string | null;
  completed_at: string | null;
  error: string | null;
}

/** Normalize a stack category to always return StackItem objects. */
export function normalizeStackItems(items: StackCategory): StackItem[] {
  return items.map((item) =>
    typeof item === "string"
      ? { name: item, evidence: [], confidence: 0 }
      : item
  );
}
