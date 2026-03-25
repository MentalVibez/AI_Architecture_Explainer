"""
Derives higher-level metrics (test count, source count, router count) from the fact store.
"""
from pathlib import Path

from ..models import RepoFacts


def collect(facts: RepoFacts) -> None:
    files = facts.structure.files

    facts.metrics.test_file_count = sum(
        1 for f in files
        if "test" in Path(f).parts
        or Path(f).stem.startswith("test_")
        or Path(f).stem.endswith("_test")
    )
    source_extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"}
    facts.metrics.source_file_count = sum(
        1 for f in files
        if Path(f).suffix in source_extensions
        and "test" not in Path(f).parts
        and "vendor" not in Path(f).parts
    )
    facts.metrics.router_file_count = sum(
        1 for f in files
        if "router" in Path(f).stem.lower() or "route" in Path(f).stem.lower()
    )
