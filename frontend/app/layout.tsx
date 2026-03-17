/**
 * app/layout.tsx  —  Codebase Atlas Toolkit
 *
 * Stack: Next.js 14 App Router · TypeScript · Tailwind CSS
 */

import type { Metadata } from "next";
import "./globals.css";
import Nav from "@/components/Nav";
import Logo from "@/components/Logo";

export const metadata: Metadata = {
  title: "CodebaseAtlas — Developer Toolkit",
  description:
    "Discover, evaluate, and deeply understand open-source repositories. " +
    "RepoScout finds the right repo. Atlas explains it. Map charts the API surface.",
  metadataBase: new URL("https://www.codebaseatlas.com"),
  openGraph: {
    title: "CodebaseAtlas — Developer Toolkit",
    description:
      "Understand any GitHub repository in seconds. Architecture diagrams, framework detection, API surface mapping — powered by Anthropic Claude.",
    url: "https://www.codebaseatlas.com",
    siteName: "CodebaseAtlas",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "CodebaseAtlas — Developer Toolkit",
    description:
      "Understand any GitHub repository in seconds. Architecture diagrams, framework detection, API surface mapping.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-[#0f0f0f] text-[#e8e0d4] font-sans antialiased min-h-screen">
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

        {/* ── Page content ─────────────────────────────────────────────── */}
        <main>{children}</main>

        {/* ── Platform footer ───────────────────────────────────────────── */}
        <footer className="border-t border-[#1a1a1a] mt-24">
          {/* Main footer grid */}
          <div className="max-w-6xl mx-auto px-6 py-14 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10">

            {/* Brand column */}
            <div className="lg:col-span-1">
              <div className="flex items-center gap-2.5 mb-4">
                <Logo size={18} />
                <span className="font-sans font-medium text-[13px] text-[#e8e0d4] tracking-tight">
                  CodebaseAtlas
                </span>
              </div>
              <p className="font-sans text-[13px] text-[#4a4a4a] leading-relaxed mb-5 max-w-[220px]">
                Understand any codebase in seconds. No signup required.
              </p>
              <p className="font-mono text-[10px] text-[#2a2a2a] leading-relaxed">
                Analysis engine powered by<br />
                <span className="text-[#3a3a3a]">Anthropic claude-sonnet-4-6</span>
              </p>
            </div>

            {/* Product column */}
            <div>
              <p className="font-mono text-[10px] tracking-[0.25em] text-[#3a3a3a] uppercase mb-4">
                Product
              </p>
              <ul className="flex flex-col gap-2.5">
                <li><FooterLink href="/#analyze" label="Atlas — Architecture Analysis" /></li>
                <li><FooterLink href="/scout" label="RepoScout — Discovery" /></li>
                <li><FooterLink href="/map" label="Map — API Surface" /></li>
                <li><FooterLink href="/review" label="Review — Quality Score" badge="Beta" /></li>
                <li><FooterLink href="/pricing" label="Pricing" /></li>
              </ul>
            </div>

            {/* Resources column */}
            <div>
              <p className="font-mono text-[10px] tracking-[0.25em] text-[#3a3a3a] uppercase mb-4">
                Resources
              </p>
              <ul className="flex flex-col gap-2.5">
                <li><FooterLink href="/how-it-works" label="How It Works" /></li>
                <li>
                  <FooterLink
                    href="https://github.com/MentalVibez/AI_Architecture_Explainer"
                    label="GitHub Repository"
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

            {/* Legal column */}
            <div>
              <p className="font-mono text-[10px] tracking-[0.25em] text-[#3a3a3a] uppercase mb-4">
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

          {/* Bottom bar */}
          <div className="border-t border-[#141414]">
            <div className="max-w-6xl mx-auto px-6 py-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <p className="font-mono text-[10px] text-[#2a2a2a]">
                © 2026 CodebaseAtlas. Open source under AGPL-3.0.
              </p>
              <p className="font-mono text-[10px] text-[#2a2a2a]">
                Analyzes public repositories only · No account required
              </p>
            </div>
          </div>
        </footer>
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
    <a
      href={href}
      target={external ? "_blank" : undefined}
      rel={external ? "noopener noreferrer" : undefined}
      className="group flex items-center gap-2 font-sans text-[13px] text-[#3a3a3a]
                 hover:text-[#6a6a6a] transition-colors"
    >
      <span>{label}</span>
      {external && (
        <span className="text-[10px] text-[#2a2a2a] group-hover:text-[#4a4a4a] transition-colors">
          ↗
        </span>
      )}
      {badge && (
        <span className="font-mono text-[9px] tracking-wider px-1.5 py-0.5 border border-[#9a7cb8]/30 text-[#9a7cb8]/60 rounded">
          {badge}
        </span>
      )}
    </a>
  );
}
