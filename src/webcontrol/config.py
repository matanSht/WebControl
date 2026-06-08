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

    # Stealth / anti-bot evasion (applied to new contexts when enabled).
    # Masks the common headless-Chromium tells (navigator.webdriver, the
    # HeadlessChrome UA token, missing window.chrome, etc.). See core/stealth.py.
    stealth_enabled: bool = True
    user_agent: str = ""  # empty = use stealth.DEFAULT_USER_AGENT
    locale: str = "en-US"
    timezone_id: str = ""  # empty = don't override the browser default

    # Search tier (Tier S) — reads results from a search engine's pre-crawled
    # index instead of contacting the target origin directly. Sidesteps anti-bot
    # walls for read-only info gathering (the "web search" path).
    search_tier_enabled: bool = False
    search_provider: Literal["exa", "brave"] = "exa"
    search_api_key: str = ""
    search_max_results: int = 5
    search_fetch_contents: bool = True
    search_timeout_ms: int = 15000

    # Navigation robustness — escalation ladder when a bot wall is detected.
    # direct (stealth) -> behavioral -> proxy (iff proxy_server set) -> terminal.
    # See core/navigation_escalation.py and core/block_detection.py.
    navigation_escalation: bool = True
    behavioral_jitter_ms: int = 800  # max random pre-retry delay for the behavioral tier

    # Retry settings
    navigation_retries: int = 2
    action_retries: int = 1
    retry_delay_ms: int = 500

    # Logging
    log_level: str = "INFO"
    log_json: bool = False


settings = Settings()
