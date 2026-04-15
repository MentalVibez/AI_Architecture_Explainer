import type { AnalysisResult } from "@/lib/types";

interface Props {
  result: AnalysisResult;
}

function BulletSummary({ text }: { text: string }) {
  const lines = text.split("\n").filter((l) => l.trim() !== "");
  return (
    <div className="space-y-3">
      {lines.map((line, i) => {
        const trimmed = line.trim();
        const isBullet = trimmed.startsWith("•") || trimmed.startsWith("*") || trimmed.startsWith("-");
        if (isBullet) {
          const content = trimmed.replace(/^[•*-]\s*/, "");
          return (
            <div key={i} className="flex items-start gap-2">
              <span className="text-[#c5b3ff] mt-0.5 shrink-0">•</span>
              <span className="font-sans text-[13px] text-[#d7e4ff] leading-relaxed">{content}</span>
            </div>
          );
        }
        return (
          <p key={i} className="font-mono text-[11px] text-[#6d7f9f] uppercase tracking-widest pt-2 first:pt-0">
            {trimmed}
          </p>
        );
      })}
    </div>
  );
}

export default function HiringManagerSummary({ result }: Props) {
  const { hiring_manager_summary, confidence_score } = result;

  return (
    <section className="panel rounded-[28px] overflow-hidden">
      <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
        <h2 className="font-mono text-[11px] tracking-[0.24em] text-[#6d7f9f] uppercase">
          Non-Technical
        </h2>
        {confidence_score != null && (
          <span
            className={`font-mono text-[11px] ${
              confidence_score >= 0.7 ? "text-[#35c58b]" : confidence_score >= 0.4 ? "text-[#ffcb6b]" : "text-[#ff8d8d]"
            }`}
          >
            Confidence: {confidence_score.toFixed(2)}
          </span>
        )}
      </div>

      <div className="px-6 py-5">
        {hiring_manager_summary ? (
          <BulletSummary text={hiring_manager_summary} />
        ) : (
          <p className="font-mono text-[12px] text-[#94a8cb]">Summary not yet available.</p>
        )}
      </div>
    </section>
  );
}
