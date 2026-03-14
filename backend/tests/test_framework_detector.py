from app.services.framework_detector import detect_stack


def _detect(tree=None, npm=None, python=None):
    return detect_stack(tree or [], npm or [], python or [])


# --- Frontend ---

def test_detects_nextjs():
    result = _detect(npm=["next", "react"])
    assert "Next.js" in result["frontend"]
    assert "React" in result["frontend"]


def test_detects_react_without_next():
    result = _detect(npm=["react", "react-dom"])
    assert "React" in result["frontend"]
    assert "Next.js" not in result["frontend"]


def test_detects_typescript_from_tree():
    result = _detect(tree=["src/index.tsx", "lib/utils.ts"])
    assert "TypeScript" in result["frontend"]


def test_detects_vue():
    result = _detect(npm=["vue"])
    assert "Vue" in result["frontend"]


# --- Backend ---

def test_detects_fastapi():
    result = _detect(python=["fastapi"])
    assert "FastAPI" in result["backend"]


def test_detects_django():
    result = _detect(python=["django"])
    assert "Django" in result["backend"]


def test_detects_flask():
    result = _detect(python=["flask"])
    assert "Flask" in result["backend"]


def test_detects_express():
    result = _detect(npm=["express"])
    assert "Express" in result["backend"]


# --- Database ---

def test_detects_sqlalchemy():
    result = _detect(python=["sqlalchemy"])
    assert "SQLAlchemy" in result["database"]


def test_detects_supabase_from_npm():
    result = _detect(npm=["supabase"])
    assert "Supabase" in result["database"]


def test_detects_prisma():
    result = _detect(npm=["prisma"])
    assert "Prisma" in result["database"]


# --- Infra ---

def test_detects_docker_from_tree():
    result = _detect(tree=["Dockerfile", "docker-compose.yml"])
    assert "Docker" in result["infra"]
    assert "Docker Compose" in result["infra"]


def test_detects_vercel_from_tree():
    result = _detect(tree=["vercel.json"])
    assert "Vercel" in result["infra"]


def test_detects_github_actions_from_tree():
    result = _detect(tree=[".github/workflows/ci.yml"])
    assert "GitHub Actions" in result["infra"]


# --- Edge cases ---

def test_empty_inputs_return_empty_stacks():
    result = _detect()
    for category in ("frontend", "backend", "database", "infra", "testing"):
        assert result[category] == [], f"Expected empty {category}"


def test_no_false_positives_on_unrelated_deps():
    result = _detect(npm=["lodash", "axios", "dayjs"], python=["requests", "boto3"])
    # None of these should trigger framework detection
    assert result["frontend"] == []
    assert result["backend"] == []
