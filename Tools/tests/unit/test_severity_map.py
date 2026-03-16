import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from atlas_reviewer.adapters.severity_map import (
    normalize_ruff, normalize_bandit, normalize_gitleaks, normalize_hadolint,
)


def test_ruff_security_codes_are_high_or_above():
    security_codes = ["S603", "S105", "S106", "S107", "S608", "S506", "S501"]
    for code in security_codes:
        result = normalize_ruff(code)
        assert result in ("critical", "high"), f"{code} mapped to {result}, expected high or critical"


def test_ruff_style_codes_are_low():
    style_codes = ["E501", "W291", "W292", "W391"]
    for code in style_codes:
        assert normalize_ruff(code) == "low", f"{code} should be low"


def test_ruff_unknown_code_returns_low():
    assert normalize_ruff("ZZZZ999") == "low"


def test_bandit_high_high_is_critical():
    assert normalize_bandit("HIGH", "HIGH") == "critical"


def test_bandit_low_low_is_low():
    assert normalize_bandit("LOW", "LOW") == "low"


def test_gitleaks_generic_key_is_high():
    assert normalize_gitleaks("generic-api-key") == "high"


def test_gitleaks_specific_secret_is_critical():
    assert normalize_gitleaks("aws-access-token") == "critical"


def test_hadolint_error_is_high():
    assert normalize_hadolint("error") == "high"


def test_hadolint_style_is_low():
    assert normalize_hadolint("style") == "low"
