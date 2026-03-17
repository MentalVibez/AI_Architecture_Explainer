export default function NotFound() {
  return (
    <div className="max-w-lg mx-auto px-6 py-32 text-center">
      <div className="font-mono text-[10px] tracking-[0.3em] text-[#c8a96e] uppercase mb-6">
        404
      </div>
      <h1 className="font-serif text-5xl text-[#e8e0d4] mb-4">
        Page not found
      </h1>
      <p className="font-sans text-[14px] text-[#4a4a4a] leading-relaxed mb-10">
        This page doesn&apos;t exist or may have been removed.
      </p>
      <a
        href="/"
        className="inline-block font-mono text-[12px] tracking-widest uppercase
                   px-6 py-3 bg-[#c8a96e] text-[#0a0a0a] rounded
                   hover:bg-[#d4b87a] transition-colors"
      >
        Back to CodebaseAtlas
      </a>
    </div>
  );
}
