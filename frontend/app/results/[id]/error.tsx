"use client";

interface Props {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ResultError({ error, reset }: Props) {
  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-950 text-white px-4">
      <div className="text-center space-y-4 max-w-md">
        <h2 className="text-xl font-semibold text-red-400">Failed to load analysis</h2>
        <p className="text-sm text-gray-500">
          {error.message || "Something went wrong loading this result."}
        </p>
        <div className="flex gap-3 justify-center pt-2">
          <button
            onClick={reset}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-medium transition-colors"
          >
            Try again
          </button>
          <a
            href="/"
            className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-sm font-medium transition-colors"
          >
            Analyze another repo
          </a>
        </div>
      </div>
    </main>
  );
}
