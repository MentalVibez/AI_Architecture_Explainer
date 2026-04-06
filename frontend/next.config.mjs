import { withSentryConfig } from "@sentry/nextjs";

/** @type {import('next').NextConfig} */
const BACKEND = process.env.API_URL ?? "http://localhost:8000";

const nextConfig = {
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
