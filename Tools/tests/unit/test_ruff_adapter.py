"""
Tests for RuffAdapter normalization.
Does not invoke ruff binary — tests the normalize() method directly.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

import json
from atlas_reviewer.adapters.ruff import RuffAdapter
from atlas_reviewer.adapters.base import AdapterStatus


SAMPLE_RUFF_OUTPUT = json.dumps([
    {
        "code": "F401",
        "message": "'os' imported but unused",
        "filename": "src/main.py",
        "location": {"row": 1, "column": 1},
        "end_location": {"row": 1, "column": 9},
        "fix": None,
        "noqa_row": None,
        "url": "https://docs.astral.sh/ruff/rules/F401",
    },
    {
        "code": "S603",
        "message": "subprocess call with shell=True identified",
        "filename": "src/utils.py",
        "location": {"row": 42, "column": 5},
        "end_location": {"row": 42, "column": 25},
        "fix": None,
        "noqa_row": None,
        "url": "https://docs.astral.sh/ruff/rules/S603",
    },
    {
        "code": "E501",
        "message": "line too long (120 > 100 characters)",
        "filename": "src/models.py",
        "location": {"row": 88, "column": 101},
        "end_location": {"row": 88, "column": 120},
        "fix": None,
        "noqa_row": None,
        "url": "https://docs.astral.sh/ruff/rules/E501",
    },
])


def test_normalize_produces_correct_count():
    adapter = RuffAdapter()
    issues = adapter.normalize(SAMPLE_RUFF_OUTPUT)
    assert len(issues) == 3


def test_security_rule_maps_to_high():
    adapter = RuffAdapter()
    issues = adapter.normalize(SAMPLE_RUFF_OUTPUT)
    s603 = next(i for i in issues if i.rule_code == "S603")
    assert s603.severity == "high"
    assert "security" in s603.tags


def test_import_rule_maps_to_medium():
    adapter = RuffAdapter()
    issues = adapter.normalize(SAMPLE_RUFF_OUTPUT)
    f401 = next(i for i in issues if i.rule_code == "F401")
    assert f401.severity == "medium"


def test_style_rule_maps_to_low():
    adapter = RuffAdapter()
    issues = adapter.normalize(SAMPLE_RUFF_OUTPUT)
    e501 = next(i for i in issues if i.rule_code == "E501")
    assert e501.severity == "low"


def test_file_and_line_preserved():
    adapter = RuffAdapter()
    issues = adapter.normalize(SAMPLE_RUFF_OUTPUT)
    f401 = next(i for i in issues if i.rule_code == "F401")
    assert f401.file == "src/main.py"
    assert f401.line == 1


def test_raw_output_preserved():
    adapter = RuffAdapter()
    issues = adapter.normalize(SAMPLE_RUFF_OUTPUT)
    assert all(i.raw for i in issues)


def test_invalid_json_returns_empty():
    adapter = RuffAdapter()
    assert adapter.normalize("not json") == []


def test_empty_output_returns_empty():
    adapter = RuffAdapter()
    assert adapter.normalize("[]") == []
