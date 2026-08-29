---
title: Web Scraper API
emoji: 🕸️
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: true
---

# Web Scraping Service

A web scraping service built with FastAPI and Playwright, designed to be deployed on Hugging Face Spaces using Docker.

## Features

- **URL Scraping**: Renders a given URL with headless Chromium and extracts its main content.
- **Content Extraction**: Uses [trafilatura](https://github.com/adbar/trafilatura) (readability-style boilerplate removal) to drop nav/ads/footers and keep the real article text.
- **SSRF Guard**: Rejects targets that resolve to private, loopback, link-local, or reserved addresses, or use a non-http(s) scheme.
- **Rate Limiting**: Per-IP sliding-window limit, with an optional API key gate.
- **Response Caching**: Short-TTL in-memory cache so repeat requests for the same URL skip re-rendering.
- **JSON Output**: Returns clean text, title, and status.
- **Dockerized**: Runs one long-lived browser process, reused across requests via isolated contexts.

## Project layout

```
app/
  main.py       # FastAPI app, routes, request pipeline
  config.py     # env-driven settings
  security.py   # SSRF guard
  rate_limit.py # per-IP rate limiter + API key check
  cache.py      # TTL cache
  extractor.py  # content extraction (trafilatura)
  scraper.py    # Playwright browser lifecycle
tests/          # pytest suite (see Testing below)
```

## Local Development

1.  **Install dependencies**:
    ```bash
    pip install -r requirements-dev.txt
    playwright install chromium
    ```

2.  **Run the application**:
    ```bash
    uvicorn app.main:app --reload
    ```

3.  **Test**:
    Open your browser to `http://127.0.0.1:8000/docs` to see the interactive API documentation.

## Testing

The test suite mocks Playwright, so it runs without a real browser or network access:

```bash
pip install -r requirements-dev.txt
pytest
```

## Configuration

All settings are environment variables with sane defaults; none are required.

| Variable | Default | Purpose |
|---|---|---|
| `SCRAPE_TIMEOUT_MS` | `30000` | Max time to wait for page navigation |
| `MAX_CONCURRENT_SCRAPES` | `3` | Caps simultaneous browser renders |
| `SCRAPER_USER_AGENT` | a modern Chrome UA | User-Agent sent by the browser |
| `RATE_LIMIT_REQUESTS` | `20` | Max requests per client IP per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window length |
| `SCRAPER_API_KEY` | unset | If set, `/scrape` requires header `X-API-Key: <value>` |
| `CACHE_TTL_SECONDS` | `300` | How long a scraped result is cached (`0` disables caching) |
| `CACHE_MAX_SIZE` | `256` | Max cached URLs (LRU eviction) |
| `PORT` | `7860` | Port for the `python -m app.main` entry point (the Docker image's `CMD` sets this directly for uvicorn) |

## Deployment on Hugging Face Spaces

1.  Create a new Space on Hugging Face.
2.  Select **Docker** as the SDK.
3.  Push this repository's contents to the Space's `main` branch.
4.  The application will build and start automatically on port 7860.

## API Usage

### Endpoint: `POST /scrape`

**Request Body:**
```json
{
  "url": "https://example.com/article"
}
```

**Response:**
```json
{
  "url": "https://example.com/article",
  "title": "Example Article Title",
  "content": "Extracted text content...",
  "status": "success",
  "cached": false
}
```

### Endpoint: `GET /scrape`

**Query Parameter:** `url`

Example: `https://your-space-url.hf.space/scrape?url=https://example.com`

If `SCRAPER_API_KEY` is set, both endpoints require an `X-API-Key` header matching it.
