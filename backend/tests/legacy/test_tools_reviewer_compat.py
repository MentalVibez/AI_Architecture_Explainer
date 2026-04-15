# ruff: noqa: I001

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from Tools.exports.json_exporter import export as tools_json_export  # noqa: E402
from Tools.exports.markdown_exporter import export as tools_markdown_export  # noqa: E402
from Tools.service import ReviewError as tools_review_error  # noqa: E402
from Tools.service import run_review as tools_run_review  # noqa: E402
from app.services.reviewer.exports.json_exporter import export as backend_json_export  # noqa: E402
from app.services.reviewer.exports.markdown_exporter import export as backend_markdown_export  # noqa: E402
from app.services.reviewer.service import ReviewError, run_review  # noqa: E402


def test_tools_service_shim_matches_backend_service():
    assert tools_run_review is run_review
    assert tools_review_error is ReviewError


def test_tools_export_shims_match_backend_exports():
    assert tools_json_export is backend_json_export
    assert tools_markdown_export is backend_markdown_export
