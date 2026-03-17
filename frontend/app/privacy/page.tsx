import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Privacy Policy — CodebaseAtlas",
  description: "How CodebaseAtlas handles your data. No accounts, no PII, public repositories only.",
};

export default function PrivacyPage() {
  return (
    <div className="max-w-3xl mx-auto px-6 py-20">

      {/* Header */}
      <div className="mb-12">
        <div className="flex items-center gap-3 mb-6">
          <span className="font-mono text-[10px] tracking-[0.3em] text-[#c8a96e] uppercase">Legal</span>
          <span className="h-px w-8 bg-[#1e1e1e]" />
        </div>
        <h1 className="font-serif text-5xl text-[#e8e0d4] mb-4">Privacy Policy</h1>
        <p className="font-mono text-[11px] text-[#3a3a3a]">Last updated: March 2026</p>
      </div>

      <div className="space-y-10 font-sans text-[14px] text-[#5a5a5a] leading-relaxed">

        <Section title="Overview">
          <p>
            CodebaseAtlas is a developer tool that analyzes public GitHub repositories.
            We are committed to being transparent about what data we collect and how it
            is used. The short version: we collect almost nothing, and what little we do
            collect is not linked to your identity.
          </p>
        </Section>

        <Section title="What we collect">
          <ul className="space-y-3 list-none">
            <Li>
              <strong className="text-[#c8c0b8]">Repository URLs</strong> — when you submit a GitHub URL for analysis,
              that URL is sent to our backend and passed to the GitHub API to fetch the repository tree.
              It is stored in our database alongside the analysis result.
            </Li>
            <Li>
              <strong className="text-[#c8c0b8]">Job IDs and result data</strong> — analysis results are stored
              by a numeric job ID so you can retrieve them. Results are not linked to any user account
              or identifying information.
            </Li>
            <Li>
              <strong className="text-[#c8c0b8]">Standard server logs</strong> — like all web services, our
              hosting providers (Railway, Vercel) may collect IP addresses, request timestamps, and
              browser user-agent strings in standard access logs. These are not used for tracking.
            </Li>
          </ul>
        </Section>

        <Section title="What we do NOT collect">
          <ul className="space-y-2 list-none">
            <Li>No user accounts, names, or email addresses</Li>
            <Li>No cookies beyond what Next.js sets for basic functionality</Li>
            <Li>No advertising trackers or third-party analytics SDKs</Li>
            <Li>No private repository content — only public repositories can be analyzed</Li>
          </ul>
        </Section>

        <Section title="GitHub tokens (optional)">
          <p>
            RepoScout offers an optional GitHub personal access token input to increase
            API rate limits. <strong className="text-[#c8c0b8]">Tokens are used only for the duration of the
            single request and are never stored</strong> in our database or logs. They are
            transmitted directly to the GitHub API and discarded immediately after the
            request completes.
          </p>
        </Section>

        <Section title="How analysis data is used">
          <p>
            Repository URLs and analysis results are stored to allow result retrieval via
            the results page. We do not use this data to train AI models, share it with
            third parties, or use it for any commercial purpose beyond operating the service.
          </p>
          <p className="mt-3">
            Analysis requests are sent to <strong className="text-[#c8c0b8]">Anthropic</strong> (the maker of Claude)
            for processing. Anthropic&apos;s own privacy policy governs how they handle API requests.
            Specifically, structured repository data (file names, detected frameworks, dependency lists)
            is included in the prompt sent to Claude. Raw file source code is not sent.
          </p>
        </Section>

        <Section title="Data retention">
          <p>
            Analysis results may be retained indefinitely to support result retrieval by job ID.
            We may periodically purge old results as part of database maintenance.
            There is no user-facing mechanism to delete a specific result, as results are
            not linked to any account.
          </p>
          <p className="mt-3 font-mono text-[12px] text-[#3a3a3a] border border-[#1e1e1e] rounded p-3">
            Note: If you have a specific data deletion request, contact us via the
            GitHub repository issue tracker.
          </p>
        </Section>

        <Section title="Third-party services">
          <ul className="space-y-2 list-none">
            <Li><strong className="text-[#c8c0b8]">Railway</strong> — backend hosting (Python/FastAPI)</Li>
            <Li><strong className="text-[#c8c0b8]">Vercel</strong> — frontend hosting (Next.js)</Li>
            <Li><strong className="text-[#c8c0b8]">Supabase</strong> — production database (Postgres)</Li>
            <Li><strong className="text-[#c8c0b8]">Anthropic Claude API</strong> — LLM analysis</Li>
            <Li><strong className="text-[#c8c0b8]">GitHub API / GitLab API</strong> — repository data</Li>
          </ul>
          <p className="mt-3">Each provider operates under their own privacy policies and data handling practices.</p>
        </Section>

        <Section title="Changes to this policy">
          <p>
            This policy may be updated over time. The &ldquo;Last updated&rdquo; date at the top of this
            page reflects when the most recent changes were made. Continued use of CodebaseAtlas
            after changes constitutes acceptance of the updated policy.
          </p>
        </Section>

        <div className="border-t border-[#1a1a1a] pt-8">
          <p className="font-mono text-[11px] text-[#3a3a3a]">
            Questions?{" "}
            <a
              href="https://github.com/MentalVibez/AI_Architecture_Explainer/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#c8a96e] hover:text-[#d4b87a] transition-colors"
            >
              Open an issue on GitHub ↗
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-[#1a1a1a] pt-8">
      <h2 className="font-serif text-2xl text-[#e8e0d4] mb-4">{title}</h2>
      {children}
    </div>
  );
}

function Li({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex gap-2">
      <span className="text-[#2a2a2a] mt-0.5 shrink-0">—</span>
      <span>{children}</span>
    </li>
  );
}
