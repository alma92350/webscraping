from typing import Callable, Optional

from playwright.async_api import Browser, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright_stealth import stealth_async

from app.errors import ScrapeError


class BrowserManager:
    """Owns the single, long-lived Playwright browser process for the app's
    lifetime, started/stopped via FastAPI's lifespan hook. Launching a fresh
    browser per request is prohibitively slow and memory-hungry; requests
    instead get an isolated `new_context()` from this shared browser."""

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()

    def get_browser(self) -> Optional[Browser]:
        return self._browser


class PlaywrightScraper:
    def __init__(
        self,
        browser_provider: Callable[[], Optional[Browser]],
        *,
        user_agent: str,
        timeout_ms: int,
        stealth: Callable = stealth_async,
    ):
        self._browser_provider = browser_provider
        self._user_agent = user_agent
        self._timeout_ms = timeout_ms
        self._stealth = stealth

    async def scrape(self, url: str) -> str:
        browser = self._browser_provider()
        if browser is None:
            raise ScrapeError(503, "Scraper is not ready yet, try again shortly.")

        # A fresh context per request keeps cookies/storage isolated between
        # callers while reusing the shared browser process.
        context = await browser.new_context(
            user_agent=self._user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
        )
        try:
            page = await context.new_page()
            await self._stealth(page)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
            except PlaywrightTimeoutError:
                raise ScrapeError(504, "Timed out loading the page.")

            return await page.content()
        finally:
            await context.close()
