interface PipelineBadgeProps {
  variant?: "full" | "compact";
}

const STEPS = [
  { label: "Fetch", kind: "det", desc: "Repository tree + priority files" },
  { label: "Resolve", kind: "det", desc: "Frameworks, manifests, routes, graph clues" },
  { label: "Score", kind: "det", desc: "Evidence-backed findings and confidence" },
  { label: "Explain", kind: "llm", desc: "LLM turns evidence into human-readable output" },
] as const;

export default function PipelineBadge({ variant = "compact" }: PipelineBadgeProps) {
  if (variant === "compact") {
    return (
      <div className="flex items-center gap-2 flex-wrap">
        <span
          className="font-mono text-[10px] tracking-[0.2em] uppercase px-2.5 py-1 rounded"
          style={{ color: "#8eb1ff", border: "1px solid #8eb1ff25", background: "#8eb1ff10" }}
        >
          Deterministic core
        </span>
        <span className="font-mono text-[10px] text-[#62779d]">→</span>
        <span
          className="font-mono text-[10px] tracking-[0.2em] uppercase px-2.5 py-1 rounded"
          style={{ color: "#c5b3ff", border: "1px solid #c5b3ff25", background: "#c5b3ff10" }}
        >
          LLM explanation layer
        </span>
        <a
          href="/how-it-works"
          className="font-mono text-[10px] text-[#7a8dad] hover:text-[#dbe7ff] transition-colors"
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
                color: step.kind === "llm" ? "#c5b3ff" : "#8eb1ff",
                border: `1px solid ${step.kind === "llm" ? "#c5b3ff" : "#8eb1ff"}20`,
                background: `${step.kind === "llm" ? "#c5b3ff" : "#8eb1ff"}10`,
              }}
            >
              {step.label}
            </div>
            <span
              className="font-mono text-[9px] tracking-[0.15em] uppercase"
              style={{ color: step.kind === "llm" ? "#c5b3ff80" : "#8eb1ff80" }}
            >
              {step.kind === "llm" ? "LLM" : "Det."}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <span className="font-mono text-[11px] text-[#62779d] mt-1.5 mx-1.5">→</span>
          )}
        </div>
      ))}
    </div>
  );
}
