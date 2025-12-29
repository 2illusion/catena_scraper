# -*- coding: utf-8 -*-
"""
CATENA Journal Scraper - Local Driver Version
Uses existing local ChromeDriver, no download needed.

Usage:
    python scraper_local.py --test
"""

import time
import random
import re
import csv
import logging
import argparse
import os
import glob
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import List
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def find_chromedriver():
    """Find existing ChromeDriver"""
    paths = [
        # webdriver-manager cache
        os.path.expanduser("~/.wdm/drivers/chromedriver/win64/*/chromedriver-win32/chromedriver.exe"),
        os.path.expanduser("~/.wdm/drivers/chromedriver/win64/*/chromedriver.exe"),
        # Current directory
        "./chromedriver.exe",
        "./chromedriver-win64/chromedriver.exe",
    ]
    
    for pattern in paths:
        matches = glob.glob(pattern)
        if matches:
            # Get newest
            matches.sort(key=os.path.getmtime, reverse=True)
            return matches[0]
    return None


@dataclass
class ArticleInfo:
    title: str
    url: str
    volume: int = None
    doi: str = None
    received_date: str = None
    accepted_date: str = None
    review_days: int = None
    scrape_status: str = "pending"
    
    def calculate_review_days(self):
        if self.received_date and self.accepted_date:
            try:
                received = date_parser.parse(self.received_date)
                accepted = date_parser.parse(self.accepted_date)
                self.review_days = (accepted - received).days
            except:
                pass


class LocalDriverScraper:
    BASE_URL = "https://www.sciencedirect.com"
    
    def __init__(self):
        self.driver = None
        self.articles: List[ArticleInfo] = []
        Path("data").mkdir(exist_ok=True)
        Path("data/debug").mkdir(parents=True, exist_ok=True)
    
    def init_driver(self):
        """Initialize Chrome with local driver"""
        driver_path = find_chromedriver()
        
        if not driver_path:
            logger.error("ChromeDriver not found!")
            logger.info("Please download manually from:")
            logger.info("https://googlechromelabs.github.io/chrome-for-testing/")
            logger.info("Get version 142 and put chromedriver.exe in current folder")
            raise FileNotFoundError("ChromeDriver not found")
        
        logger.info(f"Using: {driver_path}")
        
        options = Options()
        
        # Anti-detection settings
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        # Disable automation flags
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-extensions')
        
        service = Service(executable_path=driver_path)
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(15)
        
        # Remove webdriver property
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.navigator.chrome = {runtime: {}};
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            '''
        })
        
        logger.info("Chrome started!")
    
    def close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def delay(self, min_s=3, max_s=7):
        time.sleep(random.uniform(min_s, max_s))
    
    def scroll(self):
        for _ in range(random.randint(2, 4)):
            self.driver.execute_script(f"window.scrollBy(0, {random.randint(200, 500)});")
            time.sleep(random.uniform(0.3, 0.8))
    
    def is_blocked(self) -> bool:
        try:
            src = self.driver.page_source
            blocked = any(x in src for x in [
                'There was a problem providing',
                'Reference number:',
                'px-captcha',
                '\u63d0\u4f9b\u60a8\u8bf7\u6c42',  # Chinese block text
            ])
            return blocked
        except:
            return False
    
    def wait_if_blocked(self, context="page"):
        if self.is_blocked():
            logger.warning("=" * 50)
            logger.warning(f"BLOCKED! ({context})")
            logger.warning("")
            logger.warning("Options:")
            logger.warning("1. Wait 30-60 seconds in the browser")
            logger.warning("2. Solve captcha if visible")
            logger.warning("3. Try refreshing (F5)")
            logger.warning("")
            logger.warning("Press Enter when page loads normally...")
            logger.warning("Or type 'skip' to skip, 'quit' to stop")
            logger.warning("=" * 50)
            
            response = input().strip().lower()
            if response == 'skip':
                return False
            elif response == 'quit':
                raise KeyboardInterrupt()
            
            time.sleep(2)
            if self.is_blocked():
                return self.wait_if_blocked(context)
        return True
    
    def save_debug(self, filename):
        path = Path('data/debug') / filename
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.driver.page_source)
        logger.info(f"Saved: {path}")
    
    def get_articles(self, volume: int, max_articles: int) -> List[ArticleInfo]:
        url = f"{self.BASE_URL}/journal/catena/vol/{volume}"
        logger.info(f"Opening volume page: {url}")
        
        self.driver.get(url)
        self.delay(4, 7)
        
        if not self.wait_if_blocked("volume page"):
            return []
        
        self.scroll()
        
        # Scroll to load all
        for _ in range(3):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)
        
        self.save_debug("volume_page.html")
        
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        articles = []
        seen = set()
        
        for link in soup.find_all('a', href=re.compile(r'/science/article/pii/')):
            href = link.get('href', '')
            title = link.get_text(strip=True)
            
            if len(title) < 10:
                continue
            
            full_url = self.BASE_URL + href if href.startswith('/') else href
            
            if full_url in seen:
                continue
            seen.add(full_url)
            
            articles.append(ArticleInfo(title=title[:200], url=full_url, volume=volume))
        
        logger.info(f"Found {len(articles)} articles")
        return articles[:max_articles]
    
    def get_details(self, article: ArticleInfo, num: int) -> ArticleInfo:
        logger.info(f"[{num}] {article.title[:50]}...")
        
        try:
            self.driver.get(article.url)
            self.delay(3, 6)
            
            if not self.wait_if_blocked(f"article {num}"):
                article.scrape_status = "skipped"
                return article
            
            self.scroll()
            
            # Scroll for lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            if num == 1:
                self.save_debug("first_article.html")
            
            if self.is_blocked():
                if not self.wait_if_blocked("article content"):
                    article.scrape_status = "blocked"
                    return article
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            text = soup.get_text()
            
            # Extract dates
            for pattern, field in [
                (r'Received\s+(\d{1,2}\s+\w+\s+\d{4})', 'received_date'),
                (r'Accepted\s+(\d{1,2}\s+\w+\s+\d{4})', 'accepted_date'),
            ]:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    setattr(article, field, match.group(1))
                    logger.info(f"  {field}: {match.group(1)}")
            
            # DOI
            doi_meta = soup.find('meta', {'name': 'citation_doi'})
            if doi_meta:
                article.doi = doi_meta.get('content')
            
            article.calculate_review_days()
            
            if article.received_date or article.accepted_date:
                article.scrape_status = "success"
                if article.review_days:
                    logger.info(f"  Review: {article.review_days} days")
            else:
                article.scrape_status = "no_dates"
                self.save_debug(f"no_dates_{num}.html")
            
            return article
            
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"Error: {e}")
            article.scrape_status = "error"
            return article
    
    def export(self):
        if not self.articles:
            return
        
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # CSV
        csv_file = Path('data') / f'catena_{ts}.csv'
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            fields = ['title', 'volume', 'received_date', 'accepted_date', 'review_days', 'doi', 'url', 'scrape_status']
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for a in self.articles:
                writer.writerow({k: getattr(a, k) for k in fields})
        logger.info(f"Saved: {csv_file}")
        
        # Excel
        xlsx_file = Path('data') / f'catena_{ts}.xlsx'
        wb = Workbook()
        ws = wb.active
        ws.append(['Title', 'Volume', 'Received', 'Accepted', 'Review Days', 'DOI', 'URL', 'Status'])
        
        for cell in ws[1]:
            cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
            cell.font = Font(bold=True, color='FFFFFF')
        
        for a in self.articles:
            ws.append([a.title, a.volume, a.received_date, a.accepted_date, a.review_days, a.doi, a.url, a.scrape_status])
        
        ws.column_dimensions['A'].width = 60
        ws.column_dimensions['G'].width = 50
        wb.save(xlsx_file)
        logger.info(f"Saved: {xlsx_file}")
        
        # Stats
        total = len(self.articles)
        success = sum(1 for a in self.articles if a.scrape_status == "success")
        with_dates = sum(1 for a in self.articles if a.review_days)
        
        logger.info(f"\n{'='*50}")
        logger.info(f"Total: {total}, Success: {success}, With dates: {with_dates}")
        if with_dates:
            times = [a.review_days for a in self.articles if a.review_days]
            logger.info(f"Average: {sum(times)/len(times):.1f} days")
        logger.info("=" * 50)
    
    def scrape(self, volume: int, max_articles: int):
        try:
            self.init_driver()
            
            # Visit homepage first
            logger.info("Visiting homepage...")
            self.driver.get(self.BASE_URL)
            self.delay(4, 7)
            self.wait_if_blocked("homepage")
            self.scroll()
            
            # Get articles
            articles = self.get_articles(volume, max_articles)
            
            if not articles:
                logger.error("No articles found")
                return
            
            # Get details
            for i, article in enumerate(articles, 1):
                try:
                    article = self.get_details(article, i)
                    self.articles.append(article)
                    self.delay(6, 12)  # Longer delay
                except KeyboardInterrupt:
                    logger.info("Interrupted")
                    break
            
            self.export()
            
        except KeyboardInterrupt:
            logger.info("Saving partial results...")
            self.export()
        finally:
            self.close_driver()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--volume', type=int, default=263)
    parser.add_argument('--max', type=int, default=10)
    
    args = parser.parse_args()
    if args.test:
        args.max = 5
    
    print("\n" + "=" * 50)
    print("CATENA Scraper - Local Driver")
    print("=" * 50)
    print("Uses existing ChromeDriver (no download)")
    print("=" * 50 + "\n")
    
    scraper = LocalDriverScraper()
    scraper.scrape(args.volume, args.max)


if __name__ == '__main__':
    main()