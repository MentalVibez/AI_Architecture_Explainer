import { getResult } from "@/lib/api";
import DeveloperSummary from "@/components/DeveloperSummary";
import HiringManagerSummary from "@/components/HiringManagerSummary";
import DiagramPanel from "@/components/DiagramPanel";

interface Props {
  params: { id: string };
}

export default async function ResultPage({ params }: Props) {
  const result = await getResult(Number(params.id));

  return (
    <main className="min-h-screen bg-gray-950 text-white px-4 py-10">
      <div className="max-w-5xl mx-auto space-y-8">
        <header className="space-y-1">
          <h1 className="text-3xl font-bold">Architecture Analysis</h1>
          <p className="text-gray-400 text-sm">Result #{result.id}</p>
        </header>

        {result.diagram_mermaid && (
          <DiagramPanel mermaid={result.diagram_mermaid} />
        )}

        <div className="grid md:grid-cols-2 gap-6">
          <DeveloperSummary result={result} />
          <HiringManagerSummary result={result} />
        </div>
      </div>
    </main>
  );
}
