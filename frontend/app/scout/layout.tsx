import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "RepoScout — GitHub & GitLab Repository Discovery | CodebaseAtlas",
  description:
    "Search GitHub and GitLab simultaneously. Credibility scores, noise suppression, and intent-aware ranking tell you which repository to actually use before you spend hours reading it.",
  openGraph: {
    title: "RepoScout — GitHub & GitLab Repository Discovery",
    description:
      "Search GitHub and GitLab simultaneously. Quality scores, relevance ranking, and noise suppression — find the right repo fast.",
    url: "https://www.codebaseatlas.com/scout",
  },
};

export default function ScoutLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
