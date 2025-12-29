#!/bin/bash
# Quick run script for CATENA Scraper

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}CATENA Journal Scraper${NC}"
echo "========================"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Check if dependencies are installed
if ! pip show playwright > /dev/null 2>&1; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -r requirements.txt
    playwright install chromium
fi

# Run the scraper with provided arguments
echo -e "${GREEN}Starting scraper...${NC}"
python main.py "$@"

echo -e "${GREEN}Done!${NC}"
