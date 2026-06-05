"""Utility for detecting and masking secrets in code."""
import re


class SecretDetector:
    """Detect common secrets in code (API keys, tokens, etc)."""

    # Patterns for common secrets
    PATTERNS = {
        "api_key": r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?([a-zA-Z0-9\-_]{20,})['\"]?",
        "aws_key": r"(?i)(aws_access_key|AKIA[0-9A-Z]{16})",
        "github_token": r"(?i)(github[_-]?token|ghp_[a-zA-Z0-9_]{36,})",
        "private_key": r"-----BEGIN (RSA|DSA|EC|PGP|OPENSSH)? ?PRIVATE KEY",
        "password": r"(?i)(password|passwd)\s*[=:]\s*['\"]([^'\"]{8,})['\"]",
        "slack_token": r"(?i)(xoxb|xoxp|xoxa)-[a-zA-Z0-9]+-[a-zA-Z0-9]+-[a-zA-Z0-9-]{32}",
        "database_url": r"(?i)(database|db)_url\s*[=:]\s*['\"]?([a-zA-Z0-9:/@\-_.]*@[a-zA-Z0-9:/@\-_.]+)['\"]?",
    }

    @staticmethod
    def detect_secrets(text: str) -> list[dict]:
        """Detect secrets in text.

        Args:
            text: Code or config content

        Returns:
            List of detected secrets with type and location
        """
        secrets = []

        for secret_type, pattern in SecretDetector.PATTERNS.items():
            matches = re.finditer(pattern, text, re.MULTILINE)
            for match in matches:
                line_num = text[: match.start()].count("\n") + 1
                secrets.append(
                    {
                        "type": secret_type,
                        "value": match.group(0),
                        "line": line_num,
                        "start": match.start(),
                        "end": match.end(),
                    }
                )

        return secrets

    @staticmethod
    def mask_secret(text: str, start: int, end: int, prefix_len: int = 4) -> str:
        """Mask a secret in text, preserving context.

        Args:
            text: Original text
            start: Secret start index
            end: Secret end index
            prefix_len: How many characters to show before masking

        Returns:
            Text with secret masked
        """
        secret = text[start:end]

        # Show first N chars, then mask
        if len(secret) > prefix_len:
            masked = secret[:prefix_len] + "*" * (len(secret) - prefix_len)
        else:
            masked = "*" * len(secret)

        return text[:start] + masked + text[end:]

    @staticmethod
    def mask_all_secrets(text: str) -> str:
        """Mask all detected secrets in text.

        Args:
            text: Code or config content

        Returns:
            Text with all secrets masked
        """
        secrets = SecretDetector.detect_secrets(text)

        # Sort by position descending so we don't mess up indices
        secrets.sort(key=lambda s: s["start"], reverse=True)

        for secret in secrets:
            text = SecretDetector.mask_secret(text, secret["start"], secret["end"])

        return text

    @staticmethod
    def get_summary(secrets: list[dict]) -> dict:
        """Get summary of detected secrets.

        Returns:
            Summary like {"api_key": 3, "password": 1, ...}
        """
        summary = {}
        for secret in secrets:
            secret_type = secret["type"]
            summary[secret_type] = summary.get(secret_type, 0) + 1

        return summary
