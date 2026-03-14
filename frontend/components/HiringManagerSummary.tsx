import type { AnalysisResult } from "@/lib/types";

interface Props {
  result: AnalysisResult;
}

export default function HiringManagerSummary({ result }: Props) {
  const { hiring_manager_summary, confidence_score } = result;

  const confidenceLabel =
    confidence_score == null
      ? null
      : confidence_score >= 0.7
      ? "High"
      : confidence_score >= 0.4
      ? "Medium"
      : "Low";

  const confidenceColor =
    confidenceLabel === "High"
      ? "text-green-400"
      : confidenceLabel === "Medium"
      ? "text-yellow-400"
      : "text-red-400";

  return (
    <section className="bg-gray-900 rounded-xl p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Hiring Manager View</h2>
        {confidenceLabel && (
          <span className={`text-xs font-medium ${confidenceColor}`}>
            Confidence: {confidenceLabel}
          </span>
        )}
      </div>

      {hiring_manager_summary ? (
        <p className="text-gray-300 text-sm leading-relaxed">{hiring_manager_summary}</p>
      ) : (
        <p className="text-gray-500 text-sm">Summary not yet available.</p>
      )}
    </section>
  );
}
