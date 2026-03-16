"""
Application settings loaded from environment variables.
Uses pydantic-settings for validation and type coercion.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Supabase
    supabase_url: str
    supabase_service_key: str
    supabase_storage_bucket: str = "filings"

    # Anthropic
    anthropic_api_key: str
    extraction_model: str = "claude-sonnet-4-20250514"
    comparison_model: str = "claude-opus-4-20250514"
    scraper_model: str = "claude-haiku-4-5-20251001"
    max_extraction_retries: int = 3

    # Resend
    resend_api_key: str
    alert_email_to: str
    alert_email_from: str = "mREIT Monitor <alerts@yourdomain.com>"

    # SEC EDGAR
    edgar_user_agent: str = "mREIT-Monitor contact@example.com"

    # Scheduler
    poll_hour: int = 5          # Hour to run daily poll (Eastern Time)
    poll_minute: int = 0
    poll_timezone: str = "US/Eastern"

    # Summary Reports
    summary_model: str = "claude-opus-4-20250514"
    summary_enabled: bool = False  # Enable after review app testing

    # Frontend API
    reit_monitor_api_key: str = ""
    cors_origins: str = "https://mmglob.com,http://localhost:3000"

    # Webhook
    webhook_url: str = ""
    webhook_secret: str = ""

    # App
    log_level: str = "INFO"
    environment: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000


settings = Settings()
