from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite+aiosqlite:///cfs_routes.db"
    airports_csv_path: str = "data/airports.csv"
    log_level: str = "INFO"
    fetch_retry_days_before: int = 7
    fetch_retry_days_after: int = 3
    scheduler_enabled: bool = True
    save_pdfs: bool = False
    pdf_base_url: str | None = None


settings = Settings()
