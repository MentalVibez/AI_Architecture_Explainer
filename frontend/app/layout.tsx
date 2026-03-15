/**
 * app/layout.tsx  —  Codebase Atlas Toolkit
 *
 * Drop-in replacement for the existing Atlas layout.tsx.
 * Adds platform-level nav with both tools. Everything else unchanged.
 *
 * Stack: Next.js 14 App Router · TypeScript · Tailwind CSS
 */

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CodebaseAtlas — Developer Toolkit",
  description:
    "Discover, evaluate, and deeply understand open-source repositories. " +
    "RepoScout finds the right repo. Atlas explains it. Map charts the API surface.",
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
      <body className="bg-[#0a0a0a] text-[#e8e0d4] font-sans antialiased min-h-screen">
        {/* ── Platform nav ─────────────────────────────────────────────── */}
        <nav className="border-b border-[#1e1e1e] bg-[#0a0a0a]/95 backdrop-blur-sm sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">

            {/* Wordmark */}
            <a
              href="/"
              className="flex items-center gap-3 group"
              aria-label="CodebaseAtlas home"
            >
              <span className="font-mono text-[11px] tracking-[0.25em] text-[#c8a96e] uppercase select-none">
                Atlas
              </span>
              <span className="w-px h-4 bg-[#2a2a2a]" />
              <span className="font-mono text-[11px] tracking-[0.2em] text-[#4a4a4a] uppercase">
                Toolkit
              </span>
            </a>

            {/* Tool links */}
            <div className="flex items-center gap-1">
              <NavLink href="/" label="01 / Atlas" />
              <NavLink href="/scout" label="02 / RepoScout" />
              <NavLink href="/map" label="03 / Map" />
              <a
                href="https://github.com/MentalVibez/AI_Architecture_Explainer"
                target="_blank"
                rel="noopener noreferrer"
                className="ml-3 text-[11px] font-mono tracking-widest text-[#3a3a3a] hover:text-[#5a5a5a] transition-colors"
                aria-label="GitHub"
              >
                GH ↗
              </a>
            </div>
          </div>
        </nav>

        {/* ── Page content ─────────────────────────────────────────────── */}
        <main>{children}</main>

        {/* ── Platform footer ───────────────────────────────────────────── */}
        <footer className="border-t border-[#1a1a1a] mt-24 py-10">
          <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <p className="font-mono text-[11px] tracking-[0.2em] text-[#3a3a3a] uppercase">
                CodebaseAtlas Toolkit
              </p>
              <p className="font-mono text-[10px] text-[#2a2a2a] mt-1">
                Analysis engine powered by Anthropic claude-sonnet-4-6
              </p>
            </div>
            <div className="flex gap-6">
              <FooterLink href="/" label="Atlas" />
              <FooterLink href="/scout" label="RepoScout" />
              <FooterLink href="/map" label="Map" />
              <FooterLink
                href="https://github.com/MentalVibez/AI_Architecture_Explainer"
                label="GitHub"
                external
              />
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}

/* ── Sub-components ──────────────────────────────────────────────────────── */

function NavLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      className="px-3 py-1.5 font-mono text-[11px] tracking-widest text-[#4a4a4a]
                 hover:text-[#c8a96e] hover:bg-[#c8a96e]/5 rounded
                 transition-all duration-150 uppercase"
    >
      {label}
    </a>
  );
}

function FooterLink({
  href,
  label,
  external,
}: {
  href: string;
  label: string;
  external?: boolean;
}) {
  return (
    <a
      href={href}
      target={external ? "_blank" : undefined}
      rel={external ? "noopener noreferrer" : undefined}
      className="font-mono text-[11px] tracking-widest text-[#2a2a2a]
                 hover:text-[#4a4a4a] transition-colors uppercase"
    >
      {label}
    </a>
  );
}
