import Link from "next/link";

import RepoUrlForm from "@/components/RepoUrlForm";
import SampleRepos from "@/components/SampleRepos";
import PipelineBadge from "@/components/atlas/PipelineBadge";
import OpsSnapshot from "@/components/workspace/OpsSnapshot";
import RecentRepos from "@/components/workspace/RecentRepos";
import RecentPublicRuns from "@/components/workspace/RecentPublicRuns";
import RecentRuns from "@/components/workspace/RecentRuns";

const HERO_NOTES = [
  { label: "Primary flow", value: "Scout -> Atlas -> Map -> Review" },
  { label: "Input", value: "Public GitHub repositories only" },
] as const;

const QUESTIONS = [
  "Where is the real app entrypoint?",
  "What framework and runtime am I looking at?",
  "How are routes grouped and exposed?",
  "Is this repo safe enough to build on?",
] as const;

const TOOL_CARDS = [
  {
    name: "Atlas",
    href: "/#analyze",
    accent: "#4d7cff",
    title: "Understand the system before you read the whole repo",
    body:
      "Paste a repository URL and get architecture, frameworks, stack clues, and plain-English summaries grounded in real files.",
    points: ["Architecture summary", "Mermaid diagram"],
  },
  {
    name: "RepoScout",
    href: "/scout",
    accent: "#35c58b",
    title: "Find a repo worth your time",
    body:
      "Search GitHub and GitLab together, rank by quality and relevance, and cut down the noise before deep analysis starts.",
    points: ["Quality ranking", "Intent-aware search"],
  },
  {
    name: "Map",
    href: "/map",
    accent: "#7ec8ff",
    title: "Chart the API surface quickly",
    body:
      "Detect the framework, extract routes with targeted patterns, and group the API surface so you can orient fast.",
    points: ["Endpoint extraction", "Grouped surface"],
  },
  {
    name: "Review",
    href: "/review",
    accent: "#c5b3ff",
    title: "Review operational and code quality risk",
    body:
      "Run a deeper evidence-backed pass across security, testing, reliability, and maintainability with confidence-aware scoring.",
    points: ["Evidence-backed findings", "Scorecard"],
  },
] as const;

const DELIVERY_STEPS = [
  {
    number: "01",
    title: "Pick the right repository",
    body: "Use RepoScout when you need candidates, or jump straight into Atlas if you already have a repository in mind.",
  },
  {
    number: "02",
    title: "Build orientation quickly",
    body: "Atlas collects manifests, tree structure, and high-signal files first, then turns those facts into a readable system view.",
  },
  {
    number: "03",
    title: "Drill into APIs and risk",
    body: "Map and Review cover the two most common next questions: what surface area exists and whether the repo looks production-ready.",
  },
] as const;

export default function HomePage() {
  return (
    <div className="page-shell">
      <section className="page-hero">
        <div className="grid gap-10 lg:grid-cols-[1.15fr_0.85fr] lg:items-start">
          <div>
            <div className="mb-5 flex flex-wrap items-center gap-3">
              <span className="hero-kicker">
                Public repository workspace
              </span>
            </div>

            <h1 className="hero-title max-w-4xl sm:max-w-[12ch] lg:max-w-[12ch]">
              Code understanding
              <br />
              for real repository decisions.
            </h1>

            <p className="hero-copy mt-6 max-w-2xl">
              CodebaseAtlas turns repository sprawl into a usable workspace. Scout candidates,
              explain architecture, map APIs, and review engineering risk without pretending
              the LLM did the hard deterministic work.
            </p>

            <div className="mt-8 panel-strong rounded-[28px] p-5 sm:p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-[#a9c2ff]">
                    Start With Atlas
                  </p>
                  <p className="mt-2 text-sm leading-relaxed text-[#8ea3c7]">
                    Paste one public GitHub repository and open the core analysis flow.
                  </p>
                </div>
                <PipelineBadge variant="compact" />
              </div>

              <div className="mt-5">
                <RepoUrlForm />
              </div>

              <RecentRepos />
              <RecentRuns />
              <RecentPublicRuns />

              <div className="mt-5 border-t border-white/10 pt-5">
                <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.24em] text-[#6d7f9f]">
                  Sample repositories
                </p>
                <SampleRepos />
              </div>
            </div>

            <div className="mt-6 grid gap-3 md:grid-cols-2">
              {HERO_NOTES.map((item) => (
                <div key={item.label} className="surface-note">
                  <p className="surface-note-title">
                    {item.label}
                  </p>
                  <p className="surface-note-copy">
                    {item.value}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="panel-strong rounded-[28px] p-5 sm:p-6">
            <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-[#c5b3ff]">
              Workspace Preview
            </p>
            <h2 className="mt-2 max-w-sm text-2xl font-semibold tracking-[-0.03em] text-[#f5f7ff]">
              Search-first, then move into concrete analysis.
            </h2>

            <div className="mt-6 rounded-3xl border border-white/10 bg-[#07101d] p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-[#ff7a90]" />
                <span className="h-2.5 w-2.5 rounded-full bg-[#ffd36e]" />
                <span className="h-2.5 w-2.5 rounded-full bg-[#35c58b]" />
                <span className="ml-3 font-mono text-[10px] uppercase tracking-[0.2em] text-[#6d7f9f]">
                  codebaseatlas workspace
                </span>
              </div>

              <div className="mt-4 rounded-2xl border border-[#4d7cff]/20 bg-[#0b1423] px-4 py-3 font-mono text-[12px] text-[#d9e6ff]">
                &gt; Understand `vercel/next.js` and show the API surface
              </div>

              <div className="mt-4">
                <PreviewPanel title="What this workspace answers well" accent="#4d7cff" items={QUESTIONS} />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="py-10">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-[#6d7f9f]">
              One Workspace, Four Jobs
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-[#f5f8ff]">
              Keep the current product surface. Present it like a platform.
            </h2>
          </div>
          <Link
            href="/how-it-works"
            className="rounded-full border border-white/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.18em] text-[#b7c8e8] hover:border-[#4d7cff]/30 hover:text-white"
          >
            Read the pipeline
          </Link>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {TOOL_CARDS.map((tool) => (
            <ToolCard key={tool.name} {...tool} />
          ))}
        </div>
      </section>

      <section className="py-10">
        <div className="mb-6">
          <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-[#6d7f9f]">
            Working Flow
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-[#f5f8ff]">
            A strong product flow is a clear sequence, not a long roadmap.
          </h2>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {DELIVERY_STEPS.map((step) => (
            <div key={step.number} className="panel rounded-[24px] p-5">
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-[#4d7cff]/25 bg-[#4d7cff]/10 font-mono text-[11px] tracking-[0.2em] text-[#b8ccff]">
                {step.number}
              </span>
              <h3 className="mt-4 text-xl font-semibold text-[#f4f8ff]">{step.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-[#94a8cb]">{step.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="py-10">
        <OpsSnapshot />
      </section>

      <section id="analyze" className="py-10">
        <div className="panel-strong rounded-[32px] p-6 sm:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-[#a9c2ff]">
                Ready To Run
              </p>
              <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-[-0.03em] text-[#f5f8ff]">
                Open the workspace with the repo you actually care about.
              </h2>
              <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-[#96aad0]">
                Atlas is still the best first step when you already know the repository.
                Scout is there when you need to discover candidates first.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              <Link
                href="/scout"
                className="rounded-full border border-white/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.18em] text-[#c2d3f2] hover:border-[#35c58b]/40 hover:text-white"
              >
                Open RepoScout
              </Link>
              <Link
                href="/review"
                className="rounded-full border border-white/10 px-4 py-2 font-mono text-[11px] uppercase tracking-[0.18em] text-[#c2d3f2] hover:border-[#c5b3ff]/40 hover:text-white"
              >
                Open Review
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function ToolCard({
  name,
  href,
  accent,
  title,
  body,
  points,
}: {
  name: string;
  href: string;
  accent: string;
  title: string;
  body: string;
  points: readonly string[];
}) {
  return (
    <Link
      href={href}
      className="panel group rounded-[26px] p-5 hover:-translate-y-0.5 hover:border-white/20"
    >
      <div className="flex items-center gap-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.22em]" style={{ color: accent }}>
          {name}
        </span>
      </div>
      <h3 className="mt-4 text-xl font-semibold leading-tight text-[#f5f8ff]">{title}</h3>
      <p className="mt-3 text-sm leading-relaxed text-[#94a8cb]">{body}</p>
      <div className="mt-5 flex flex-wrap gap-2">
        {points.map((point) => (
          <span
            key={point}
            className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 font-mono text-[10px] text-[#b7c8e8]"
          >
            {point}
          </span>
        ))}
      </div>
      <div className="mt-5 font-mono text-[11px] uppercase tracking-[0.18em]" style={{ color: accent }}>
        Open {name} →
      </div>
    </Link>
  );
}

function PreviewPanel({
  title,
  accent,
  items,
}: {
  title: string;
  accent: string;
  items: readonly string[];
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-4">
      <p className="font-mono text-[10px] uppercase tracking-[0.22em]" style={{ color: accent }}>
        {title}
      </p>
      <div className="mt-3 space-y-2">
        {items.map((item) => (
          <div key={item} className="flex items-start gap-3">
            <span className="mt-1 h-1.5 w-1.5 rounded-full" style={{ backgroundColor: accent }} />
            <p className="text-sm leading-relaxed text-[#dbe5f8]">{item}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
