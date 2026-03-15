from app.services.framework_detector import detect_stack


def _detect(tree=None, npm=None, python=None):
    return detect_stack(tree or [], npm or [], python or [])


def _names(items: list) -> list[str]:
    """Extract names from the rich detection format."""
    return [d["name"] for d in items]


# --- Frontend ---

def test_detects_nextjs():
    result = _detect(npm=["next", "react"])
    assert "Next.js" in _names(result["frontend"])
    assert "React" in _names(result["frontend"])


def test_detects_react_without_next():
    result = _detect(npm=["react", "react-dom"])
    assert "React" in _names(result["frontend"])
    assert "Next.js" not in _names(result["frontend"])


def test_detects_typescript_from_tree():
    result = _detect(tree=["src/index.tsx", "lib/utils.ts"])
    assert "TypeScript" in _names(result["frontend"])


def test_detects_vue():
    result = _detect(npm=["vue"])
    assert "Vue" in _names(result["frontend"])


# --- Backend ---

def test_detects_fastapi():
    result = _detect(python=["fastapi"])
    assert "FastAPI" in _names(result["backend"])


def test_detects_django():
    result = _detect(python=["django"])
    assert "Django" in _names(result["backend"])


def test_detects_flask():
    result = _detect(python=["flask"])
    assert "Flask" in _names(result["backend"])


def test_detects_express():
    result = _detect(npm=["express"])
    assert "Express" in _names(result["backend"])


# --- Database ---

def test_detects_sqlalchemy():
    result = _detect(python=["sqlalchemy"])
    assert "SQLAlchemy" in _names(result["database"])


def test_detects_supabase_from_npm():
    result = _detect(npm=["supabase"])
    assert "Supabase" in _names(result["database"])


def test_detects_prisma():
    result = _detect(npm=["prisma"])
    assert "Prisma" in _names(result["database"])


# --- Infra ---

def test_detects_docker_from_tree():
    result = _detect(tree=["Dockerfile", "docker-compose.yml"])
    assert "Docker" in _names(result["infra"])
    assert "Docker Compose" in _names(result["infra"])


def test_detects_vercel_from_tree():
    result = _detect(tree=["vercel.json"])
    assert "Vercel" in _names(result["infra"])


def test_detects_github_actions_from_tree():
    result = _detect(tree=[".github/workflows/ci.yml"])
    assert "GitHub Actions" in _names(result["infra"])


# --- Rich format validation ---

def test_items_have_evidence_and_confidence():
    result = _detect(npm=["next", "react"], python=["fastapi"])
    for category in result.values():
        for item in category:
            assert "name" in item
            assert "evidence" in item
            assert "confidence" in item
            assert isinstance(item["evidence"], list)
            assert 0.0 <= item["confidence"] <= 1.0


def test_evidence_includes_source_hint():
    result = _detect(npm=["next"])
    nextjs = next(d for d in result["frontend"] if d["name"] == "Next.js")
    assert any("package.json" in ev for ev in nextjs["evidence"])


def test_fastapi_evidence_includes_entry_file():
    result = _detect(python=["fastapi"], tree=["app/main.py"])
    fastapi = next(d for d in result["backend"] if d["name"] == "FastAPI")
    assert any("main.py" in ev for ev in fastapi["evidence"])


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
