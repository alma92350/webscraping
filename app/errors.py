class ScrapeError(Exception):
    """Raised for any scrape-request failure that maps to a specific HTTP status."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
