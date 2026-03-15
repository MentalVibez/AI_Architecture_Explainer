"use client";

import { useState } from "react";
import type { AnalysisResult } from "@/lib/types";
import { normalizeStackItems } from "@/lib/types";

interface Props {
  result: AnalysisResult;
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    value >= 0.9 ? "bg-green-500" : value >= 0.7 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="w-14 h-1.5 bg-gray-700 rounded-full overflow-hidden shrink-0">
      <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function ConfidenceLabel({ value }: { value: number }) {
  const color =
    value >= 0.9
      ? "text-green-400"
      : value >= 0.7
      ? "text-yellow-400"
      : "text-red-400";
  return (
    <span className={`font-mono text-xs w-8 text-right shrink-0 ${color}`}>
      {value.toFixed(2)}
    </span>
  );
}

const CATEGORY_ORDER = ["backend", "frontend", "database", "infra", "testing"] as const;

export default function DeveloperSummary({ result }: Props) {
  const { detected_stack, developer_summary, caveats } = result;
  const [expanded, setExpanded] = useState<string | null>(null);

  const rows = CATEGORY_ORDER.flatMap((cat) => {
    const items = normalizeStackItems(detected_stack[cat] ?? []);
    return items.map((item) => ({ cat, item, key: `${cat}-${item.name}` }));
  });

  const toggle = (key: string) =>
    setExpanded((prev) => (prev === key ? null : key));

  return (
    <div className="space-y-6">

      {/* Stack Detection */}
      <section className="bg-gray-900 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-800">
          <h2 className="text-xs font-mono font-semibold text-gray-400 uppercase tracking-widest">
            Stack Detection
          </h2>
        </div>

        {rows.length === 0 ? (
          <p className="px-6 py-4 text-sm text-gray-500">No frameworks detected.</p>
        ) : (
          <div>
            {rows.map(({ cat, item, key }) => (
              <div key={key} className="border-b border-gray-800/50 last:border-0">
                <button
                  className="w-full flex items-center gap-3 px-6 py-3 hover:bg-gray-800/50 transition-colors text-left"
                  onClick={() => toggle(key)}
                >
                  <span className="w-16 text-xs text-gray-500 font-mono capitalize shrink-0">
                    {cat}
                  </span>
                  <span className="flex-1 text-sm font-medium">{item.name}</span>
                  <ConfidenceBar value={item.confidence} />
                  <ConfidenceLabel value={item.confidence} />
                  <span className="text-gray-600 text-xs w-3 shrink-0">
                    {expanded === key ? "▲" : "▼"}
                  </span>
                </button>

                {expanded === key && (
                  <div className="px-6 pb-3 pl-[6.5rem] space-y-1">
                    {item.evidence.length > 0 ? (
                      item.evidence.map((ev, i) => (
                        <span
                          key={i}
                          className="block font-mono text-xs text-gray-400 bg-gray-800/60 px-2 py-0.5 rounded"
                        >
                          {ev}
                        </span>
                      ))
                    ) : (
                      <span className="text-xs text-gray-600 italic">
                        No evidence recorded
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Technical View */}
      {developer_summary && (
        <section className="bg-gray-900 rounded-xl p-6 space-y-3">
          <h2 className="text-xs font-mono font-semibold text-gray-400 uppercase tracking-widest">
            Technical View
          </h2>
          <div className="space-y-3">
            {developer_summary.split("\n").filter((l) => l.trim() !== "").map((line, i) => {
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
        </section>
      )}

      {/* Caveats / Unknowns */}
      {caveats.length > 0 && (
        <section className="bg-gray-900 rounded-xl p-6">
          <h2 className="text-xs font-mono font-semibold text-yellow-500/70 uppercase tracking-widest mb-3">
            Unknowns
          </h2>
          <ul className="space-y-1">
            {caveats.map((c, i) => (
              <li key={i} className="text-xs text-yellow-300 font-mono">
                {c}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
