# ruff: noqa: I001

import sys
from importlib import import_module
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from app.services.reviewer.facts import models as backend_facts_models  # noqa: E402
from app.services.reviewer.service import ReviewError, run_review  # noqa: E402


def test_atlas_reviewer_service_alias_matches_backend():
    legacy_service = import_module("atlas_reviewer.service")

    assert legacy_service.run_review is run_review
    assert legacy_service.ReviewError is ReviewError


def test_atlas_reviewer_nested_module_alias_matches_backend():
    legacy_models = import_module("atlas_reviewer.facts.models")

    assert legacy_models is backend_facts_models
