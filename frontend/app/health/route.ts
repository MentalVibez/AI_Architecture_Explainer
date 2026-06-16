import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function normalizeBackendUrl(value: string | undefined): string {
  if (!value) return "http://localhost:8000";

  const trimmed = value.trim();

  try {
    const url = new URL(trimmed);
    if (url.protocol === "http:" && url.hostname.endsWith(".railway.app")) {
      url.protocol = "https:";
    }
    return url.toString().replace(/\/$/, "");
  } catch {
    return trimmed.replace(/\/$/, "");
  }
}

const BACKEND = normalizeBackendUrl(process.env.API_URL);

async function fetchBackendHealth(): Promise<Response> {
  return fetch(`${BACKEND}/health`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
}

export async function GET(): Promise<Response> {
  try {
    const response = await fetchBackendHealth();
    const body = await response.text();

    return new Response(body, {
      status: response.status,
      headers: {
        "Cache-Control": "no-store",
        "Content-Type": response.headers.get("content-type") ?? "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      {
        status: "degraded",
        service: "codebase-atlas-frontend",
        checks: { backend: "unreachable" },
      },
      {
        status: 503,
        headers: { "Cache-Control": "no-store" },
      },
    );
  }
}

export async function HEAD(): Promise<Response> {
  try {
    const response = await fetchBackendHealth();

    return new Response(null, {
      status: response.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return new Response(null, {
      status: 503,
      headers: { "Cache-Control": "no-store" },
    });
  }
}

export function OPTIONS(): Response {
  return new Response(null, {
    status: 204,
    headers: {
      Allow: "GET, HEAD, OPTIONS",
      "Cache-Control": "no-store",
    },
  });
}
