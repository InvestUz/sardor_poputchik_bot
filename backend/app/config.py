from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./data/dev.db"

    # Telegram
    bot_token: str = ""
    bot_mode: str = "off"  # webhook | polling | off
    webhook_secret: str = ""
    admin_chat_id: int | None = None  # Telegram group for moderator alerts

    # Public URLs
    public_url: str = "http://localhost:8000"  # https://yourdomain.uz
    miniapp_dist: str = "../miniapp/dist"

    # Security
    session_secret: str = "change-me"
    init_data_ttl_seconds: int = 86400
    debug: bool = False  # enables "Authorization: dev <telegram_id>" for local Mini App testing

    # Files
    files_dir: str = "./data/files"
    max_upload_mb: int = 10

    # Background jobs
    run_jobs: bool = True
    jobs_interval_seconds: int = 60

    @property
    def miniapp_url(self) -> str:
        return self.public_url.rstrip("/") + "/app/"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


settings = Settings()
