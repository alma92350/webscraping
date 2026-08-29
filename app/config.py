import os
from dataclasses import dataclass
from typing import Mapping, Optional

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class Settings:
    scrape_timeout_ms: int
    max_concurrent_scrapes: int
    user_agent: str
    port: int
    rate_limit_requests: int
    rate_limit_window_seconds: int
    api_key: Optional[str]
    cache_ttl_seconds: int
    cache_max_size: int


def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
    env = env if env is not None else os.environ
    return Settings(
        scrape_timeout_ms=int(env.get("SCRAPE_TIMEOUT_MS", "30000")),
        max_concurrent_scrapes=int(env.get("MAX_CONCURRENT_SCRAPES", "3")),
        user_agent=env.get("SCRAPER_USER_AGENT") or DEFAULT_USER_AGENT,
        port=int(env.get("PORT", "7860")),
        rate_limit_requests=int(env.get("RATE_LIMIT_REQUESTS", "20")),
        rate_limit_window_seconds=int(env.get("RATE_LIMIT_WINDOW_SECONDS", "60")),
        api_key=env.get("SCRAPER_API_KEY") or None,
        cache_ttl_seconds=int(env.get("CACHE_TTL_SECONDS", "300")),
        cache_max_size=int(env.get("CACHE_MAX_SIZE", "256")),
    )
