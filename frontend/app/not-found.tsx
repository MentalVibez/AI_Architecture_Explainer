export default function NotFound() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-950 text-white px-4">
      <div className="text-center space-y-4">
        <h1 className="text-6xl font-bold text-gray-700">404</h1>
        <h2 className="text-xl font-semibold text-gray-300">Page not found</h2>
        <p className="text-sm text-gray-500">
          This analysis result doesn&apos;t exist or may have been removed.
        </p>
        <a
          href="/"
          className="inline-block mt-4 px-5 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-medium transition-colors"
        >
          Analyze a repo
        </a>
      </div>
    </main>
  );
}
