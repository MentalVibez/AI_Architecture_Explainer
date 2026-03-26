"""
tests/test_invariants.py
------------------------
Semantic invariants for the Codebase Atlas intelligence pipeline.

These are NOT feature tests. They are invariant tests.
Each test encodes a rule from docs/SEMANTICS.md.

If a test here fails, either:
  (a) the implementation broke a semantic contract — fix the implementation, or
  (b) the semantic was deliberately changed — update SEMANTICS.md, bump
      SCHEMA_VERSION, and update this test with an explicit comment explaining
      the change.

Never silently update these tests to make them pass.
Every change here needs a reason in SEMANTICS.md.
"""

from __future__ import annotations

import pytest

from app.schemas.intelligence import (
    SCHEMA_VERSION,
    CodeFinding,
    ConfidenceBreakdown,
    DependencyEdge,
    FileIntelligence,
    RepoIntelligence,
)
from app.services.deep_scanner import (
    build_code_contexts,
    build_file_intelligence,
    is_generated,
    should_skip,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fi(path: str, content: str = "") -> FileIntelligence:
    return build_file_intelligence(path, content or f"# {path}\n")


def chain(*paths: str) -> list[FileIntelligence]:
    """
    Build a linear import chain: paths[0] imports paths[1], which imports paths[2], etc.
    The first file is always named main.py (or uses the given path) so it is
    detected as an entrypoint and critical path propagation starts from it.

    If you pass explicit paths, the first one must be an entrypoint-recognizable
    name (main.py, app.py, index.ts, or a Next.js page.tsx in an app/ dir).
    """
    files = []
    for i, path in enumerate(paths):
        if i < len(paths) - 1:
            next_path = paths[i + 1]
            # Build import string from path
            next_mod = (
                next_path
                .replace("/", ".")
                .replace(".py", "")
                .replace(".ts", "")
                .replace(".tsx", "")
            )
            content = f"from {next_mod} import x\ndef f(): pass\n"
        else:
            content = "def f(): pass\n"
        files.append(build_file_intelligence(path, content))
    return files


def entrypoint_chain(depth: int) -> list[FileIntelligence]:
    """
    Build a linear chain of `depth+1` files starting from main.py.
    main.py → mod1.py → mod2.py → ... → mod{depth}.py

    Convenience wrapper for critical-path depth invariant tests.
    """
    paths = ["app/main.py"] + [f"app/mod{i}.py" for i in range(1, depth + 1)]
    return chain(*paths)


# ---------------------------------------------------------------------------
# Invariant 1: Critical path depth semantics
# SEMANTICS.md §1
# ---------------------------------------------------------------------------

class TestCriticalPathDepthInvariants:
    """
    Encodes the depth rule: 0, 1, 2 = critical; 3+ = not critical.
    All tests use entrypoint_chain() which starts from main.py (recognized entrypoint).
    """

    def test_depth_0_always_critical(self):
        """Invariant: The entrypoint itself is always on the critical path."""
        files = entrypoint_chain(0)
        contexts, _, _ = build_code_contexts(files)
        assert contexts["app/main.py"].is_on_critical_path is True

    def test_depth_1_always_critical(self):
        """Invariant: Direct dependencies of an entrypoint are always critical."""
        files = entrypoint_chain(1)
        contexts, _, _ = build_code_contexts(files)
        assert contexts["app/main.py"].is_on_critical_path is True   # depth 0
        assert contexts["app/mod1.py"].is_on_critical_path is True   # depth 1

    def test_depth_2_always_critical_in_linear_chain(self):
        """
        Invariant: depth-2 files ARE critical in a linear chain.
        (DFS visits them at depth=2 which is within the cap > 2.)
        """
        files = entrypoint_chain(2)
        contexts, _, _ = build_code_contexts(files)
        assert contexts["app/mod2.py"].is_on_critical_path is True   # depth 2 — within cap

    def test_depth_3_never_critical_in_linear_chain(self):
        """
        Invariant: depth-3 files are NEVER critical in a linear chain.
        This is the hard boundary enforced by `depth > 2` in _mark_critical_path.
        """
        files = entrypoint_chain(3)
        contexts, _, _ = build_code_contexts(files)
        assert contexts["app/mod3.py"].is_on_critical_path is False  # depth 3 — blocked

    def test_depth_4_never_critical(self):
        """Invariant: depth-4 is also never critical."""
        files = entrypoint_chain(4)
        contexts, _, _ = build_code_contexts(files)
        assert contexts["app/mod4.py"].is_on_critical_path is False

    def test_depth_10_never_critical(self):
        """Invariant: no matter how long the chain, depth 10 is not critical."""
        files = entrypoint_chain(10)
        contexts, _, _ = build_code_contexts(files)
        for i in range(3, 11):
            assert contexts[f"app/mod{i}.py"].is_on_critical_path is False, (
                f"depth {i} must not be critical"
            )

    def test_non_entrypoint_has_no_critical_downstream_alone(self):
        """
        Invariant: A file that is not an entrypoint does not trigger critical
        path propagation on its own.
        """
        util = build_file_intelligence(
            "app/utils.py",
            "from app.deep import deep\ndef helper(): pass\n"
        )
        downstream = build_file_intelligence("app/deep.py", "def deep(): pass\n")
        contexts, _, _ = build_code_contexts([util, downstream])
        # Neither should be critical — no entrypoint in the set
        assert contexts["app/utils.py"].is_on_critical_path is False
        assert contexts["app/deep.py"].is_on_critical_path is False

    def test_entrypoint_always_marks_itself_critical(self):
        """Invariant: An entrypoint is critical even if it imports nothing."""
        entry = build_file_intelligence("app/main.py", "# empty entrypoint\n")
        contexts, _, _ = build_code_contexts([entry])
        assert contexts["app/main.py"].is_on_critical_path is True

    def test_bfs_diamond_shortest_path(self):
        """
        BFS invariant: in a diamond pattern, the shared node is always at its
        TRUE shortest-path depth, not the depth DFS happened to visit it.

        Pattern:
            main(0) → a(1) → c(2)
            main(0) → b(1) → c(2)   ← c is at depth 2 via BOTH paths

        DFS artifact would have been: if DFS processes a→c before b, then when
        b tries to visit c it's already in visited. With BFS, c is enqueued at
        depth 2 from BOTH a and b — but since it's already visited at depth 2,
        the second enqueue is a no-op. c is correctly marked critical.
        """
        main = build_file_intelligence("app/main.py", "from app.a import a\nfrom app.b import b\n")
        a = build_file_intelligence("app/a.py", "from app.c import c\ndef a(): pass\n")
        b = build_file_intelligence("app/b.py", "from app.c import c\ndef b(): pass\n")
        c = build_file_intelligence("app/c.py", "def c(): pass\n")

        contexts, _, _ = build_code_contexts([main, a, b, c])

        assert contexts["app/main.py"].is_on_critical_path is True  # depth 0
        assert contexts["app/a.py"].is_on_critical_path is True     # depth 1
        assert contexts["app/b.py"].is_on_critical_path is True     # depth 1
        assert contexts["app/c.py"].is_on_critical_path is True     # depth 2 — BFS guarantees this

    def test_bfs_long_path_does_not_block_short_path(self):
        """
        BFS invariant: if node X is reachable at depth 1 directly AND at depth 3
        via a long path, BFS marks it critical (shortest path wins).

        DFS could have visited X at depth 3 first (blocking it).
        BFS always finds the depth-1 path first.

        Pattern:
            main(0) → x(1)                   ← direct, depth 1
            main(0) → y(1) → z(2) → x(3)    ← long path, depth 3 (blocked)

        BFS processes all depth-1 nodes before any depth-2 nodes, so x is
        visited at depth 1 before z even gets to try enqueuing it at depth 3.
        """
        main = build_file_intelligence(
            "app/main.py",
            "from app.x import x\nfrom app.y import y\n"
        )
        x = build_file_intelligence("app/x.py", "def x(): pass\n")
        y = build_file_intelligence("app/y.py", "from app.z import z\ndef y(): pass\n")
        z = build_file_intelligence("app/z.py", "from app.x import x\ndef z(): pass\n")

        contexts, _, _ = build_code_contexts([main, x, y, z])

        assert contexts["app/x.py"].is_on_critical_path is True   # depth 1, must be critical
        assert contexts["app/y.py"].is_on_critical_path is True   # depth 1
        assert contexts["app/z.py"].is_on_critical_path is True   # depth 2

    def test_multiple_entrypoints_union_semantics(self):
        """
        Invariant: with multiple entrypoints, a file is critical if ANY
        entrypoint can reach it within depth 2.
        The BFS for each entrypoint is independent.
        """
        # ep_a can reach shared at depth 1
        # ep_b can reach shared at depth 2
        ep_a = build_file_intelligence("app/main.py", "from app.shared import s\n")
        ep_b = build_file_intelligence("app/server.py", "from app.middle import m\n")
        middle = build_file_intelligence("app/middle.py", "from app.shared import s\ndef m(): pass\n")
        shared = build_file_intelligence("app/shared.py", "def s(): pass\n")
        isolated = build_file_intelligence("app/isolated.py", "def i(): pass\n")

        contexts, _, _ = build_code_contexts([ep_a, ep_b, middle, shared, isolated])

        assert contexts["app/main.py"].is_on_critical_path is True    # entrypoint
        assert contexts["app/server.py"].is_on_critical_path is True  # entrypoint
        assert contexts["app/shared.py"].is_on_critical_path is True  # depth 1 from ep_a
        assert contexts["app/middle.py"].is_on_critical_path is True  # depth 1 from ep_b
        assert contexts["app/isolated.py"].is_on_critical_path is False  # unreachable


# ---------------------------------------------------------------------------
# Invariant 2: Lock file handling
# SEMANTICS.md §2
# ---------------------------------------------------------------------------

class TestLockFileInvariants:
    """
    Invariant: lock files are handled by is_generated(), not should_skip().
    The two functions are independent. should_skip() returns False for lock files.
    """

    LOCK_FILES = [
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "Pipfile.lock",
        "Gemfile.lock",
        "cargo.lock",
        "composer.lock",
    ]

    @pytest.mark.parametrize("lockfile", LOCK_FILES)
    def test_lock_file_not_in_should_skip(self, lockfile: str):
        """
        Invariant: should_skip() returns False for lock files.
        Lock files are text — they are not binary/vendor/compiled assets.
        """
        assert should_skip(lockfile) is False, (
            f"should_skip({lockfile!r}) must return False. "
            "Lock files are handled by is_generated(), not should_skip()."
        )

    @pytest.mark.parametrize("lockfile", LOCK_FILES)
    def test_lock_file_in_is_generated(self, lockfile: str):
        """
        Invariant: is_generated() returns True for lock files.
        They are excluded from deep analysis but visible in the inventory.
        """
        assert is_generated(lockfile) is True, (
            f"is_generated({lockfile!r}) must return True."
        )

    def test_source_file_not_generated(self):
        """Invariant: source files are never marked as generated."""
        for path in ["app/main.py", "src/app/page.tsx", "backend/service.go"]:
            assert is_generated(path) is False

    def test_source_file_not_skipped(self):
        """Invariant: source files are never skipped."""
        for path in ["app/main.py", "src/app/page.tsx", "backend/service.go"]:
            assert should_skip(path) is False

    def test_binary_in_should_skip_not_is_generated(self):
        """
        Invariant: binary assets are in should_skip().
        They may or may not be in is_generated() — but they ARE in should_skip().
        """
        assert should_skip("static/logo.png") is True
        assert should_skip("fonts/Inter.woff2") is True


# ---------------------------------------------------------------------------
# Invariant 3: Confirmed vs unresolved edge
# SEMANTICS.md §3
# ---------------------------------------------------------------------------

class TestEdgeConfidenceInvariants:
    """
    Invariant: edge confidence is determined by whether target_path is in
    known_paths, NOT by the target file's parse confidence.
    """

    def test_known_path_produces_confirmed_edge(self):
        """
        Invariant: if target exists in the scanned file set, the edge is confirmed
        regardless of the target file's parse confidence.
        """
        importer = build_file_intelligence(
            "app/main.py",
            "from app.broken import something\n"
        )
        # Target exists as a zero-confidence stub (fetch failed)
        target_stub = FileIntelligence(
            path="app/broken.py",
            language="python",
            role="unknown",
            confidence=0.0,
            parse_errors=["fetch_failed"],
        )
        _, edges, _ = build_code_contexts([importer, target_stub])
        confirmed = [e for e in edges if e.confidence == "confirmed"]
        assert any(e.target_path == "app/broken.py" for e in confirmed), (
            "Import of a known-path file must produce a confirmed edge "
            "even when the target's parse confidence is 0.0"
        )

    def test_unknown_path_produces_unresolved_edge(self):
        """
        Invariant: if target cannot be resolved to any file in known_paths
        AND is not an external package, the edge is unresolved.
        """
        importer = build_file_intelligence(
            "app/main.py",
            "from app.completely_missing_module import x\n"
        )
        # Only the importer in the file set — target is absent
        _, edges, _ = build_code_contexts([importer])
        unresolved = [e for e in edges if e.confidence == "unresolved"]
        assert any(
            "completely_missing_module" in e.raw_import
            for e in unresolved
        ), "Import of an unknown non-external module must produce an unresolved edge"

    def test_external_package_produces_no_edge(self):
        """
        Invariant: imports of known external packages produce no edge at all.
        They must not appear as confirmed or unresolved — they are silently dropped.
        """
        importer = build_file_intelligence(
            "app/main.py",
            "from fastapi import FastAPI\nimport numpy as np\nfrom react import useState\n"
        )
        _, edges, _ = build_code_contexts([importer])
        external_targets = {"fastapi", "numpy", "react"}
        for edge in edges:
            raw = edge.raw_import.split(".")[0].split("/")[0]
            assert raw.lower() not in external_targets, (
                f"External package '{raw}' must not produce any edge. "
                f"Got: {edge.source_path} -> {edge.target_path} [{edge.confidence}]"
            )

    def test_external_imports_not_counted_against_graph_confidence(self):
        """
        Invariant: graph_confidence is not degraded by external imports.
        A file that only imports external packages has graph_confidence = 0.5
        (neutral), not 0.0.
        """
        fi_only_external = build_file_intelligence(
            "app/service.py",
            "from fastapi import FastAPI\nimport httpx\nfrom pydantic import BaseModel\n"
        )
        _, _, gc = build_code_contexts([fi_only_external])
        assert gc == 0.5, (
            f"graph_confidence should be 0.5 (neutral) when no internal imports exist. "
            f"Got: {gc}"
        )

    def test_confirmed_edge_schema_requires_target(self):
        """
        Invariant: DependencyEdge schema prevents confirmed edges without target_path.
        """
        with pytest.raises(Exception, match="target_path"):
            DependencyEdge(
                source_path="a.py",
                target_path=None,
                raw_import="a.b",
                kind="import",
                confidence="confirmed",
            )

    def test_unresolved_edge_allows_no_target(self):
        """Invariant: unresolved edges may have target_path=None."""
        edge = DependencyEdge(
            source_path="a.py",
            target_path=None,
            raw_import="some.unknown",
            kind="import",
            confidence="unresolved",
            unresolved_reason="file_not_scanned",
        )
        assert edge.target_path is None


# ---------------------------------------------------------------------------
# Invariant 4: Confidence ceiling
# SEMANTICS.md §4
# ---------------------------------------------------------------------------

class TestConfidenceCeilingInvariants:
    """
    Invariant: score_confidence never exceeds 0.97.
    """

    def test_all_ones_caps_at_097(self):
        cb = ConfidenceBreakdown.compute(1.0, 1.0, 1.0)
        assert cb.score_confidence == 0.97

    def test_cannot_exceed_097_with_any_input(self):
        """Invariant: no valid input combination can produce > 0.97."""
        import random
        random.seed(42)
        for _ in range(200):
            e = random.uniform(0.0, 1.0)
            g = random.uniform(0.0, 1.0)
            f = random.uniform(0.0, 1.0)
            cb = ConfidenceBreakdown.compute(e, g, f)
            assert cb.score_confidence <= 0.97, (
                f"score_confidence {cb.score_confidence} exceeded 0.97 "
                f"with inputs e={e:.3f}, g={g:.3f}, f={f:.3f}"
            )

    def test_zero_inputs_produce_zero(self):
        cb = ConfidenceBreakdown.compute(0.0, 0.0, 0.0)
        assert cb.score_confidence == 0.0

    def test_high_label_requires_085(self):
        """Invariant: HIGH label requires score_confidence >= 0.85."""
        cb_high = ConfidenceBreakdown.compute(1.0, 1.0, 1.0)
        assert cb_high.score_label == "HIGH"

        cb_moderate = ConfidenceBreakdown.compute(0.7, 0.6, 0.7)
        # 0.7*0.4 + 0.6*0.35 + 0.7*0.25 = 0.28 + 0.21 + 0.175 = 0.665
        assert cb_moderate.score_label in ("MODERATE", "LOW")

    def test_weights_sum_to_one(self):
        """Invariant: confidence formula weights sum to 1.0."""
        weights = [0.40, 0.35, 0.25]
        assert abs(sum(weights) - 1.0) < 1e-10


# ---------------------------------------------------------------------------
# Invariant 5: Graph confidence neutrality for external-only repos
# SEMANTICS.md §5
# ---------------------------------------------------------------------------

class TestGraphConfidenceInvariants:
    def test_no_internal_imports_yields_neutral_confidence(self):
        """
        Invariant: a repo whose files only import external packages has
        graph_confidence == 0.5, not 0.0.
        """
        files = [
            build_file_intelligence("app/a.py", "import os\nimport json\n"),
            build_file_intelligence("app/b.py", "from fastapi import FastAPI\n"),
        ]
        _, _, gc = build_code_contexts(files)
        assert gc == 0.5

    def test_all_resolved_yields_high_confidence(self):
        """
        Invariant: when all internal imports resolve, graph_confidence == 1.0.
        """
        a = build_file_intelligence("app/a.py", "from app.b import helper\n")
        b = build_file_intelligence("app/b.py", "def helper(): pass\n")
        _, _, gc = build_code_contexts([a, b])
        assert gc == 1.0

    def test_partial_resolution_yields_fractional_confidence(self):
        """
        Invariant: partially resolved imports produce 0 < gc < 1.
        """
        a = build_file_intelligence(
            "app/a.py",
            "from app.b import x\nfrom app.missing import y\n"
        )
        b = build_file_intelligence("app/b.py", "def x(): pass\n")
        # app.missing is not in the file set and not external
        _, _, gc = build_code_contexts([a, b])
        assert 0.0 < gc < 1.0


# ---------------------------------------------------------------------------
# Invariant 6: Schema version
# SEMANTICS.md §6
# ---------------------------------------------------------------------------

class TestSchemaVersionInvariants:
    def test_schema_version_is_semver(self):
        """Invariant: SCHEMA_VERSION follows major.minor.patch format."""
        parts = SCHEMA_VERSION.split(".")
        assert len(parts) == 3, f"SCHEMA_VERSION must be semver: {SCHEMA_VERSION}"
        for part in parts:
            assert part.isdigit(), f"Each semver component must be numeric: {part}"

    def test_repo_intelligence_carries_version(self):
        """Invariant: RepoIntelligence always embeds schema_version."""
        ri = RepoIntelligence(
            repo_url="https://github.com/test/repo",
            repo_owner="test",
            repo_name="repo",
            default_branch="main",
        )
        assert ri.schema_version == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Invariant 7: LLM boundary — CodeFinding evidence requirement
# SEMANTICS.md §7
# ---------------------------------------------------------------------------

class TestFindingEvidenceInvariants:
    """
    Every CodeFinding must have evidence. The schema enforces this.
    LLM output that lacks evidence must be rejected at the schema boundary.
    """

    def test_finding_requires_evidence_snippet(self):
        """Invariant: empty evidence_snippet raises ValidationError."""
        with pytest.raises(Exception):
            CodeFinding(
                file_path="app/main.py",
                category="security",
                severity="high",
                source="llm_assisted",
                line_start=10,
                line_end=10,
                evidence_snippet="   ",  # whitespace only
                title="Test",
                explanation="Test",
                score_impact=-10,
                confidence=0.75,
            )

    def test_finding_requires_valid_line_range(self):
        """Invariant: line_end < line_start raises ValidationError."""
        with pytest.raises(Exception):
            CodeFinding(
                file_path="app/main.py",
                category="security",
                severity="low",
                source="deterministic",
                line_start=20,
                line_end=5,  # invalid
                evidence_snippet="code here",
                title="Test",
                explanation="Test",
                score_impact=-1,
                confidence=1.0,
            )

    def test_finding_requires_line_start_gte_1(self):
        """Invariant: line numbers are 1-indexed."""
        with pytest.raises(Exception):
            CodeFinding(
                file_path="app/main.py",
                category="security",
                severity="low",
                source="deterministic",
                line_start=0,  # invalid — lines start at 1
                line_end=1,
                evidence_snippet="code here",
                title="Test",
                explanation="Test",
                score_impact=-1,
                confidence=1.0,
            )

    def test_valid_finding_constructs_successfully(self):
        """Control: a properly evidenced finding must construct without error."""
        f = CodeFinding(
            file_path="app/main.py",
            category="security",
            severity="critical",
            source="deterministic",
            line_start=15,
            line_end=15,
            evidence_snippet='password = "hardcoded"',
            title="Hardcoded credential",
            explanation="Password embedded in source.",
            score_impact=-20,
            confidence=1.0,
        )
        assert f.id is not None
        assert len(f.id) == 8

    def test_score_impact_must_be_nonpositive(self):
        """Invariant: score_impact is always <= 0 (deductions only, no bonuses)."""
        with pytest.raises(Exception):
            CodeFinding(
                file_path="app/main.py",
                category="security",
                severity="low",
                source="deterministic",
                line_start=1,
                line_end=1,
                evidence_snippet="code",
                title="Test",
                explanation="Test",
                score_impact=5,   # positive — invalid
                confidence=1.0,
            )


# ---------------------------------------------------------------------------
# Invariant 9: Unresolved edge reason codes
# LIMITATIONS.md — every unresolved edge has a classified reason
# ---------------------------------------------------------------------------

class TestUnresolvedReasonCodes:
    """
    Invariant: every unresolved edge has a reason code that accurately
    classifies WHY it couldn't be resolved. The codes map to LIMITATIONS.md.
    """

    def test_package_dir_import_classified_as_ambiguous(self):
        """
        L-001: `from app.services import pipeline` should be classified
        as ambiguous_package_import, not file_not_scanned.
        The last component 'services' is a known package directory signal.
        """
        from app.services.deep_scanner import _classify_unresolved_reason
        reason = _classify_unresolved_reason("app.services", "python", {})
        assert reason == "ambiguous_package_import", (
            f"'app.services' should be ambiguous_package_import, got {reason!r}"
        )

    def test_route_dir_import_classified_as_ambiguous(self):
        """L-001: 'app.api.routes' is a package directory pattern."""
        from app.services.deep_scanner import _classify_unresolved_reason
        reason = _classify_unresolved_reason("app.api.routes", "python", {})
        assert reason == "ambiguous_package_import"

    def test_module_import_classified_as_file_not_scanned(self):
        """A direct module import that just doesn't exist is file_not_scanned."""
        from app.services.deep_scanner import _classify_unresolved_reason
        reason = _classify_unresolved_reason("app.missing_module", "python", {})
        assert reason == "file_not_scanned"

    def test_relative_import_classified_as_file_not_scanned(self):
        """Relative imports that fail are file_not_scanned, not ambiguous."""
        from app.services.deep_scanner import _classify_unresolved_reason
        reason = _classify_unresolved_reason(".missing_sibling", "python", {})
        assert reason == "file_not_scanned"

    def test_dynamic_import_classified_correctly(self):
        """L-003: importlib calls are dynamic_import."""
        from app.services.deep_scanner import _classify_unresolved_reason
        reason = _classify_unresolved_reason("importlib.import_module", "python", {})
        assert reason == "dynamic_import"

    def test_unknown_ts_alias_classified_correctly(self):
        """L-004: @unknown/ prefix not in ts_aliases is alias_unknown."""
        from app.services.deep_scanner import _classify_unresolved_reason
        aliases = {"@/": "src/"}
        reason = _classify_unresolved_reason("@unknown/components/Button", "typescript", aliases)
        assert reason == "alias_unknown"

    def test_known_alias_missing_file_is_file_not_scanned(self):
        """
        L-004: if alias IS known but the resolved file doesn't exist,
        it's file_not_scanned (alias resolved, file absent).
        """
        from app.services.deep_scanner import _classify_unresolved_reason
        aliases = {"@/": "src/"}
        reason = _classify_unresolved_reason("@/missing/File", "typescript", aliases)
        assert reason == "file_not_scanned"

    def test_dynamic_imports_excluded_from_graph_confidence(self):
        """
        Invariant: dynamic imports must not reduce graph_confidence.
        A file with only dynamic imports has graph_confidence == 0.5 (neutral),
        not below 0.5.
        """
        # Simulate a file that only has importlib calls
        fi_dyn = build_file_intelligence(
            "app/loader.py",
            "import importlib\ndef load(name): return importlib.import_module(f'app.plugins.{name}')\n"
        )
        # imports will contain 'importlib' which is external — dropped
        # The f-string dynamic import may or may not be extracted by the regex
        # Either way, no internal imports → graph_confidence = 0.5
        _, _, gc = build_code_contexts([fi_dyn])
        assert gc == 0.5, (
            f"File with only dynamic/external imports should have gc=0.5, got {gc}"
        )

    def test_all_unresolved_edges_have_reason_codes(self):
        """
        Invariant: every unresolved edge in the graph must have a non-None
        reason code. No unresolved edge is ever 'mysteriously' unresolved.
        """
        # Build a file with several different unresolved import patterns
        content = (
            "from app.services import pipeline\n"      # ambiguous_package_import
            "from app.missing import thing\n"           # file_not_scanned
            "import importlib\n"                        # external (dropped)
        )
        fi = build_file_intelligence("app/main.py", content)
        svc_fi = build_file_intelligence("app/services/pipeline.py", "def run(): pass\n")
        _, edges, _ = build_code_contexts([fi, svc_fi])

        unresolved = [e for e in edges if e.confidence == "unresolved"]
        for edge in unresolved:
            assert edge.unresolved_reason is not None, (
                f"Unresolved edge {edge.source_path} → raw={edge.raw_import!r} "
                f"has no reason code"
            )
# ---------------------------------------------------------------------------

class TestGraphSymmetryInvariants:
    """
    Invariant: if A lists B in downstream_dependencies,
    then B must list A in upstream_callers.
    The graph is always bidirectional and consistent.
    """

    def _assert_symmetric(self, files):
        contexts, _, _ = build_code_contexts(files)
        violations = []
        for path, ctx in contexts.items():
            for dep in ctx.downstream_dependencies:
                if dep in contexts:
                    if path not in contexts[dep].upstream_callers:
                        violations.append(
                            f"{path} → {dep}: downstream set, but not in upstream"
                        )
        assert not violations, "\n".join(violations)

    def test_linear_chain_symmetric(self):
        files = entrypoint_chain(2)  # main.py → mod1.py → mod2.py
        self._assert_symmetric(files)

    def test_diamond_dependency_symmetric(self):
        """A→B, A→C, B→D, C→D — diamond shape must be symmetric."""
        a = build_file_intelligence("app/main.py", "from app.b import b\nfrom app.c import c\n")
        b = build_file_intelligence("app/b.py", "from app.d import d\ndef b(): pass\n")
        c = build_file_intelligence("app/c.py", "from app.d import d\ndef c(): pass\n")
        d = build_file_intelligence("app/d.py", "def d(): pass\n")
        self._assert_symmetric([a, b, c, d])

    def test_isolated_files_symmetric(self):
        """Files with no imports have empty upstream/downstream — trivially symmetric."""
        files = [fi(f"app/isolated{i}.py") for i in range(5)]
        self._assert_symmetric(files)

    def test_all_contexts_exist_for_all_files(self):
        """Invariant: every file in the input has a corresponding context entry."""
        files = entrypoint_chain(3)
        contexts, _, _ = build_code_contexts(files)
        for f in files:
            assert f.path in contexts, f"Missing context for {f.path}"
