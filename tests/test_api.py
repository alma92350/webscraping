import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import ScrapeError
from app.main import create_app

SAMPLE_HTML = (
    "<html><head><title>Sample Title</title></head>"
    "<body><article><p>Some real sample body content for the test page.</p></article></body></html>"
)


class FakeBrowserManager:
    def __init__(self):
        self.started = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.started = False

    def get_browser(self):
        return object() if self.started else None


class FakeScraper:
    def __init__(self, html=None, error=None, delay=0.0):
        self.html = html if html is not None else SAMPLE_HTML
        self.error = error
        self.delay = delay
        self.calls: list[str] = []
        self.active = 0
        self.max_active = 0

    async def scrape(self, url: str) -> str:
        self.calls.append(url)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.error is not None:
                raise self.error
            return self.html
        finally:
            self.active -= 1


def base_settings(**overrides) -> Settings:
    defaults = dict(
        scrape_timeout_ms=5000,
        max_concurrent_scrapes=3,
        user_agent="TestAgent/1.0",
        port=7860,
        rate_limit_requests=1000,
        rate_limit_window_seconds=60,
        api_key=None,
        cache_ttl_seconds=300,
        cache_max_size=256,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def make_client(settings=None, scraper=None):
    app = create_app(
        settings=settings or base_settings(),
        browser_manager=FakeBrowserManager(),
        scraper=scraper or FakeScraper(),
    )
    return TestClient(app)


def test_root_endpoint():
    with make_client() as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "message" in r.json()


def test_health_reports_browser_ready_once_lifespan_has_started():
    with make_client() as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "browser_ready": True}


@pytest.mark.parametrize(
    "url",
    ["http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/", "http://10.0.0.5/"],
)
def test_scrape_blocks_ssrf_targets(url):
    with make_client() as client:
        r = client.get("/scrape", params={"url": url})
        assert r.status_code == 400


def test_scrape_rejects_invalid_url():
    with make_client() as client:
        r = client.get("/scrape", params={"url": "not-a-url"})
        assert r.status_code == 422


def test_scrape_get_returns_extracted_content():
    with make_client() as client:
        r = client.get("/scrape", params={"url": "https://example.com/"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert body["title"] == "Sample Title"
        assert "real sample body content" in body["content"]
        assert body["cached"] is False


def test_scrape_post_returns_extracted_content():
    with make_client() as client:
        r = client.post("/scrape", json={"url": "https://example.com/"})
        assert r.status_code == 200
        assert r.json()["status"] == "success"


def test_repeat_requests_are_served_from_cache():
    scraper = FakeScraper()
    with make_client(scraper=scraper) as client:
        first = client.get("/scrape", params={"url": "https://example.com/"})
        second = client.get("/scrape", params={"url": "https://example.com/"})

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert scraper.calls == ["https://example.com/"]  # scraper only invoked once


def test_cache_disabled_when_ttl_is_zero():
    scraper = FakeScraper()
    settings = base_settings(cache_ttl_seconds=0)
    with make_client(settings=settings, scraper=scraper) as client:
        client.get("/scrape", params={"url": "https://example.com/"})
        client.get("/scrape", params={"url": "https://example.com/"})

    assert scraper.calls == ["https://example.com/", "https://example.com/"]


def test_rate_limit_blocks_after_the_configured_number_of_requests():
    settings = base_settings(rate_limit_requests=2, rate_limit_window_seconds=60, cache_ttl_seconds=0)
    with make_client(settings=settings) as client:
        r1 = client.get("/scrape", params={"url": "https://example.com/1"})
        r2 = client.get("/scrape", params={"url": "https://example.com/2"})
        r3 = client.get("/scrape", params={"url": "https://example.com/3"})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429


def test_api_key_required_when_configured():
    settings = base_settings(api_key="secret123")
    with make_client(settings=settings) as client:
        unauthenticated = client.get("/scrape", params={"url": "https://example.com/"})
        wrong_key = client.get(
            "/scrape", params={"url": "https://example.com/"}, headers={"X-API-Key": "wrong"}
        )
        correct_key = client.get(
            "/scrape", params={"url": "https://example.com/"}, headers={"X-API-Key": "secret123"}
        )

    assert unauthenticated.status_code == 401
    assert wrong_key.status_code == 401
    assert correct_key.status_code == 200


def test_no_api_key_required_when_not_configured():
    with make_client(settings=base_settings(api_key=None)) as client:
        r = client.get("/scrape", params={"url": "https://example.com/"})
    assert r.status_code == 200


def test_scrape_timeout_is_mapped_to_504():
    scraper = FakeScraper(error=ScrapeError(504, "Timed out loading the page."))
    with make_client(scraper=scraper) as client:
        r = client.get("/scrape", params={"url": "https://example.com/"})
    assert r.status_code == 504


def test_unexpected_scraper_error_is_mapped_to_502_without_leaking_details():
    scraper = FakeScraper(error=RuntimeError("some internal secret stack detail"))
    with make_client(scraper=scraper) as client:
        r = client.get("/scrape", params={"url": "https://example.com/"})
    assert r.status_code == 502
    assert "some internal secret stack detail" not in r.text


def test_concurrent_scrapes_are_limited_by_the_semaphore():
    scraper = FakeScraper(delay=0.05)
    settings = base_settings(max_concurrent_scrapes=2, cache_ttl_seconds=0, rate_limit_requests=1000)
    app = create_app(settings=settings, browser_manager=FakeBrowserManager(), scraper=scraper)

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            async with app.router.lifespan_context(app):
                requests = [client.get("/scrape", params={"url": f"https://example.com/{i}"}) for i in range(5)]
                responses = await asyncio.gather(*requests)
        return responses

    responses = asyncio.run(run())

    assert all(r.status_code == 200 for r in responses)
    assert scraper.max_active == 2  # never exceeded the configured limit
    assert len(scraper.calls) == 5
