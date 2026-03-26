interface PipelineBadgeProps {
  variant?: "full" | "compact";
}

const STEPS = [
  { label: "Scan",      kind: "det", desc: "GitHub API fetch + manifest parsing" },
  { label: "Structure", kind: "det", desc: "Framework detection (heuristic rules)" },
  { label: "Classify",  kind: "det", desc: "Evidence object construction" },
  { label: "Explain",   kind: "llm", desc: "Claude: diagram + summaries" },
] as const;

export default function PipelineBadge({ variant = "compact" }: PipelineBadgeProps) {
  if (variant === "compact") {
    return (
      <div className="flex items-center gap-2 flex-wrap">
        <span
          className="font-mono text-[10px] tracking-[0.2em] uppercase px-2.5 py-1 rounded"
          style={{ color: "#7cb9c8", border: "1px solid #7cb9c820", background: "#7cb9c808" }}
        >
          Deterministic
        </span>
        <span className="font-mono text-[10px] text-[#2a2a2a]">→</span>
        <span
          className="font-mono text-[10px] tracking-[0.2em] uppercase px-2.5 py-1 rounded"
          style={{ color: "#c8a96e", border: "1px solid #c8a96e20", background: "#c8a96e08" }}
        >
          LLM last-mile
        </span>
        <a
          href="/how-it-works"
          className="font-mono text-[10px] text-[#2a2a2a] hover:text-[#4a4a4a] transition-colors"
        >
          How it works →
        </a>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-0 flex-wrap sm:flex-nowrap">
      {STEPS.map((step, i) => (
        <div key={step.label} className="flex items-start">
          <div className="flex flex-col items-center gap-1.5">
            <div
              className="px-3 py-1.5 rounded font-mono text-[11px] tracking-wider whitespace-nowrap"
              style={{
                color: step.kind === "llm" ? "#c8a96e" : "#7cb9c8",
                border: `1px solid ${step.kind === "llm" ? "#c8a96e" : "#7cb9c8"}20`,
                background: `${step.kind === "llm" ? "#c8a96e" : "#7cb9c8"}08`,
              }}
            >
              {step.label}
            </div>
            <span
              className="font-mono text-[9px] tracking-[0.15em] uppercase"
              style={{ color: step.kind === "llm" ? "#c8a96e40" : "#7cb9c840" }}
            >
              {step.kind === "llm" ? "LLM" : "Det."}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <span className="font-mono text-[11px] text-[#2a2a2a] mt-1.5 mx-1.5">→</span>
          )}
        </div>
      ))}
    </div>
  );
}
