"use client";

import RepoUrlForm from "@/components/RepoUrlForm";
import SampleRepos from "@/components/SampleRepos";

export default function HomePage() {
  return (
    <div className="max-w-6xl mx-auto px-6">

      {/* ── Platform hero ────────────────────────────────────────────── */}
      <section className="pt-20 pb-16 border-b border-[#1a1a1a]">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-12 items-end">
          <div>
            {/* Eyebrow */}
            <div className="flex items-center gap-3 mb-6">
              <span className="font-mono text-[10px] tracking-[0.3em] text-[#c8a96e] uppercase">
                Developer Toolkit
              </span>
              <span className="flex-1 h-px bg-[#1e1e1e] max-w-[60px]" />
            </div>

            {/* Headline */}
            <h1 className="font-serif text-5xl sm:text-6xl lg:text-7xl leading-[0.95] tracking-[-0.02em] text-[#e8e0d4] mb-6">
              Find the repo.<br />
              <em className="text-[#c8a96e] not-italic">Understand</em> it.
            </h1>

            <p className="font-sans text-[#6a6a6a] text-lg leading-relaxed max-w-xl">
              Two instruments. One workflow. RepoScout discovers and ranks
              repositories by intent and quality. Atlas reads the winner and
              explains its architecture — deterministically, without guesswork.
            </p>
          </div>

          {/* Workflow diagram */}
          <div className="hidden lg:flex flex-col gap-2 font-mono text-[11px] tracking-wider">
            {[
              { n: "01", label: "Search", tool: "RepoScout" },
              { n: "→",  label: "",       tool: "" },
              { n: "02", label: "Analyze", tool: "Atlas" },
              { n: "→",  label: "",       tool: "" },
              { n: "✓",  label: "Done",   tool: "" },
            ].map((row, i) =>
              row.tool ? (
                <div key={i} className="flex items-center gap-3">
                  <span className="w-6 text-right text-[#c8a96e]">{row.n}</span>
                  <span className="text-[#2a2a2a]">{row.label}</span>
                  <span className="text-[#1e1e1e] mx-1">/</span>
                  <span className="text-[#3a3a3a]">{row.tool}</span>
                </div>
              ) : (
                <div key={i} className="flex items-center gap-3">
                  <span className="w-6 text-right text-[#2a2a2a]">{row.n}</span>
                </div>
              )
            )}
          </div>
        </div>
      </section>

      {/* ── Tool cards ───────────────────────────────────────────────── */}
      <section className="py-14 border-b border-[#1a1a1a]">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ToolCard
            number="01"
            name="RepoScout"
            href="/scout"
            tagline="Discovery + ranking"
            description="Search GitHub and GitLab simultaneously. Get credibility scores, noise suppression, intent-aware ranking, and a TLDR — so you know which repo to actually use before spending hours reading it."
            cta="Scout repos →"
            signals={["Quality score", "Relevance score", "Noise suppressed", "Intent-aware"]}
            accent="#c8a96e"
          />
          <ToolCard
            number="02"
            name="Atlas"
            href="/#analyze"
            tagline="Deep analysis"
            description="Paste a GitHub URL. Atlas fetches the repo tree, parses manifests, detects frameworks with deterministic heuristics, then generates an architecture diagram and dual plain-English summaries."
            cta="Analyze a repo →"
            signals={["Mermaid diagram", "Framework detection", "Dev summary", "Hiring summary"]}
            accent="#7cb9c8"
          />
        </div>

        {/* Workflow connector — mobile */}
        <p className="mt-6 font-mono text-[11px] text-[#2a2a2a] tracking-widest text-center">
          REPOSCOUT → ATLAS — the complete workflow
        </p>
      </section>

      {/* ── Atlas tool section ────────────────────────────────────────── */}
      <section id="analyze" className="py-16">

        {/* Section header */}
        <div className="flex items-center gap-4 mb-10">
          <span className="font-mono text-[10px] tracking-[0.3em] text-[#7cb9c8] uppercase">
            Tool 02
          </span>
          <span className="h-px flex-1 bg-[#1a1a1a] max-w-[40px]" />
          <h2 className="font-serif text-3xl text-[#e8e0d4]">
            Codebase Atlas
          </h2>
        </div>

        <RepoUrlForm />

        <div className="pt-6">
          <p className="font-mono text-[10px] text-[#2a2a2a] tracking-widest mb-3">
            Try a sample repo
          </p>
          <SampleRepos />
        </div>

        {/* What Atlas gives you — keep your existing section or use this */}
        <div className="mt-14 grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { icon: "🗺️", title: "Architecture diagram", body: "Mermaid flowchart from real file structure, not guesswork." },
            { icon: "🔍", title: "Framework detection",  body: "Frontend, backend, database, infra, testing — from manifests." },
            { icon: "👩‍💻", title: "Developer summary",   body: "Entry points, responsibilities, dependencies, patterns." },
            { icon: "🤝", title: "Hiring summary",       body: "What the project does, skills demonstrated, complexity." },
          ].map(({ icon, title, body }) => (
            <div
              key={title}
              className="border border-[#1a1a1a] p-5 rounded-lg hover:border-[#2a2a2a] transition-colors"
            >
              <span className="text-2xl block mb-3">{icon}</span>
              <h3 className="font-sans font-semibold text-[13px] text-[#c8c0b8] mb-1">{title}</h3>
              <p className="font-mono text-[11px] text-[#3a3a3a] leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

/* ── ToolCard ─────────────────────────────────────────────────────────────── */

function ToolCard({
  number, name, href, tagline, description, cta, signals, accent,
}: {
  number: string;
  name: string;
  href: string;
  tagline: string;
  description: string;
  cta: string;
  signals: string[];
  accent: string;
}) {
  return (
    <a
      href={href}
      className="group relative border border-[#1a1a1a] rounded-lg p-7
                 hover:border-[#2a2a2a] transition-all duration-200
                 hover:bg-[#0e0e0e] flex flex-col gap-5 cursor-pointer"
    >
      {/* Number + tagline */}
      <div className="flex items-center justify-between">
        <span
          className="font-mono text-[11px] tracking-[0.3em] uppercase"
          style={{ color: accent }}
        >
          {number}
        </span>
        <span className="font-mono text-[10px] tracking-widest text-[#2a2a2a] uppercase">
          {tagline}
        </span>
      </div>

      {/* Name */}
      <div>
        <h2 className="font-serif text-3xl text-[#e8e0d4] group-hover:text-white transition-colors">
          {name}
        </h2>
      </div>

      {/* Description */}
      <p className="font-sans text-[13px] text-[#5a5a5a] leading-relaxed flex-1">
        {description}
      </p>

      {/* Signal chips */}
      <div className="flex flex-wrap gap-1.5">
        {signals.map((s) => (
          <span
            key={s}
            className="font-mono text-[10px] tracking-wider px-2 py-0.5
                       border border-[#1e1e1e] text-[#2a2a2a] rounded"
          >
            {s}
          </span>
        ))}
      </div>

      {/* CTA */}
      <div className="flex items-center justify-between mt-1">
        <span
          className="font-mono text-[12px] tracking-wider group-hover:translate-x-0.5 transition-transform"
          style={{ color: accent }}
        >
          {cta}
        </span>
        <span
          className="w-5 h-5 border rounded-full flex items-center justify-center
                     text-[10px] opacity-0 group-hover:opacity-100 transition-opacity"
          style={{ borderColor: accent, color: accent }}
        >
          →
        </span>
      </div>

      {/* Accent bar on hover */}
      <span
        className="absolute bottom-0 left-0 h-0.5 w-0 group-hover:w-full
                   transition-all duration-300 rounded-b-lg"
        style={{ backgroundColor: accent }}
      />
    </a>
  );
}
