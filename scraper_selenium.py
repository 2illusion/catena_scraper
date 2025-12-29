# -*- coding: utf-8 -*-
"""
CATENA Journal Scraper - Search API Version
Based on the blog method: use search API to get articles

Usage:
    1. Open Chrome, go to sciencedirect.com and search for something
    2. Open DevTools (F12) -> Network tab -> search for "search/api"
    3. Copy the cookie and any required headers
    4. Paste cookie in this script or cookies.txt
    5. Run: python scraper_search_api.py --test
"""

import requests
import json
import re
import csv
import time
import random
import logging
import argparse
import os
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
from dataclasses import dataclass, field
from typing import List, Optional
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper_api.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ArticleInfo:
    title: str
    url: str
    pii: str = None
    volume: str = None
    year: int = None
    doi: str = None
    authors: List[str] = field(default_factory=list)
    publication_date: str = None
    received_date: str = None
    revised_date: str = None
    accepted_date: str = None
    available_online_date: str = None
    review_days: int = None
    scrape_status: str = "pending"
    
    def calculate_review_days(self):
        if self.received_date and self.accepted_date:
            try:
                received = date_parser.parse(self.received_date)
                accepted = date_parser.parse(self.accepted_date)
                self.review_days = (accepted - received).days
            except Exception as e:
                logger.warning(f"Could not parse dates: {e}")


class SearchAPIScraper:
    """Scraper using ScienceDirect Search API"""
    
    BASE_URL = "https://www.sciencedirect.com"
    SEARCH_API = "https://www.sciencedirect.com/search/api"
    
    def __init__(self, cookie_string: str = None):
        self.session = requests.Session()
        self.articles: List[ArticleInfo] = []
        self.cookie_string = cookie_string
        
        Path("data").mkdir(exist_ok=True)
        Path("data/debug").mkdir(parents=True, exist_ok=True)
        
        # Default headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://www.sciencedirect.com',
            'Referer': 'https://www.sciencedirect.com/search',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })
        
        if cookie_string:
            self.session.headers['Cookie'] = cookie_string
    
    def load_cookie_from_file(self, filepath: str = "cookies.txt") -> bool:
        """Load cookie string from file"""
        if not os.path.exists(filepath):
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                cookie = f.read().strip()
            
            if cookie:
                self.session.headers['Cookie'] = cookie
                self.cookie_string = cookie
                logger.info(f"Loaded cookie from {filepath}")
                return True
        except Exception as e:
            logger.error(f"Error loading cookie: {e}")
        
        return False
    
    def random_delay(self, min_sec: float = 2, max_sec: float = 5):
        time.sleep(random.uniform(min_sec, max_sec))
    
    def save_debug(self, filename: str, content: str):
        filepath = Path('data/debug') / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"Saved debug: {filepath}")
    
    def search_journal_volume(self, journal: str = "CATENA", volume: int = 263, rows: int = 100) -> List[dict]:
        """
        Search for articles in a specific journal volume using the search API
        """
        logger.info(f"Searching {journal} Volume {volume}...")
        
        # Build search query
        query = f'vol({volume})'
        
        params = {
            'qs': query,
            'pub': journal,
            'show': str(rows),
            'sortBy': 'date',
            't': 'placeholder',  # Token - might not be strictly required
            'hostname': 'www.sciencedirect.com',
            'origin': 'resultsAnalyzer',
        }
        
        try:
            resp = self.session.get(self.SEARCH_API, params=params, timeout=30)
            
            logger.info(f"Search API status: {resp.status_code}")
            
            # Save raw response for debugging
            self.save_debug("search_response.json", resp.text)
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    results = data.get('searchResults', [])
                    logger.info(f"Found {len(results)} results from API")
                    return results
                except json.JSONDecodeError:
                    logger.error("Response is not valid JSON")
                    self.save_debug("search_response.html", resp.text)
                    return []
            elif resp.status_code == 403:
                logger.error("403 Forbidden - Cookie may be invalid or expired")
                return []
            else:
                logger.error(f"API returned status {resp.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Search API error: {e}")
            return []
    
    def parse_search_results(self, results: List[dict], volume: int) -> List[ArticleInfo]:
        """Parse search API results into ArticleInfo objects"""
        articles = []
        
        for item in results:
            try:
                # Get basic info from search result
                title = item.get('title', '').replace('<em>', '').replace('</em>', '')
                doi = item.get('doi', '')
                pii = item.get('pii', '')
                
                # Build URL
                if pii:
                    url = f"{self.BASE_URL}/science/article/pii/{pii}"
                elif doi:
                    url = f"https://doi.org/{doi}"
                else:
                    continue
                
                # Get authors
                authors = []
                for author in item.get('authors', []):
                    name = author.get('name', '')
                    if name:
                        authors.append(name)
                
                # Get publication date
                pub_date = item.get('publicationDate', '')
                
                # Get source title to verify it's CATENA
                source = item.get('sourceTitle', '')
                
                article = ArticleInfo(
                    title=title,
                    url=url,
                    pii=pii,
                    doi=doi,
                    volume=str(volume),
                    authors=authors,
                    publication_date=pub_date,
                )
                
                articles.append(article)
                
            except Exception as e:
                logger.warning(f"Error parsing result: {e}")
                continue
        
        return articles
    
    def get_article_details(self, article: ArticleInfo, num: int) -> ArticleInfo:
        """Get article page to extract received/accepted dates"""
        logger.info(f"[{num}] {article.title[:50]}...")
        
        try:
            # Use the abstract page which might have less protection
            if article.pii:
                url = f"{self.BASE_URL}/science/article/abs/pii/{article.pii}"
            else:
                url = article.url
            
            resp = self.session.get(url, timeout=30)
            
            if resp.status_code == 403:
                logger.warning("  403 Forbidden - trying alternative...")
                # Try the DOI redirect
                if article.doi:
                    resp = self.session.get(f"https://doi.org/{article.doi}", timeout=30, allow_redirects=True)
            
            if resp.status_code != 200:
                logger.warning(f"  Status {resp.status_code}")
                article.scrape_status = "http_error"
                return article
            
            # Save first article for debugging
            if num == 1:
                self.save_debug("first_article.html", resp.text)
            
            # Check if blocked
            if 'There was a problem providing' in resp.text or 'Reference number:' in resp.text:
                logger.warning("  Page blocked")
                article.scrape_status = "blocked"
                return article
            
            # Parse HTML
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text()
            
            # Extract dates
            patterns = [
                (r'Received\s+(\d{1,2}\s+\w+\s+\d{4})', 'received_date'),
                (r'Revised\s+(\d{1,2}\s+\w+\s+\d{4})', 'revised_date'),
                (r'Accepted\s+(\d{1,2}\s+\w+\s+\d{4})', 'accepted_date'),
                (r'Available\s+online\s+(\d{1,2}\s+\w+\s+\d{4})', 'available_online_date'),
            ]
            
            for pattern, field in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    setattr(article, field, match.group(1))
                    logger.info(f"  {field}: {match.group(1)}")
            
            article.calculate_review_days()
            
            if article.received_date or article.accepted_date:
                article.scrape_status = "success"
                if article.review_days:
                    logger.info(f"  Review time: {article.review_days} days")
            else:
                article.scrape_status = "no_dates"
            
            return article
            
        except Exception as e:
            logger.error(f"  Error: {e}")
            article.scrape_status = "error"
            return article
    
    def export_results(self):
        if not self.articles:
            logger.warning("No articles to export")
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # CSV
        csv_file = Path('data') / f'catena_{timestamp}.csv'
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            fields = ['title', 'volume', 'doi', 'received_date', 'accepted_date',
                     'review_days', 'publication_date', 'url', 'scrape_status']
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for a in self.articles:
                writer.writerow({k: getattr(a, k, '') for k in fields})
        logger.info(f"Saved: {csv_file}")
        
        # Excel
        xlsx_file = Path('data') / f'catena_{timestamp}.xlsx'
        wb = Workbook()
        ws = wb.active
        ws.title = "Articles"
        
        headers = ['Title', 'Volume', 'DOI', 'Received', 'Accepted', 
                   'Review Days', 'Published', 'URL', 'Status']
        ws.append(headers)
        
        for cell in ws[1]:
            cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
            cell.font = Font(bold=True, color='FFFFFF')
        
        for a in self.articles:
            ws.append([a.title, a.volume, a.doi, a.received_date, a.accepted_date,
                      a.review_days, a.publication_date, a.url, a.scrape_status])
        
        ws.column_dimensions['A'].width = 60
        ws.column_dimensions['H'].width = 50
        wb.save(xlsx_file)
        logger.info(f"Saved: {xlsx_file}")
        
        # Stats
        total = len(self.articles)
        success = sum(1 for a in self.articles if a.scrape_status == "success")
        with_dates = sum(1 for a in self.articles if a.review_days)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"RESULTS: {total} total, {success} success, {with_dates} with dates")
        if with_dates:
            avg = sum(a.review_days for a in self.articles if a.review_days) / with_dates
            logger.info(f"Average review time: {avg:.1f} days")
        logger.info("=" * 60)
    
    def scrape(self, volume: int = 263, max_articles: int = 10, fetch_details: bool = True):
        """Main scraping workflow"""
        
        # Try to load cookie
        if not self.cookie_string:
            self.load_cookie_from_file("cookies.txt")
        
        # Step 1: Get article list from search API
        results = self.search_journal_volume("CATENA", volume, rows=100)
        
        if not results:
            logger.error("No results from search API")
            logger.info("")
            logger.info("=" * 60)
            logger.info("TROUBLESHOOTING:")
            logger.info("=" * 60)
            logger.info("1. Open Chrome and go to: https://www.sciencedirect.com/search")
            logger.info("2. Search for 'CATENA' and wait for results")
            logger.info("3. Press F12 -> Network tab")
            logger.info("4. In the filter box, type 'search/api'")
            logger.info("5. Click on the request and copy the Cookie header value")
            logger.info("6. Paste it into cookies.txt file")
            logger.info("7. Run this script again")
            logger.info("=" * 60)
            return
        
        # Step 2: Parse results
        articles = self.parse_search_results(results, volume)
        logger.info(f"Parsed {len(articles)} articles")
        
        if not articles:
            logger.error("No articles parsed from results")
            return
        
        # Limit articles
        articles = articles[:max_articles]
        
        # Step 3: Get details (dates) from each article page
        if fetch_details:
            for i, article in enumerate(articles, 1):
                article = self.get_article_details(article, i)
                self.articles.append(article)
                self.random_delay(3, 6)
        else:
            # Just use search results without fetching pages
            self.articles = articles
            for a in self.articles:
                a.scrape_status = "api_only"
        
        # Step 4: Export
        self.export_results()


def main():
    parser = argparse.ArgumentParser(description='CATENA Search API Scraper')
    parser.add_argument('--test', action='store_true', help='Test mode (5 articles)')
    parser.add_argument('--volume', type=int, default=263, help='Volume number')
    parser.add_argument('--max', type=int, default=10, help='Max articles')
    parser.add_argument('--cookie', type=str, help='Cookie string')
    parser.add_argument('--no-details', action='store_true', help='Skip fetching article pages')
    
    args = parser.parse_args()
    
    if args.test:
        args.max = 5
    
    print("\n" + "="*60)
    print("CATENA Journal Scraper - Search API Version")
    print("="*60)
    print("")
    print("To get cookies:")
    print("1. Go to sciencedirect.com/search in Chrome")
    print("2. Search for anything")
    print("3. F12 -> Network -> filter 'search/api'")
    print("4. Copy Cookie header -> paste in cookies.txt")
    print("="*60 + "\n")
    
    scraper = SearchAPIScraper(cookie_string=args.cookie)
    scraper.scrape(
        volume=args.volume,
        max_articles=args.max,
        fetch_details=not args.no_details
    )


if __name__ == '__main__':
    main()