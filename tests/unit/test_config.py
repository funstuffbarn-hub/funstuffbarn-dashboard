"""
Unit tests for shared/config.py
"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from services.shared.config import Settings, get_settings


class TestSettings:
    """Tests for Settings configuration."""

    def test_settings_loading_from_env(self):
        """Test that settings load from environment variables."""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test_groq_key",
            "ETSY_API_KEY": "test_etsy_key",
            "ETSY_API_SECRET": "test_etsy_secret",
            "ETSY_SHOP_ID": "12345",
            "PRINTFUL_TOKEN": "test_printful_token",
            "PRINTFUL_STORE_ID": "67890",
            "GMAIL_USER": "test@gmail.com",
            "GMAIL_PASSWORD": "test_password",
            "EMAIL_DESTINATION": "dest@test.com",
        }, clear=True):
            settings = Settings()
            assert settings.groq_api_key == "test_groq_key"
            assert settings.etsy_api_key == "test_etsy_key"
            assert settings.etsy_api_secret == "test_etsy_secret"
            assert settings.etsy_shop_id == "12345"
            assert settings.printful_token == "test_printful_token"
            assert settings.printful_store_id == "67890"
            assert settings.gmail_user == "test@gmail.com"
            assert settings.gmail_password == "test_password"
            assert settings.email_destination == "dest@test.com"

    def test_secret_value_access(self):
        """Test that secret values are properly accessed."""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "secret_key",
            "ETSY_API_KEY": "etsy_key",
            "ETSY_API_SECRET": "etsy_secret",
            "ETSY_SHOP_ID": "12345",
            "PRINTFUL_TOKEN": "printful_token",
            "PRINTFUL_STORE_ID": "11111",
            "GMAIL_USER": "user@gmail.com",
            "GMAIL_PASSWORD": "password",
            "EMAIL_DESTINATION": "dest@test.com",
        }, clear=True):
            settings = Settings()
            assert settings.groq_api_key == "secret_key"
            assert settings.etsy_api_key == "etsy_key"
            assert settings.etsy_api_secret == "etsy_secret"
            assert settings.printful_token == "printful_token"
            assert settings.gmail_user == "user@gmail.com"
            assert settings.gmail_password == "password"
            assert settings.email_destination == "dest@test.com"

    def test_path_resolution(self):
        """Test that paths are properly resolved."""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test",
            "ETSY_API_KEY": "test",
            "ETSY_API_SECRET": "test",
            "ETSY_SHOP_ID": "12345",
            "PRINTFUL_TOKEN": "test",
            "PRINTFUL_STORE_ID": "11111",
            "GMAIL_USER": "test@test.com",
            "GMAIL_PASSWORD": "test",
            "EMAIL_DESTINATION": "test@test.com",
        }, clear=True):
            settings = Settings()
            assert isinstance(settings.REPORTES_DIR, Path)
            assert isinstance(settings.PROMPT_ARCHIVE_DIR, Path)
            assert isinstance(settings.DISENOS_ROOT, Path)
            assert isinstance(settings.ENV_FILE, Path)
            assert isinstance(settings.LOGS_DIR, Path)

    def test_groq_config_values(self):
        """Test Groq-specific configuration values."""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test",
            "ETSY_API_KEY": "test",
            "ETSY_API_SECRET": "test",
            "ETSY_SHOP_ID": "12345",
            "PRINTFUL_TOKEN": "test",
            "PRINTFUL_STORE_ID": "11111",
            "GMAIL_USER": "test@test.com",
            "GMAIL_PASSWORD": "test",
            "EMAIL_DESTINATION": "test@test.com",
        }, clear=True):
            settings = Settings()
            assert settings.GROQ_MODEL == "llama-3.1-8b-instant"
            assert settings.GROQ_MAX_TOKENS == 4000
            assert settings.GROQ_TEMPERATURE == 0.7
            assert settings.GROQ_MAX_RETRIES == 3

    def test_etsy_config_values(self):
        """Test Etsy-specific configuration values."""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test",
            "ETSY_API_KEY": "test",
            "ETSY_API_SECRET": "test",
            "ETSY_SHOP_ID": "12345",
            "PRINTFUL_TOKEN": "test",
            "PRINTFUL_STORE_ID": "11111",
            "GMAIL_USER": "test@test.com",
            "GMAIL_PASSWORD": "test",
            "EMAIL_DESTINATION": "test@test.com",
        }, clear=True):
            settings = Settings()
            assert settings.ETSY_API_BASE_URL == "https://api.etsy.com/v3"
            assert settings.ETSY_OAUTH_BASE_URL == "https://www.etsy.com/oauth"
            assert settings.ETSY_SCOPES == "listings_r listings_w shops_r shops_w transactions_r"

    def test_cache_ttl_values(self):
        """Test cache TTL configuration values."""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test",
            "ETSY_API_KEY": "test",
            "ETSY_API_SECRET": "test",
            "ETSY_SHOP_ID": "12345",
            "PRINTFUL_TOKEN": "test",
            "PRINTFUL_STORE_ID": "11111",
            "GMAIL_USER": "test@test.com",
            "GMAIL_PASSWORD": "test",
            "EMAIL_DESTINATION": "test@test.com",
        }, clear=True):
            settings = Settings()
            assert settings.CACHE_TRENDS_TTL == 86400
            assert settings.CACHE_ETSY_SEARCH_TTL == 21600
            assert settings.CACHE_PRINTFUL_PRODUCTS_TTL == 3600
            assert settings.CACHE_PINTEREST_TRENDS_TTL == 43200

    def test_report_retention_values(self):
        """Test report retention configuration values."""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test",
            "ETSY_API_KEY": "test",
            "ETSY_API_SECRET": "test",
            "ETSY_SHOP_ID": "12345",
            "PRINTFUL_TOKEN": "test",
            "PRINTFUL_STORE_ID": "11111",
            "GMAIL_USER": "test@test.com",
            "GMAIL_PASSWORD": "test",
            "EMAIL_DESTINATION": "test@test.com",
        }, clear=True):
            settings = Settings()
            assert settings.REPORT_RETENTION_DAILY_DAYS == 30
            assert settings.REPORT_RETENTION_WEEKLY_WEEKS == 12
            assert settings.REPORT_RETENTION_MONTHLY_MONTHS == 12

    def test_backup_config_values(self):
        """Test backup configuration values."""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test",
            "ETSY_API_KEY": "test",
            "ETSY_API_SECRET": "test",
            "ETSY_SHOP_ID": "12345",
            "PRINTFUL_TOKEN": "test",
            "PRINTFUL_STORE_ID": "11111",
            "GMAIL_USER": "test@test.com",
            "GMAIL_PASSWORD": "test",
            "EMAIL_DESTINATION": "test@test.com",
        }, clear=True):
            settings = Settings()
            assert settings.BACKUP_ENABLED is True
            assert settings.BACKUP_SCHEDULE == "0 2 * * *"
            assert settings.BACKUP_RETENTION_DAYS == 30
            assert settings.BACKUP_RETENTION_WEEKS == 12
            assert settings.BACKUP_RETENTION_MONTHS == 12

    def test_get_settings_cached(self):
        """Test that get_settings returns cached instance."""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test",
            "ETSY_API_KEY": "test",
            "ETSY_API_SECRET": "test",
            "ETSY_SHOP_ID": "12345",
            "PRINTFUL_TOKEN": "test",
            "PRINTFUL_STORE_ID": "11111",
            "GMAIL_USER": "test@test.com",
            "GMAIL_PASSWORD": "test",
            "EMAIL_DESTINATION": "test@test.com",
        }, clear=True):
            settings1 = get_settings()
            settings2 = get_settings()
            assert settings1 is settings2


class TestSettingsValidation:
    """Test settings validation."""

    def test_missing_required_fields_raises_error(self):
        """Test that missing required fields raise validation error."""
        with patch.dict(os.environ, {
            # Missing required fields
        }, clear=True):
            # Disable .env file loading by setting env_file to None
            with pytest.raises(Exception):
                Settings(_env_file=None)

    def test_field_validators(self):
        """Test field validators work correctly."""
        with patch.dict(os.environ, {
            "GROQ_API_KEY": "test",
            "ETSY_API_KEY": "test",
            "ETSY_API_SECRET": "test",
            "ETSY_SHOP_ID": "12345",
            "PRINTFUL_TOKEN": "test",
            "PRINTFUL_STORE_ID": "11111",
            "GMAIL_USER": "test@test.com",
            "GMAIL_PASSWORD": "test",
            "EMAIL_DESTINATION": "test@test.com",
        }, clear=True):
            settings = Settings()
            # Path validators should convert strings to Path objects
            assert isinstance(settings.REPORTES_DIR, Path)
            assert isinstance(settings.PROMPT_ARCHIVE_DIR, Path)
            assert isinstance(settings.DISENOS_ROOT, Path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
