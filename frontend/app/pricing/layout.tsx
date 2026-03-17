import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pricing — CodebaseAtlas",
  description:
    "Free for public repositories. No account required. Pro and Team plans coming soon.",
  openGraph: {
    title: "Pricing — CodebaseAtlas",
    description: "Free for public repositories. No account required.",
    url: "https://www.codebaseatlas.com/pricing",
  },
};

export default function PricingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
