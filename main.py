from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, HttpUrl
import requests
from bs4 import BeautifulSoup, Comment
import re

app = FastAPI(title="Web Scraping Service")

class ScrapeRequest(BaseModel):
    url: HttpUrl

@app.get("/")
def read_root():
    return {"message": "Welcome to the Web Scraping Service! Send a POST request to /scrape with a JSON body {'url': '...'} or use GET /scrape?url=..."}

def clean_html(soup: BeautifulSoup):
    # Remove script, style, iframe, and other non-content tags
    for tag in soup(["script", "style", "iframe", "noscript", "meta", "link", "svg", "button", "input", "form"]):
        tag.decompose()

    # Remove comments
    for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Remove common ad and clutter classes/ids
    # This list is not exhaustive but catches many common patterns
    ad_patterns = re.compile(
        r"(ad|ads|advert|advertisement|banner|social|share|nav|footer|header|menu|sidebar|cookie|popup|modal|newsletter)",
        re.IGNORECASE
    )

    # Remove elements by class or id matching ad patterns
    for tag in soup.find_all(attrs={"class": ad_patterns}):
        tag.decompose()
    for tag in soup.find_all(attrs={"id": ad_patterns}):
        tag.decompose()

    return soup

@app.post("/scrape")
def scrape_url(request: ScrapeRequest):
    return process_scrape(str(request.url))

@app.get("/scrape")
def scrape_url_get(url: str):
    return process_scrape(url)

def process_scrape(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "lxml")

        # Extract title before cleaning
        title = soup.title.string.strip() if soup.title else "No title found"

        # Clean the HTML
        cleaned_soup = clean_html(soup)

        # Extract text
        # get_text with separator handles block elements better
        text = cleaned_soup.get_text(separator="\n", strip=True)

        # Simple cleanup of excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)

        return {
            "url": url,
            "title": title,
            "content": text,
            "status": "success"
        }

    except requests.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraping error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
