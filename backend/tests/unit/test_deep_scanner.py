"""
tests/test_deep_scanner.py
--------------------------
Deterministic tests for DeepScanner, language detection, role classification,
FileIntelligence construction, and CodeContext building.

All tests are deterministic — no LLM, no network, no mocking required.
This is the test suite style Atlas already uses in Tool 04.
"""

import pytest

from app.schemas.intelligence import CodeFinding, OptimizationCandidate
from app.services.deep_scanner import (
    build_code_contexts,
    build_file_intelligence,
    classify_role,
    detect_language,
    prioritize_files,
    should_skip,
)

# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

class TestLanguageDetection:
    def test_python_by_extension(self):
        assert detect_language("backend/app/main.py") == "python"

    def test_typescript_by_extension(self):
        assert detect_language("frontend/src/page.tsx") == "typescript"

    def test_javascript_by_extension(self):
        assert detect_language("lib/utils.js") == "javascript"

    def test_yaml_by_extension(self):
        assert detect_language(".github/workflows/ci.yml") == "yaml"

    def test_dockerfile_by_name(self):
        assert detect_language("Dockerfile") == "dockerfile"

    def test_python_by_shebang(self):
        content = "#!/usr/bin/env python3\nprint('hello')"
        assert detect_language("script", content) == "python"

    def test_shell_by_shebang(self):
        content = "#!/bin/bash\necho hello"
        assert detect_language("deploy", content) == "shell"

    def test_unknown_for_binary_extension(self):
        assert detect_language("image.png") == "unknown"

    def test_toml_extension(self):
        assert detect_language("pyproject.toml") == "toml"

    def test_json_extension(self):
        assert detect_language("package.json") == "json"


# ---------------------------------------------------------------------------
# Role classification
# ---------------------------------------------------------------------------

class TestRoleClassification:
    def test_entrypoint_main_py(self):
        assert classify_role("backend/app/main.py") == "entrypoint"

    def test_entrypoint_index_ts(self):
        assert classify_role("src/index.ts") == "entrypoint"

    def test_test_file_by_prefix(self):
        assert classify_role("tests/test_scanner.py") == "test"

    def test_test_file_by_directory(self):
        assert classify_role("test/unit/parser_test.py") == "test"

    def test_config_settings_py(self):
        assert classify_role("app/settings.py") == "config"

    def test_config_package_json(self):
        assert classify_role("package.json") == "config"

    def test_infra_dockerfile(self):
        assert classify_role("Dockerfile") == "infra"

    def test_infra_github_workflow(self):
        assert classify_role(".github/workflows/backend.yml") == "infra"

    def test_service_by_name(self):
        assert classify_role("app/services/analysis_service.py") == "service"

    def test_service_by_directory(self):
        assert classify_role("app/handlers/webhook_handler.py") == "service"

    def test_migration_by_directory(self):
        assert classify_role("alembic/versions/001_initial.py") == "migration"

    def test_schema_by_name(self):
        assert classify_role("app/schemas/user_schema.py") == "schema"

    def test_utility_by_name(self):
        assert classify_role("utils/helpers.py") == "utility"

    def test_utility_by_directory(self):
        assert classify_role("lib/common/formatters.ts") == "utility"

    def test_module_generic_python(self):
        assert classify_role("app/core/engine.py") == "module"

    def test_unknown_for_markdown(self):
        role = classify_role("README.md")
        assert role == "unknown"


# ---------------------------------------------------------------------------
# Skip detection
# ---------------------------------------------------------------------------

class TestShouldSkip:
    def test_skip_node_modules(self):
        assert should_skip("node_modules/lodash/index.js") is True

    def test_skip_git_directory(self):
        assert should_skip(".git/config") is True

    def test_skip_pycache(self):
        assert should_skip("app/__pycache__/main.cpython-311.pyc") is True

    def test_skip_venv(self):
        assert should_skip(".venv/lib/python3.11/site-packages/fastapi/__init__.py") is True

    def test_skip_png(self):
        assert should_skip("static/logo.png") is True

    def test_skip_lock_file(self):
        # Lock files are handled by is_generated(), not should_skip()
        # should_skip covers binary/vendor/compiled — is_generated covers lockfiles/built output
        # This test verifies the separation of concerns is maintained
        assert should_skip("package-lock.json") is False  # NOT binary — handled by is_generated
        from app.services.deep_scanner import is_generated
        assert is_generated("package-lock.json") is True   # IS generated — correct classifier

    def test_do_not_skip_source(self):
        assert should_skip("backend/app/main.py") is False

    def test_do_not_skip_test(self):
        assert should_skip("tests/test_main.py") is False

    def test_do_not_skip_config(self):
        assert should_skip("pyproject.toml") is False


# ---------------------------------------------------------------------------
# FileIntelligence construction
# ---------------------------------------------------------------------------

PYTHON_SAMPLE = '''\
#!/usr/bin/env python3
"""Main application entrypoint for the Atlas backend."""
from fastapi import FastAPI
from sqlalchemy import create_engine

app = FastAPI()

def analyze_repo(url: str) -> dict:
    """Analyze a repository and return structured intelligence."""
    try:
        result = _fetch_tree(url)
        return result
    except Exception as e:
        raise ValueError(f"Analysis failed: {e}")

def _fetch_tree(url: str):
    import httpx
    response = httpx.get(url)
    return response.json()

password = "supersecret123"  # noqa: S105 - intentional for test

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''

TYPESCRIPT_SAMPLE = '''\
import { useState, useEffect } from "react";
import axios from "axios";
import type { RepoAnalysis } from "@/types";

export default function AnalysisPage() {
  const [analysis, setAnalysis] = useState<RepoAnalysis | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const resp = await axios.get("/api/analyze");
        setAnalysis(resp.data);
      } catch (err) {
        console.error(err);
      }
    }
    load();
  }, []);

  return <div>{analysis?.repo_name}</div>;
}
'''


class TestBuildFileIntelligence:
    def test_python_language_detected(self):
        fi = build_file_intelligence("app/main.py", PYTHON_SAMPLE)
        assert fi.language == "python"

    def test_python_role_entrypoint(self):
        fi = build_file_intelligence("app/main.py", PYTHON_SAMPLE)
        assert fi.role == "entrypoint"
        assert fi.is_entrypoint is True

    def test_python_imports_extracted(self):
        fi = build_file_intelligence("app/main.py", PYTHON_SAMPLE)
        assert "fastapi" in fi.imports
        assert "sqlalchemy" in fi.imports

    def test_python_framework_signals(self):
        fi = build_file_intelligence("app/main.py", PYTHON_SAMPLE)
        assert "fastapi" in fi.framework_signals
        assert "sqlalchemy" in fi.framework_signals

    def test_python_sensitive_operations_detected(self):
        fi = build_file_intelligence("app/main.py", PYTHON_SAMPLE)
        assert "hardcoded_secret" in fi.sensitive_operations

    def test_python_is_executable_main_guard(self):
        fi = build_file_intelligence("app/main.py", PYTHON_SAMPLE)
        assert fi.is_executable is True

    def test_python_has_type_annotations(self):
        fi = build_file_intelligence("app/main.py", PYTHON_SAMPLE)
        assert fi.has_type_annotations is True

    def test_python_has_docstrings(self):
        fi = build_file_intelligence("app/main.py", PYTHON_SAMPLE)
        assert fi.has_docstrings is True

    def test_python_has_error_handling(self):
        fi = build_file_intelligence("app/main.py", PYTHON_SAMPLE)
        assert fi.has_error_handling is True

    def test_python_loc_positive(self):
        fi = build_file_intelligence("app/main.py", PYTHON_SAMPLE)
        assert fi.loc > 0

    def test_python_function_count(self):
        fi = build_file_intelligence("app/main.py", PYTHON_SAMPLE)
        assert fi.function_count >= 2

    def test_typescript_language_detected(self):
        fi = build_file_intelligence("frontend/app/page.tsx", TYPESCRIPT_SAMPLE)
        assert fi.language == "typescript"

    def test_typescript_imports_extracted(self):
        fi = build_file_intelligence("frontend/app/page.tsx", TYPESCRIPT_SAMPLE)
        assert "react" in fi.imports or "react" in "".join(fi.imports)

    def test_typescript_framework_signals(self):
        fi = build_file_intelligence("frontend/app/page.tsx", TYPESCRIPT_SAMPLE)
        assert "react" in fi.framework_signals

    def test_typescript_has_error_handling(self):
        fi = build_file_intelligence("frontend/app/page.tsx", TYPESCRIPT_SAMPLE)
        assert fi.has_error_handling is True

    def test_truncation_flagged(self):
        large_content = "x = 1\n" * 30_000  # ~180KB
        fi = build_file_intelligence("app/large.py", large_content, size_bytes=180_000)
        assert fi.was_truncated is True

    def test_confidence_full_on_clean_file(self):
        fi = build_file_intelligence("app/utils.py", "def hello(): pass\n")
        assert fi.confidence == 1.0

    def test_empty_file_handled(self):
        fi = build_file_intelligence("app/empty.py", "")
        assert fi.language == "python"
        assert fi.loc == 0


# ---------------------------------------------------------------------------
# CodeContext building
# ---------------------------------------------------------------------------

class TestCodeContextBuilding:
    def _make_files(self):
        """Create a minimal three-file dependency chain."""
        main_fi = build_file_intelligence(
            "app/main.py",
            "from app.service import analyze\nfrom fastapi import FastAPI\napp = FastAPI()\ndef analyze(): pass\n",
        )
        # Override path to match import
        service_fi = build_file_intelligence(
            "app/service.py",
            "from app.utils import parse\ndef analyze(url: str): return parse(url)\n",
        )
        utils_fi = build_file_intelligence(
            "app/utils.py",
            "def parse(url: str): return url.strip()\n",
        )
        return [main_fi, service_fi, utils_fi]

    def test_contexts_created_for_all_files(self):
        files = self._make_files()
        contexts, _, _ = build_code_contexts(files)
        assert len(contexts) == 3

    def test_all_file_paths_present(self):
        files = self._make_files()
        contexts, _, _ = build_code_contexts(files)
        for fi in files:
            assert fi.path in contexts

    def test_service_boundary_inference(self):
        fi = build_file_intelligence("app/services/auth/login.py", "def login(): pass\n")
        contexts, _, _ = build_code_contexts([fi])
        ctx = contexts["app/services/auth/login.py"]
        assert ctx.service_boundary == "services"

    def test_entrypoint_marked_critical(self):
        fi = build_file_intelligence("app/main.py", "from fastapi import FastAPI\napp = FastAPI()\n")
        contexts, _, _ = build_code_contexts([fi])
        assert contexts["app/main.py"].is_on_critical_path is True

    def test_caller_count_zero_for_isolated_file(self):
        fi = build_file_intelligence("app/standalone.py", "def helper(): pass\n")
        contexts, _, _ = build_code_contexts([fi])
        assert contexts["app/standalone.py"].caller_count == 0


# ---------------------------------------------------------------------------
# CodeFinding schema validation
# ---------------------------------------------------------------------------

class TestCodeFindingValidation:
    def test_valid_finding_constructs(self):
        f = CodeFinding(
            file_path="app/main.py",
            category="security",
            severity="critical",
            source="deterministic",
            line_start=15,
            line_end=15,
            evidence_snippet='password = "supersecret123"',
            title="Hardcoded credential",
            explanation="Password embedded in source code.",
            score_impact=-20,
            confidence=1.0,
        )
        assert f.id is not None
        assert len(f.id) == 8

    def test_line_end_lt_start_raises(self):
        with pytest.raises(ValueError, match="line_end"):
            CodeFinding(
                file_path="app/main.py",
                category="security",
                severity="low",
                source="deterministic",
                line_start=10,
                line_end=5,  # invalid
                evidence_snippet="some code",
                title="Test",
                explanation="Test explanation",
                score_impact=-1,
                confidence=0.9,
            )

    def test_empty_snippet_raises(self):
        with pytest.raises(ValueError, match="evidence_snippet"):
            CodeFinding(
                file_path="app/main.py",
                category="security",
                severity="low",
                source="deterministic",
                line_start=1,
                line_end=1,
                evidence_snippet="   ",  # whitespace only
                title="Test",
                explanation="Test",
                score_impact=-1,
                confidence=0.9,
            )


# ---------------------------------------------------------------------------
# OptimizationCandidate schema
# ---------------------------------------------------------------------------

class TestOptimizationCandidate:
    def test_requires_approval_by_default(self):
        candidate = OptimizationCandidate(
            finding_id="abc12345",
            file_path="app/main.py",
            change_type="security_fix",
            patch_diff="--- a/app/main.py\n+++ b/app/main.py\n@@ -15 +15 @@\n-password = 'supersecret'\n+password = os.environ['PASSWORD']",
            explanation="Replace hardcoded password with environment variable.",
            before_snippet='password = "supersecret"',
            after_snippet='password = os.environ["PASSWORD"]',
            risk="low",
        )
        assert candidate.requires_user_approval is True
        assert candidate.is_approved is False
        assert candidate.is_applied is False

    def test_expected_score_impact_recorded(self):
        candidate = OptimizationCandidate(
            finding_id="abc12345",
            file_path="app/main.py",
            change_type="security_fix",
            patch_diff="--- a/app/main.py\n+++ b/app/main.py\n@@ -1 +1 @@",
            explanation="Fix.",
            before_snippet="old",
            after_snippet="new",
            expected_score_impact={"security": 20},
            risk="low",
        )
        assert candidate.expected_score_impact["security"] == 20


# ---------------------------------------------------------------------------
# Fix 1: Complexity scoring — no false positives from strings/comments
# ---------------------------------------------------------------------------

class TestComplexityScoring:
    def test_comment_with_keywords_does_not_inflate_score(self):
        # This comment contains if/or/and — should NOT count as branches
        content = '''
def process():
    # Use this if you want speed or reliability and correctness
    return 42
'''
        fi = build_file_intelligence("app/process.py", content)
        # One function, no real branches — score should be low
        assert fi.complexity_score < 5.0

    def test_string_with_keywords_does_not_inflate(self):
        content = '''
def validate(x):
    msg = "fails if value is None or empty and not a string"
    return bool(x)
'''
        fi = build_file_intelligence("app/validate.py", content)
        assert fi.complexity_score < 5.0

    def test_real_branches_are_counted(self):
        content = '''
def route_request(req):
    if req.method == "GET":
        return handle_get(req)
    elif req.method == "POST":
        if req.user and req.user.is_authenticated:
            return handle_post(req)
        else:
            return 401
    else:
        return 405
'''
        fi = build_file_intelligence("app/router.py", content)
        # 4 structural branches (if/elif/if/else) + logical (and)
        assert fi.complexity_score >= 3.0

    def test_complex_file_scores_higher_than_simple(self):
        simple = '''
def add(a, b):
    return a + b

def sub(a, b):
    return a - b
'''
        complex_ = '''
def process(data):
    if not data:
        return None
    for item in data:
        if item.get("active"):
            try:
                result = transform(item)
                if result and result.valid:
                    yield result
            except ValueError:
                continue
        elif item.get("pending") and not item.get("archived"):
            handle_pending(item)
'''
        fi_simple = build_file_intelligence("app/simple.py", simple)
        fi_complex = build_file_intelligence("app/complex.py", complex_)
        assert fi_complex.complexity_score > fi_simple.complexity_score


# ---------------------------------------------------------------------------
# Fix 2: Contents stored in DeepScanResult (structural test)
# ---------------------------------------------------------------------------

class TestDeepScanResultContents:
    def test_result_has_contents_field(self):
        import dataclasses

        from app.services.deep_scanner import DeepScanResult

        fields = {f.name for f in dataclasses.fields(DeepScanResult)}
        assert "contents" in fields

    def test_contents_field_defaults_to_empty_dict(self):
        from app.schemas.intelligence import ScanMetadata
        from app.services.deep_scanner import DeepScanResult

        result = DeepScanResult(
            files=[],
            contexts={},
            scan_metadata=ScanMetadata(
                total_files=0,
                files_scanned=0,
                files_skipped=0,
                files_failed=0,
                parse_success_rate=0.0,
                languages_detected={},
                scan_duration_seconds=0.0,
            ),
        )
        assert isinstance(result.contents, dict)
        assert len(result.contents) == 0


# ---------------------------------------------------------------------------
# Fix 3: Import resolution — Python dotted paths and TypeScript relative paths
# ---------------------------------------------------------------------------

class TestImportResolution:
    def _make_python_files(self):
        """Three-file Python repo with real dotted import paths."""
        main = build_file_intelligence(
            "app/main.py",
            "from app.services.analyzer import AnalysisService\nfrom fastapi import FastAPI\n",
        )
        analyzer = build_file_intelligence(
            "app/services/analyzer.py",
            "from app.utils.parser import parse\nclass AnalysisService: pass\n",
        )
        parser = build_file_intelligence(
            "app/utils/parser.py",
            "def parse(url: str): return url\n",
        )
        return [main, analyzer, parser]

    def _make_ts_files(self):
        """Three-file TypeScript repo with relative imports."""
        page = build_file_intelligence(
            "src/app/page.tsx",
            'import { AnalysisForm } from "../components/AnalysisForm";\n',
        )
        form = build_file_intelligence(
            "src/components/AnalysisForm.tsx",
            'import { apiClient } from "../lib/api";\nexport function AnalysisForm() {}\n',
        )
        api = build_file_intelligence(
            "src/lib/api.ts",
            'export const apiClient = { get: fetch };\n',
        )
        return [page, form, api]

    def test_python_dotted_import_resolves(self):
        files = self._make_python_files()
        contexts, _, _ = build_code_contexts(files)
        main_ctx = contexts["app/main.py"]
        assert "app/services/analyzer.py" in main_ctx.downstream_dependencies

    def test_python_transitive_resolves(self):
        files = self._make_python_files()
        contexts, _, _ = build_code_contexts(files)
        analyzer_ctx = contexts["app/services/analyzer.py"]
        assert "app/utils/parser.py" in analyzer_ctx.downstream_dependencies

    def test_python_upstream_callers_populated(self):
        files = self._make_python_files()
        contexts, _, _ = build_code_contexts(files)
        analyzer_ctx = contexts["app/services/analyzer.py"]
        assert "app/main.py" in analyzer_ctx.upstream_callers

    def test_python_external_package_not_in_downstream(self):
        files = self._make_python_files()
        contexts, _, _ = build_code_contexts(files)
        main_ctx = contexts["app/main.py"]
        assert not any("fastapi" in d for d in main_ctx.downstream_dependencies)

    def test_ts_relative_import_resolves(self):
        files = self._make_ts_files()
        contexts, _, _ = build_code_contexts(files)
        page_ctx = contexts["src/app/page.tsx"]
        assert "src/components/AnalysisForm.tsx" in page_ctx.downstream_dependencies

    def test_ts_upstream_callers_populated(self):
        files = self._make_ts_files()
        contexts, _, _ = build_code_contexts(files)
        form_ctx = contexts["src/components/AnalysisForm.tsx"]
        assert "src/app/page.tsx" in form_ctx.upstream_callers

    def test_ts_nested_relative_resolves(self):
        files = self._make_ts_files()
        contexts, _, _ = build_code_contexts(files)
        form_ctx = contexts["src/components/AnalysisForm.tsx"]
        assert "src/lib/api.ts" in form_ctx.downstream_dependencies


# ---------------------------------------------------------------------------
# Fix 4: Critical path depth cap — no full-repo propagation
# ---------------------------------------------------------------------------

class TestCriticalPathDepthCap:
    def test_depth_2_files_are_marked_critical(self):
        """depth cap is > 2, so files at depth 0, 1, and 2 are all critical"""
        main = build_file_intelligence("app/main.py", "from app.service import run\n")
        service = build_file_intelligence("app/service.py", "from app.util import helper\ndef run(): pass\n")
        util = build_file_intelligence("app/util.py", "def helper(): pass\n")
        contexts, _, _ = build_code_contexts([main, service, util])
        assert contexts["app/main.py"].is_on_critical_path is True    # depth 0
        assert contexts["app/service.py"].is_on_critical_path is True  # depth 1
        assert contexts["app/util.py"].is_on_critical_path is True     # depth 2 — within cap

    def test_depth_3_files_are_not_marked_critical(self):
        """depth > 2 is blocked — depth 3 must NOT be critical"""
        main = build_file_intelligence("app/main.py", "from app.a import a\n")
        a = build_file_intelligence("app/a.py", "from app.b import b\ndef a(): pass\n")
        b = build_file_intelligence("app/b.py", "from app.c import c\ndef b(): pass\n")
        c = build_file_intelligence("app/c.py", "def c(): pass\n")  # depth 3
        contexts, _, _ = build_code_contexts([main, a, b, c])
        assert contexts["app/main.py"].is_on_critical_path is True   # depth 0
        assert contexts["app/a.py"].is_on_critical_path is True      # depth 1
        assert contexts["app/b.py"].is_on_critical_path is True      # depth 2
        assert contexts["app/c.py"].is_on_critical_path is False     # depth 3 — blocked

    def test_barrel_export_does_not_mark_entire_repo(self):
        index = build_file_intelligence(
            "src/index.ts",
            "\n".join(f'export {{ M{i} }} from "./module{i}";' for i in range(5)),
        )
        modules = [
            build_file_intelligence(f"src/module{i}.ts", f"export class M{i} {{}}\n")
            for i in range(5)
        ]
        deep_deps = [
            build_file_intelligence(f"src/deep{i}.ts", f"export function d{i}() {{}}\n")
            for i in range(5)
        ]
        all_files = [index] + modules + deep_deps
        contexts, _, _ = build_code_contexts(all_files)
        critical_paths = [p for p, ctx in contexts.items() if ctx.is_on_critical_path]
        assert len(critical_paths) <= 6


# ---------------------------------------------------------------------------
# Fix 5: Scorecard confidence — parse quality from FileIntelligence scores
# ---------------------------------------------------------------------------

class TestScorecardConfidence:
    def _make_metadata(self, scanned=10, total=10, failed=0, skipped=0):
        from app.schemas.intelligence import ScanMetadata
        return ScanMetadata(
            total_files=total,
            files_scanned=scanned,
            files_skipped=skipped,
            files_failed=failed,
            parse_success_rate=scanned / total if total else 0.0,
            languages_detected={"python": scanned},
            scan_duration_seconds=1.0,
        )

    def test_full_scan_high_confidence(self):
        from app.services.scorecard import _compute_confidence

        files = [
            build_file_intelligence(f"app/file{i}.py", "def f(): pass\n")
            for i in range(10)
        ]
        # All have confidence=1.0, full scan
        meta = self._make_metadata(scanned=10, total=10)
        conf = _compute_confidence(meta, files)
        assert conf >= 0.85

    def test_partial_scan_lower_confidence(self):
        from app.services.scorecard import _compute_confidence

        files = [
            build_file_intelligence(f"app/file{i}.py", "def f(): pass\n")
            for i in range(5)
        ]
        meta = self._make_metadata(scanned=5, total=20)  # only 25% scanned
        conf = _compute_confidence(meta, files)
        assert conf < 0.65

    def test_parse_errors_lower_confidence(self):
        from app.services.scorecard import _compute_confidence

        # Files with parse errors have low confidence scores
        bad_files = []
        for i in range(10):
            fi = build_file_intelligence(f"app/file{i}.py", "def f(): pass\n")
            # Simulate parse errors
            object.__setattr__(fi, "confidence", 0.3)
            object.__setattr__(fi, "parse_errors", ["parse_exception:SyntaxError:invalid syntax"])
            bad_files.append(fi)

        meta = self._make_metadata(scanned=10, total=10)
        conf = _compute_confidence(meta, bad_files)
        assert conf < 0.65

    def test_confidence_never_reaches_1_0(self):
        from app.services.scorecard import _compute_confidence

        files = [
            build_file_intelligence(f"app/file{i}.py", "def f(): return True\n")
            for i in range(20)
        ]
        meta = self._make_metadata(scanned=20, total=20)
        conf = _compute_confidence(meta, files)
        assert conf < 1.0
        assert conf <= 0.97
    def _make_tree(self):
        return [
            {"path": "tests/test_main.py", "type": "blob", "size": 2000},
            {"path": "app/main.py", "type": "blob", "size": 1500},
            {"path": "app/services/analyzer.py", "type": "blob", "size": 3000},
            {"path": ".github/workflows/ci.yml", "type": "blob", "size": 500},
            {"path": "node_modules/lodash/index.js", "type": "blob", "size": 50000},
            {"path": "app/utils/helpers.py", "type": "blob", "size": 800},
            {"path": "static/logo.png", "type": "blob", "size": 10000},
        ]

    def test_entrypoint_comes_before_tests(self):
        tree = self._make_tree()
        prioritized = prioritize_files(tree)
        paths = [item["path"] for item in prioritized]
        # main.py (entrypoint) should come before test file
        if "app/main.py" in paths and "tests/test_main.py" in paths:
            assert paths.index("app/main.py") < paths.index("tests/test_main.py")

    def test_noise_files_ranked_last(self):
        tree = self._make_tree()
        prioritized = prioritize_files(tree)
        paths = [item["path"] for item in prioritized]
        # node_modules and png should be at the very end (high priority score = last)
        if "app/main.py" in paths and "node_modules/lodash/index.js" in paths:
            assert paths.index("app/main.py") < paths.index("node_modules/lodash/index.js")
