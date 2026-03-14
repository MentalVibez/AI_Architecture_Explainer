from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: str = ""
    github_token: str = ""
    database_url: str = "sqlite+aiosqlite:///./dev.db"
    environment: str = "development"
    cors_origins: str = "http://localhost:3000"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
