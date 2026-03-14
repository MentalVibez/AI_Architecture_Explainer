"use client";

import { useEffect, useRef, useState } from "react";

interface Props {
  mermaid: string;
}

export default function DiagramPanel({ mermaid }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [renderError, setRenderError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setRenderError(false);
    import("mermaid").then((m) => {
      if (cancelled || !ref.current) return;
      try {
        m.default.initialize({ startOnLoad: false, theme: "dark" });
        ref.current.removeAttribute("data-processed");
        ref.current.textContent = mermaid;
        m.default.run({ nodes: [ref.current] });
      } catch {
        if (!cancelled) setRenderError(true);
      }
    });
    return () => { cancelled = true; };
  }, [mermaid]);

  return (
    <section className="bg-gray-900 rounded-xl p-6 overflow-auto">
      <h2 className="text-lg font-semibold mb-4">Architecture Diagram</h2>
      {renderError ? (
        <div className="text-sm text-gray-500 py-4">
          Could not render diagram.{" "}
          <details className="inline">
            <summary className="cursor-pointer underline">Show raw</summary>
            <pre className="mt-2 text-xs text-gray-400 whitespace-pre-wrap">{mermaid}</pre>
          </details>
        </div>
      ) : (
        <div ref={ref} className="mermaid text-sm" />
      )}
    </section>
  );
}
