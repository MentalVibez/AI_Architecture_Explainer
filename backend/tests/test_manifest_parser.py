import json
from app.services.manifest_parser import (
    parse_package_json,
    parse_requirements_txt,
    parse_pyproject_toml,
)


# --- parse_package_json ---

def test_package_json_extracts_deps():
    content = json.dumps({
        "name": "my-app",
        "description": "A test app",
        "dependencies": {"react": "^18.0.0", "next": "14.0.0"},
        "devDependencies": {"typescript": "^5.0.0"},
        "scripts": {"dev": "next dev", "build": "next build"},
    })
    result = parse_package_json(content)
    assert result["name"] == "my-app"
    assert "react" in result["dependencies"]
    assert "next" in result["dependencies"]
    assert "typescript" in result["dependencies"]
    assert "dev" in result["scripts"]
    assert "build" in result["scripts"]


def test_package_json_empty_fields():
    result = parse_package_json(json.dumps({}))
    assert result["dependencies"] == []
    assert result["scripts"] == []


def test_package_json_invalid_json():
    result = parse_package_json("not json at all")
    assert result == {}


# --- parse_requirements_txt ---

def test_requirements_txt_strips_versions():
    content = "\n".join([
        "fastapi==0.115.0",
        "httpx>=0.27.0",
        "pydantic~=2.0",
        "anthropic",
    ])
    result = parse_requirements_txt(content)
    assert "fastapi" in result
    assert "httpx" in result
    assert "pydantic" in result
    assert "anthropic" in result


def test_requirements_txt_ignores_comments():
    content = "\n".join([
        "# This is a comment",
        "requests==2.31.0",
        "",
        "  # Another comment",
        "pytest",
    ])
    result = parse_requirements_txt(content)
    assert "requests" in result
    assert "pytest" in result
    assert len([r for r in result if r.startswith("#")]) == 0


def test_requirements_txt_ignores_flags():
    content = "-r other_requirements.txt\nflask"
    result = parse_requirements_txt(content)
    assert "flask" in result
    assert not any(r.startswith("-") for r in result)


def test_requirements_txt_empty():
    assert parse_requirements_txt("") == []
    assert parse_requirements_txt("# only comments\n") == []


# --- parse_pyproject_toml ---

def test_pyproject_toml_extracts_deps():
    content = """
[project]
name = "my-backend"
dependencies = [
    "fastapi>=0.115.0",
    "httpx[http2]>=0.27.0",
    "pydantic==2.0.0",
]
"""
    result = parse_pyproject_toml(content)
    assert result["name"] == "my-backend"
    assert "fastapi" in result["dependencies"]
    assert "httpx" in result["dependencies"]
    assert "pydantic" in result["dependencies"]


def test_pyproject_toml_no_project_section():
    content = "[build-system]\nrequires = ['hatchling']\n"
    result = parse_pyproject_toml(content)
    assert result.get("dependencies", []) == []


def test_pyproject_toml_empty():
    result = parse_pyproject_toml("")
    assert isinstance(result, dict)
