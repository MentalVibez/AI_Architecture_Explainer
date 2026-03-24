import re

_GITHUB_URL_RE = re.compile(
    r"https://github\.com/(?P<owner>[a-zA-Z0-9_-]+)/(?P<repo>[a-zA-Z0-9_.-]+?)(?:\.git)?(?:[/?#].*)?$"
)


def parse_github_url(url: str) -> tuple[str, str] | None:
    match = _GITHUB_URL_RE.match(url.strip())
    if not match:
        return None
    return match.group("owner"), match.group("repo")
