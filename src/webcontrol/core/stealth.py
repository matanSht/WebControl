"""Anti-detection hardening for Playwright browser contexts.

Headless Chromium ships with several machine-detectable "tells" that anti-bot
systems (Amazon, Cloudflare, DataDome, etc.) key on: ``navigator.webdriver``,
the ``HeadlessChrome`` user-agent token, a missing ``window.chrome`` runtime,
empty plugin/language lists, and so on. This module collects the launch args,
context options, and an init script that mask the most common of these.

None of this is a guarantee — a determined anti-bot wall (especially Amazon's)
can still block automated traffic, and the most reliable path for read-only
data is the search-index tier (see ``core/search_tier.py``). But this closes
the easy gaps so legitimate automation against ordinary sites works.
"""

from webcontrol.config import Settings

# A realistic, current desktop Chrome user-agent. Critically, it does NOT
# contain the "HeadlessChrome" token that the default headless UA exposes.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Chromium launch flags. The key one is AutomationControlled: without it,
# navigator.webdriver is true, which is the single most-used bot signal.
STEALTH_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]

# Injected before any page script runs. Patches the residual JS-visible tells
# that launch flags alone don't cover.
STEALTH_INIT_SCRIPT = """
(() => {
  // navigator.webdriver -> undefined
  Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

  // Plausible language list
  Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
  });

  // Non-empty plugins array (headless reports zero)
  Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
  });

  // window.chrome runtime stub (absent in headless)
  if (!window.chrome) {
    window.chrome = { runtime: {} };
  }

  // Permissions API: notifications query returns a sane state instead of
  // throwing, which is itself a detectable difference.
  const originalQuery = window.navigator.permissions &&
    window.navigator.permissions.query;
  if (originalQuery) {
    window.navigator.permissions.query = (parameters) =>
      parameters && parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);
  }
})();
"""


def stealth_launch_args(settings: Settings) -> list[str]:
    """Chromium launch args for the browser, empty when stealth is disabled.

    Only applies to chromium — firefox/webkit ignore these flags.
    """
    if not settings.stealth_enabled or settings.browser_type != "chromium":
        return []
    return list(STEALTH_LAUNCH_ARGS)


def stealth_context_options(settings: Settings) -> dict:
    """Context kwargs (UA, locale, timezone, headers) for anti-detection.

    Returns only the keys that should be set; callers merge these into their
    own context options without clobbering explicit per-session overrides.
    """
    if not settings.stealth_enabled:
        return {}
    opts: dict = {
        "user_agent": settings.user_agent or DEFAULT_USER_AGENT,
        "locale": settings.locale,
        "extra_http_headers": {
            "Accept-Language": f"{settings.locale},en;q=0.9",
        },
    }
    if settings.timezone_id:
        opts["timezone_id"] = settings.timezone_id
    return opts
