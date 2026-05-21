"use client";

import { useCallback, useEffect, useState } from "react";
import type { AgentRunResponse, AgentStepTrace } from "@/lib/types";
import { triggerAgentAnalysis, getAgentAnalysis } from "@/lib/api";
import DiagramPanel from "./DiagramPanel";

interface Props {
  resultId: number;
}

export default function AgentAnalysisSection({ resultId }: Props) {
  const [run, setRun] = useState<AgentRunResponse | null>(null);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openStep, setOpenStep] = useState<string | null>(null);

  // Check if a run already exists on mount
  useEffect(() => {
    getAgentAnalysis(resultId).then(setRun).catch(() => null);
  }, [resultId]);

  // Poll while running
  useEffect(() => {
    if (!run || run.status === "completed" || run.status === "failed") return;
    const timer = setInterval(() => {
      getAgentAnalysis(resultId)
        .then(setRun)
        .catch(() => null);
    }, 3000);
    return () => clearInterval(timer);
  }, [run, resultId]);

  const handleTrigger = useCallback(async () => {
    setTriggering(true);
    setError(null);
    try {
      const initial = await triggerAgentAnalysis(resultId);
      setRun({
        agent_run_id: initial.agent_run_id,
        status: initial.status,
        architecture_narrative: null,
        mermaid_diagram: null,
        confidence: null,
        agent_trace: null,
        created_at: null,
        completed_at: null,
        error: null,
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setTriggering(false);
    }
  }, [resultId]);

  const isRunning = run?.status === "queued" || run?.status === "running";

  return (
    <section className="panel-strong rounded-[32px] p-6 sm:p-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#c5b3ff]">
            Agent Analysis
          </p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[#f5f8ff]">
            Multi-Agent Architecture Deep Dive
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-[#a9bce0]">
            A 4-agent pipeline (Planner → Retrieval → Synthesis → Diagram) fetches key source
            files and produces a richer architecture narrative with an agent-verified Mermaid
            diagram.
          </p>
        </div>

        {!run || run.status === "failed" ? (
          <button
            onClick={handleTrigger}
            disabled={triggering}
            className="shrink-0 rounded-full bg-[#c5b3ff] px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.16em] text-[#0d0d1a] hover:bg-[#d4c7ff] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {triggering ? "Starting…" : "Run Deep Agent Analysis"}
          </button>
        ) : isRunning ? (
          <div className="flex items-center gap-2 shrink-0">
            <span className="h-2 w-2 rounded-full bg-[#c5b3ff] animate-pulse" />
            <span className="font-mono text-xs text-[#c5b3ff]">
              {run.status === "queued" ? "Queued…" : "Analyzing…"}
            </span>
          </div>
        ) : run.status === "completed" ? (
          <div className="flex items-center gap-2 shrink-0">
            <span className="h-2 w-2 rounded-full bg-[#35c58b]" />
            <span className="font-mono text-xs text-[#35c58b]">Completed</span>
            {run.confidence !== null && (
              <span className="font-mono text-xs text-[#6d7f9f]">
                {Math.round(run.confidence * 100)}% confidence
              </span>
            )}
          </div>
        ) : null}
      </div>

      {error && (
        <p className="font-mono text-xs text-[#c84b4b] bg-[#1a0808] rounded-xl px-4 py-3">
          {error}
        </p>
      )}

      {/* Running progress placeholder */}
      {isRunning && (
        <div className="space-y-2">
          {["Planner", "Retrieval", "Synthesis", "Diagram"].map((step, i) => (
            <div key={step} className="flex items-center gap-3">
              <span className="h-1.5 w-1.5 rounded-full bg-[#c5b3ff] animate-pulse" style={{ animationDelay: `${i * 0.2}s` }} />
              <span className="font-mono text-xs text-[#6d7f9f]">{step}</span>
            </div>
          ))}
        </div>
      )}

      {/* Completed results */}
      {run?.status === "completed" && (
        <div className="space-y-6">
          {/* Architecture narrative */}
          {run.architecture_narrative && (
            <div className="surface-note">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#c5b3ff] mb-3">
                Architecture Narrative
              </p>
              <p className="text-sm leading-relaxed text-[#c2d3f2] whitespace-pre-line">
                {run.architecture_narrative}
              </p>
            </div>
          )}

          {/* Agent-generated diagram */}
          {run.mermaid_diagram && (
            <DiagramPanel mermaid={run.mermaid_diagram} />
          )}

          {/* Agent trace accordion */}
          {run.agent_trace && run.agent_trace.length > 0 && (
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[#6d7f9f] mb-3">
                Agent Trace
              </p>
              <div className="space-y-2">
                {run.agent_trace.map((step: AgentStepTrace) => (
                  <TraceAccordion
                    key={step.agent}
                    step={step}
                    isOpen={openStep === step.agent}
                    onToggle={() =>
                      setOpenStep((prev) => (prev === step.agent ? null : step.agent))
                    }
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Failed state */}
      {run?.status === "failed" && run.error && (
        <div className="surface-note border-[#c84b4b]/20">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#c84b4b] mb-1">
            Analysis failed
          </p>
          <p className="font-mono text-xs text-[#c84b4b]">{run.error}</p>
        </div>
      )}
    </section>
  );
}

function TraceAccordion({
  step,
  isOpen,
  onToggle,
}: {
  step: AgentStepTrace;
  isOpen: boolean;
  onToggle: () => void;
}) {
  const AGENT_LABELS: Record<string, string> = {
    planner: "Planner — decided which files to fetch",
    retrieval: "Retrieval — fetched file contents via GitHub",
    synthesis: "Synthesis — built architecture narrative",
    diagram: "Diagram — generated Mermaid diagram",
  };

  const toolCalls = (step.messages as Array<{ role?: string; content?: unknown }>).flatMap(
    (msg) => {
      if (!Array.isArray(msg.content)) return [];
      return (msg.content as Array<{ type?: string; name?: string; input?: unknown }>).filter(
        (block) => block.type === "tool_use"
      );
    }
  );

  return (
    <div className="rounded-xl border border-white/10 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-white/[0.02] transition-colors"
      >
        <div className="flex items-center gap-3">
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ backgroundColor: STEP_COLORS[step.agent] ?? "#6d7f9f" }}
          />
          <span className="font-mono text-xs text-[#c2d3f2]">
            {AGENT_LABELS[step.agent] ?? step.agent}
          </span>
          {toolCalls.length > 0 && (
            <span className="font-mono text-[10px] text-[#6d7f9f]">
              {toolCalls.length} tool call{toolCalls.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        <span className="font-mono text-[10px] text-[#4a5568]">{isOpen ? "▲" : "▼"}</span>
      </button>

      {isOpen && toolCalls.length > 0 && (
        <div className="px-4 pb-4 space-y-2">
          {toolCalls.map((call, i) => (
            <div key={i} className="rounded-lg bg-[#0d1017] border border-white/5 px-3 py-2">
              <p className="font-mono text-[10px] text-[#c5b3ff]">{call.name}</p>
              {call.input != null && (
                <pre className="mt-1 font-mono text-[10px] text-[#6d7f9f] whitespace-pre-wrap break-all">
                  {JSON.stringify(call.input, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const STEP_COLORS: Record<string, string> = {
  planner: "#4d7cff",
  retrieval: "#35c58b",
  synthesis: "#f0a500",
  diagram: "#c5b3ff",
};
