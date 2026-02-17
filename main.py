import nest_asyncio
nest_asyncio.apply()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup, Comment
import re
import asyncio

app = FastAPI(title="Web Scraper API")

class ScrapeRequest(BaseModel):
    url: HttpUrl

@app.get("/")
def read_root():
    return {"message": "Welcome to the Playwright Web Scraping Service! Send a POST request to /scrape with a JSON body {'url': '...'} or use GET /scrape?url=..."}

def clean_html(html_content: str):
    soup = BeautifulSoup(html_content, "lxml")

    # Extract title before cleaning
    title = soup.title.string.strip() if soup.title else "No title found"

    # Remove script, style, iframe, and other non-content tags
    for tag in soup(["script", "style", "iframe", "noscript", "meta", "link", "svg", "button", "input", "form"]):
        tag.decompose()

    # Remove comments
    for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Remove common ad and clutter classes/ids
    ad_patterns = re.compile(
        r"(ad|ads|advert|advertisement|banner|social|share|nav|footer|header|menu|sidebar|cookie|popup|modal|newsletter)",
        re.IGNORECASE
    )

    for tag in soup.find_all(attrs={"class": ad_patterns}):
        tag.decompose()
    for tag in soup.find_all(attrs={"id": ad_patterns}):
        tag.decompose()

    # Extract text
    text = soup.get_text(separator="\n", strip=True)
    # Simple cleanup of excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return title, text

async def scrape_with_playwright(url: str):
    async with async_playwright() as p:
        # Launch with arguments to hide automation
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        # Use a modern User-Agent and realistic viewport
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York"
        )

        # Add init script to further hide webdriver property
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = await context.new_page()

        try:
            # Go to URL and wait for network to be idle (load complete)
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Get content
            content = await page.content()

            return content
        finally:
            await browser.close()

@app.post("/scrape")
async def scrape_url(request: ScrapeRequest):
    return await process_scrape(str(request.url))

@app.get("/scrape")
async def scrape_url_get(url: str):
    return await process_scrape(url)

async def process_scrape(url: str):
    try:
        html_content = await scrape_with_playwright(url)
        title, text = clean_html(html_content)

        return {
            "url": url,
            "title": title,
            "content": text,
            "status": "success"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
