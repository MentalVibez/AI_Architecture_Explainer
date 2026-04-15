export default function PricingPage() {
  return (
    <div className="max-w-5xl mx-auto px-6">

      {/* Header */}
      <section className="pt-20 pb-14 border-b border-[#1a1a1a]">
        <div className="flex items-center gap-3 mb-6">
          <span className="font-mono text-[10px] tracking-[0.3em] text-[#c8a96e] uppercase">
            Pricing
          </span>
        </div>
        <h1 className="font-serif text-5xl sm:text-6xl text-[#e8e0d4] mb-5 leading-[0.95]">
          Simple, transparent<br />
          <em className="text-[#c8a96e] not-italic">pricing.</em>
        </h1>
        <p className="font-sans text-[#5a5a5a] text-lg leading-relaxed max-w-lg">
          All core tools are free for public repositories — no account required.
          Paid plans with higher limits and private repo support are on the roadmap.
        </p>
      </section>

      {/* Tier cards */}
      <section className="py-16 border-b border-[#1a1a1a]">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

          {/* Free */}
          <div className="border border-[#c8a96e]/40 rounded-lg p-7 flex flex-col gap-6 relative">
            <div className="absolute top-4 right-4">
              <span className="font-mono text-[9px] tracking-[0.2em] uppercase px-2 py-0.5
                               border border-[#c8a96e]/40 text-[#c8a96e] rounded bg-[#c8a96e]/5">
                Current
              </span>
            </div>
            <div>
              <p className="font-mono text-[10px] tracking-[0.3em] text-[#c8a96e] uppercase mb-3">
                Free
              </p>
              <div className="flex items-end gap-1.5 mb-1">
                <span className="font-serif text-5xl text-[#e8e0d4]">$0</span>
                <span className="font-mono text-[11px] text-[#3a3a3a] mb-1.5">/ forever</span>
              </div>
              <p className="font-sans text-[13px] text-[#4a4a4a]">No signup. No card.</p>
            </div>

            <ul className="space-y-2.5 flex-1">
              {[
                "All 4 tools — Atlas, Scout, Map, Review",
                "Public GitHub & GitLab repos",
                "10 analyses per day",
                "Architecture diagrams",
                "Framework detection",
                "API surface mapping",
                "Quality scorecard",
              ].map((f) => (
                <li key={f} className="flex items-start gap-2.5">
                  <span className="text-[#c8a96e] mt-0.5 shrink-0 text-[11px]">✓</span>
                  <span className="font-sans text-[13px] text-[#5a5a5a] leading-snug">{f}</span>
                </li>
              ))}
            </ul>

            <a
              href="/#analyze"
              className="inline-flex items-center justify-center gap-2 px-5 py-2.5
                         bg-[#c8a96e] text-[#0a0a0a] font-mono text-[12px] tracking-wider
                         rounded hover:bg-[#d4b87a] transition-colors"
            >
              Start analyzing →
            </a>
          </div>

          {/* Pro */}
          <div className="border border-[#1e1e1e] rounded-lg p-7 flex flex-col gap-6 relative opacity-60">
            <div className="absolute top-4 right-4">
              <span className="font-mono text-[9px] tracking-[0.2em] uppercase px-2 py-0.5
                               border border-[#1e1e1e] text-[#3a3a3a] rounded">
                Coming soon
              </span>
            </div>
            <div>
              <p className="font-mono text-[10px] tracking-[0.3em] text-[#3a3a3a] uppercase mb-3">
                Pro
              </p>
              <div className="flex items-end gap-1.5 mb-1">
                <span className="font-serif text-5xl text-[#e8e0d4]">$9</span>
                <span className="font-mono text-[11px] text-[#3a3a3a] mb-1.5">/ month</span>
              </div>
              <p className="font-sans text-[13px] text-[#4a4a4a]">For individual developers.</p>
            </div>

            <ul className="space-y-2.5 flex-1">
              {[
                "Everything in Free",
                "Private repository support",
                "100 analyses per day",
                "Priority analysis queue",
                "Persistent result history",
                "API access",
                "Email support",
              ].map((f) => (
                <li key={f} className="flex items-start gap-2.5">
                  <span className="text-[#3a3a3a] mt-0.5 shrink-0 text-[11px]">✓</span>
                  <span className="font-sans text-[13px] text-[#3a3a3a] leading-snug">{f}</span>
                </li>
              ))}
            </ul>

            <div className="px-5 py-2.5 border border-[#1e1e1e] text-[#3a3a3a] font-mono
                            text-[12px] tracking-wider rounded text-center cursor-not-allowed">
              Notify me
            </div>
          </div>

          {/* Team */}
          <div className="border border-[#1e1e1e] rounded-lg p-7 flex flex-col gap-6 relative opacity-60">
            <div className="absolute top-4 right-4">
              <span className="font-mono text-[9px] tracking-[0.2em] uppercase px-2 py-0.5
                               border border-[#1e1e1e] text-[#3a3a3a] rounded">
                Coming soon
              </span>
            </div>
            <div>
              <p className="font-mono text-[10px] tracking-[0.3em] text-[#3a3a3a] uppercase mb-3">
                Team
              </p>
              <div className="flex items-end gap-1.5 mb-1">
                <span className="font-serif text-5xl text-[#e8e0d4]">$29</span>
                <span className="font-mono text-[11px] text-[#3a3a3a] mb-1.5">/ month</span>
              </div>
              <p className="font-sans text-[13px] text-[#4a4a4a]">For engineering teams.</p>
            </div>

            <ul className="space-y-2.5 flex-1">
              {[
                "Everything in Pro",
                "Up to 10 seats",
                "Shared analysis workspace",
                "Team result history",
                "Webhook integrations",
                "Custom rate limits",
                "Priority support + SLA",
              ].map((f) => (
                <li key={f} className="flex items-start gap-2.5">
                  <span className="text-[#3a3a3a] mt-0.5 shrink-0 text-[11px]">✓</span>
                  <span className="font-sans text-[13px] text-[#3a3a3a] leading-snug">{f}</span>
                </li>
              ))}
            </ul>

            <div className="px-5 py-2.5 border border-[#1e1e1e] text-[#3a3a3a] font-mono
                            text-[12px] tracking-wider rounded text-center cursor-not-allowed">
              Notify me
            </div>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-14">
        <div className="flex items-center gap-3 mb-10">
          <span className="font-mono text-[10px] tracking-[0.3em] text-[#3a3a3a] uppercase">
            FAQ
          </span>
          <span className="h-px flex-1 bg-[#1a1a1a]" />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {[
            {
              q: "What counts as an analysis?",
              a: "Each time you submit a repository URL to Atlas, Map, or Review — that counts as one analysis. RepoScout searches are separate and don't count toward the limit.",
            },
            {
              q: "Do I need an account?",
              a: "No. The free tier requires zero signup. Just paste a repo URL and go. Paid plans will require an account for billing and history.",
            },
            {
              q: "Does it work with private repos?",
              a: "Not yet. The current system only analyzes public GitHub and GitLab repositories. Private repo support is planned for the Pro tier.",
            },
            {
              q: "How is the data used?",
              a: "Repo URLs and analysis results are stored by job ID only — not linked to your identity. See the Privacy Policy for full details.",
            },
            {
              q: "Is the code open source?",
              a: "Yes. CodebaseAtlas is open source under the AGPL-3.0 license. You can self-host the entire stack. If you run it as a public service, you must publish your source.",
            },
            {
              q: "When are paid plans available?",
              a: "We're focused on making the public-repo workflow strong first. Paid tiers will launch once private repos, higher limits, and persistent team features are ready. The free tier will always exist.",
            },
          ].map(({ q, a }) => (
            <div key={q} className="border-t border-[#1a1a1a] pt-6">
              <p className="font-sans text-[14px] text-[#c8c0b8] font-medium mb-2">{q}</p>
              <p className="font-sans text-[13px] text-[#4a4a4a] leading-relaxed">{a}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
