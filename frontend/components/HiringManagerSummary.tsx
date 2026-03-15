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
              <span className="text-blue-400 mt-0.5 shrink-0">•</span>
              <span className="text-gray-300 text-sm leading-relaxed">{content}</span>
            </div>
          );
        }
        return (
          <p key={i} className="text-gray-400 text-xs font-mono uppercase tracking-widest pt-2 first:pt-0">
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
    <section className="bg-gray-900 rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
        <h2 className="text-xs font-mono font-semibold text-gray-400 uppercase tracking-widest">
          Non-Technical View
        </h2>
        {confidence_score != null && (
          <span
            className={`font-mono text-xs ${
              confidence_score >= 0.7
                ? "text-green-400"
                : confidence_score >= 0.4
                ? "text-yellow-400"
                : "text-red-400"
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
          <p className="text-gray-500 text-sm">Summary not yet available.</p>
        )}
      </div>
    </section>
  );
}
