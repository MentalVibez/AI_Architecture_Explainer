"""
GitHub repo URL normalizer and validator.
"""
import re
from dataclasses import dataclass

GITHUB_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/"
    r"([A-Za-z0-9][A-Za-z0-9_.-]*)/"
    r"([A-Za-z0-9][A-Za-z0-9_.-]*)"
    r"(?:\.git)?(?:[/?#].*)?"
    r"$"
)


@dataclass
class NormalizedRepo:
    owner: str
    name: str
    clone_url: str
    canonical_url: str


def normalize_repo_url(raw_url: str) -> NormalizedRepo:
    """
    Parse and normalize a GitHub repo URL.
    Raises ValueError with a descriptive message on any unrecognized shape.
    """
    url = raw_url.strip().rstrip("/")

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    match = GITHUB_PATTERN.match(url)
    if not match:
        raise ValueError(
            f"Unrecognized GitHub URL: {raw_url!r}. "
            "Expected format: https://github.com/owner/repo"
        )

    owner = match.group(1)
    name  = match.group(2)

    # Strip trailing .git from name if the regex captured it
    if name.endswith(".git"):
        name = name[:-4]

    if owner in ("orgs", "users", "topics", "explore", "marketplace", "settings"):
        raise ValueError(
            f"URL appears to be a GitHub profile or org page, not a repo: {raw_url!r}"
        )

    # Must have both owner and repo segments
    if not owner or not name:
        raise ValueError(
            f"Could not extract owner/repo from: {raw_url!r}"
        )

    return NormalizedRepo(
        owner=owner,
        name=name,
        clone_url=f"https://github.com/{owner}/{name}.git",
        canonical_url=f"https://github.com/{owner}/{name}",
    )
