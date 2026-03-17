import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Review — Repository Quality Assessment | CodebaseAtlas",
  description:
    "Evidence-backed quality scoring across security, testing, reliability, and maintainability. Deterministic rules, static analysis, anti-gaming detection, and depth-aware confidence labels.",
  openGraph: {
    title: "Review — Repository Quality Assessment",
    description:
      "Evidence-backed quality scoring across security, testing, reliability, and maintainability. Anti-gaming detection included.",
    url: "https://www.codebaseatlas.com/review",
  },
};

export default function ReviewLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
