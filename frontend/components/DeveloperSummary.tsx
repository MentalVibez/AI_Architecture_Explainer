import type { AnalysisResult } from "@/lib/types";

interface Props {
  result: AnalysisResult;
}

export default function DeveloperSummary({ result }: Props) {
  const { detected_stack, developer_summary, entry_points, caveats } = result;

  return (
    <section className="bg-gray-900 rounded-xl p-6 space-y-4">
      <h2 className="text-lg font-semibold">Developer View</h2>

      {developer_summary && (
        <p className="text-gray-300 text-sm leading-relaxed">{developer_summary}</p>
      )}

      <div>
        <h3 className="text-sm font-medium text-gray-400 mb-2">Detected Stack</h3>
        <div className="flex flex-wrap gap-2">
          {Object.entries(detected_stack)
            .flatMap(([, items]) => items)
            .map((item) => (
              <span
                key={item}
                className="px-2 py-1 bg-blue-900/40 text-blue-300 rounded text-xs"
              >
                {item}
              </span>
            ))}
        </div>
      </div>

      {entry_points.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-400 mb-2">Entry Points</h3>
          <ul className="space-y-1">
            {entry_points.map((ep) => (
              <li key={ep} className="font-mono text-xs text-gray-300">{ep}</li>
            ))}
          </ul>
        </div>
      )}

      {caveats.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-yellow-500 mb-2">Caveats</h3>
          <ul className="space-y-1">
            {caveats.map((c, i) => (
              <li key={i} className="text-xs text-yellow-300">{c}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
