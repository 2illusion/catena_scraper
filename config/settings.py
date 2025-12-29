"""
CATENA Journal Scraper Configuration
"""

# Target URL
BASE_URL = "https://www.sciencedirect.com"
JOURNAL_URL = "https://www.sciencedirect.com/journal/catena/issues"

# Request settings
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# Rate limiting (be respectful to the server)
MIN_DELAY = 2  # minimum delay between requests (seconds)
MAX_DELAY = 5  # maximum delay between requests (seconds)

# Playwright settings
HEADLESS = True
SLOW_MO = 100  # milliseconds between actions

# User agents rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Output settings
OUTPUT_DIR = "data"
CSV_OUTPUT = "catena_articles.csv"
EXCEL_OUTPUT = "catena_articles.xlsx"
JSON_OUTPUT = "catena_articles.json"

# Logging
LOG_DIR = "logs"
LOG_FILE = "scraper.log"
LOG_LEVEL = "INFO"

# Scraping scope (set to None to scrape all)
# Example: YEAR_RANGE = (2020, 2025) to only scrape 2020-2025
YEAR_RANGE = None  # or (2020, 2025)

# Volume range (set to None to scrape all)
# Example: VOLUME_RANGE = (240, 263) to only scrape volumes 240-263
VOLUME_RANGE = None  # or (240, 263)

# Maximum articles to scrape (for testing, set to None for all)
MAX_ARTICLES = None  # or 100 for testing

# Proxy settings (optional)
PROXY = None  # or "http://proxy:port"
