/**
 * app/layout.tsx  —  Codebase Atlas Toolkit
 *
 * Stack: Next.js 14 App Router · TypeScript · Tailwind CSS
 */

import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { dmMono, dmSans, dmSerif } from "@/app/fonts";
import Nav from "@/components/Nav";
import Logo from "@/components/Logo";
import { RepoWorkspaceProvider } from "@/components/workspace/RepoWorkspaceProvider";
import WorkspaceBar from "@/components/workspace/WorkspaceBar";

export const metadata: Metadata = {
  title: "CodebaseAtlas — Code Understanding Platform",
  description:
    "Search, inspect, map, and review public repositories with deterministic analysis and LLM last-mile explanation.",
  metadataBase: new URL("https://www.codebaseatlas.com"),
  openGraph: {
    title: "CodebaseAtlas — Code Understanding Platform",
    description:
      "Understand public repositories faster with architecture analysis, API mapping, and evidence-backed review.",
    url: "https://www.codebaseatlas.com",
    siteName: "CodebaseAtlas",
    type: "website",
    images: [
      {
        url: "/og-preview.svg",
        width: 1200,
        height: 630,
        alt: "CodebaseAtlas developer toolkit preview",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "CodebaseAtlas — Code Understanding Platform",
    description:
      "Search, inspect, map, and review public repositories faster.",
    images: ["/og-preview.svg"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark ${dmSans.variable} ${dmMono.variable} ${dmSerif.variable}`}>
      <body className="bg-[#08111f] text-[#edf4ff] font-sans antialiased min-h-screen">
        <RepoWorkspaceProvider>
          {/* ── JSON-LD structured data ───────────────────────────────────── */}
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{
              __html: JSON.stringify({
                "@context": "https://schema.org",
                "@type": "SoftwareApplication",
                name: "CodebaseAtlas",
                url: "https://www.codebaseatlas.com",
                description:
                  "AI-powered developer toolkit for discovering, evaluating, and understanding open-source repositories. Includes architecture analysis, API surface mapping, and quality assessment.",
                applicationCategory: "DeveloperApplication",
                operatingSystem: "Web",
                offers: {
                  "@type": "Offer",
                  price: "0",
                  priceCurrency: "USD",
                },
                creator: {
                  "@type": "Organization",
                  name: "CodebaseAtlas",
                  url: "https://www.codebaseatlas.com",
                },
                license: "https://www.gnu.org/licenses/agpl-3.0.html",
                codeRepository:
                  "https://github.com/MentalVibez/AI_Architecture_Explainer",
              }),
            }}
          />

          {/* ── Platform nav ─────────────────────────────────────────────── */}
          <Nav />
          <WorkspaceBar />

          {/* ── Page content ─────────────────────────────────────────────── */}
          <main>{children}</main>

          {/* ── Platform footer ───────────────────────────────────────────── */}
          <footer className="mt-24 border-t border-white/10 bg-[#08111f]/80">
            <div className="max-w-7xl mx-auto px-6 py-14 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10">
              <div className="lg:col-span-1">
                <div className="flex items-center gap-2.5 mb-4">
                  <Logo size={18} />
                  <span className="font-sans font-semibold text-[13px] text-[#f3f7ff] tracking-tight">
                    CodebaseAtlas
                  </span>
                </div>
                <p className="font-sans text-[13px] text-[#98abd0] leading-relaxed mb-5 max-w-[260px]">
                  A pragmatic code understanding workspace for public repositories: search, architecture, APIs, and quality in one flow.
                </p>
                <p className="font-mono text-[10px] text-[#6d7f9f] leading-relaxed">
                  Deterministic analysis first
                  <br />
                  <span className="text-[#b9c8e7]">LLM used only for explanation</span>
                </p>
              </div>

              <div>
                <p className="font-mono text-[10px] tracking-[0.25em] text-[#6d7f9f] uppercase mb-4">
                  Workspace
                </p>
                <ul className="flex flex-col gap-2.5">
                  <li><FooterLink href="/#analyze" label="Atlas — Architecture Analysis" /></li>
                  <li><FooterLink href="/scout" label="RepoScout — Discovery" /></li>
                  <li><FooterLink href="/map" label="Map — API Surface" /></li>
                  <li><FooterLink href="/review" label="Review — Quality Score" /></li>
                  <li><FooterLink href="/pricing" label="Pricing" /></li>
                </ul>
              </div>

              <div>
                <p className="font-mono text-[10px] tracking-[0.25em] text-[#6d7f9f] uppercase mb-4">
                  Resources
                </p>
                <ul className="flex flex-col gap-2.5">
                  <li><FooterLink href="/how-it-works" label="How It Works" /></li>
                  <li>
                    <FooterLink
                      href="https://github.com/MentalVibez/AI_Architecture_Explainer"
                      label="Open source"
                      external
                    />
                  </li>
                  <li>
                    <FooterLink
                      href="https://docs.anthropic.com"
                      label="Anthropic Docs"
                      external
                    />
                  </li>
                </ul>
              </div>

              <div>
                <p className="font-mono text-[10px] tracking-[0.25em] text-[#6d7f9f] uppercase mb-4">
                  Legal
                </p>
                <ul className="flex flex-col gap-2.5">
                  <li><FooterLink href="/privacy" label="Privacy Policy" /></li>
                  <li><FooterLink href="/terms" label="Terms of Use" /></li>
                  <li>
                    <FooterLink
                      href="https://github.com/MentalVibez/AI_Architecture_Explainer/blob/main/LICENSE"
                      label="AGPL-3.0 License"
                      external
                    />
                  </li>
                </ul>
              </div>
            </div>

            <div className="border-t border-white/10">
              <div className="max-w-7xl mx-auto px-6 py-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <p className="font-mono text-[10px] text-[#62779d]">
                  © 2026 CodebaseAtlas. Open source under AGPL-3.0.
                </p>
                <p className="font-mono text-[10px] text-[#62779d]">
                  Public repositories only · developer intelligence workspace
                </p>
              </div>
            </div>
          </footer>
        </RepoWorkspaceProvider>
      </body>
    </html>
  );
}

/* ── Sub-components ──────────────────────────────────────────────────────── */

function FooterLink({
  href,
  label,
  external,
  badge,
}: {
  href: string;
  label: string;
  external?: boolean;
  badge?: string;
}) {
  return (
    external ? (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="group flex items-center gap-2 font-sans text-[13px] text-[#9fb0cf] hover:text-white transition-colors"
      >
        <span>{label}</span>
        <span className="text-[10px] text-[#62779d] group-hover:text-[#dce8ff] transition-colors">↗</span>
        {badge && (
          <span className="font-mono text-[9px] tracking-wider px-1.5 py-0.5 border border-[#bca9ff]/30 text-[#c5b3ff] rounded">
            {badge}
          </span>
        )}
      </a>
    ) : (
      <Link
        href={href}
        className="group flex items-center gap-2 font-sans text-[13px] text-[#9fb0cf] hover:text-white transition-colors"
      >
        <span>{label}</span>
        {badge && (
          <span className="font-mono text-[9px] tracking-wider px-1.5 py-0.5 border border-[#bca9ff]/30 text-[#c5b3ff] rounded">
            {badge}
          </span>
        )}
      </Link>
    )
  );
}
