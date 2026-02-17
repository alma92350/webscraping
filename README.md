# Web Scraping Service

This is a simple web scraping service built with FastAPI and BeautifulSoup, designed to be deployed on Hugging Face Spaces using Docker.

## Features

- **URL Scraping**: Extracts main content from a given URL.
- **Content Cleaning**: Removes ads, scripts, styles, and other clutter using heuristic rules.
- **JSON Output**: Returns clean text, title, and metadata.
- **Dockerized**: Easy to deploy and run anywhere.

## Local Development

1.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the application**:
    ```bash
    uvicorn main:app --reload
    ```

3.  **Test**:
    Open your browser to `http://127.0.0.1:8000/docs` to see the interactive API documentation.

## Deployment on Hugging Face Spaces

1.  Create a new Space on Hugging Face.
2.  Select **Docker** as the SDK.
3.  Upload the files in this repository to the Space.
    - `Dockerfile`
    - `requirements.txt`
    - `main.py`
    - `README.md`
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
  "status": "success"
}
```

### Endpoint: `GET /scrape`

**Query Parameter:** `url`

Example: `https://your-space-url.hf.space/scrape?url=https://example.com`
