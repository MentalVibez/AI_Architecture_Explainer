from app.utils.github_url import parse_github_url


def test_parse_standard_url():
    assert parse_github_url("https://github.com/vercel/next.js") == ("vercel", "next.js")


def test_parse_trailing_slash():
    assert parse_github_url("https://github.com/owner/repo/") == ("owner", "repo")


def test_parse_git_suffix():
    assert parse_github_url("https://github.com/owner/repo.git") == ("owner", "repo")


def test_invalid_url():
    assert parse_github_url("https://gitlab.com/owner/repo") is None


def test_not_a_url():
    assert parse_github_url("just-some-text") is None
