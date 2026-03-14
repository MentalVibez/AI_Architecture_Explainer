import RepoUrlForm from "@/components/RepoUrlForm";

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4 bg-gray-950 text-white">
      <div className="max-w-2xl w-full text-center space-y-6">
        <h1 className="text-4xl font-bold tracking-tight">Codebase Atlas</h1>
        <p className="text-lg text-gray-400">
          Turn any public GitHub repository into an architecture diagram and
          technical summary — for developers and hiring managers.
        </p>
        <RepoUrlForm />
        <p className="text-sm text-gray-600">
          Try:{" "}
          <span className="font-mono text-gray-500">
            https://github.com/vercel/next.js
          </span>
        </p>
      </div>
    </main>
  );
}
