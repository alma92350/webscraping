import asyncio
import ipaddress
import logging
import os
import re
import socket
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment
from fastapi import FastAPI, HTTPException, Query
from playwright.async_api import Browser, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright_stealth import stealth_async
from pydantic import BaseModel, HttpUrl

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web_scraper")

SCRAPE_TIMEOUT_MS = int(os.environ.get("SCRAPE_TIMEOUT_MS", "30000"))
MAX_CONCURRENT_SCRAPES = int(os.environ.get("MAX_CONCURRENT_SCRAPES", "3"))
USER_AGENT = os.environ.get(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
)

# Hostnames worth blocking explicitly because they don't resolve to a
# "private" IP range but still expose sensitive data (cloud metadata APIs).
BLOCKED_HOSTNAMES = {"metadata.google.internal"}

state: dict[str, Optional[object]] = {"playwright": None, "browser": None}
scrape_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCRAPES)


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["playwright"] = await async_playwright().start()
    state["browser"] = await state["playwright"].chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    logger.info("Playwright browser launched")
    try:
        yield
    finally:
        browser = state.get("browser")
        if browser is not None:
            await browser.close()
        playwright = state.get("playwright")
        if playwright is not None:
            await playwright.stop()
        logger.info("Playwright browser closed")


app = FastAPI(title="Web Scraper API", lifespan=lifespan)


class ScrapeRequest(BaseModel):
    url: HttpUrl


class ScrapeError(Exception):
    """Raised for any scrape failure that should map to a specific HTTP status."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def assert_url_is_safe(url: str) -> None:
    """Best-effort SSRF guard.

    Rejects non-http(s) schemes and hostnames that resolve to
    private/loopback/link-local/reserved addresses. This narrows the attack
    surface but is not a complete defense against DNS rebinding, since
    Playwright performs its own DNS resolution when it actually fetches the
    page (after this check has passed).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ScrapeError(400, "Only http and https URLs are supported.")

    hostname = parsed.hostname
    if not hostname:
        raise ScrapeError(400, "URL is missing a hostname.")

    if hostname.lower() in BLOCKED_HOSTNAMES:
        raise ScrapeError(400, "This host is not allowed.")

    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ScrapeError(400, "Could not resolve host.")

    for family, _, _, _, sockaddr in addr_infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ScrapeError(400, "This host resolves to a disallowed address.")


def clean_html(html_content: str):
    soup = BeautifulSoup(html_content, "lxml")

    # Extract title before cleaning
    title = soup.title.string.strip() if soup.title and soup.title.string else "No title found"

    # Remove script, style, iframe, and other non-content tags
    for tag in soup(["script", "style", "iframe", "noscript", "meta", "link", "svg", "button", "input", "form"]):
        tag.decompose()

    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Remove common ad and clutter classes/ids
    ad_patterns = re.compile(
        r"(ad|ads|advert|advertisement|banner|social|share|nav|footer|header|menu|sidebar|cookie|popup|modal|newsletter)",
        re.IGNORECASE,
    )

    for tag in soup.find_all(attrs={"class": ad_patterns}):
        tag.decompose()
    for tag in soup.find_all(attrs={"id": ad_patterns}):
        tag.decompose()

    # Extract text
    text = soup.get_text(separator="\n", strip=True)
    # Simple cleanup of excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return title, text


async def scrape_with_playwright(url: str) -> str:
    browser: Optional[Browser] = state.get("browser")
    if browser is None:
        raise ScrapeError(503, "Scraper is not ready yet, try again shortly.")

    # A fresh context per request keeps cookies/storage isolated between
    # callers while reusing the single long-lived browser process, instead
    # of paying Chromium's full startup cost on every request.
    context = await browser.new_context(
        user_agent=USER_AGENT,
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        timezone_id="America/New_York",
    )
    try:
        page = await context.new_page()
        await stealth_async(page)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=SCRAPE_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            raise ScrapeError(504, "Timed out loading the page.")

        return await page.content()
    finally:
        await context.close()


@app.get("/")
def read_root():
    return {
        "message": (
            "Welcome to the Playwright Web Scraping Service! Send a POST request "
            "to /scrape with a JSON body {'url': '...'} or use GET /scrape?url=..."
        )
    }


@app.get("/health")
def health():
    return {"status": "ok", "browser_ready": state.get("browser") is not None}


@app.post("/scrape")
async def scrape_url(request: ScrapeRequest):
    return await process_scrape(str(request.url))


@app.get("/scrape")
async def scrape_url_get(url: HttpUrl = Query(...)):
    return await process_scrape(str(url))


async def process_scrape(url: str):
    try:
        assert_url_is_safe(url)

        async with scrape_semaphore:
            html_content = await scrape_with_playwright(url)
    except ScrapeError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception:
        logger.exception("Unexpected error scraping %s", url)
        raise HTTPException(status_code=502, detail="Failed to fetch or render the page.")

    try:
        title, text = clean_html(html_content)
    except Exception:
        logger.exception("Unexpected error cleaning content for %s", url)
        raise HTTPException(status_code=500, detail="Failed to process page content.")

    return {
        "url": url,
        "title": title,
        "content": text,
        "status": "success",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "7860")))
