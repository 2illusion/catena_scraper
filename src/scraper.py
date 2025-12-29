"""
CATENA Journal Scraper - Main scraping logic using Playwright with stealth
"""

import asyncio
import random
import re
import logging
from datetime import datetime
from typing import List, Optional, Tuple
from urllib.parse import urljoin
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (
    BASE_URL, JOURNAL_URL, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY,
    MIN_DELAY, MAX_DELAY, HEADLESS, SLOW_MO, USER_AGENTS, PROXY,
    YEAR_RANGE, VOLUME_RANGE, MAX_ARTICLES
)
from src.models import ArticleInfo, VolumeInfo, ScrapingProgress


logger = logging.getLogger(__name__)


# Stealth JavaScript to inject
STEALTH_JS = """
// Webdriver property
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// Languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en', 'zh-CN']
});

// Plugins - make it look like a real browser
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' }
        ];
        const pluginArray = Object.create(PluginArray.prototype);
        plugins.forEach((p, i) => {
            pluginArray[i] = p;
        });
        pluginArray.length = plugins.length;
        return pluginArray;
    }
});

// Platform
Object.defineProperty(navigator, 'platform', {
    get: () => 'Win32'
});

// Hardware concurrency
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8
});

// Device memory
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8
});

// Chrome runtime
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};

// Permissions
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// WebGL Vendor and Renderer
const getParameterProxyHandler = {
    apply: function(target, thisArg, argumentsList) {
        const param = argumentsList[0];
        const gl = thisArg;
        if (param === 37445) {
            return 'Intel Inc.';
        }
        if (param === 37446) {
            return 'Intel Iris OpenGL Engine';
        }
        return Reflect.apply(target, thisArg, argumentsList);
    }
};

// Override getParameter
try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (gl) {
        gl.getParameter = new Proxy(gl.getParameter, getParameterProxyHandler);
    }
} catch (e) {}

// Remove automation-related properties
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

// Override toString to hide proxy
const originalToString = Function.prototype.toString;
Function.prototype.toString = function() {
    if (this === window.navigator.permissions.query) {
        return 'function query() { [native code] }';
    }
    return originalToString.call(this);
};
"""


class CatenaScraper:
    """Scraper for CATENA journal articles from ScienceDirect"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.progress = ScrapingProgress()
        self.articles: List[ArticleInfo] = []
        self.volumes: List[VolumeInfo] = []
        self.playwright = None
        
    async def init_browser(self):
        """Initialize Playwright browser with enhanced anti-detection settings"""
        self.playwright = await async_playwright().start()
        
        # Use Firefox for better anti-detection (ScienceDirect seems to allow it better)
        # Or use Chromium with channel='chrome' to use real Chrome
        
        # Try to use real Chrome first, fall back to Chromium
        try:
            self.browser = await self.playwright.chromium.launch(
                headless=HEADLESS,
                slow_mo=SLOW_MO,
                channel='chrome',  # Use real Chrome browser
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                    '--start-maximized',
                ]
            )
            logger.info("Using Chrome browser")
        except Exception as e:
            logger.warning(f"Chrome not available, using Chromium: {e}")
            self.browser = await self.playwright.chromium.launch(
                headless=HEADLESS,
                slow_mo=SLOW_MO,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                ]
            )
        
        # Create context with realistic settings
        user_agent = random.choice(USER_AGENTS)
        
        self.context = await self.browser.new_context(
            user_agent=user_agent,
            viewport={'width': 1920, 'height': 1080},
            screen={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=True,
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
            }
        )
        
        # Add stealth scripts
        await self.context.add_init_script(STEALTH_JS)
        
        self.page = await self.context.new_page()
        
        # Set default timeout
        self.page.set_default_timeout(REQUEST_TIMEOUT * 1000)
        
        # Add human-like mouse movements
        await self._setup_human_behavior()
        
        logger.info(f"Browser initialized with user agent: {user_agent[:50]}...")
    
    async def _setup_human_behavior(self):
        """Setup human-like behavior patterns"""
        # Random viewport adjustments
        width = random.randint(1200, 1920)
        height = random.randint(800, 1080)
        await self.page.set_viewport_size({'width': width, 'height': height})
        
    async def close_browser(self):
        """Close browser resources"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")
        logger.info("Browser closed")
    
    async def random_delay(self, min_delay: float = None, max_delay: float = None):
        """Add random delay to avoid detection"""
        min_d = min_delay or MIN_DELAY
        max_d = max_delay or MAX_DELAY
        delay = random.uniform(min_d, max_d)
        await asyncio.sleep(delay)
    
    async def _human_scroll(self):
        """Perform human-like scrolling"""
        # Scroll down slowly
        for _ in range(random.randint(2, 5)):
            scroll_amount = random.randint(100, 300)
            await self.page.evaluate(f'window.scrollBy(0, {scroll_amount})')
            await asyncio.sleep(random.uniform(0.1, 0.3))
    
    async def _move_mouse_randomly(self):
        """Move mouse randomly to simulate human behavior"""
        try:
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            await self.page.mouse.move(x, y)
        except:
            pass
    
    async def navigate_with_retry(self, url: str, retries: int = MAX_RETRIES) -> bool:
        """Navigate to URL with retry logic and human-like behavior"""
        for attempt in range(retries):
            try:
                # Add random delay before navigation
                if attempt > 0:
                    await self.random_delay(3, 8)
                
                # Navigate with domcontentloaded first (faster)
                response = await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
                
                # Wait a bit more for dynamic content
                await asyncio.sleep(random.uniform(1, 2))
                
                # Check for Cloudflare or other challenges
                content = await self.page.content()
                if 'challenge' in content.lower() or 'captcha' in content.lower():
                    logger.warning(f"Challenge detected on {url}, waiting...")
                    await asyncio.sleep(5)
                    # Try to wait for challenge to complete
                    await self.page.wait_for_load_state('networkidle', timeout=30000)
                
                if response and response.ok:
                    # Human-like behavior after page load
                    await self._move_mouse_randomly()
                    await self._human_scroll()
                    await self.random_delay(1, 3)
                    return True
                    
                if response and response.status == 403:
                    logger.warning(f"403 Forbidden for {url}, attempt {attempt + 1}/{retries}")
                    # Longer delay on 403
                    await asyncio.sleep(random.uniform(5, 10))
                else:
                    logger.warning(f"Response not OK for {url}: {response.status if response else 'No response'}")
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{retries} failed for {url}: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
        return False
    
    async def get_all_volumes(self) -> List[VolumeInfo]:
        """Get all volume/issue information from the journal issues page"""
        logger.info(f"Fetching volume list from {JOURNAL_URL}")
        
        # Warm-up: Visit homepage first to get cookies
        logger.info("Warming up - visiting ScienceDirect homepage...")
        try:
            await self.page.goto('https://www.sciencedirect.com', wait_until='domcontentloaded', timeout=30000)
            await self.random_delay(2, 4)
            await self._human_scroll()
        except Exception as e:
            logger.warning(f"Homepage warmup failed: {e}")
        
        # Now navigate to journal page
        if not await self.navigate_with_retry(JOURNAL_URL):
            logger.error("Failed to load journal issues page")
            return []
        
        volumes = []
        
        # Wait for content to load
        try:
            await self.page.wait_for_selector('.issue-item, .accordion-panel, [class*="issue"]', timeout=30000)
        except:
            logger.warning("Could not find issue elements, trying alternative approach...")
        
        # Get page content
        content = await self.page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Debug: Save page for analysis
        debug_path = Path('data/debug_page.html')
        debug_path.parent.mkdir(exist_ok=True)
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Saved debug page to {debug_path}")
        
        # Try multiple selectors for year sections
        year_sections = soup.find_all('div', class_='accordion-panel')
        
        if not year_sections:
            # Alternative: look for year headers
            year_sections = soup.find_all('div', class_=re.compile(r'year|volume|issue', re.I))
        
        if not year_sections:
            # Try to find all volume links directly
            logger.info("No year sections found, looking for volume links directly...")
            all_links = soup.find_all('a', href=re.compile(r'/journal/catena/vol/\d+'))
            
            for link in all_links:
                href = link.get('href', '')
                vol_match = re.search(r'/vol/(\d+)', href)
                if not vol_match:
                    continue
                
                vol_num = int(vol_match.group(1))
                
                # Check volume range filter
                if VOLUME_RANGE and (vol_num < VOLUME_RANGE[0] or vol_num > VOLUME_RANGE[1]):
                    continue
                
                # Try to extract year from nearby text
                year = None
                parent = link.find_parent(['li', 'div', 'section'])
                if parent:
                    text = parent.get_text()
                    year_match = re.search(r'20\d{2}', text)
                    if year_match:
                        year = int(year_match.group(0))
                
                # Check year range filter
                if year and YEAR_RANGE and (year < YEAR_RANGE[0] or year > YEAR_RANGE[1]):
                    continue
                
                full_url = urljoin(BASE_URL, href)
                
                volume = VolumeInfo(
                    volume_number=vol_num,
                    year=year or 2025,
                    url=full_url
                )
                
                # Avoid duplicates
                if not any(v.volume_number == vol_num for v in volumes):
                    volumes.append(volume)
                    logger.debug(f"Found volume {vol_num}: {full_url}")
            
        else:
            # Original logic for accordion panels
            for section in year_sections:
                # Extract year from header
                header = section.find('button', class_='accordion-panel-header')
                if not header:
                    header = section.find(['h2', 'h3', 'h4', 'span'], class_=re.compile(r'header|title', re.I))
                if not header:
                    continue
                
                year_text = header.get_text(strip=True)
                year_match = re.search(r'(\d{4})', year_text)
                if not year_match:
                    continue
                year = int(year_match.group(1))
                
                # Check year range filter
                if YEAR_RANGE and (year < YEAR_RANGE[0] or year > YEAR_RANGE[1]):
                    logger.info(f"Skipping year {year} (outside range {YEAR_RANGE})")
                    continue
                
                # Click to expand this year's section if needed
                panel_id = header.get('aria-controls', '')
                if panel_id:
                    try:
                        button = await self.page.query_selector(f'button[aria-controls="{panel_id}"]')
                        if button:
                            is_expanded = await button.get_attribute('aria-expanded')
                            if is_expanded == 'false':
                                await button.click()
                                await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.warning(f"Could not expand year {year}: {e}")
                
                # Find volume links within this section
                volume_links = section.find_all('a', href=re.compile(r'/journal/catena/vol/\d+'))
                
                for link in volume_links:
                    href = link.get('href', '')
                    vol_match = re.search(r'/vol/(\d+)', href)
                    if not vol_match:
                        continue
                    
                    vol_num = int(vol_match.group(1))
                    
                    # Check volume range filter
                    if VOLUME_RANGE and (vol_num < VOLUME_RANGE[0] or vol_num > VOLUME_RANGE[1]):
                        continue
                    
                    # Get issue info from link text
                    issue_info = None
                    
                    # Find associated date/issue info
                    parent = link.find_parent('li') or link.find_parent('div')
                    if parent:
                        issue_text = parent.get_text(strip=True)
                        # Extract month/issue info
                        issue_match = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s*\d{4}', issue_text, re.I)
                        if issue_match:
                            issue_info = issue_match.group(0)
                    
                    full_url = urljoin(BASE_URL, href)
                    
                    volume = VolumeInfo(
                        volume_number=vol_num,
                        year=year,
                        issue=issue_info,
                        url=full_url
                    )
                    volumes.append(volume)
                    logger.debug(f"Found volume {vol_num} ({year}): {full_url}")
        
        # Sort by volume number descending (newest first)
        volumes.sort(key=lambda v: v.volume_number, reverse=True)
        
        self.progress.total_volumes = len(volumes)
        logger.info(f"Found {len(volumes)} volumes")
        
        return volumes
    
    async def get_articles_from_volume(self, volume: VolumeInfo) -> List[ArticleInfo]:
        """Get all articles from a specific volume page"""
        logger.info(f"Fetching articles from Volume {volume.volume_number} ({volume.year})")
        
        if not await self.navigate_with_retry(volume.url):
            logger.error(f"Failed to load volume page: {volume.url}")
            return []
        
        articles = []
        
        # Wait for article list to load
        try:
            await self.page.wait_for_selector('.article-list', timeout=15000)
        except:
            logger.warning(f"No article list found for volume {volume.volume_number}")
            return []
        
        # Scroll to load all articles (lazy loading)
        await self._scroll_to_bottom()
        
        content = await self.page.content()
        soup = BeautifulSoup(content, 'html.parser')
        
        # Find all article items
        article_items = soup.find_all('li', class_='js-article-list-item')
        
        for item in article_items:
            try:
                # Get article title and link
                title_elem = item.find('a', class_='article-content-title')
                if not title_elem:
                    title_elem = item.find('h2')
                    if title_elem:
                        title_elem = title_elem.find('a')
                
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                href = title_elem.get('href', '')
                
                if not href or not title:
                    continue
                
                full_url = urljoin(BASE_URL, href)
                
                # Get article ID from URL
                article_id = None
                id_match = re.search(r'/pii/([A-Z0-9]+)', href)
                if id_match:
                    article_id = id_match.group(1)
                
                # Get authors
                authors = []
                author_list = item.find('div', class_='article-authors')
                if author_list:
                    author_links = author_list.find_all('a')
                    authors = [a.get_text(strip=True) for a in author_links]
                
                article = ArticleInfo(
                    title=title,
                    url=full_url,
                    article_id=article_id,
                    volume=volume.volume_number,
                    year=volume.year,
                    issue=volume.issue,
                    authors=authors,
                    scraped_at=datetime.now().isoformat()
                )
                articles.append(article)
                
            except Exception as e:
                logger.warning(f"Error parsing article item: {e}")
                continue
        
        volume.article_count = len(articles)
        logger.info(f"Found {len(articles)} articles in Volume {volume.volume_number}")
        
        return articles
    
    async def _scroll_to_bottom(self):
        """Scroll page to bottom to trigger lazy loading"""
        prev_height = 0
        max_scrolls = 10
        
        for _ in range(max_scrolls):
            await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await asyncio.sleep(0.5)
            
            curr_height = await self.page.evaluate('document.body.scrollHeight')
            if curr_height == prev_height:
                break
            prev_height = curr_height
        
        # Scroll back to top
        await self.page.evaluate('window.scrollTo(0, 0)')
    
    async def get_article_details(self, article: ArticleInfo) -> ArticleInfo:
        """Get detailed information (dates) from article page"""
        logger.debug(f"Fetching details for: {article.title[:50]}...")
        
        if not await self.navigate_with_retry(article.url):
            article.scrape_status = "failed"
            article.error_message = "Failed to load article page"
            return article
        
        try:
            content = await self.page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Method 1: Find dates in the history section
            # Pattern: "Received 24 April 2025, Revised 10 November 2025, Accepted 20 November 2025..."
            dates_section = soup.find('div', class_='publication-history')
            
            if not dates_section:
                # Try alternative selectors
                dates_section = soup.find('p', class_='article-dates')
                
            if not dates_section:
                # Look for text containing "Received"
                for p in soup.find_all(['p', 'div', 'span']):
                    text = p.get_text()
                    if 'Received' in text and ('Accepted' in text or 'Revised' in text):
                        dates_section = p
                        break
            
            if dates_section:
                dates_text = dates_section.get_text()
                
                # Extract dates using regex
                # Patterns like "Received 24 April 2025"
                received_match = re.search(
                    r'Received\s+(\d{1,2}\s+\w+\s+\d{4})', 
                    dates_text, re.IGNORECASE
                )
                if received_match:
                    article.received_date = received_match.group(1)
                
                revised_match = re.search(
                    r'Revised\s+(\d{1,2}\s+\w+\s+\d{4})', 
                    dates_text, re.IGNORECASE
                )
                if revised_match:
                    article.revised_date = revised_match.group(1)
                
                accepted_match = re.search(
                    r'Accepted\s+(\d{1,2}\s+\w+\s+\d{4})', 
                    dates_text, re.IGNORECASE
                )
                if accepted_match:
                    article.accepted_date = accepted_match.group(1)
                
                online_match = re.search(
                    r'Available\s+online\s+(\d{1,2}\s+\w+\s+\d{4})', 
                    dates_text, re.IGNORECASE
                )
                if online_match:
                    article.available_online_date = online_match.group(1)
                
                version_match = re.search(
                    r'Version\s+of\s+Record\s+(\d{1,2}\s+\w+\s+\d{4})', 
                    dates_text, re.IGNORECASE
                )
                if version_match:
                    article.version_of_record_date = version_match.group(1)
            
            # Get DOI
            doi_elem = soup.find('a', class_='doi')
            if doi_elem:
                article.doi = doi_elem.get_text(strip=True)
            else:
                # Try meta tag
                doi_meta = soup.find('meta', {'name': 'citation_doi'})
                if doi_meta:
                    article.doi = doi_meta.get('content', '')
            
            # Parse dates and calculate review time
            article.parse_dates()
            
            article.scrape_status = "success"
            logger.debug(f"Got dates - Received: {article.received_date}, Accepted: {article.accepted_date}, Review days: {article.review_days}")
            
        except Exception as e:
            article.scrape_status = "failed"
            article.error_message = str(e)
            logger.error(f"Error getting article details: {e}")
        
        return article
    
    async def scrape_all(self, resume: bool = False) -> List[ArticleInfo]:
        """Main scraping method - scrape all articles"""
        try:
            await self.init_browser()
            
            self.progress.started_at = datetime.now().isoformat()
            
            # Get all volumes
            self.volumes = await self.get_all_volumes()
            
            if not self.volumes:
                logger.error("No volumes found")
                return []
            
            article_count = 0
            
            # Process each volume
            for vol_idx, volume in enumerate(self.volumes):
                logger.info(f"Processing volume {vol_idx + 1}/{len(self.volumes)}: Volume {volume.volume_number}")
                
                # Get articles from volume page
                volume_articles = await self.get_articles_from_volume(volume)
                
                # Get detailed info for each article
                for art_idx, article in enumerate(volume_articles):
                    # Check max articles limit
                    if MAX_ARTICLES and article_count >= MAX_ARTICLES:
                        logger.info(f"Reached max articles limit ({MAX_ARTICLES})")
                        break
                    
                    logger.info(f"  Article {art_idx + 1}/{len(volume_articles)}: {article.title[:50]}...")
                    
                    await self.get_article_details(article)
                    self.articles.append(article)
                    article_count += 1
                    
                    # Update progress
                    self.progress.scraped_articles = article_count
                    if article.scrape_status == "failed":
                        self.progress.failed_articles += 1
                
                self.progress.scraped_volumes = vol_idx + 1
                self.progress.last_volume = volume.volume_number
                
                if MAX_ARTICLES and article_count >= MAX_ARTICLES:
                    break
            
            logger.info(f"Scraping complete: {len(self.articles)} articles")
            return self.articles
            
        finally:
            await self.close_browser()
    
    def get_statistics(self) -> dict:
        """Calculate statistics from scraped data"""
        if not self.articles:
            return {}
        
        successful = [a for a in self.articles if a.scrape_status == "success" and a.review_days is not None]
        
        if not successful:
            return {
                "total_articles": len(self.articles),
                "successful_scrapes": 0,
                "failed_scrapes": len(self.articles),
            }
        
        review_days = [a.review_days for a in successful]
        
        return {
            "total_articles": len(self.articles),
            "successful_scrapes": len(successful),
            "failed_scrapes": len(self.articles) - len(successful),
            "avg_review_days": sum(review_days) / len(review_days),
            "min_review_days": min(review_days),
            "max_review_days": max(review_days),
            "median_review_days": sorted(review_days)[len(review_days) // 2],
        }


async def main():
    """Main entry point"""
    scraper = CatenaScraper()
    articles = await scraper.scrape_all()
    
    stats = scraper.get_statistics()
    print("\n=== Scraping Statistics ===")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.1f}")
        else:
            print(f"{key}: {value}")
    
    return articles


if __name__ == "__main__":
    asyncio.run(main())
