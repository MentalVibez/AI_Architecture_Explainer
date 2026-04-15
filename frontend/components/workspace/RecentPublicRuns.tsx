"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getRecentRuns } from "@/lib/api";
import type { RecentRunItem } from "@/lib/types";

const KIND_LABELS = {
  atlas: "Atlas",
  review: "Review",
} as const;

export default function RecentPublicRuns() {
  const [items, setItems] = useState<RecentRunItem[]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await getRecentRuns(6);
        if (!cancelled) {
          setItems(response.items);
        }
      } catch {
        if (!cancelled) {
          setError(true);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  if (error || items.length === 0) {
    return null;
  }

  return (
    <div className="mt-5 border-t border-white/10 pt-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">
          Recent public runs
        </p>
        <p className="hidden font-mono text-[10px] text-[#5f7397] sm:block">
          Server-backed Atlas and Review history.
        </p>
      </div>
      <div className="mt-3 grid gap-3">
        {items.map((run) => (
          <Link
            key={`${run.kind}-${run.id}`}
            href={run.href}
            className="surface-note hover:border-white/20 hover:bg-white/[0.05]"
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.16em] text-[#b7c8e8]">
                    {KIND_LABELS[run.kind]}
                  </span>
                  <p className="truncate text-sm font-semibold text-[#edf4ff]">{run.repo}</p>
                </div>
                <p className="mt-2 text-sm leading-relaxed text-[#94a8cb]">{run.title}</p>
              </div>
              <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[#7f95ba]">
                Open run →
              </p>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
