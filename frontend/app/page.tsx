"use client";

import RepoUrlForm from "@/components/RepoUrlForm";
import SampleRepos from "@/components/SampleRepos";
import PipelineBadge from "@/components/atlas/PipelineBadge";

export default function HomePage() {
  return (
    <div className="max-w-6xl mx-auto px-6">

      {/* ── Platform hero ────────────────────────────────────────────── */}
      <section className="pt-20 pb-16 border-b border-[#1a1a1a]">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-12 items-end">
          <div>
            {/* Eyebrow */}
            <div className="flex flex-wrap items-center gap-3 mb-6">
              <span className="font-mono text-[10px] tracking-[0.3em] text-[#c8a96e] uppercase">
                Developer Toolkit
              </span>
              <span className="h-px bg-[#1e1e1e] w-10" />
              <a
                href="https://github.com/MentalVibez/AI_Architecture_Explainer"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-2.5 py-1 border border-[#1e1e1e] rounded-full
                           font-mono text-[10px] text-[#3a3a3a] hover:text-[#5a5a5a]
                           hover:border-[#2a2a2a] transition-colors"
              >
                <span>★</span>
                <span>Star on GitHub</span>
              </a>
            </div>

            {/* Headline */}
            <h1 className="font-serif text-5xl sm:text-6xl lg:text-7xl leading-[0.95] tracking-[-0.02em] text-[#e8e0d4] mb-6">
              Find the repo.<br />
              <em className="text-[#c8a96e] not-italic">Understand</em> it.
            </h1>

            <p className="font-sans text-[#6a6a6a] text-lg leading-relaxed max-w-xl mb-8">
              Save hours of onboarding time. Three instruments, one workflow.
              RepoScout discovers and ranks repositories by intent and quality.
              Atlas explains the architecture. Map charts the full API surface —
              deterministically, without guesswork.
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap gap-3">
              <a
                href="/#analyze"
                className="inline-flex items-center gap-2 px-6 py-3 bg-[#c8a96e] text-[#0a0a0a]
                           font-mono text-[12px] tracking-widest uppercase rounded
                           hover:bg-[#d4b87a] transition-colors"
              >
                Analyze a repo →
              </a>
              <a
                href="/scout"
                className="inline-flex items-center gap-2 px-6 py-3 border border-[#1e1e1e]
                           text-[#4a4a4a] font-mono text-[12px] tracking-widest uppercase rounded
                           hover:border-[#2a2a2a] hover:text-[#6a6a6a] transition-colors"
              >
                Scout repos
              </a>
            </div>

            {/* Pipeline trust signal */}
            <div className="mt-6">
              <PipelineBadge variant="compact" />
            </div>
          </div>

          {/* Workflow diagram */}
          <div className="hidden lg:flex flex-col gap-2 font-mono text-[11px] tracking-wider">
            {[
              { n: "01", label: "Search",  tool: "RepoScout" },
              { n: "→",  label: "",        tool: "" },
              { n: "02", label: "Analyze", tool: "Atlas" },
              { n: "→",  label: "",        tool: "" },
              { n: "03", label: "Map",     tool: "Map" },
              { n: "→",  label: "",        tool: "" },
              { n: "✓",  label: "Done",    tool: "" },
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

      {/* ── Trust strip ──────────────────────────────────────────────── */}
      <section className="py-7 border-b border-[#1a1a1a]">
        <div className="flex flex-wrap items-center gap-x-10 gap-y-3">
          <span className="font-mono text-[10px] tracking-[0.3em] text-[#2a2a2a] uppercase shrink-0">
            Works with
          </span>
          <div className="flex flex-wrap items-center gap-x-7 gap-y-2">
            {[
              { label: "GitHub",     accent: "#e8e0d4" },
              { label: "GitLab",     accent: "#e8e0d4" },
              { label: "Python",     accent: "#7cb9c8" },
              { label: "TypeScript", accent: "#7cb9c8" },
              { label: "Go",         accent: "#7cb9c8" },
              { label: "Rust",       accent: "#c8a96e" },
              { label: "Java",       accent: "#c8a96e" },
              { label: "Ruby",       accent: "#c84b4b" },
              { label: "PHP",        accent: "#8ab58a" },
              { label: "C#",         accent: "#9a7cb8" },
            ].map(({ label, accent }) => (
              <span
                key={label}
                className="font-mono text-[11px] tracking-wider"
                style={{ color: accent + "60" }}
              >
                {label}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── Tool cards ───────────────────────────────────────────────── */}
      <section className="py-14 border-b border-[#1a1a1a]">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
            signals={["Mermaid diagram", "Framework detection", "Technical", "Non-Technical"]}
            accent="#7cb9c8"
          />
          <ToolCard
            number="03"
            name="Map"
            href="/map"
            tagline="API surface"
            description="Paste a GitHub URL. Map detects the framework, selects targeted regex patterns, extracts every route, then uses Claude to group and describe the full API surface — no guessing required."
            cta="Map the API →"
            signals={["Framework-targeted", "Grouped endpoints", "Auth detection", "LLM-described"]}
            accent="#8ab58a"
          />
          <ToolCard
            number="04"
            name="Review"
            href="/review"
            tagline="Quality assessment"
            description="Evidence-backed scoring across security, testing, reliability, and maintainability. Deterministic rules, static analysis adapters, anti-gaming detection, and depth-aware confidence labels."
            cta="Review a repo →"
            signals={["Scorecard", "Findings", "Anti-gaming", "Depth-aware"]}
            accent="#9a7cb8"
            beta
          />
        </div>

        {/* Workflow connector — mobile */}
        <p className="mt-6 font-mono text-[11px] text-[#2a2a2a] tracking-widest text-center">
          REPOSCOUT → ATLAS → MAP → REVIEW (Beta)
        </p>
      </section>

      {/* ── Product preview ──────────────────────────────────────────── */}
      <section className="py-14 border-b border-[#1a1a1a]">
        <div className="flex items-center gap-3 mb-10">
          <span className="font-mono text-[10px] tracking-[0.3em] text-[#3a3a3a] uppercase">
            Sample output
          </span>
          <span className="h-px flex-1 bg-[#1a1a1a]" />
          <span className="font-mono text-[10px] text-[#2a2a2a]">github.com/vercel/next.js</span>
        </div>

        <div className="border border-[#1a1a1a] rounded-lg overflow-hidden">
          {/* Window chrome */}
          <div className="flex items-center gap-2 px-4 py-3 border-b border-[#1a1a1a] bg-[#0d0d0d]">
            <span className="w-2.5 h-2.5 rounded-full bg-[#1e1e1e]" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#1e1e1e]" />
            <span className="w-2.5 h-2.5 rounded-full bg-[#1e1e1e]" />
            <span className="ml-3 font-mono text-[11px] text-[#3a3a3a]">CodebaseAtlas — Atlas Report</span>
          </div>

          {/* Two-column result */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-[#1a1a1a]">

            {/* Diagram column */}
            <div className="bg-[#0f0f0f] p-6">
              <p className="font-mono text-[10px] tracking-[0.3em] text-[#7cb9c8] uppercase mb-4">
                Architecture Diagram
              </p>
              <div className="font-mono text-[11px] leading-loose text-[#3a3a3a] select-none">
                <p><span className="text-[#7cb9c8]">flowchart</span> <span className="text-[#c8a96e]">TD</span></p>
                {[
                  ["Browser", "NextApp"],
                  ["NextApp", "AppRouter"],
                  ["AppRouter", "ServerComponents"],
                  ["AppRouter", "APIRoutes"],
                  ["ServerComponents", "ReactCache"],
                  ["APIRoutes", "EdgeRuntime"],
                ].map(([a, b], i) => (
                  <p key={i} className="pl-4">
                    <span className="text-[#5a5a5a]">{a}</span>
                    <span className="text-[#2a2a2a]"> {"-->"} </span>
                    <span className="text-[#5a5a5a]">{b}</span>
                  </p>
                ))}
              </div>

              <div className="mt-5 pt-5 border-t border-[#1a1a1a]">
                <p className="font-mono text-[10px] tracking-[0.3em] text-[#3a3a3a] uppercase mb-3">
                  Stack detected
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {["Next.js 14", "React 18", "TypeScript", "Turbopack", "Edge Runtime"].map((t) => (
                    <span
                      key={t}
                      className="font-mono text-[10px] px-2 py-0.5 border border-[#1e1e1e] text-[#3a3a3a] rounded"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* Summaries column */}
            <div className="bg-[#0f0f0f] p-6 space-y-6">
              <div>
                <p className="font-mono text-[10px] tracking-[0.3em] text-[#7cb9c8] uppercase mb-3">
                  Technical
                </p>
                <div className="space-y-2">
                  {[
                    "App Router as the core routing layer with full RSC support",
                    "Turbopack replaces Webpack for sub-100ms HMR in dev",
                    "Edge-compatible API routes via Next.js Route Handlers",
                    "Streaming and Suspense boundaries throughout UI tree",
                  ].map((line) => (
                    <div key={line} className="flex items-start gap-2">
                      <span className="text-[#7cb9c8] mt-0.5 shrink-0 text-[10px]">•</span>
                      <span className="font-sans text-[12px] text-[#4a4a4a] leading-relaxed">{line}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="border-t border-[#1a1a1a] pt-5">
                <p className="font-mono text-[10px] tracking-[0.3em] text-[#c8a96e] uppercase mb-3">
                  Non-Technical
                </p>
                <div className="space-y-2">
                  {[
                    "The backbone framework powering most of today's React apps",
                    "Production-grade — used by Fortune 500s and thousands of startups",
                    "Demonstrates mastery of modern full-stack JavaScript architecture",
                  ].map((line) => (
                    <div key={line} className="flex items-start gap-2">
                      <span className="text-[#c8a96e] mt-0.5 shrink-0 text-[10px]">•</span>
                      <span className="font-sans text-[12px] text-[#4a4a4a] leading-relaxed">{line}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── How it works strip ───────────────────────────────────────── */}
      <section className="py-14 border-b border-[#1a1a1a]">
        <div className="flex items-center gap-3 mb-10">
          <span className="font-mono text-[10px] tracking-[0.3em] text-[#3a3a3a] uppercase">
            How it works
          </span>
          <span className="h-px flex-1 bg-[#1a1a1a]" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-[#1a1a1a] rounded-lg overflow-hidden">
          {[
            {
              step: "01",
              title: "Search",
              body: "RepoScout scans GitHub and GitLab simultaneously, scores each result for quality and relevance, and surfaces the repos actually worth your time.",
              accent: "#c8a96e",
            },
            {
              step: "02",
              title: "Analyze",
              body: "Paste any public GitHub URL into Atlas. It fetches the file tree, parses manifests deterministically, then generates an architecture diagram and plain-English summaries.",
              accent: "#7cb9c8",
            },
            {
              step: "03",
              title: "Understand",
              body: "Map charts every API endpoint. Review scores security, testing, and maintainability. Together they give you the full picture before you write a single line of code.",
              accent: "#8ab58a",
            },
          ].map(({ step, title, body, accent }) => (
            <div key={step} className="bg-[#0f0f0f] p-8 flex flex-col gap-4">
              <div
                className="font-mono text-[11px] tracking-[0.3em] uppercase w-8 h-8
                           flex items-center justify-center rounded border"
                style={{ color: accent, borderColor: `${accent}30`, backgroundColor: `${accent}08` }}
              >
                {step}
              </div>
              <h3 className="font-serif text-2xl text-[#e8e0d4]">{title}</h3>
              <p className="font-sans text-[13px] text-[#4a4a4a] leading-relaxed flex-1">{body}</p>
            </div>
          ))}
        </div>
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
            CodebaseAtlas
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
            { icon: "👩‍💻", title: "Technical",      body: "Entry points, responsibilities, dependencies, patterns." },
            { icon: "🤝", title: "Non-Technical",   body: "What the project does, skills demonstrated, complexity." },
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
  number, name, href, tagline, description, cta, signals, accent, beta,
}: {
  number: string;
  name: string;
  href: string;
  tagline: string;
  description: string;
  cta: string;
  signals: string[];
  accent: string;
  beta?: boolean;
}) {
  return (
    <a
      href={href}
      className="group relative border border-[#1a1a1a] rounded-lg p-7
                 hover:border-[#2a2a2a] transition-all duration-200
                 hover:bg-[#161616] flex flex-col gap-5 cursor-pointer"
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

      {/* Name + beta badge */}
      <div className="flex items-center gap-3">
        <h2 className="font-serif text-3xl text-[#e8e0d4] group-hover:text-white transition-colors">
          {name}
        </h2>
        {beta && (
          <span
            className="font-mono text-[9px] tracking-[0.2em] uppercase
                       px-2 py-0.5 border rounded self-start mt-1"
            style={{ color: accent, borderColor: accent + "40", backgroundColor: accent + "0d" }}
          >
            Beta
          </span>
        )}
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
