#!/usr/bin/env python3
"""
CATENA Journal Article Scraper

Scrapes article submission and acceptance dates from CATENA journal on ScienceDirect,
calculates review time intervals, and exports data to CSV/Excel/JSON.

Usage:
    python main.py                    # Full scrape
    python main.py --test             # Test with 10 articles
    python main.py --volumes 260-263  # Scrape specific volume range
    python main.py --years 2024-2025  # Scrape specific year range
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.scraper import CatenaScraper
from src.exporter import DataExporter
from config import settings


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration"""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Reduce noise from external libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('playwright').setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)


def parse_range(range_str: str) -> tuple:
    """Parse range string like '260-263' to tuple (260, 263)"""
    if '-' in range_str:
        parts = range_str.split('-')
        return (int(parts[0]), int(parts[1]))
    else:
        val = int(range_str)
        return (val, val)


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Scrape CATENA journal articles from ScienceDirect',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                      # Scrape all articles
  python main.py --test               # Test mode (10 articles)
  python main.py --max 100            # Scrape max 100 articles
  python main.py --volumes 260-263    # Only volumes 260-263
  python main.py --years 2024-2025    # Only years 2024-2025
  python main.py --headless false     # Show browser window
        """
    )
    
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Test mode: scrape only 10 articles'
    )
    
    parser.add_argument(
        '--max', '-m',
        type=int,
        default=None,
        help='Maximum number of articles to scrape'
    )
    
    parser.add_argument(
        '--volumes', '-v',
        type=str,
        default=None,
        help='Volume range to scrape (e.g., "260-263" or "263")'
    )
    
    parser.add_argument(
        '--years', '-y',
        type=str,
        default=None,
        help='Year range to scrape (e.g., "2024-2025" or "2025")'
    )
    
    parser.add_argument(
        '--headless',
        type=str,
        choices=['true', 'false'],
        default='true',
        help='Run browser in headless mode (default: true)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='data',
        help='Output directory (default: data)'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--format', '-f',
        type=str,
        choices=['all', 'csv', 'json', 'excel'],
        default='all',
        help='Output format (default: all)'
    )
    
    return parser.parse_args()


async def run_scraper(args):
    """Run the scraper with given arguments"""
    logger = logging.getLogger(__name__)
    
    # Apply settings from arguments
    if args.test:
        settings.MAX_ARTICLES = 10
        logger.info("Test mode: limiting to 10 articles")
    elif args.max:
        settings.MAX_ARTICLES = args.max
        logger.info(f"Limiting to {args.max} articles")
    
    if args.volumes:
        settings.VOLUME_RANGE = parse_range(args.volumes)
        logger.info(f"Volume range: {settings.VOLUME_RANGE}")
    
    if args.years:
        settings.YEAR_RANGE = parse_range(args.years)
        logger.info(f"Year range: {settings.YEAR_RANGE}")
    
    settings.HEADLESS = args.headless.lower() == 'true'
    settings.OUTPUT_DIR = args.output
    
    # Run scraper
    logger.info("=" * 60)
    logger.info("CATENA Journal Scraper")
    logger.info("=" * 60)
    logger.info(f"Target: {settings.JOURNAL_URL}")
    logger.info(f"Output directory: {settings.OUTPUT_DIR}")
    logger.info("=" * 60)
    
    scraper = CatenaScraper()
    
    try:
        articles = await scraper.scrape_all()
        
        if not articles:
            logger.warning("No articles scraped")
            return
        
        # Print statistics
        stats = scraper.get_statistics()
        logger.info("\n" + "=" * 60)
        logger.info("SCRAPING STATISTICS")
        logger.info("=" * 60)
        for key, value in stats.items():
            if isinstance(value, float):
                logger.info(f"  {key}: {value:.1f}")
            else:
                logger.info(f"  {key}: {value}")
        
        # Export data
        logger.info("\n" + "=" * 60)
        logger.info("EXPORTING DATA")
        logger.info("=" * 60)
        
        exporter = DataExporter(articles, args.output)
        
        if args.format == 'all':
            files = exporter.export_all()
            for fmt, path in files.items():
                logger.info(f"  {fmt.upper()}: {path}")
        elif args.format == 'csv':
            logger.info(f"  CSV: {exporter.export_csv()}")
        elif args.format == 'json':
            logger.info(f"  JSON: {exporter.export_json()}")
        elif args.format == 'excel':
            logger.info(f"  Excel: {exporter.export_excel()}")
        
        logger.info("\n" + "=" * 60)
        logger.info("SCRAPING COMPLETE")
        logger.info("=" * 60)
        
    except KeyboardInterrupt:
        logger.info("\nScraping interrupted by user")
    except Exception as e:
        logger.exception(f"Scraping failed: {e}")
        raise


def main():
    """Main entry point"""
    args = parse_args()
    logger = setup_logging(args.log_level)
    
    try:
        asyncio.run(run_scraper(args))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
