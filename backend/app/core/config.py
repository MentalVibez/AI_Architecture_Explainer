from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    github_token: str = ""

    # Full URL takes precedence. Individual components are used when set,
    # allowing Railway to inject each value separately (avoids URL-parsing issues).
    database_url: str = ""
    db_host: str = ""
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: str = ""
    db_name: str = "postgres"

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
        1. DATABASE_URL if set and non-empty (stripped of whitespace)
        2. Individual DB_* components if DB_HOST is set
        3. SQLite dev fallback
        """
        url = self.database_url.strip()
        if url:
            # Normalise bare postgres:// → postgresql+asyncpg://
            if url.startswith("postgres://"):
                url = "postgresql+asyncpg://" + url[len("postgres://"):]
            elif url.startswith("postgresql://"):
                url = "postgresql+asyncpg://" + url[len("postgresql://"):]
            return url

        if self.db_host.strip():
            from urllib.parse import quote_plus
            password = quote_plus(self.db_password)
            return (
                f"postgresql+asyncpg://{self.db_user}:{password}"
                f"@{self.db_host.strip()}:{self.db_port}/{self.db_name}?ssl=require"
            )

        return "sqlite+aiosqlite:///./dev.db"


settings = Settings()
