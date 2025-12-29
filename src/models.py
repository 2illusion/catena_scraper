"""
Data models for CATENA scraper
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Optional, List
import json


@dataclass
class ArticleInfo:
    """Represents a single article's information"""
    
    # Basic info
    title: str
    url: str
    doi: Optional[str] = None
    article_id: Optional[str] = None
    
    # Volume/Issue info
    volume: Optional[int] = None
    issue: Optional[str] = None
    year: Optional[int] = None
    
    # Authors
    authors: List[str] = field(default_factory=list)
    
    # Dates (as strings initially)
    received_date: Optional[str] = None
    revised_date: Optional[str] = None
    accepted_date: Optional[str] = None
    available_online_date: Optional[str] = None
    version_of_record_date: Optional[str] = None
    
    # Parsed dates
    received_datetime: Optional[date] = None
    accepted_datetime: Optional[date] = None
    
    # Calculated metrics
    review_days: Optional[int] = None  # Days from received to accepted
    
    # Scraping metadata
    scraped_at: Optional[str] = None
    scrape_status: str = "pending"  # pending, success, failed
    error_message: Optional[str] = None
    
    def parse_dates(self):
        """Parse date strings to date objects and calculate review time"""
        from dateutil import parser
        
        try:
            if self.received_date:
                self.received_datetime = parser.parse(self.received_date).date()
            if self.accepted_date:
                self.accepted_datetime = parser.parse(self.accepted_date).date()
            
            # Calculate review days
            if self.received_datetime and self.accepted_datetime:
                delta = self.accepted_datetime - self.received_datetime
                self.review_days = delta.days
        except Exception as e:
            self.error_message = f"Date parsing error: {str(e)}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for export"""
        d = asdict(self)
        # Convert date objects to strings for JSON serialization
        if d.get('received_datetime'):
            d['received_datetime'] = d['received_datetime'].isoformat()
        if d.get('accepted_datetime'):
            d['accepted_datetime'] = d['accepted_datetime'].isoformat()
        return d
    
    def to_csv_row(self) -> dict:
        """Get flattened dict for CSV export"""
        return {
            'title': self.title,
            'url': self.url,
            'doi': self.doi,
            'article_id': self.article_id,
            'volume': self.volume,
            'issue': self.issue,
            'year': self.year,
            'authors': '; '.join(self.authors) if self.authors else '',
            'received_date': self.received_date,
            'revised_date': self.revised_date,
            'accepted_date': self.accepted_date,
            'available_online_date': self.available_online_date,
            'version_of_record_date': self.version_of_record_date,
            'review_days': self.review_days,
            'scraped_at': self.scraped_at,
            'scrape_status': self.scrape_status,
            'error_message': self.error_message,
        }


@dataclass
class VolumeInfo:
    """Represents a journal volume"""
    volume_number: int
    year: int
    issue: Optional[str] = None
    url: str = ""
    article_count: int = 0
    articles: List[ArticleInfo] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d['articles'] = [a.to_dict() for a in self.articles]
        return d


@dataclass 
class ScrapingProgress:
    """Track scraping progress for resume capability"""
    total_volumes: int = 0
    scraped_volumes: int = 0
    total_articles: int = 0
    scraped_articles: int = 0
    failed_articles: int = 0
    last_volume: Optional[int] = None
    last_article_url: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def save(self, filepath: str):
        """Save progress to file"""
        self.updated_at = datetime.now().isoformat()
        with open(filepath, 'w') as f:
            json.dump(asdict(self), f, indent=2)
    
    @classmethod
    def load(cls, filepath: str) -> 'ScrapingProgress':
        """Load progress from file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            return cls(**data)
        except FileNotFoundError:
            return cls()
