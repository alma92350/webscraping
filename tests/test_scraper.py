from unittest.mock import AsyncMock, MagicMock

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.errors import ScrapeError
from app.scraper import PlaywrightScraper


def make_mock_browser(page: MagicMock) -> MagicMock:
    context = MagicMock()
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()

    browser = MagicMock()
    browser.new_context = AsyncMock(return_value=context)
    return browser, context


def make_mock_page(content: str = "<html>ok</html>") -> MagicMock:
    page = MagicMock()
    page.goto = AsyncMock()
    page.content = AsyncMock(return_value=content)
    return page


async def test_scrape_returns_page_content_on_success():
    page = make_mock_page("<html>hello</html>")
    browser, context = make_mock_browser(page)
    stealth = AsyncMock()

    scraper = PlaywrightScraper(
        browser_provider=lambda: browser, user_agent="UA", timeout_ms=5000, stealth=stealth
    )

    result = await scraper.scrape("https://example.com/")

    assert result == "<html>hello</html>"
    stealth.assert_awaited_once_with(page)
    context.close.assert_awaited_once()


async def test_scrape_raises_503_when_browser_not_ready():
    scraper = PlaywrightScraper(browser_provider=lambda: None, user_agent="UA", timeout_ms=5000)

    with pytest.raises(ScrapeError) as exc_info:
        await scraper.scrape("https://example.com/")
    assert exc_info.value.status_code == 503


async def test_scrape_maps_playwright_timeout_to_504_and_still_closes_context():
    page = make_mock_page()
    page.goto = AsyncMock(side_effect=PlaywrightTimeoutError("timed out"))
    browser, context = make_mock_browser(page)

    scraper = PlaywrightScraper(
        browser_provider=lambda: browser, user_agent="UA", timeout_ms=5000, stealth=AsyncMock()
    )

    with pytest.raises(ScrapeError) as exc_info:
        await scraper.scrape("https://example.com/")

    assert exc_info.value.status_code == 504
    context.close.assert_awaited_once()


async def test_context_is_closed_even_when_page_setup_fails():
    page = make_mock_page()
    browser, context = make_mock_browser(page)
    failing_stealth = AsyncMock(side_effect=RuntimeError("boom"))

    scraper = PlaywrightScraper(
        browser_provider=lambda: browser, user_agent="UA", timeout_ms=5000, stealth=failing_stealth
    )

    with pytest.raises(RuntimeError):
        await scraper.scrape("https://example.com/")

    context.close.assert_awaited_once()


async def test_scrape_configures_context_and_navigation():
    page = make_mock_page()
    browser, context = make_mock_browser(page)

    scraper = PlaywrightScraper(
        browser_provider=lambda: browser, user_agent="Custom UA", timeout_ms=12345, stealth=AsyncMock()
    )

    await scraper.scrape("https://example.com/")

    _args, kwargs = browser.new_context.call_args
    assert kwargs["user_agent"] == "Custom UA"
    assert kwargs["viewport"] == {"width": 1920, "height": 1080}

    _args, kwargs = page.goto.call_args
    assert kwargs["wait_until"] == "domcontentloaded"
    assert kwargs["timeout"] == 12345
