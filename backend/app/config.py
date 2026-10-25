from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WEAK_SECRETS = {"", "change-me", "secret", "changeme"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "production" refuses to start with unsafe defaults (see app.main.check_production_settings)
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://pcg:pcg@localhost:5432/pcg"
    jwt_secret: str = "change-me"
    jwt_expire_hours: int = 24
    # browser origins allowed to call the API, comma-separated (the frontend's URL)
    cors_origins: str = "http://localhost:3000"
    # serve items still in review (dev/demo only: in a study only approved items are shown)
    include_draft_items: bool = False
    # salt for pseudonymised admin exports; exports are refused until it is set
    export_salt: str = ""
    gemini_api_key: str = ""
    gemini_model_explain: str = ""
    gemini_model_offline: str = ""
    llm_timeout_seconds: float = 4.0
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 120
    # stricter limit for login/register, per client and per email, to slow password guessing
    auth_rate_limit_per_minute: int = 10  # per account
    # per client IP: higher, since a whole classroom can share one address behind NAT
    auth_ip_rate_limit_per_minute: int = 60
    # only trust X-Forwarded-For when a known proxy (e.g. Render, Fly) sets it
    trust_proxy_headers: bool = False

    @field_validator("database_url")
    @classmethod
    def _psycopg_driver(cls, url: str) -> str:
        # hosting platforms hand out postgres:// URLs; SQLAlchemy needs the driver named
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def production_problems(self) -> list[str]:
        problems = []
        if self.jwt_secret in WEAK_SECRETS or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be a random string of at least 32 characters")
        if "*" in self.cors_origin_list:
            problems.append("CORS_ORIGINS must list the frontend's origin, not '*'")
        if self.include_draft_items:
            problems.append("INCLUDE_DRAFT_ITEMS must be false: only reviewed items in a study")
        return problems


settings = Settings()
