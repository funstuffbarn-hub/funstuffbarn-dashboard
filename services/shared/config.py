#!/usr/bin/env python3
"""
shared/config.py - Configuration management using Pydantic Settings
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "FunStuffBarn Agent-Etsy"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = Field(default="development", pattern="^(development|staging|production)$")
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8080
    WORKERS: int = 1

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5

# Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list[str] = ["json"]
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 300
    CELERY_TASK_SOFT_TIME_LIMIT: int = 240
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 4
    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = 100

    # Property aliases for lowercase access (used by celery config)
    @property
    def celery_result_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND

    @property
    def etsy_shop_id(self) -> str:
        return self.ETSY_SHOP_ID

    @property
    def printful_store_id(self) -> str:
        return self.PRINTFUL_STORE_ID

    @property
    def email_destination(self) -> str:
        return self.EMAIL_DESTINATION

    @property
    def celery_broker_url(self) -> str:
        return self.CELERY_BROKER_URL

    # Groq API
    GROQ_API_KEY: SecretStr = Field(..., description="Groq API Key for LLM")
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    GROQ_MAX_TOKENS: int = 4000
    GROQ_TEMPERATURE: float = 0.7
    GROQ_MAX_RETRIES: int = 3
    GROQ_BASE_DELAY: float = 5.0
    GROQ_MAX_DELAY: float = 60.0

    # Etsy API
    ETSY_API_KEY: SecretStr = Field(..., description="Etsy API Key")
    ETSY_API_SECRET: SecretStr = Field(..., description="Etsy API Secret")
    ETSY_SHOP_ID: str = Field(..., description="Etsy Shop ID")
    ETSY_REDIRECT_URI: str = "http://localhost:8080/callback"
    ETSY_SCOPES: str = "listings_r listings_w shops_r shops_w transactions_r"
    ETSY_API_BASE_URL: str = "https://api.etsy.com/v3"
    ETSY_OAUTH_BASE_URL: str = "https://www.etsy.com/oauth"

    # Printful
    PRINTFUL_TOKEN: SecretStr = Field(..., description="Printful API Token")
    PRINTFUL_STORE_ID: str = Field(..., description="Printful Store ID")
    PRINTFUL_API_BASE: str = "https://api.printful.com"

    # Email (Gmail SMTP)
    GMAIL_USER: SecretStr = Field(..., description="Gmail address")
    GMAIL_PASSWORD: SecretStr = Field(..., description="Gmail App Password")
    EMAIL_DESTINATION: str = Field(..., description="Destination email for reports")
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 465
    SMTP_USE_TLS: bool = True

    # Google Trends (pytrends)
    TRENDS_HL: str = "en-US"
    TRENDS_TZ: int = 360
    TRENDS_TIMEFRAME: str = "today 3-m"
    TRENDS_GEO: str = "US"

    # Pinterest
    PINTEREST_USER_AGENT: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # File Paths
    DASHBOARD_DIR: Path = Path(__file__).parent.parent.parent
    REPORTES_DIR: Path = Path("/Users/javiermaldonadocorreaair/agente-etsy/reportes")
    PROMPT_ARCHIVE_DIR: Path = Path("/Users/javiermaldonadocorreaair/agente-etsy/prompt_archive")
    DISENOS_ROOT: Path = Path("/Users/javiermaldonadocorreaair/Tienda FunStuffBarn")
    ENV_FILE: Path = Path("/Users/javiermaldonadocorreaair/agente-etsy/.env")
    LOGS_DIR: Path = DASHBOARD_DIR / "logs"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_FILE_MAX_SIZE: int = 10_000_000  # 10MB
    LOG_FILE_BACKUP_COUNT: int = 10

    # Monitoring
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    HEALTH_CHECK_INTERVAL: int = 30

    # Rate Limiting (requests per second)
    RATE_LIMIT_GROQ: float = 10.0
    RATE_LIMIT_ETSY: float = 5.0
    RATE_LIMIT_PRINTFUL: float = 5.0
    RATE_LIMIT_TRENDS: float = 1.0
    RATE_LIMIT_PINTEREST: float = 2.0

    # Circuit Breaker
    CB_GROQ_FAILURE_THRESHOLD: int = 5
    CB_GROQ_RESET_TIMEOUT: float = 300.0
    CB_ETSY_FAILURE_THRESHOLD: int = 5
    CB_ETSY_RESET_TIMEOUT: float = 120.0
    CB_PRINTFUL_FAILURE_THRESHOLD: int = 5
    CB_PRINTFUL_RESET_TIMEOUT: float = 120.0
    CB_TRENDS_FAILURE_THRESHOLD: int = 3
    CB_TRENDS_RESET_TIMEOUT: float = 180.0

    # Retry Policy
    RETRY_MAX_ATTEMPTS: int = 3
    RETRY_BASE_DELAY: float = 5.0
    RETRY_MAX_DELAY: float = 60.0
    RETRY_JITTER: float = 0.1

    # Cache TTL (seconds)
    CACHE_TRENDS_TTL: int = 86400  # 24 hours
    CACHE_ETSY_SEARCH_TTL: int = 21600  # 6 hours
    CACHE_PRINTFUL_PRODUCTS_TTL: int = 3600  # 1 hour
    CACHE_PINTEREST_TRENDS_TTL: int = 43200  # 12 hours

    # Report Retention
    REPORT_RETENTION_DAILY_DAYS: int = 30
    REPORT_RETENTION_WEEKLY_WEEKS: int = 12
    REPORT_RETENTION_MONTHLY_MONTHS: int = 12

    # Backup
    BACKUP_ENABLED: bool = True
    BACKUP_SCHEDULE: str = "0 2 * * *"  # Daily at 02:00
    BACKUP_RETENTION_DAYS: int = 30
    BACKUP_RETENTION_WEEKS: int = 12
    BACKUP_RETENTION_MONTHS: int = 12

    # Monitoring
    GRAFANA_PASSWORD: str | None = None
    SLACK_WEBHOOK_URL: str | None = None

    @field_validator("REPORTES_DIR", "PROMPT_ARCHIVE_DIR", "DISENOS_ROOT", "ENV_FILE", "LOGS_DIR", mode="before")
    @classmethod
    def _ensure_path(cls, v: str) -> Path:
        return Path(v).expanduser().resolve()

    @property
    def groq_api_key(self) -> str:
        return self.GROQ_API_KEY.get_secret_value()

    @property
    def etsy_api_key(self) -> str:
        return self.ETSY_API_KEY.get_secret_value()

    @property
    def etsy_api_secret(self) -> str:
        return self.ETSY_API_SECRET.get_secret_value()

    @property
    def printful_token(self) -> str:
        return self.PRINTFUL_TOKEN.get_secret_value()

    @property
    def gmail_user(self) -> str:
        return self.GMAIL_USER.get_secret_value()

    @property
    def gmail_password(self) -> str:
        return self.GMAIL_PASSWORD.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
