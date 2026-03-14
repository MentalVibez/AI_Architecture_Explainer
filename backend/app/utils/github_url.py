import re


_GITHUB_URL_RE = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$"
)


def parse_github_url(url: str) -> tuple[str, str] | None:
    match = _GITHUB_URL_RE.match(url.strip())
    if not match:
        return None
    return match.group("owner"), match.group("repo")
