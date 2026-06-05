"use client";

import { useState } from "react";

type GenerateState =
  | { status: "idle" }
  | { status: "generating" }
  | { status: "done"; config: Record<string, unknown>; version: number }
  | { status: "error"; message: string }
  | { status: "unauthenticated" };

interface Props {
  jobId: number;
  repoLabel: string;
}

function statusAnnouncement(state: GenerateState): string {
  switch (state.status) {
    case "generating": return "Generating devcontainer configuration…";
    case "done": return `Devcontainer v${state.version} ready. You can download the ZIP or copy the JSON.`;
    case "error": return `Error: ${state.message}`;
    case "unauthenticated": return "Sign in with GitHub to generate your devcontainer.";
    default: return "";
  }
}

export default function DevcontainerPanel({ jobId, repoLabel }: Props) {
  const [state, setState] = useState<GenerateState>({ status: "idle" });
  const [copied, setCopied] = useState(false);

  async function generate() {
    setState({ status: "generating" });
    try {
      const res = await fetch(`/api/devcontainer/${jobId}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ languages: [], services: [], features: [] }),
      });

      if (res.status === 401) {
        setState({ status: "unauthenticated" });
        return;
      }
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        setState({ status: "error", message: body || `HTTP ${res.status}` });
        return;
      }

      const data = await res.json();
      setState({ status: "done", config: data.config, version: data.version_number });
    } catch (err) {
      setState({ status: "error", message: String(err) });
    }
  }

  async function copyJson() {
    if (state.status !== "done") return;
    await navigator.clipboard.writeText(JSON.stringify(state.config, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const announcement = statusAnnouncement(state);

  return (
    <div className="rounded-[28px] border border-emerald-500/15 bg-emerald-500/[0.04] p-6">
      {/* Screen-reader live region for status transitions */}
      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {announcement}
        {copied ? " JSON copied to clipboard." : ""}
      </div>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-emerald-400/80">
            DevContainer Generator
          </p>
          <h2 className="mt-1 text-lg font-semibold text-[#f5f8ff]">
            Ready to code in seconds
          </h2>
          <p className="mt-1 text-sm text-white/50">
            Generate a production-quality devcontainer.json tailored to{" "}
            <span className="font-mono text-white/70">{repoLabel}</span> using
            Claude&nbsp;analysis.
          </p>
        </div>

        {state.status === "idle" && (
          <button
            onClick={generate}
            className="shrink-0 rounded-full bg-emerald-600 px-5 py-2.5 font-mono text-[11px] uppercase tracking-[0.16em] text-white hover:bg-emerald-500 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
          >
            Generate DevContainer
          </button>
        )}

        {state.status === "generating" && (
          <div className="flex items-center gap-2 text-emerald-400" aria-hidden="true">
            <Spinner />
            <span className="font-mono text-[11px] tracking-wide">Generating…</span>
          </div>
        )}
      </div>

      {/* Unauthenticated */}
      {state.status === "unauthenticated" && (
        <div className="mt-4 flex items-center gap-3 rounded-xl border border-amber-500/20 bg-amber-500/8 px-4 py-3">
          <p className="text-sm text-amber-200">
            Sign in with GitHub to generate your devcontainer.
          </p>
          <a
            href="/api/auth/login"
            className="ml-auto shrink-0 rounded-full bg-amber-500/20 border border-amber-500/30 px-3 py-1.5 font-mono text-[11px] tracking-wide text-amber-200 hover:bg-amber-500/30 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
          >
            Sign in ↗
          </a>
        </div>
      )}

      {/* Error */}
      {state.status === "error" && (
        <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/8 px-4 py-3" role="alert">
          <p className="text-sm text-red-300">{state.message}</p>
          <button
            onClick={() => setState({ status: "idle" })}
            className="mt-2 font-mono text-[11px] text-red-400 hover:text-red-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"
          >
            Try again
          </button>
        </div>
      )}

      {/* Result */}
      {state.status === "done" && (
        <div className="mt-5 space-y-4">
          {/* Action bar */}
          <div className="flex flex-wrap gap-2">
            <a
              href={`/api/devcontainer/${jobId}/download?version=${state.version}`}
              className="rounded-full bg-emerald-600 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-white hover:bg-emerald-500 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
              download={`devcontainer-v${state.version}.zip`}
              aria-label={`Download devcontainer v${state.version} as ZIP`}
            >
              Download ZIP ↓
            </a>
            <button
              onClick={copyJson}
              aria-pressed={copied}
              className="rounded-full border border-white/15 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-[#c2d3f2] hover:bg-white/[0.04] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#4d7cff]"
            >
              {copied ? "Copied ✓" : "Copy JSON"}
            </button>
            <button
              onClick={() => setState({ status: "idle" })}
              className="rounded-full border border-white/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-white/40 hover:text-white/70 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
            >
              Regenerate
            </button>
          </div>

          {/* Usage hint */}
          <div className="rounded-xl border border-white/8 bg-white/[0.02] px-4 py-3 text-xs text-white/50 space-y-1">
            <p>
              <span className="text-white/70">Option A:</span> Extract the ZIP, place{" "}
              <code className="font-mono text-emerald-400">.devcontainer/</code> at your repo root,
              push to GitHub, then click{" "}
              <span className="font-mono text-white/70">Code → Codespaces → New codespace</span>.
            </p>
            <p>
              <span className="text-white/70">Option B:</span> Open the folder in VS Code and select{" "}
              <span className="font-mono text-white/70">Reopen in Container</span>.
            </p>
          </div>

          {/* JSON preview — tabIndex allows keyboard users to scroll */}
          <pre
            tabIndex={0}
            aria-label="Generated devcontainer.json"
            className="max-h-80 overflow-auto rounded-xl border border-white/8 bg-[#060e1a] p-4 font-mono text-[11px] leading-relaxed text-emerald-300/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
          >
            {JSON.stringify(state.config, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-20" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path
        className="opacity-80"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}
