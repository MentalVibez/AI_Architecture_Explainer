import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

import json
from atlas_reviewer.adapters.bandit import BanditAdapter

SAMPLE_BANDIT_OUTPUT = json.dumps({
    "results": [
        {
            "test_id": "B106",
            "test_name": "hardcoded_password_funcarg",
            "issue_text": "Possible hardcoded password: 'secret'",
            "issue_severity": "LOW",
            "issue_confidence": "MEDIUM",
            "filename": "app/config.py",
            "line_number": 22,
        },
        {
            "test_id": "B301",
            "test_name": "pickle",
            "issue_text": "Pickle and modules that wrap it can be unsafe.",
            "issue_severity": "MEDIUM",
            "issue_confidence": "HIGH",
            "filename": "app/cache.py",
            "line_number": 8,
        },
        {
            "test_id": "B102",
            "test_name": "exec_used",
            "issue_text": "Use of exec detected.",
            "issue_severity": "HIGH",
            "issue_confidence": "HIGH",
            "filename": "app/utils.py",
            "line_number": 55,
        },
    ],
    "metrics": {}
})


def test_high_high_maps_to_critical():
    adapter = BanditAdapter()
    issues = adapter.normalize(SAMPLE_BANDIT_OUTPUT)
    exec_issue = next(i for i in issues if i.rule_code == "B102")
    assert exec_issue.severity == "critical"


def test_medium_high_maps_to_high():
    adapter = BanditAdapter()
    issues = adapter.normalize(SAMPLE_BANDIT_OUTPUT)
    pickle_issue = next(i for i in issues if i.rule_code == "B301")
    assert pickle_issue.severity == "high"


def test_low_medium_maps_to_low():
    adapter = BanditAdapter()
    issues = adapter.normalize(SAMPLE_BANDIT_OUTPUT)
    pwd_issue = next(i for i in issues if i.rule_code == "B106")
    assert pwd_issue.severity == "low"


def test_all_tagged_security():
    adapter = BanditAdapter()
    issues = adapter.normalize(SAMPLE_BANDIT_OUTPUT)
    assert all("security" in i.tags for i in issues)


def test_empty_results_key_returns_empty():
    adapter = BanditAdapter()
    assert adapter.normalize(json.dumps({"results": [], "metrics": {}})) == []
