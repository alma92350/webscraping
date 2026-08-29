from app.config import load_settings


def test_defaults_when_environment_is_empty():
    settings = load_settings(env={})

    assert settings.scrape_timeout_ms == 30000
    assert settings.max_concurrent_scrapes == 3
    assert settings.port == 7860
    assert settings.rate_limit_requests == 20
    assert settings.rate_limit_window_seconds == 60
    assert settings.api_key is None
    assert settings.cache_ttl_seconds == 300
    assert settings.cache_max_size == 256
    assert "Mozilla" in settings.user_agent


def test_reads_overrides_from_the_given_environment_mapping():
    env = {
        "SCRAPE_TIMEOUT_MS": "5000",
        "MAX_CONCURRENT_SCRAPES": "7",
        "PORT": "9000",
        "RATE_LIMIT_REQUESTS": "5",
        "RATE_LIMIT_WINDOW_SECONDS": "30",
        "SCRAPER_API_KEY": "secret123",
        "CACHE_TTL_SECONDS": "0",
        "CACHE_MAX_SIZE": "10",
        "SCRAPER_USER_AGENT": "TestAgent/1.0",
    }
    settings = load_settings(env=env)

    assert settings.scrape_timeout_ms == 5000
    assert settings.max_concurrent_scrapes == 7
    assert settings.port == 9000
    assert settings.rate_limit_requests == 5
    assert settings.rate_limit_window_seconds == 30
    assert settings.api_key == "secret123"
    assert settings.cache_ttl_seconds == 0
    assert settings.cache_max_size == 10
    assert settings.user_agent == "TestAgent/1.0"


def test_blank_api_key_is_treated_as_unset():
    settings = load_settings(env={"SCRAPER_API_KEY": ""})
    assert settings.api_key is None
