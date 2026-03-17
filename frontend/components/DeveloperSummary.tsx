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
    value >= 0.9 ? "bg-[#8ab58a]" : value >= 0.7 ? "bg-[#c8a96e]" : "bg-[#c84b4b]";
  return (
    <div className="w-14 h-1.5 bg-[#1a1a1a] rounded-full overflow-hidden shrink-0">
      <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function ConfidenceLabel({ value }: { value: number }) {
  const color =
    value >= 0.9
      ? "text-[#8ab58a]"
      : value >= 0.7
      ? "text-[#c8a96e]"
      : "text-[#c84b4b]";
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
      <section className="border border-[#1a1a1a] rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-[#1a1a1a]">
          <h2 className="font-mono text-[11px] tracking-[0.3em] text-[#3a3a3a] uppercase">
            Stack Detection
          </h2>
        </div>

        {rows.length === 0 ? (
          <p className="px-6 py-4 font-mono text-[12px] text-[#4a4a4a]">No frameworks detected.</p>
        ) : (
          <div>
            {rows.map(({ cat, item, key }) => (
              <div key={key} className="border-b border-[#1a1a1a]/50 last:border-0">
                <button
                  className="w-full flex items-center gap-3 px-6 py-3 hover:bg-[#161616] transition-colors text-left"
                  onClick={() => toggle(key)}
                >
                  <span className="w-16 font-mono text-[11px] text-[#3a3a3a] capitalize shrink-0">
                    {cat}
                  </span>
                  <span className="flex-1 font-sans text-[13px] text-[#c8c0b8]">{item.name}</span>
                  <ConfidenceBar value={item.confidence} />
                  <ConfidenceLabel value={item.confidence} />
                  <span className="font-mono text-[10px] text-[#2a2a2a] w-3 shrink-0">
                    {expanded === key ? "▲" : "▼"}
                  </span>
                </button>

                {expanded === key && (
                  <div className="px-6 pb-3 pl-[6.5rem] space-y-1">
                    {item.evidence.length > 0 ? (
                      item.evidence.map((ev, i) => (
                        <span
                          key={i}
                          className="block font-mono text-[11px] text-[#5a5a5a] bg-[#171717] px-2 py-0.5 rounded"
                        >
                          {ev}
                        </span>
                      ))
                    ) : (
                      <span className="font-mono text-[11px] text-[#2a2a2a] italic">
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

      {/* Technical */}
      {developer_summary && (
        <section className="border border-[#1a1a1a] rounded-lg p-6 space-y-3">
          <h2 className="font-mono text-[11px] tracking-[0.3em] text-[#3a3a3a] uppercase">
            Technical
          </h2>
          <div className="space-y-3">
            {developer_summary.split("\n").filter((l) => l.trim() !== "").map((line, i) => {
              const trimmed = line.trim();
              const isBullet = trimmed.startsWith("•") || trimmed.startsWith("*") || trimmed.startsWith("-");
              if (isBullet) {
                const content = trimmed.replace(/^[•*-]\s*/, "");
                return (
                  <div key={i} className="flex items-start gap-2">
                    <span className="text-[#7cb9c8] mt-0.5 shrink-0">•</span>
                    <span className="font-sans text-[13px] text-[#8a8a8a] leading-relaxed">{content}</span>
                  </div>
                );
              }
              return (
                <p key={i} className="font-mono text-[11px] text-[#3a3a3a] uppercase tracking-widest pt-2 first:pt-0">
                  {trimmed}
                </p>
              );
            })}
          </div>
        </section>
      )}

      {/* Caveats / Unknowns */}
      {caveats.length > 0 && (
        <section className="border border-[#c8a96e]/20 rounded-lg p-6">
          <h2 className="font-mono text-[11px] tracking-[0.3em] text-[#c8a96e] uppercase mb-3">
            Unknowns
          </h2>
          <ul className="space-y-1">
            {caveats.map((c, i) => (
              <li key={i} className="font-mono text-[11px] text-[#c8a96e]/70">
                {c}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
