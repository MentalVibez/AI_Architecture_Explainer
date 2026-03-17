import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "How It Works — CodebaseAtlas",
  description: "Technical documentation: how CodebaseAtlas analyzes repositories, what Claude is used for, how confidence scores work, and data handling.",
};

export default function HowItWorksPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-20">

      {/* Header */}
      <div className="mb-12">
        <div className="flex items-center gap-3 mb-6">
          <span className="font-mono text-[10px] tracking-[0.3em] text-[#c8a96e] uppercase">Docs</span>
          <span className="h-px w-8 bg-[#1e1e1e]" />
        </div>
        <h1 className="font-serif text-5xl text-[#e8e0d4] mb-4">How It Works</h1>
        <p className="font-sans text-[#5a5a5a] text-lg leading-relaxed">
          A technical overview of the CodebaseAtlas analysis pipeline —
          what each step does, what the LLM is and isn&apos;t responsible for,
          and how your data is handled.
        </p>
      </div>

      <div className="space-y-14 font-sans text-[14px] text-[#5a5a5a] leading-relaxed">

        {/* Pipeline */}
        <Section title="The analysis pipeline">
          <p className="mb-6">
            When you submit a GitHub URL to Atlas, the backend runs through five
            deterministic stages before the LLM ever sees any data:
          </p>
          <div className="space-y-4">
            {[
              {
                step: "01",
                title: "GitHub API fetch",
                color: "#c8a96e",
                body: "The backend calls the GitHub REST API to fetch the repository file tree and the content of high-priority files (package.json, requirements.txt, Dockerfile, README, etc.). Only file names and manifest contents are read — source code is not sent anywhere.",
              },
              {
                step: "02",
                title: "Manifest parsing",
                color: "#c8a96e",
                body: "manifest_parser.py deterministically extracts dependency lists from package.json, requirements.txt, pyproject.toml, Cargo.toml, go.mod, and similar files. No AI is involved — this is pattern matching and JSON parsing.",
              },
              {
                step: "03",
                title: "Framework detection",
                color: "#7cb9c8",
                body: "framework_detector.py uses heuristic rules to classify the tech stack: frontend framework, backend framework, database, infrastructure tooling, and testing setup. Evidence is collected for each inference.",
              },
              {
                step: "04",
                title: "Evidence object construction",
                color: "#7cb9c8",
                body: "A structured evidence object is assembled from the parsed manifests and detected frameworks. This is what gets sent to the LLM — not raw file contents. The LLM never invents dependencies or frameworks; it only describes what the evidence shows.",
              },
              {
                step: "05",
                title: "LLM analysis (Claude)",
                color: "#8ab58a",
                body: "Claude receives the evidence object and generates: a Mermaid architecture diagram, a developer-focused technical summary, and a non-technical summary for hiring managers. Tool-use (structured output) ensures the response is machine-parseable.",
              },
            ].map(({ step, title, color, body }) => (
              <div key={step} className="flex gap-5 group">
                <div className="flex flex-col items-center gap-1 shrink-0">
                  <div
                    className="w-8 h-8 rounded flex items-center justify-center font-mono text-[11px]"
                    style={{ color, border: `1px solid ${color}30`, backgroundColor: `${color}08` }}
                  >
                    {step}
                  </div>
                  <div className="w-px flex-1 bg-[#1a1a1a]" />
                </div>
                <div className="pb-6">
                  <h3 className="font-serif text-lg text-[#c8c0b8] mb-2">{title}</h3>
                  <p>{body}</p>
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* LLM scope */}
        <Section title="What Claude is and isn't responsible for">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="border border-[#6dba8a]/15 rounded-lg p-5 bg-[#6dba8a]/3">
              <p className="font-mono text-[10px] tracking-[0.25em] text-[#6dba8a]/70 uppercase mb-3">
                LLM is used for
              </p>
              <ul className="space-y-2 list-none">
                {[
                  "Architecture diagram (Mermaid syntax)",
                  "Technical summary",
                  "Non-Technical summary",
                  "Grouping and describing API endpoints",
                  "Quality finding descriptions",
                ].map((t) => (
                  <li key={t} className="flex gap-2 text-[#4a4a4a]">
                    <span className="text-[#6dba8a]/50 shrink-0">✓</span>
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="border border-[#b86a6a]/15 rounded-lg p-5 bg-[#b86a6a]/3">
              <p className="font-mono text-[10px] tracking-[0.25em] text-[#b86a6a]/70 uppercase mb-3">
                LLM is NOT used for
              </p>
              <ul className="space-y-2 list-none">
                {[
                  "Detecting dependencies",
                  "Identifying frameworks",
                  "Fetching or reading file content",
                  "Calculating confidence scores",
                  "Extracting API routes",
                ].map((t) => (
                  <li key={t} className="flex gap-2 text-[#4a4a4a]">
                    <span className="text-[#b86a6a]/50 shrink-0">✗</span>
                    <span>{t}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <p className="mt-4 text-[13px] text-[#4a4a4a]">
            This separation means that framework detection and dependency parsing are
            fully deterministic and testable — results are reproducible. The LLM adds
            human-readable interpretation on top of verified evidence.
          </p>
        </Section>

        {/* Confidence scores */}
        <Section title="Confidence scores">
          <p>
            Each detected stack item (e.g., &ldquo;React&rdquo; in the frontend slot) carries a
            confidence score between 0 and 1. This score reflects how much file evidence
            supports the inference:
          </p>
          <div className="mt-4 space-y-2">
            {[
              { range: "0.80 – 1.0", label: "High", color: "#6dba8a", desc: "Multiple manifest files confirm the framework" },
              { range: "0.50 – 0.79", label: "Medium", color: "#c8a96e", desc: "Some evidence present, possibly inferred from file patterns" },
              { range: "0.0 – 0.49", label: "Low", color: "#b86a6a", desc: "Weak signal — treat as a best-guess" },
            ].map(({ range, label, color, desc }) => (
              <div key={range} className="flex items-start gap-4 border border-[#1a1a1a] rounded p-3">
                <div className="font-mono text-[11px] shrink-0 w-20" style={{ color }}>{range}</div>
                <div>
                  <span className="font-sans font-semibold text-[13px]" style={{ color }}>{label}</span>
                  <span className="text-[#4a4a4a] text-[13px]"> — {desc}</span>
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Data handling */}
        <Section title="Data handling and security">
          <div className="space-y-4">
            <div className="border border-[#1e1e1e] rounded-lg p-5">
              <p className="font-mono text-[10px] tracking-[0.2em] text-[#3a3a3a] uppercase mb-2">Public repos only</p>
              <p>
                CodebaseAtlas only works with public repositories. It uses the unauthenticated
                GitHub API by default, which can only access public data. No authentication
                to private repos is possible through this service.
              </p>
            </div>
            <div className="border border-[#1e1e1e] rounded-lg p-5">
              <p className="font-mono text-[10px] tracking-[0.2em] text-[#3a3a3a] uppercase mb-2">GitHub tokens</p>
              <p>
                RepoScout accepts an optional GitHub personal access token to raise the API
                rate limit. <strong className="text-[#c8c0b8]">Tokens are used for a single request only and are
                never stored</strong>. They are not logged or persisted in any form.
              </p>
            </div>
            <div className="border border-[#1e1e1e] rounded-lg p-5">
              <p className="font-mono text-[10px] tracking-[0.2em] text-[#3a3a3a] uppercase mb-2">What is sent to Claude</p>
              <p>
                The Anthropic API receives a structured prompt containing: detected framework names,
                dependency lists (package names only, not versions), file counts, and directory
                structure summaries. <strong className="text-[#c8c0b8]">Source code is never sent to any LLM.</strong>
              </p>
            </div>
          </div>
        </Section>

        {/* Source */}
        <Section title="Full transparency">
          <p>
            CodebaseAtlas is fully open source under the AGPL-3.0 license. The complete
            source code — including the analysis pipeline, framework detection logic,
            manifest parsers, and LLM prompts — is available on GitHub.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <a
              href="https://github.com/MentalVibez/AI_Architecture_Explainer"
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-[12px] px-4 py-2 border border-[#c8a96e]/30
                         text-[#c8a96e]/70 hover:text-[#c8a96e] hover:border-[#c8a96e]/60
                         rounded transition-all tracking-wider"
            >
              View source on GitHub ↗
            </a>
            <a
              href="https://github.com/MentalVibez/AI_Architecture_Explainer/blob/main/backend/app/services/analysis_pipeline.py"
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-[12px] px-4 py-2 border border-[#1e1e1e]
                         text-[#3a3a3a] hover:text-[#5a5a5a] hover:border-[#2a2a2a]
                         rounded transition-all tracking-wider"
            >
              analysis_pipeline.py ↗
            </a>
            <a
              href="https://github.com/MentalVibez/AI_Architecture_Explainer/blob/main/backend/app/services/summary_service.py"
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-[12px] px-4 py-2 border border-[#1e1e1e]
                         text-[#3a3a3a] hover:text-[#5a5a5a] hover:border-[#2a2a2a]
                         rounded transition-all tracking-wider"
            >
              summary_service.py ↗
            </a>
          </div>
        </Section>

        <div className="border-t border-[#1a1a1a] pt-8 flex flex-wrap gap-6">
          <a href="/privacy" className="font-mono text-[11px] text-[#3a3a3a] hover:text-[#c8a96e] transition-colors">
            Privacy Policy →
          </a>
          <a href="/terms" className="font-mono text-[11px] text-[#3a3a3a] hover:text-[#c8a96e] transition-colors">
            Terms of Use →
          </a>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-[#1a1a1a] pt-10">
      <h2 className="font-serif text-3xl text-[#e8e0d4] mb-5">{title}</h2>
      {children}
    </div>
  );
}
