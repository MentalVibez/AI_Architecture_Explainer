"use client";

import { useEffect, useRef } from "react";

interface Props {
  mermaid: string;
}

export default function DiagramPanel({ mermaid }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    import("mermaid").then((m) => {
      if (cancelled || !ref.current) return;
      m.default.initialize({ startOnLoad: false, theme: "dark" });
      ref.current.removeAttribute("data-processed");
      ref.current.textContent = mermaid;
      m.default.run({ nodes: [ref.current] });
    });
    return () => { cancelled = true; };
  }, [mermaid]);

  return (
    <section className="bg-gray-900 rounded-xl p-6 overflow-auto">
      <h2 className="text-lg font-semibold mb-4">Architecture Diagram</h2>
      <div ref={ref} className="mermaid text-sm" />
    </section>
  );
}
