import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Atlas — Repository Architecture Analysis | CodebaseAtlas",
  description:
    "Paste a GitHub URL and get an architecture diagram, framework detection, and dual plain-English summaries in seconds. Powered by Anthropic Claude.",
  openGraph: {
    title: "Atlas — Repository Architecture Analysis",
    description:
      "Paste a GitHub URL and get an architecture diagram, framework detection, and plain-English summaries in seconds.",
    url: "https://www.codebaseatlas.com/analyze",
  },
};

export default function AnalyzeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
