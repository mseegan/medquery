from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    db_path: str = "medquery.db"
    sonnet_model: str = "claude-sonnet-5"
    haiku_model: str = "claude-haiku-4-5-20251001"


settings = Settings()
