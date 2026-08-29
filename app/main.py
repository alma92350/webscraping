import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, HttpUrl

from app.cache import TTLCache
from app.config import Settings, load_settings
from app.errors import ScrapeError
from app.extractor import extract_content
from app.rate_limit import RateLimiter, assert_api_key
from app.scraper import BrowserManager, PlaywrightScraper
from app.security import assert_url_is_safe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web_scraper")


class ScrapeRequest(BaseModel):
    url: HttpUrl


def get_client_ip(request: Request) -> str:
    """Identify the caller for rate limiting.

    Prefers X-Forwarded-For's left-most (original client) entry over
    request.client.host. The app is only reachable through a platform
    reverse proxy (e.g. Hugging Face Spaces' gateway) which sets this
    header on every request and is the only path to the container - so it
    can be trusted here. request.client.host would instead reflect that
    proxy's own connecting address, not the real caller, which silently
    breaks per-client rate limiting.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def create_app(
    settings: Optional[Settings] = None,
    browser_manager: Optional[BrowserManager] = None,
    scraper: Optional[PlaywrightScraper] = None,
) -> FastAPI:
    """Assemble the FastAPI app from its component modules.

    `browser_manager` and `scraper` are injectable so tests (and any future
    caller) can swap in fakes instead of launching a real browser.
    """
    settings = settings or load_settings()
    browser_manager = browser_manager or BrowserManager()
    rate_limiter = RateLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds)
    cache = TTLCache(settings.cache_ttl_seconds, settings.cache_max_size)
    semaphore = asyncio.Semaphore(settings.max_concurrent_scrapes)

    # Held in a mutable box so the lifespan hook can populate it lazily
    # (real deployments) while still allowing a pre-built scraper to be
    # injected up front (tests).
    scraper_box: dict[str, Optional[PlaywrightScraper]] = {"instance": scraper}

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await browser_manager.start()
        if scraper_box["instance"] is None:
            scraper_box["instance"] = PlaywrightScraper(
                browser_manager.get_browser,
                user_agent=settings.user_agent,
                timeout_ms=settings.scrape_timeout_ms,
            )
        logger.info("Playwright browser launched")
        try:
            yield
        finally:
            await browser_manager.stop()
            logger.info("Playwright browser closed")

    app = FastAPI(title="Web Scraper API", lifespan=lifespan)

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
        return {"status": "ok", "browser_ready": browser_manager.get_browser() is not None}

    async def process_scrape(url: str, request: Request) -> dict:
        client_ip = get_client_ip(request)

        try:
            if not rate_limiter.allow(client_ip):
                raise ScrapeError(429, "Rate limit exceeded. Try again later.")

            assert_api_key(provided=request.headers.get("x-api-key"), expected=settings.api_key)
            assert_url_is_safe(url)

            cached = cache.get(url)
            if cached is not None:
                title, text = cached
                return {"url": url, "title": title, "content": text, "status": "success", "cached": True}

            async with semaphore:
                html_content = await scraper_box["instance"].scrape(url)
        except ScrapeError as e:
            raise HTTPException(status_code=e.status_code, detail=e.message)
        except Exception:
            logger.exception("Unexpected error scraping %s", url)
            raise HTTPException(status_code=502, detail="Failed to fetch or render the page.")

        try:
            title, text = extract_content(html_content, url=url)
        except Exception:
            logger.exception("Unexpected error extracting content for %s", url)
            raise HTTPException(status_code=500, detail="Failed to process page content.")

        cache.set(url, (title, text))
        return {"url": url, "title": title, "content": text, "status": "success", "cached": False}

    @app.post("/scrape")
    async def scrape_url(body: ScrapeRequest, request: Request):
        return await process_scrape(str(body.url), request)

    @app.get("/scrape")
    async def scrape_url_get(request: Request, url: HttpUrl = Query(...)):
        return await process_scrape(str(url), request)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=load_settings().port)
