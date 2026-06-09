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

    # Page parsing limits — how much of a rendered page the parser captures.
    # Raising these gives more reach on content-heavy pages (search results,
    # catalogs) at the cost of a larger response and more per-element DOM
    # round-trips. See core/page_parser.py.
    max_text_content_chars: int = 8000
    max_interactive_elements: int = 120
    max_form_fields: int = 60
    max_links: int = 80

    # Page settle — wait for async / JS-rendered content to land before the
    # parser snapshots the DOM. Pages routinely return HTTP 200 with a shell,
    # then hydrate prices/listings/ratings via later XHR. See core/page_settle.py.
    page_settle_enabled: bool = True
    settle_timeout_ms: int = 4000  # ceiling for networkidle + wait_for_selector
    dom_stable_polls: int = 2  # consecutive equal DOM-size reads required
    dom_stable_interval_ms: int = 300  # gap between DOM-stability polls
    scroll_to_load_default: bool = False  # auto-scroll on every navigate
    scroll_steps: int = 8  # number of scroll steps when scroll_to_load is on
    scroll_delay_ms: int = 250  # pause between scroll steps

    # Targeted extraction + structured data — the "accuracy" path: pull exact
    # values via CSS selectors or page metadata instead of mining the text dump.
    # See core/action_executor.extract and core/page_parser._extract_structured_data.
    max_extract_rows: int = 100  # ceiling on rows returned by extract()
    extract_max_field_chars: int = 2000  # per-field value cap in extract()
    structured_data_max_blobs: int = 10  # max JSON-LD scripts parsed per page
    structured_data_max_chars: int = 20000  # skip JSON-LD scripts larger than this
    html_max_chars: int = 500000  # cap for get_html() raw page source

    # Retry settings
    navigation_retries: int = 2
    action_retries: int = 1
    retry_delay_ms: int = 500

    # Logging
    log_level: str = "INFO"
    log_json: bool = False


settings = Settings()
