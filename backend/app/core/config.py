from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    anthropic_custom_headers: str = ""
    github_token: str = ""

    # Full URL takes precedence. Individual components are used when set,
    # allowing Railway to inject each value separately (avoids URL-parsing issues).
    database_url: str = ""
    db_host: str = ""
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = ""
    db_name: str = "postgres"

    sentry_dsn: str = ""

    environment: str = "development"
    cors_origins: str = "http://localhost:3000"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def resolved_database_url(self) -> str:
        """Return a valid SQLAlchemy async DB URL.

        Priority:
        1. DATABASE_URL if set, non-empty, and parseable
        2. Individual DB_* components if DB_HOST is set (password is url-encoded)
        3. SQLite dev fallback
        """
        from urllib.parse import quote_plus, urlparse

        raw = self.database_url.strip()
        if raw:
            # Normalise scheme
            if raw.startswith("postgres://"):
                raw = "postgresql+asyncpg://" + raw[len("postgres://"):]
            elif raw.startswith("postgresql://") and "+asyncpg" not in raw:
                raw = "postgresql+asyncpg://" + raw[len("postgresql://"):]
            # Strip query params unsupported by asyncpg (e.g. pgbouncer=true)
            if "?" in raw:
                raw = raw.split("?")[0]
            # Validate: must have a recognisable netloc; reject placeholders
            try:
                parsed = urlparse(raw)
                if parsed.hostname and "[" not in (parsed.password or ""):
                    return raw
            except Exception:
                pass
            # Fall through — DATABASE_URL was malformed

        if self.db_host.strip():
            password = quote_plus(self.db_password)
            return (
                f"postgresql+asyncpg://{self.db_user}:{password}"
                f"@{self.db_host.strip()}:{self.db_port}/{self.db_name}?ssl=require"
            )

        return "sqlite+aiosqlite:///./dev.db"


settings = Settings()
