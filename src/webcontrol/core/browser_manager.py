import asyncio

from playwright.async_api import Browser, Playwright, async_playwright

from webcontrol.config import Settings


class BrowserManager:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()

    @property
    def browser(self) -> Browser:
        if self._browser is None:
            raise RuntimeError("BrowserManager not started. Call startup() first.")
        return self._browser

    async def startup(self) -> None:
        async with self._lock:
            if self._browser is not None:
                return
            self._playwright = await async_playwright().start()
            launcher = getattr(self._playwright, self._settings.browser_type)
            self._browser = await launcher.launch(headless=self._settings.headless)

    async def shutdown(self) -> None:
        async with self._lock:
            if self._browser is not None:
                await self._browser.close()
                self._browser = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None
