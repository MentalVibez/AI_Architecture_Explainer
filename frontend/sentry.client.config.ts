import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NODE_ENV,
  // Capture 10% of traces in production — enough for latency data, not expensive
  tracesSampleRate: 0.1,
  // Replay only on errors
  replaysOnErrorSampleRate: 1.0,
  replaysSessionSampleRate: 0,
  sendDefaultPii: false,
});
