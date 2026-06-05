import { withSentryConfig } from "@sentry/nextjs";

/** @type {import('next').NextConfig} */
function normalizeBackendUrl(value) {
  if (!value) return "http://localhost:8000";

  try {
    const url = new URL(value);
    if (url.protocol === "http:" && url.hostname.endsWith(".railway.app")) {
      url.protocol = "https:";
    }
    return url.toString().replace(/\/$/, "");
  } catch {
    return value.replace(/\/$/, "");
  }
}

const BACKEND = normalizeBackendUrl(
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL,
);

function getConnectSrc() {
  const sources = ["'self'", "ws:", "wss:", "https://*.sentry.io"];

  try {
    const backendOrigin = new URL(BACKEND).origin;
    if (!sources.includes(backendOrigin)) {
      sources.push(backendOrigin);
    }
  } catch {
    // Relative or invalid backend values are not valid CSP sources.
  }

  return `connect-src ${sources.join(" ")}`;
}

const nextConfig = {
  async headers() {
    const securityHeaders = [
      {
        key: "Content-Security-Policy",
        value: [
          "default-src 'self'",
          "script-src 'self' 'unsafe-inline'",
          "style-src 'self' 'unsafe-inline'",
          "img-src 'self' data: blob: https:",
          "font-src 'self' data:",
          getConnectSrc(),
          "worker-src 'self' blob:",
          "object-src 'none'",
          "base-uri 'self'",
          "form-action 'self'",
          "frame-ancestors 'none'",
        ].join("; "),
      },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "X-Frame-Options", value: "DENY" },
      {
        key: "Permissions-Policy",
        value: "camera=(), microphone=(), geolocation=(), payment=()",
      },
      {
        key: "Strict-Transport-Security",
        value: "max-age=63072000; includeSubDomains",
      },
    ];

    return [
      {
        source: "/:path*",
        headers: securityHeaders,
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND}/api/:path*`,
      },
      {
        source: "/health",
        destination: `${BACKEND}/health`,
      },
    ];
  },
};

export default withSentryConfig(nextConfig, {
  org: "dotish",
  project: "javascript-astro",
  // Source maps are uploaded during build — disable to avoid auth token requirement in CI
  silent: true,
  disableSourceMapUpload: !process.env.SENTRY_AUTH_TOKEN,
  telemetry: false,
});
