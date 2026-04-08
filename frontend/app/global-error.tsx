"use client";

import { useEffect } from "react";

import { dmMono, dmSans, dmSerif } from "@/app/fonts";
import * as Sentry from "@sentry/nextjs";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="en" className={`dark ${dmSans.variable} ${dmMono.variable} ${dmSerif.variable}`}>
      <body className="min-h-screen bg-[#0f0f0f] text-[#e8e0d4] font-sans antialiased">
        <main className="min-h-screen flex items-center justify-center px-6">
          <div className="max-w-lg w-full border border-[#1a1a1a] rounded-xl p-8 bg-[#111]">
            <p className="font-mono text-[10px] tracking-[0.3em] text-[#b86a6a] uppercase mb-4">
              Application Error
            </p>
            <h1 className="font-serif text-4xl text-[#e8e0d4] mb-4">
              Something went wrong.
            </h1>
            <p className="font-sans text-[14px] text-[#6a6a6a] leading-relaxed mb-6">
              The error has been captured for debugging. You can retry this view without
              reloading the whole app.
            </p>
            <button
              onClick={reset}
              className="px-5 py-2.5 rounded-lg bg-[#c8a96e] text-[#0a0a0a] font-mono text-[12px] tracking-widest uppercase hover:bg-[#d4b87a] transition-colors"
            >
              Try again
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}
