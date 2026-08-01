from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    app_name: str = "SoCialMediaPost Studio"
    host: str = "127.0.0.1"
    port: int = 8765
    frontend_port: int = 3000
    timezone: str = "America/Chicago"
    demo_mode: bool = True
    auth_required: bool = True
    demo_bypass_auth: bool = False

    admin_email: str = "admin@localhost"
    admin_password: str = "ChangeThisBeforeUse123!"
    session_secret: str = "development-only-session-secret-change-me"
    session_ttl_minutes: int = 720
    cookie_secure: bool = False

    database_url: str = "sqlite:///./storage/app.db"
    redis_url: str = "redis://127.0.0.1:6379/0"
    celery_enabled: bool = False
    storage_root: Path = Path("./storage")
    encryption_key: str | None = None
    keychain_service: str = "com.rcegai.socialmediapost"

    trend_discovery_cron: str = "0 7,13 * * *"
    content_workflow_cron: str = "0 8,14,20 * * *"
    tiktok_daily_limit_per_run: int = 1
    instagram_daily_limit_per_run: int = 1
    youtube_daily_limit_per_run: int = 1
    approval_mode: Literal["manual_export", "review", "controlled_auto"] = "manual_export"

    llm_provider: str = "local_template"
    llm_api_key: str | None = None
    tts_provider: str = "local_ffmpeg"
    stt_provider: str = "disabled"
    image_provider: str = "local_ffmpeg"
    video_provider: str = "local_ffmpeg"
    stock_media_provider: str = "disabled"
    music_provider: str = "disabled"
    moderation_provider: str = "local_rules"
    embeddings_provider: str = "local_hash"

    youtube_api_key: str | None = None
    youtube_client_id: str | None = None
    youtube_client_secret: str | None = None
    youtube_redirect_uri: str = "http://127.0.0.1:8765/api/accounts/youtube/callback"
    youtube_region: str = "US"
    youtube_category_id: str = "0"

    tiktok_client_key: str | None = None
    tiktok_client_secret: str | None = None
    tiktok_redirect_uri: str = "http://127.0.0.1:8765/api/accounts/tiktok/callback"
    tiktok_research_access: bool = False
    tiktok_commercial_provider_url: str | None = None
    tiktok_commercial_provider_key: str | None = None

    meta_app_id: str | None = None
    meta_app_secret: str | None = None
    instagram_redirect_uri: str = "http://127.0.0.1:8765/api/accounts/instagram/callback"
    meta_graph_version: str = "v24.0"

    analytics_intervals_hours: str = "1,6,24,72,168,720"
    daily_budget_usd: float = 5.0
    monthly_budget_usd: float = 50.0
    hard_spending_limit_usd: float = 100.0
    budget_warning_percent: int = 80
    local_only_mode: bool = True
    low_cost_mode: bool = True
    premium_quality_mode: bool = False

    log_level: str = "INFO"
    log_json: bool = True
    macos_notifications: bool = True
    email_notifications: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    notification_email: str | None = None
    backup_retention_days: int = 30
    backup_encryption: bool = True

    auto_publish_enabled: bool = False
    global_pause: bool = False
    enable_youtube: bool = True
    enable_tiktok: bool = True
    enable_instagram: bool = True
    enable_experiments: bool = True
    enable_reports: bool = True

    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://127.0.0.1:3000", "http://localhost:3000"]
    )

    @field_validator("host")
    @classmethod
    def localhost_only_by_default(cls, value: str) -> str:
        if value not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("HOST must bind to localhost. Use a reverse proxy only after threat review.")
        return value

    @field_validator("session_secret")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("SESSION_SECRET must be at least 32 characters")
        return value

    @property
    def analytics_intervals(self) -> list[int]:
        return [int(item.strip()) for item in self.analytics_intervals_hours.split(",") if item.strip()]

    def ensure_directories(self) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    if not settings.storage_root.is_absolute():
        settings.storage_root = (PROJECT_ROOT / settings.storage_root).resolve()
    if settings.database_url.startswith("sqlite:///./"):
        relative = settings.database_url.removeprefix("sqlite:///")
        settings.database_url = f"sqlite:///{(PROJECT_ROOT / relative).resolve()}"
    settings.ensure_directories()
    return settings
