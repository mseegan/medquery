from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    sonnet_model: str = "claude-sonnet-5"
    haiku_model: str = "claude-haiku-4-5-20251001"
    records_db_path: str = "data/records.db"
    scheduling_db_path: str = "data/scheduling.db"
    chroma_dir: str = "data/chroma"
    checkpoint_db_path: str = "data/checkpoints.db"
    # Folder holding records.xlsx and the visit-note PDFs that seed the databases.
    records_data_dir: str = ""


settings = Settings()
