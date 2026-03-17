"use client";

interface Props {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ResultError({ error, reset }: Props) {
  return (
    <div className="max-w-lg mx-auto px-6 py-32 text-center">
      <div className="font-mono text-[10px] tracking-[0.3em] text-[#b86a6a] uppercase mb-6">
        Error
      </div>
      <h2 className="font-serif text-3xl text-[#e8e0d4] mb-4">
        Failed to load analysis
      </h2>
      <p className="font-sans text-[14px] text-[#4a4a4a] leading-relaxed mb-10">
        {error.message || "Something went wrong loading this result."}
      </p>
      <div className="flex gap-3 justify-center">
        <button
          onClick={reset}
          className="font-mono text-[12px] tracking-widest uppercase px-5 py-2.5
                     bg-[#c8a96e] text-[#0a0a0a] rounded hover:bg-[#d4b87a] transition-colors"
        >
          Try again
        </button>
        <a
          href="/"
          className="font-mono text-[12px] tracking-widest uppercase px-5 py-2.5
                     border border-[#1e1e1e] text-[#4a4a4a] rounded
                     hover:border-[#2a2a2a] hover:text-[#6a6a6a] transition-colors"
        >
          New analysis
        </a>
      </div>
    </div>
  );
}
