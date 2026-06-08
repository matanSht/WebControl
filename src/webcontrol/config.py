from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WC_")

    host: str = "0.0.0.0"
    port: int = 8080
    max_sessions: int = 10
    default_session_ttl_seconds: int = 1800
    headless: bool = True
    browser_type: Literal["chromium", "firefox", "webkit"] = "chromium"
    viewport_width: int = 1280
    viewport_height: int = 720
    navigation_timeout_ms: int = 30000
    action_timeout_ms: int = 10000

    # Auth (optional — empty means no auth required)
    api_key: str = ""

    # Proxy (optional — applied to all new browser contexts)
    proxy_server: str = ""
    proxy_username: str = ""
    proxy_password: str = ""

    # Retry settings
    navigation_retries: int = 2
    action_retries: int = 1
    retry_delay_ms: int = 500

    # Logging
    log_level: str = "INFO"
    log_json: bool = False


settings = Settings()
