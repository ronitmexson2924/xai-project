from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://pcg:pcg@localhost:5432/pcg"
    jwt_secret: str = "change-me"
    gemini_api_key: str = ""
    gemini_model_explain: str = ""
    gemini_model_offline: str = ""
    llm_timeout_seconds: float = 4.0


settings = Settings()
