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
    <section className="border border-[#1a1a1a] rounded-lg p-6 overflow-auto">
      <h2 className="font-mono text-[11px] tracking-[0.3em] text-[#3a3a3a] uppercase mb-4">
        Architecture Diagram
      </h2>
      {renderError ? (
        <div className="font-mono text-[12px] text-[#4a4a4a] py-4">
          Could not render diagram.{" "}
          <details className="inline">
            <summary className="cursor-pointer underline">Show raw</summary>
            <pre className="mt-2 text-[11px] text-[#5a5a5a] whitespace-pre-wrap">{mermaid}</pre>
          </details>
        </div>
      ) : (
        <div ref={ref} className="mermaid text-sm" />
      )}
    </section>
  );
}
