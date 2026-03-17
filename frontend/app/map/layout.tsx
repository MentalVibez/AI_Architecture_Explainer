import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Map — API Surface Mapper | CodebaseAtlas",
  description:
    "Extract every API endpoint from a GitHub repository. Framework-targeted regex patterns, grouped routes, auth detection, and LLM-generated descriptions — deterministically, without guesswork.",
  openGraph: {
    title: "Map — API Surface Mapper",
    description:
      "Extract every API endpoint from a GitHub repository. Grouped routes, auth detection, and LLM-generated descriptions.",
    url: "https://www.codebaseatlas.com/map",
  },
};

export default function MapLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
