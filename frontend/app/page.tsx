import RepoUrlForm from "@/components/RepoUrlForm";
import SampleRepos from "@/components/SampleRepos";

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-950 text-white flex flex-col">
      {/* Hero */}
      <main className="flex-1 flex flex-col items-center justify-center px-4 py-20">
        <div className="max-w-2xl w-full text-center space-y-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-950 border border-blue-800 text-blue-300 text-xs font-medium mb-2">
            Public GitHub repos only &middot; No sign-up required
          </div>

          <h1 className="text-5xl font-bold tracking-tight leading-tight">
            Understand any codebase
            <br />
            <span className="text-blue-400">in seconds</span>
          </h1>

          <p className="text-lg text-gray-400 max-w-xl mx-auto">
            Paste a public GitHub URL. Codebase Atlas fetches the repo tree,
            parses manifests, detects frameworks, and generates an architecture
            diagram with plain-English summaries for developers and hiring managers.
          </p>

          <RepoUrlForm />

          <div className="pt-2">
            <p className="text-xs text-gray-600 mb-3">Try a sample repo</p>
            <SampleRepos />
          </div>
        </div>
      </main>

      {/* How it works */}
      <section className="border-t border-gray-800 py-16 px-4">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-center text-xl font-semibold mb-10 text-gray-300">
            How it works
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            {STEPS.map((step, i) => (
              <div key={i} className="text-center space-y-3">
                <div className="w-10 h-10 rounded-full bg-blue-900/50 border border-blue-700 text-blue-300 font-bold flex items-center justify-center mx-auto text-sm">
                  {i + 1}
                </div>
                <h3 className="font-medium text-white">{step.title}</h3>
                <p className="text-sm text-gray-500">{step.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* What you get */}
      <section className="border-t border-gray-800 py-16 px-4 bg-gray-900/30">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-center text-xl font-semibold mb-10 text-gray-300">
            What you get
          </h2>
          <div className="grid md:grid-cols-2 gap-4">
            {OUTPUTS.map((o) => (
              <div
                key={o.title}
                className="flex gap-3 p-4 rounded-lg bg-gray-900 border border-gray-800"
              >
                <span className="text-2xl">{o.icon}</span>
                <div>
                  <h3 className="font-medium text-white text-sm">{o.title}</h3>
                  <p className="text-xs text-gray-500 mt-1">{o.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-gray-800 py-6 px-4 text-center text-xs text-gray-600">
        Codebase Atlas &mdash; analysis engine powered by Anthropic claude-sonnet-4-6
      </footer>
    </div>
  );
}

const STEPS = [
  {
    title: "Paste a GitHub URL",
    body: "Any public repository. No authentication required for public repos.",
  },
  {
    title: "We analyze the repo",
    body: "Fetches the file tree, parses manifests, detects frameworks with deterministic heuristics, then summarizes with Claude.",
  },
  {
    title: "Get your analysis",
    body: "Architecture diagram, stack breakdown, entry points, and dual summaries for developers and hiring managers.",
  },
];

const OUTPUTS = [
  {
    icon: "🗺️",
    title: "Architecture diagram",
    body: "Mermaid flowchart generated from real file structure evidence, not guesswork.",
  },
  {
    icon: "🔍",
    title: "Framework detection",
    body: "Identifies frontend, backend, database, infra, and testing layers from manifests and config files.",
  },
  {
    icon: "👩‍💻",
    title: "Developer summary",
    body: "Entry points, component responsibilities, dependency categories, and architectural patterns.",
  },
  {
    icon: "🤝",
    title: "Hiring manager summary",
    body: "Plain-English explanation of what the project does, what skills it demonstrates, and likely complexity.",
  },
];
