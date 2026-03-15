"""Infers frameworks and stack from file names, dependencies, and config files."""


def _item(name: str, evidence: list[str], confidence: float) -> dict:
    return {"name": name, "evidence": evidence, "confidence": confidence}


def detect_stack(
    tree_paths: list[str],
    npm_deps: list[str],
    python_deps: list[str],
) -> dict[str, list[dict]]:
    frontend: list[dict] = []
    backend: list[dict] = []
    database: list[dict] = []
    infra: list[dict] = []
    testing: list[dict] = []

    path_set = set(tree_paths)

    # --- Frontend ---
    if "next" in npm_deps:
        ev = ["'next' in package.json"]
        cfg = next((p for p in tree_paths if "next.config" in p), None)
        if cfg:
            ev.append(cfg)
        frontend.append(_item("Next.js", ev, 0.95))
    if "react" in npm_deps or "react-dom" in npm_deps:
        frontend.append(_item("React", ["'react' in package.json"], 0.95))
    if "vue" in npm_deps:
        frontend.append(_item("Vue", ["'vue' in package.json"], 0.95))
    if "svelte" in npm_deps:
        frontend.append(_item("Svelte", ["'svelte' in package.json"], 0.95))
    tsx_files = [p for p in tree_paths if p.endswith(".tsx") or p.endswith(".ts")]
    if tsx_files:
        frontend.append(_item("TypeScript", tsx_files[:3], 0.9))

    # --- Backend (Python) ---
    if "fastapi" in python_deps:
        ev = ["'fastapi' in python deps"]
        main = next((p for p in tree_paths if p.endswith("main.py") or p.endswith("app.py")), None)
        if main:
            ev.append(main)
        backend.append(_item("FastAPI", ev, 0.95))
    if "django" in python_deps:
        ev = ["'django' in python deps"]
        if "manage.py" in path_set:
            ev.append("manage.py")
        backend.append(_item("Django", ev, 0.95))
    if "flask" in python_deps:
        backend.append(_item("Flask", ["'flask' in python deps"], 0.95))

    # --- Backend (JS) ---
    if "express" in npm_deps:
        backend.append(_item("Express", ["'express' in package.json"], 0.95))

    # --- Database ---
    matched_orm = [d for d in ("sqlalchemy", "sqlmodel") if d in python_deps]
    if matched_orm:
        database.append(_item("SQLAlchemy", [f"'{matched_orm[0]}' in python deps"], 0.95))
    if "prisma" in npm_deps:
        database.append(_item("Prisma", ["'prisma' in package.json"], 0.95))
    matched_pg = next((d for d in ("psycopg2", "asyncpg") if d in python_deps), None)
    if matched_pg:
        database.append(_item("PostgreSQL", [f"'{matched_pg}' in python deps"], 0.9))
    if "supabase" in npm_deps or "supabase" in python_deps:
        src = "package.json" if "supabase" in npm_deps else "python deps"
        database.append(_item("Supabase", [f"'supabase' in {src}"], 0.9))

    # --- Infra ---
    dockerfiles = [p for p in tree_paths if p == "Dockerfile" or p.endswith("/Dockerfile")]
    if dockerfiles:
        infra.append(_item("Docker", dockerfiles[:2], 0.95))
    compose = [p for p in tree_paths if "docker-compose" in p]
    if compose:
        infra.append(_item("Docker Compose", compose[:1], 0.95))
    vercel_ev = []
    if any("vercel.json" in p for p in path_set):
        vercel_ev.append("vercel.json")
    if "vercel" in npm_deps:
        vercel_ev.append("'vercel' in package.json")
    if vercel_ev:
        infra.append(_item("Vercel", vercel_ev, 0.9))
    gha = [p for p in tree_paths if ".github/workflows" in p]
    if gha:
        infra.append(_item("GitHub Actions", gha[:2], 0.95))

    # --- Testing ---
    js_test_deps = [d for d in ("jest", "vitest", "playwright", "cypress") if d in npm_deps]
    if js_test_deps:
        testing.append(_item("JS Testing", [f"'{js_test_deps[0]}' in package.json"], 0.9))
    py_test_deps = [d for d in ("pytest", "unittest") if d in python_deps]
    if py_test_deps:
        testing.append(_item("Pytest", [f"'{py_test_deps[0]}' in python deps"], 0.9))

    return {
        "frontend": frontend,
        "backend": backend,
        "database": database,
        "infra": infra,
        "testing": testing,
    }
