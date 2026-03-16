"""
Detects primary programming languages from the file tree.
Uses file extension counting — no AST, no external tools.
Populates facts.languages.primary and facts.languages.by_file_count.
"""
from pathlib import Path
from ..models import RepoFacts, LanguageFacts
from collections import Counter

EXTENSION_MAP = {
    ".py":     "Python",
    ".ts":     "TypeScript",
    ".tsx":    "TypeScript",
    ".js":     "JavaScript",
    ".jsx":    "JavaScript",
    ".go":     "Go",
    ".rs":     "Rust",
    ".java":   "Java",
    ".rb":     "Ruby",
    ".cs":     "C#",
    ".cpp":    "C++",
    ".c":      "C",
    ".swift":  "Swift",
    ".kt":     "Kotlin",
    ".php":    "PHP",
}

SKIP_DIRS = {"node_modules", ".next", "dist", "build", ".venv", "venv",
             "vendor", "__pycache__", ".git", "coverage"}

MIN_FILE_THRESHOLD = 2   # language must appear at least this many times


def collect(facts: RepoFacts) -> None:
    counts: Counter = Counter()

    for filepath in facts.structure.files:
        p = Path(filepath)
        # Skip if in a vendored/generated directory
        parts = set(p.parts)
        if parts & SKIP_DIRS:
            continue
        lang = EXTENSION_MAP.get(p.suffix.lower())
        if lang:
            counts[lang] += 1

    # Filter to languages with meaningful presence
    significant = {lang: count for lang, count in counts.items() if count >= MIN_FILE_THRESHOLD}

    if not significant:
        facts.languages = LanguageFacts(primary=[], by_file_count=dict(counts))
        return

    # Primary = languages representing >10% of detected files, sorted by count
    total = sum(significant.values())
    primary = sorted(
        [lang for lang, count in significant.items() if count / total >= 0.10],
        key=lambda l: significant[l],
        reverse=True,
    )
    if not primary:
        primary = [max(significant, key=significant.get)]

    facts.languages = LanguageFacts(primary=primary, by_file_count=dict(significant))
