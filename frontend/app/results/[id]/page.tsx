import { getResult } from "@/lib/api";
import DeveloperSummary from "@/components/DeveloperSummary";
import HiringManagerSummary from "@/components/HiringManagerSummary";
import DiagramPanel from "@/components/DiagramPanel";

interface Props {
  params: { id: string };
}

export default async function ResultPage({ params }: Props) {
  const result = await getResult(Number(params.id));

  const evidence = (result.raw_evidence?.[0] as Record<string, unknown>) ?? {};
  const repo = (evidence.repo as Record<string, string>) ?? {};
  const filesScanned = (evidence.tree_paths as string[])?.length ?? 0;
  const repoLabel =
    repo.owner && repo.name ? `${repo.owner}/${repo.name}` : null;

  return (
    <main className="min-h-screen bg-gray-950 text-white px-4 py-10">
      <div className="max-w-5xl mx-auto space-y-8">

        {/* Header */}
        <header className="border-b border-gray-800 pb-5">
          <p className="text-xs font-mono text-blue-400 uppercase tracking-widest mb-1">
            CodebaseAtlas Report
          </p>
          <h1 className="text-2xl font-bold font-mono">
            {repoLabel ?? `Result #${result.id}`}
          </h1>
          <div className="flex gap-5 mt-2 text-xs text-gray-500 font-mono">
            {filesScanned > 0 && <span>Files scanned: {filesScanned}</span>}
            <span>Result #{result.id}</span>
          </div>
        </header>

        {/* Architecture Map — hero */}
        {result.diagram_mermaid && (
          <DiagramPanel mermaid={result.diagram_mermaid} />
        )}

        {/* Stack Detection + Developer Summary */}
        <DeveloperSummary result={result} />

        {/* Hiring Manager View */}
        <HiringManagerSummary result={result} />

      </div>
    </main>
  );
}
