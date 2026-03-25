"""
test_scout_heuristics.py
─────────────────────────────────────────────────────────────────────────────
Deterministic unit tests for the RepoScout heuristic scoring layer.

These tests use no API calls, no LLM, no async.
They verify that every scoring rule does exactly what it claims.

Run: pytest tests/test_scout_heuristics.py -v
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.schemas.scout import SignalType
from app.services.repo_scout import (
    _classify_intent,
    _deduplicate,
    _noise_flags,
    _quality_score,
    _should_exclude,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

def _ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def _repo(**kwargs) -> dict:
    """Base repo dict with sensible defaults."""
    defaults = {
        "id": "test/repo",
        "full_name": "test/repo",
        "platform": "github",
        "stars": 500,
        "forks": 50,
        "updated_at": _ago(30),
        "created_at": _ago(400),   # ~13 months old — old enough for sustained activity bonus
        "license_name": "MIT",
        "readme_verified": False,
        "is_fork": False,
        "is_archived": False,
        "is_template": False,
        "description": "A useful library for building things",
        "topics": ["python", "library", "tools"],
        "language": "Python",
        "open_issues": 5,
    }
    return {**defaults, **kwargs}


# ═════════════════════════════════════════════════════════════════════════════
# Stars scoring
# ═════════════════════════════════════════════════════════════════════════════

class TestStarsScoring:
    def test_mega_star_repo_receives_maximum_star_points(self):
        score, signals = _quality_score(_repo(stars=10_000), [])
        assert score >= 20
        good_labels = [s.label for s in signals if s.type == SignalType.GOOD]
        assert any("stars" in lbl for lbl in good_labels)

    def test_thousand_star_repo_receives_established_tier_bonus(self):
        score, _ = _quality_score(_repo(stars=1_500), [])
        assert score >= 15

    def test_hundred_star_repo_receives_traction_tier_bonus(self):
        score, _ = _quality_score(_repo(stars=150), [])
        star_score_min = 10   # at minimum stars should contribute ~12
        assert score >= star_score_min

    def test_sub_ten_star_repo_receives_bad_signal_not_bonus(self):
        _, signals = _quality_score(_repo(stars=3), [])
        bad = [s for s in signals if s.type == SignalType.BAD and "stars" in s.label]
        assert bad, "Expected a BAD signal for repos with <10 stars"

    def test_zero_star_repo_does_not_crash_and_scores_non_negative(self):
        score, _ = _quality_score(_repo(stars=0), [])
        assert isinstance(score, int)
        assert score >= 0


# ═════════════════════════════════════════════════════════════════════════════
# Recency scoring
# ═════════════════════════════════════════════════════════════════════════════

class TestRecencyScoring:
    def test_recently_updated_repo_outscores_stale_repo_on_recency(self):
        score_recent, _ = _quality_score(_repo(updated_at=_ago(0)), [])
        score_old,    _ = _quality_score(_repo(updated_at=_ago(500)), [])
        assert score_recent > score_old

    def test_repo_updated_within_30_days_receives_active_maintenance_signal(self):
        _, signals = _quality_score(_repo(updated_at=_ago(15)), [])
        good = [
            s for s in signals
            if s.type == SignalType.GOOD
            and ("updated" in s.label.lower() or "active" in s.label.lower())
        ]
        assert good

    def test_repo_not_updated_in_over_a_year_receives_stale_bad_signal(self):
        _, signals = _quality_score(_repo(updated_at=_ago(800)), [])
        bad = [s for s in signals if s.type == SignalType.BAD]
        assert any("stale" in s.label.lower() for s in bad)

    def test_missing_updated_at_field_does_not_crash_scorer(self):
        score, _ = _quality_score(_repo(updated_at=None), [])
        assert isinstance(score, int)


# ═════════════════════════════════════════════════════════════════════════════
# License scoring
# ═════════════════════════════════════════════════════════════════════════════

class TestLicenseScoring:
    def test_known_license_adds_quality_points_over_no_license(self):
        with_license,    _ = _quality_score(_repo(license_name="MIT"), [])
        without_license, _ = _quality_score(_repo(license_name=None), [])
        assert with_license > without_license

    def test_missing_license_receives_warn_signal_because_it_is_legal_adoption_barrier(self):
        _, signals = _quality_score(_repo(license_name=None), [])
        warn = [s for s in signals if s.type == SignalType.WARN and "license" in s.label.lower()]
        assert warn

    def test_noassertion_license_is_treated_as_missing_not_as_valid_license(self):
        _, signals = _quality_score(_repo(license_name="NOASSERTION"), [])
        warn = [s for s in signals if "license" in s.label.lower()]
        assert warn


# ═════════════════════════════════════════════════════════════════════════════
# README handling — the corrected FIX [2] behaviour
# ═════════════════════════════════════════════════════════════════════════════

class TestReadmeHandling:
    def test_github_readme_does_not_increase_quality_score_without_api_verification(self):
        """GitHub repos should NOT get bonus points for readme_verified=False."""
        base = _repo(platform="github", readme_verified=False)
        score_no_readme, _ = _quality_score(base, [])
        # Setting readme_verified=True on github should make no difference
        base_with_flag = _repo(platform="github", readme_verified=True)
        score_with_flag, _ = _quality_score(base_with_flag, [])
        # Score should be the same regardless — GitHub README is not scored
        assert score_no_readme == score_with_flag

    def test_github_readme_signal_is_always_marked_verified_false(self):
        _, signals = _quality_score(_repo(platform="github", readme_verified=False), [])
        unverified = [s for s in signals if not s.verified]
        assert unverified, "GitHub README signal should be marked verified=False"

    def test_gitlab_verified_readme_adds_expected_quality_bonus(self):
        with_readme,    _ = _quality_score(_repo(platform="gitlab", readme_verified=True), [])
        without_readme, _ = _quality_score(_repo(platform="gitlab", readme_verified=False), [])
        assert with_readme > without_readme

    def test_gitlab_confirmed_readme_signal_has_verified_true(self):
        _, signals = _quality_score(_repo(platform="gitlab", readme_verified=True), [])
        verified_readme = [
            s for s in signals
            if s.verified and "readme" in s.label.lower()
        ]
        assert verified_readme


# ═════════════════════════════════════════════════════════════════════════════
# Score ceiling
# ═════════════════════════════════════════════════════════════════════════════

class TestScoreCeiling:
    def test_quality_score_cannot_exceed_70_regardless_of_inputs(self):
        """Quality score max is 70 — relevance covers the remaining 30."""
        perfect = _repo(
            stars=100_000,
            forks=20_000,
            updated_at=_ago(0),
            license_name="MIT",
            readme_verified=True,
            platform="gitlab",
            description="A" * 100,
            topics=["a", "b", "c", "d"],
        )
        score, _ = _quality_score(perfect, [])
        assert score <= 70, f"Quality score exceeded ceiling: {score}"

    def test_quality_score_never_goes_negative_under_maximum_penalties(self):
        """Even with all penalties applied, score should not go negative."""
        terrible = _repo(
            stars=0, forks=0, updated_at=_ago(2000),
            license_name=None, readme_verified=False,
            is_fork=True, is_archived=True,
            description="",
        )
        flags = _noise_flags(terrible)
        score, _ = _quality_score(terrible, flags)
        assert score >= 0


# ═════════════════════════════════════════════════════════════════════════════
# Noise flags
# ═════════════════════════════════════════════════════════════════════════════

class TestNoiseFlags:
    def test_is_fork_true_produces_fork_noise_flag(self):
        flags = _noise_flags(_repo(is_fork=True))
        assert "fork" in flags

    def test_is_archived_true_produces_archived_noise_flag(self):
        flags = _noise_flags(_repo(is_archived=True))
        assert "archived" in flags

    def test_is_template_true_produces_template_noise_flag(self):
        flags = _noise_flags(_repo(is_template=True))
        assert "template" in flags

    def test_empty_description_produces_no_description_noise_flag(self):
        flags = _noise_flags(_repo(description=""))
        assert "no description" in flags

    def test_mirror_keyword_in_description_produces_possible_mirror_flag(self):
        flags = _noise_flags(_repo(description="Mirror of the original langchain repo"))
        assert "possible mirror" in flags

    def test_mirror_keyword_in_repo_name_produces_possible_mirror_flag(self):
        flags = _noise_flags(_repo(full_name="user/langchain-mirror"))
        assert "possible mirror" in flags

    def test_repo_with_no_noise_attributes_produces_no_flags(self):
        flags = _noise_flags(_repo())
        assert not flags

    def test_fork_flag_reduces_quality_score_relative_to_clean_equivalent(self):
        clean_score, _ = _quality_score(_repo(is_fork=False, stars=500), [])
        fork_score,  _ = _quality_score(_repo(is_fork=True,  stars=500), ["fork"])
        assert clean_score > fork_score


# ═════════════════════════════════════════════════════════════════════════════
# Hard exclusions
# ═════════════════════════════════════════════════════════════════════════════

class TestHardExclusions:
    def test_archived_repo_below_50_stars_is_hard_excluded_from_results(self):
        repo = _repo(is_archived=True, stars=10)
        flags = _noise_flags(repo)
        assert _should_exclude(repo, flags)

    def test_archived_repo_above_50_stars_survives_for_discoverability(self):
        """High-star archived repos should survive for discoverability."""
        repo = _repo(is_archived=True, stars=5_000)
        flags = _noise_flags(repo)
        assert not _should_exclude(repo, flags)

    def test_fork_below_20_stars_is_hard_excluded_as_shallow_clone(self):
        repo = _repo(is_fork=True, stars=5)
        flags = ["fork"]
        assert _should_exclude(repo, flags)

    def test_high_traction_fork_survives_because_it_may_be_a_valued_divergence(self):
        """High-traction forks (e.g. a popular hardened fork) should survive."""
        repo = _repo(is_fork=True, stars=500)
        flags = ["fork"]
        assert not _should_exclude(repo, flags)


# ═════════════════════════════════════════════════════════════════════════════
# Deduplication
# ═════════════════════════════════════════════════════════════════════════════

class TestDeduplication:
    def test_same_repo_name_on_two_platforms_keeps_only_higher_starred_version(self):
        repos = [
            _repo(id="gh_1", full_name="user/langchain", stars=1000, platform="github"),
            _repo(id="gl_1", full_name="group/langchain", stars=200, platform="gitlab"),
        ]
        deduped = _deduplicate(repos)
        assert len(deduped) == 1
        assert deduped[0]["id"] == "gh_1", "Higher-starred version should be kept"

    def test_repos_with_distinct_names_are_never_deduplicated(self):
        repos = [
            _repo(id="gh_1", full_name="user/langchain",   stars=1000),
            _repo(id="gh_2", full_name="user/llama_index",  stars=800),
        ]
        deduped = _deduplicate(repos)
        assert len(deduped) == 2

    def test_empty_repo_list_returns_empty_deduplicated_list(self):
        assert _deduplicate([]) == []

    def test_single_repo_list_returns_itself_unchanged(self):
        repos = [_repo()]
        assert _deduplicate(repos) == repos


# ═════════════════════════════════════════════════════════════════════════════
# Activity scoring (replaces flat recency)
# ═════════════════════════════════════════════════════════════════════════════

class TestActivityScoring:
    def test_sustained_repo_outscores_recently_reactivated_equivalent(self):
        """
        Same update recency, different track record.
        Old + recently active > new + recently active.
        """
        sustained, _ = _quality_score(
            _repo(updated_at=_ago(20), created_at=_ago(730)), []
        )
        reactivated, _ = _quality_score(
            _repo(updated_at=_ago(20), created_at=_ago(25)), []
        )
        assert sustained > reactivated

    def test_sustained_activity_signal_contains_track_record_text(self):
        _, signals = _quality_score(
            _repo(updated_at=_ago(20), created_at=_ago(730)), []
        )
        track_record_signals = [
            s for s in signals
            if "track record" in s.label.lower() and s.type == SignalType.GOOD
        ]
        assert track_record_signals

    def test_recently_created_repo_gets_no_sustained_bonus(self):
        """A brand-new repo cannot have a track record."""
        _, signals = _quality_score(
            _repo(updated_at=_ago(5), created_at=_ago(10)), []
        )
        track_record_signals = [s for s in signals if "track record" in s.label.lower()]
        assert not track_record_signals

    def test_activity_score_never_exceeds_15_point_budget(self):
        """Recency + sustained bonus is capped at 15 pts regardless."""
        score_active, _ = _quality_score(
            _repo(
                stars=0, forks=0, license_name=None, platform="github",
                description="x" * 5, topics=[],
                updated_at=_ago(1), created_at=_ago(800),
                open_issues=0,
            ),
            [],
        )
        score_stale, _ = _quality_score(
            _repo(
                stars=0, forks=0, license_name=None, platform="github",
                description="x" * 5, topics=[],
                updated_at=_ago(500), created_at=_ago(800),
                open_issues=0,
            ),
            [],
        )
        assert (score_active - score_stale) <= 15

    def test_missing_created_at_falls_back_gracefully_without_crash(self):
        score, _ = _quality_score(_repo(updated_at=_ago(20), created_at=None), [])
        assert isinstance(score, int)
        assert score >= 0


# ═════════════════════════════════════════════════════════════════════════════
# Issue health signal
# ═════════════════════════════════════════════════════════════════════════════

class TestIssueHealth:
    def test_high_issue_ratio_above_threshold_reduces_score(self):
        """open_issues / stars > 0.5 with >= 50 stars should penalise quality."""
        penalised, _ = _quality_score(_repo(stars=100, open_issues=60), [])   # ratio 0.6
        baseline,  _ = _quality_score(_repo(stars=100, open_issues=5),  [])   # ratio 0.05
        assert baseline > penalised

    def test_low_issue_ratio_below_threshold_adds_points(self):
        """open_issues / stars < 0.05 with >= 100 stars should boost quality."""
        boosted,  _ = _quality_score(_repo(stars=200, open_issues=3),  [])   # ratio 0.015
        baseline, _ = _quality_score(_repo(stars=200, open_issues=20), [])   # ratio 0.10
        assert boosted > baseline

    def test_issue_penalty_not_applied_below_50_star_threshold(self):
        """Small repos with high ratio should not be penalised — sample too small."""
        score_high, _ = _quality_score(_repo(stars=10, open_issues=20), [])   # ratio 2.0
        score_low,  _ = _quality_score(_repo(stars=10, open_issues=0),  [])
        assert score_high == score_low

    def test_issue_bonus_not_applied_below_100_star_threshold(self):
        """Low-ratio but low-star repos should not receive the bonus."""
        score_low_stars, _ = _quality_score(_repo(stars=50, open_issues=0),  [])
        score_neutral,   _ = _quality_score(_repo(stars=50, open_issues=10), [])
        assert score_low_stars == score_neutral

    def test_zero_stars_does_not_cause_division_by_zero(self):
        score, _ = _quality_score(_repo(stars=0, open_issues=5), [])
        assert isinstance(score, int)
        assert score >= 0

    def test_high_issue_ratio_signal_is_labelled_warn(self):
        _, signals = _quality_score(_repo(stars=200, open_issues=150), [])
        warn_signals = [
            s for s in signals
            if s.type == SignalType.WARN and "issue" in s.label.lower()
        ]
        assert warn_signals

    def test_low_issue_ratio_signal_is_labelled_good(self):
        _, signals = _quality_score(_repo(stars=200, open_issues=2), [])
        good_signals = [
            s for s in signals
            if s.type == SignalType.GOOD and "issue" in s.label.lower()
        ]
        assert good_signals


# ═════════════════════════════════════════════════════════════════════════════
# Intent classifier
# ═════════════════════════════════════════════════════════════════════════════

class TestIntentClassifier:
    def test_library_keywords_map_to_library_intent(self):
        assert _classify_intent("Python SDK for OpenAI API") == "library"
        assert _classify_intent("npm package for date formatting") == "library"

    def test_example_keywords_map_to_example_intent(self):
        assert _classify_intent("RAG tutorial LangChain") == "example"
        assert _classify_intent("nextjs starter boilerplate") == "example"

    def test_tool_keywords_map_to_tool_intent(self):
        assert _classify_intent("CLI tool for docker automation") == "tool"
        assert _classify_intent("bash script utility") == "tool"

    def test_framework_keywords_map_to_framework_intent(self):
        assert _classify_intent("web framework Python") == "framework"
        assert _classify_intent("ML platform for training") == "framework"

    def test_model_keywords_map_to_model_intent(self):
        assert _classify_intent("fine-tuned model weights LLaMA") == "model"
        assert _classify_intent("training dataset benchmark") == "model"

    def test_unrecognised_query_falls_back_to_general(self):
        assert _classify_intent("RAG pipeline LangChain") == "general"
        assert _classify_intent("async queue processor") == "general"

    def test_classifier_is_case_insensitive(self):
        assert _classify_intent("PYTHON SDK") == "library"
        assert _classify_intent("CLI TOOL") == "tool"

    def test_empty_query_returns_general(self):
        assert _classify_intent("") == "general"

    def test_word_boundary_prevents_partial_keyword_match(self):
        """'learning' should not match the 'learn' keyword."""
        assert _classify_intent("best repos for learning") == "general"
