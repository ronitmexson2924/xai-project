from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WEAK_SECRETS = {"", "change-me", "secret", "changeme", "dev", "test"}
MIN_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "production" refuses to start with unsafe settings (see check_production_settings)
    environment: Literal["development", "test", "production"] = "development"

    database_url: str = "postgresql+psycopg://pcg:pcg@localhost:5432/pcg"
    jwt_secret: str = "change-me"
    jwt_expire_hours: int = 24
    gemini_api_key: str = ""
    gemini_model_explain: str = ""
    gemini_model_offline: str = ""
    llm_timeout_seconds: float = 4.0

    # comma-separated browser origins allowed to call the API
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # only trust X-Forwarded-For when the API runs behind a proxy that sets it (e.g. Render)
    trust_forwarded_for: bool = False
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 120
    # failed logins per email (and per client) before login is locked for the window
    login_max_failures: int = 5
    login_lockout_seconds: int = 900

    # salt for pseudonyms in research exports; exports are refused while it is empty
    analysis_salt: str = ""

    @field_validator("database_url")
    @classmethod
    def use_psycopg3(cls, url: str) -> str:
        """Hosts hand out postgres:// or postgresql:// URLs; we ship the psycopg 3 driver."""
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def check_production_settings(s: "Settings") -> list[str]:
    """Problems that make a production deployment unsafe. Empty means fine."""
    problems = []
    if s.jwt_secret in WEAK_SECRETS or len(s.jwt_secret) < MIN_SECRET_LENGTH:
        problems.append(f"JWT_SECRET must be a random string of at least {MIN_SECRET_LENGTH} chars")
    if "*" in s.cors_origin_list:
        problems.append("CORS_ORIGINS must list the frontend origin(s), not *")
    if s.analysis_salt and len(s.analysis_salt) < 16:
        problems.append("ANALYSIS_SALT must be at least 16 characters")
    return problems


settings = Settings()
