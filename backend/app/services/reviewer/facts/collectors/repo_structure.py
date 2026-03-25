"""
Walks the cloned repo and populates structure + file metrics.
Skips generated/vendor directories.
"""
import os
from pathlib import Path

from ..models import FileMetric, RepoFacts, RepoStructure

SKIP_DIRS = {
    "node_modules", ".next", "dist", "build", ".venv", "venv",
    "vendor", "__pycache__", ".git", ".mypy_cache", ".pytest_cache",
    "coverage", ".terraform",
}

LARGE_FILE_THRESHOLD = 500


def collect(facts: RepoFacts, repo_path: str) -> None:
    root = Path(repo_path)
    files, directories = [], []
    file_metrics: dict = {}
    large_files = []
    max_depth = 0
    total_files = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_dir = str(Path(dirpath).relative_to(root))
        depth = rel_dir.count(os.sep)
        max_depth = max(max_depth, depth)
        if rel_dir != ".":
            directories.append(rel_dir)

        for fname in filenames:
            fpath = Path(dirpath) / fname
            rel_path = str(fpath.relative_to(root))
            files.append(rel_path)
            total_files += 1
            try:
                content = fpath.read_text(errors="ignore")
                line_count = content.count("\n") + 1
                size_bytes = fpath.stat().st_size
                metric = FileMetric(path=rel_path, line_count=line_count, size_bytes=size_bytes)
                file_metrics[rel_path] = metric
                if line_count >= LARGE_FILE_THRESHOLD:
                    large_files.append(metric)
            except Exception:
                pass

    facts.structure = RepoStructure(files=files, directories=directories, max_depth=max_depth)
    facts.metrics.file_metrics = file_metrics
    facts.metrics.large_files = large_files
    facts.metrics.total_file_count = total_files
