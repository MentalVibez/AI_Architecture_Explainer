import { notFound, redirect } from "next/navigation";

import { resolveShareSlug } from "@/lib/api";

interface Props {
  params: Promise<{ slug: string }>;
}

export default async function ShareRedirectPage({ params }: Props) {
  const { slug } = await params;

  let resolution: { type: "atlas" | "review"; id: string };
  try {
    resolution = await resolveShareSlug(slug);
  } catch {
    notFound();
  }

  if (resolution.type === "atlas") {
    redirect(`/results/${resolution.id}`);
  }
  redirect(`/review?result_id=${encodeURIComponent(resolution.id)}`);
}
