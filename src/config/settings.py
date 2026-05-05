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
    supabase_storage_bucket: str = "reit-filings"

    # OpenRouter (replaces direct Anthropic/OpenAI/Gemini keys)
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Model selection via OpenRouter model IDs
    extraction_model: str = "anthropic/claude-sonnet-4.6"
    comparison_model: str = "anthropic/claude-sonnet-4.6"
    summary_model: str = "anthropic/claude-sonnet-4.6"
    max_extraction_retries: int = 3

    # Ollama — for IR page scraping and optional local extraction (local, free)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_scraper_model: str = "qwen3:4b"
    ollama_timeout_seconds: int = 300
    # Set LOCAL_EXTRACTION=true to route text-only extraction/comparison
    # through the local Ollama model instead of OpenRouter
    local_extraction: bool = False

    # Resend email alerts
    resend_api_key: str = ""
    alert_email_to: str = ""
    alert_email_from: str = "mREIT Monitor <alerts@example.com>"

    # SEC EDGAR — must include a real contact email per SEC fair-access policy
    edgar_user_agent: str = "mREIT-Monitor user@example.com"

    # Scheduler
    poll_hour: int = 7
    poll_minute: int = 0
    poll_timezone: str = "US/Eastern"

    # Summary Reports
    summary_enabled: bool = True
    webhook_url: str = ""

    # MCP / API
    reit_monitor_api_key: str = ""
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Usage metering (optional — POST /usage/record to a gateway; no-op on failure)
    gateway_url: str = ""

    # App
    log_level: str = "INFO"
    environment: str = "production"
    app_host: str = "127.0.0.1"
    app_port: int = 8012


settings = Settings()
