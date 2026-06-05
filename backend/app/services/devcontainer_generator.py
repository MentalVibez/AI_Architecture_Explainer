"""Generate devcontainer.json configurations from analysis results."""
from typing import Any

from app.schemas.devcontainer import DevcontainerConfig


class DevcontainerGenerator:
    """Generate production-adjacent devcontainer configurations."""

    LANGUAGE_IMAGES = {
        "python": "mcr.microsoft.com/devcontainers/python:3-3.11",
        "node": "mcr.microsoft.com/devcontainers/nodejs:18",
        "go": "mcr.microsoft.com/devcontainers/go:1",
        "java": "mcr.microsoft.com/devcontainers/java:17",
        "rust": "mcr.microsoft.com/devcontainers/rust:1",
    }

    FRAMEWORK_FEATURES = {
        "fastapi": ["ghcr.io/devcontainers/features/python:latest"],
        "django": ["ghcr.io/devcontainers/features/python:latest"],
        "flask": ["ghcr.io/devcontainers/features/python:latest"],
        "react": ["ghcr.io/devcontainers/features/node:latest"],
        "nextjs": ["ghcr.io/devcontainers/features/node:latest"],
        "express": ["ghcr.io/devcontainers/features/node:latest"],
        "gin": ["ghcr.io/devcontainers/features/go:latest"],
        "spring": ["ghcr.io/devcontainers/features/java:latest"],
    }

    SERVICE_IMAGES = {
        "postgres": {"image": "postgres:15", "ports": {"5432": 5432}},
        "mysql": {"image": "mysql:8", "ports": {"3306": 3306}},
        "redis": {"image": "redis:7", "ports": {"6379": 6379}},
        "mongodb": {"image": "mongo:6", "ports": {"27017": 27017}},
    }

    @classmethod
    def generate(
        cls,
        languages: list[str],
        frameworks: list[str],
        services: list[str],
        custom_features: list[str],
    ) -> DevcontainerConfig:
        """Generate devcontainer configuration from detected stack.

        Args:
            languages: Primary languages detected (python, node, go, etc)
            frameworks: Frameworks detected (fastapi, react, django, etc)
            services: Services needed (postgres, redis, etc)
            custom_features: Additional features

        Returns:
            DevcontainerConfig ready for JSON serialization
        """
        # Determine base image (use first language)
        base_image = cls.LANGUAGE_IMAGES.get(
            languages[0] if languages else "python",
            "mcr.microsoft.com/devcontainers/base:ubuntu",
        )

        # Collect features
        features = custom_features.copy()

        # Add framework features
        for framework in frameworks:
            framework_features = cls.FRAMEWORK_FEATURES.get(framework.lower(), [])
            features.extend(framework_features)

        # Always add git + docker
        if "ghcr.io/devcontainers/features/git:latest" not in features:
            features.append("ghcr.io/devcontainers/features/git:latest")
        if "ghcr.io/devcontainers/features/docker-in-docker:latest" not in features:
            features.append("ghcr.io/devcontainers/features/docker-in-docker:latest")

        # Build services dict
        services_dict = {}
        for service in services:
            service_lower = service.lower()
            if service_lower in cls.SERVICE_IMAGES:
                services_dict[service_lower] = cls.SERVICE_IMAGES[service_lower]

        # Build post-create command
        post_create_cmd = cls._build_post_create_command(languages, frameworks)

        # Build customizations
        customizations = cls._build_customizations()

        return DevcontainerConfig(
            name=f"atlas-dev-{'-'.join(languages[:2]) if languages else 'base'}",
            image=base_image,
            features=features,
            services=services_dict,
            postCreateCommand=post_create_cmd,
            customizations=customizations,
        )

    @classmethod
    def _build_post_create_command(cls, languages: list[str], frameworks: list[str]) -> str:
        """Build installation command based on detected languages."""
        commands = []

        # Python setup
        if "python" in languages:
            commands.extend(
                [
                    "python -m pip install --upgrade pip",
                    "if [ -f requirements.txt ]; then pip install -r requirements.txt; fi",
                    "if [ -f pyproject.toml ]; then pip install -e .; fi",
                ]
            )

        # Node setup
        if "node" in languages:
            commands.extend(
                [
                    "npm install",
                ]
            )

        # Go setup
        if "go" in languages:
            commands.extend(
                [
                    "go mod download",
                ]
            )

        return " && ".join(commands) if commands else ""

    @classmethod
    def _build_customizations(cls) -> dict[str, Any]:
        """Build IDE customizations (VS Code extensions, settings)."""
        return {
            "vscode": {
                "extensions": [
                    "ms-python.python",  # Python
                    "ms-python.vscode-pylance",  # Python type checking
                    "dbaeumer.vscode-eslint",  # ESLint
                    "esbenp.prettier-vscode",  # Prettier
                    "golang.go",  # Go
                    "charliermarsh.ruff",  # Ruff (Python linter)
                    "mhutchie.git-graph",  # Git Graph
                    "ms-azuretools.vscode-docker",  # Docker
                ],
                "settings": {
                    "python.linting.enabled": True,
                    "python.linting.ruffEnabled": True,
                    "python.formatting.provider": "black",
                    "[python]": {"editor.defaultFormatter": "ms-python.python"},
                    "[javascript]": {"editor.defaultFormatter": "esbenp.prettier-vscode"},
                    "[typescript]": {"editor.defaultFormatter": "esbenp.prettier-vscode"},
                },
            }
        }

    @classmethod
    def to_json(cls, config: DevcontainerConfig) -> dict[str, Any]:
        """Convert to valid devcontainer.json structure."""
        return {
            "name": config.name,
            "image": config.image,
            "features": {
                feature: {} for feature in config.features
            },  # Features as dict for devcontainer format
            "services": config.services,
            "postCreateCommand": config.postCreateCommand,
            "customizations": config.customizations,
            "remoteUser": config.remoteUser,
        }
