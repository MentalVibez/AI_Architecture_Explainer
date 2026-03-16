"""
Internal severity normalization table.

Do NOT trust external tool severities directly. This table is the product's
judgment layer — it maps tool-native codes to Atlas internal severity levels.

Atlas severity levels:
    critical  — must fix before production (secrets, exploitable vulns)
    high      — serious quality or security gap
    medium    — maintainability, style, or moderate risk
    low       — cosmetic, informational, minor
    info      — purely informational, no penalty

Principle: when in doubt, map conservative (higher severity).
It is better to flag something real than to miss it.
"""

# ── Ruff ─────────────────────────────────────────────────────────────────────
# https://docs.astral.sh/ruff/rules/
RUFF_SEVERITY: dict[str, str] = {
    # F — Pyflakes: real correctness issues
    "F401": "medium",    # unused import
    "F811": "medium",    # redefinition of unused name
    "F821": "high",      # undefined name
    "F841": "low",       # local variable assigned but never used
    "F401": "medium",
    "F811": "medium",

    # E — pycodestyle errors
    "E501": "low",       # line too long
    "E711": "medium",    # comparison to None using ==
    "E712": "medium",    # comparison to True/False
    "E721": "medium",    # type comparison using type()
    "E741": "medium",    # ambiguous variable name

    # W — pycodestyle warnings
    "W291": "low",       # trailing whitespace
    "W292": "low",       # no newline at end of file
    "W391": "low",       # blank line at end of file

    # N — pep8-naming
    "N801": "low",       # class name should use CapWords
    "N802": "low",       # function name should be lowercase
    "N806": "low",       # variable in function should be lowercase

    # S — flake8-bandit (security via Ruff)
    "S101": "low",       # assert statements in production code
    "S102": "high",      # use of exec
    "S103": "medium",    # permissive file permissions
    "S104": "high",      # binding to all interfaces
    "S105": "high",      # hardcoded password
    "S106": "high",      # hardcoded password in function arg
    "S107": "high",      # hardcoded password in function default
    "S108": "medium",    # temp file/dir usage
    "S110": "medium",    # try/except pass (swallowed exception)
    "S301": "high",      # pickle usage (unsafe deserialization)
    "S324": "medium",    # weak hash function
    "S501": "high",      # requests call with cert verification disabled
    "S506": "high",      # unsafe yaml.load
    "S603": "high",      # subprocess call with shell=True
    "S607": "medium",    # partial path in subprocess
    "S608": "high",      # SQL injection via string formatting

    # C — complexity
    "C901": "medium",    # function is too complex (mccabe)

    # B — flake8-bugbear
    "B006": "high",      # mutable default arg
    "B007": "low",       # loop variable not used in loop body
    "B008": "medium",    # function call in default arg
    "B009": "medium",    # do not call getattr with constant
    "B010": "medium",    # do not call setattr with constant
    "B017": "high",      # pytest.raises(Exception) too broad
    "B023": "high",      # function definition in loop
    "B904": "medium",    # raise without from in except

    # ANN — annotations
    "ANN001": "low",     # missing type annotation for function arg
    "ANN201": "low",     # missing return type annotation

    # ERA — commented-out code
    "ERA001": "low",     # commented-out code

    # RUF — Ruff-specific
    "RUF100": "low",     # unused noqa directive
}

RUFF_DEFAULT_SEVERITY = "low"  # for codes not in the table


# ── Bandit ────────────────────────────────────────────────────────────────────
# Bandit has its own severity + confidence. We use both to determine Atlas severity.
# bandit_severity × bandit_confidence → atlas_severity
BANDIT_MATRIX: dict[tuple[str, str], str] = {
    ("HIGH",   "HIGH"):   "critical",
    ("HIGH",   "MEDIUM"): "high",
    ("HIGH",   "LOW"):    "high",
    ("MEDIUM", "HIGH"):   "high",
    ("MEDIUM", "MEDIUM"): "medium",
    ("MEDIUM", "LOW"):    "medium",
    ("LOW",    "HIGH"):   "medium",
    ("LOW",    "MEDIUM"): "low",
    ("LOW",    "LOW"):    "low",
}

BANDIT_DEFAULT_SEVERITY = "medium"


# ── ESLint ────────────────────────────────────────────────────────────────────
# ESLint uses 1 (warn) or 2 (error). We refine by rule name.
ESLINT_RULE_OVERRIDES: dict[str, str] = {
    "no-eval":            "high",
    "no-implied-eval":    "high",
    "no-new-func":        "high",
    "no-unused-vars":     "medium",
    "no-undef":           "high",
    "eqeqeq":             "medium",
    "no-debugger":        "medium",
    "no-console":         "low",
    "@typescript-eslint/no-explicit-any": "medium",
    "@typescript-eslint/no-unsafe-assignment": "medium",
}

ESLINT_LEVEL_MAP = {
    0: "info",
    1: "low",    # warn
    2: "medium", # error — default, rules above can override
}


# ── Gitleaks ──────────────────────────────────────────────────────────────────
# All gitleaks findings are critical by design — a matched secret pattern
# must be treated as a real credential until proven otherwise.
GITLEAKS_DEFAULT_SEVERITY = "critical"

# Rule IDs that are commonly false-positive heavy — downgrade to high
GITLEAKS_LOWER_CONFIDENCE: set[str] = {
    "generic-api-key",
    "generic-secret",
    "password-in-url",
}


# ── Hadolint ─────────────────────────────────────────────────────────────────
HADOLINT_SEVERITY: dict[str, str] = {
    "error":   "high",
    "warning": "medium",
    "info":    "low",
    "style":   "low",
}


def normalize_ruff(code: str) -> str:
    return RUFF_SEVERITY.get(code, RUFF_DEFAULT_SEVERITY)


def normalize_bandit(severity: str, confidence: str) -> str:
    key = (severity.upper(), confidence.upper())
    return BANDIT_MATRIX.get(key, BANDIT_DEFAULT_SEVERITY)


def normalize_eslint(rule_id: str, level: int) -> str:
    if rule_id in ESLINT_RULE_OVERRIDES:
        return ESLINT_RULE_OVERRIDES[rule_id]
    return ESLINT_LEVEL_MAP.get(level, "medium")


def normalize_gitleaks(rule_id: str) -> str:
    if rule_id in GITLEAKS_LOWER_CONFIDENCE:
        return "high"
    return GITLEAKS_DEFAULT_SEVERITY


def normalize_hadolint(level: str) -> str:
    return HADOLINT_SEVERITY.get(level.lower(), "medium")
