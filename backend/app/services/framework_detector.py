"""Infers frameworks and stack from file names, dependencies, and config files."""


def detect_stack(
    tree_paths: list[str],
    npm_deps: list[str],
    python_deps: list[str],
) -> dict[str, list[str]]:
    frontend: list[str] = []
    backend: list[str] = []
    database: list[str] = []
    infra: list[str] = []
    testing: list[str] = []

    path_set = set(tree_paths)

    # --- Frontend ---
    if "next" in npm_deps:
        frontend.append("Next.js")
    if "react" in npm_deps or "react-dom" in npm_deps:
        frontend.append("React")
    if "vue" in npm_deps:
        frontend.append("Vue")
    if "svelte" in npm_deps:
        frontend.append("Svelte")
    if any(p.endswith(".tsx") or p.endswith(".ts") for p in tree_paths):
        frontend.append("TypeScript")

    # --- Backend (Python) ---
    if "fastapi" in python_deps:
        backend.append("FastAPI")
    if "django" in python_deps:
        backend.append("Django")
    if "flask" in python_deps:
        backend.append("Flask")

    # --- Backend (JS) ---
    if "express" in npm_deps:
        backend.append("Express")

    # --- Database ---
    if any(d in python_deps for d in ("sqlalchemy", "sqlmodel")):
        database.append("SQLAlchemy")
    if "prisma" in npm_deps:
        database.append("Prisma")
    if any(d in python_deps for d in ("psycopg2", "asyncpg")):
        database.append("PostgreSQL")
    if "supabase" in npm_deps or "supabase" in python_deps:
        database.append("Supabase")

    # --- Infra ---
    if any("Dockerfile" in p for p in path_set):
        infra.append("Docker")
    if any("docker-compose" in p for p in path_set):
        infra.append("Docker Compose")
    if any("vercel.json" in p for p in path_set) or "vercel" in npm_deps:
        infra.append("Vercel")
    if any(".github/workflows" in p for p in path_set):
        infra.append("GitHub Actions")

    # --- Testing ---
    if any(d in npm_deps for d in ("jest", "vitest", "playwright", "cypress")):
        testing.append("JS Testing")
    if any(d in python_deps for d in ("pytest", "unittest")):
        testing.append("Pytest")

    return {
        "frontend": frontend,
        "backend": backend,
        "database": database,
        "infra": infra,
        "testing": testing,
    }
