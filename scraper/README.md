# Waitrose Scraper

Web scraper for Waitrose products, extracting product data including barcodes, ingredients, and nutritional information for NOVA classification analysis.

Scraped **two food categories** from Waitrose:
1. **Bakery** - Bread, cakes, pastries, etc.
2. **Fresh & Chilled** - Fresh produce, dairy, etc.

Total products: ~1108 

## Quick Start

```bash
cd scraper/supermarkets/spiders
python waitrose_scraper.py
```

**Output:** `data/scraped/waitrose_final_scraped_TIMESTAMP.jsonl`

## Requirements

```bash
pip install selenium --break-system-packages
```

Chrome and ChromeDriver must be installed.

## How It Works

1. Loads Waitrose bakery page
2. Clicks "Load more" to reveal all products
3. Collects product URLs from listing
4. Visits each product page
5. Extracts data from embedded JSON (`__NEXT_DATA__`)
6. Saves as JSONL (one product per line)

## Data Fields

Each product contains:
- `product_id`: Waitrose product ID
- `name`: Product name
- `barcode`: EAN barcode for Open Food Facts matching
- `price`: Display price
- `size`: Product weight/quantity
- `brand`: Brand name
- `ingredients`: Full ingredients list
- `nutrition_info`: Nutritional values per 100g
- `allergens`: Allergen information
- `category`: Product category
- `url`: Product page URL
- `image_url`: Product image

## Architecture Decisions

### Selenium vs Scrapy

**Decision:** Selenium required.

**Reason:** Waitrose uses JavaScript rendering. Product data is not in static HTML - it's loaded dynamically via React. Verified by viewing page source vs DevTools inspection.

### Barcode Extraction

Barcodes are embedded in `<script id="__NEXT_DATA__">` JSON data, not visible in HTML. Parser extracts from `props.pageProps.product.barCodes` field.

### JSONL Format

Using JSON Lines instead of JSON array for:
- Streaming compatibility
- Easier appending
- Better handling of large datasets
- Standard format for data pipelines

## Pre-scraped Data

Latest scrape: `data/scraped/waitrose_bakery_TIMESTAMP.jsonl`

[OneDrive link to be added if file too large for GitHub]

## For Student B (API Developer)

### Loading the Data

```python
import json

products = []
with open('data/scraped/waitrose_bakery_TIMESTAMP.jsonl', 'r') as f:
    for line in f:
        products.append(json.loads(line))
```

Or with pandas:
```python
import pandas as pd
df = pd.read_json('data/scraped/waitrose_bakery_TIMESTAMP.jsonl', lines=True)
```

### NOVA Matching Strategy

Use `barcode` field for exact matching with Open Food Facts:

```python
import requests

def get_nova_classification(barcode):
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('product', {}).get('nova_group')
    return None
```

Fallback for products without barcodes: use `name` + `brand` for fuzzy matching.

### Required API Endpoints

- `GET /products` - Return all products
- `GET /products/{id}` - Single product with NOVA classification
- `GET /products?nova_group=4` - Filter by NOVA group

Save enriched data to `data/enriched/`

## Performance

- URL collection: ~5 minutes
- Detail scraping: ~30-60 minutes (1108 products Ã 2-3s each)
- Total runtime: ~45-60 minutes

## Troubleshooting

**No data scraped:**
- Ensure Chrome and ChromeDriver are installed
- Check `data/scraped/` directory exists
- Run with `headless=False` to debug visually

**"Load more" not working:**
- Site may block automated clicks
- Scraper will collect at least 50 products from initial load
- Consider scraping subcategories individually

**Missing barcodes/ingredients:**
- Some products may not have complete data in Waitrose system
- Check data quality stats in terminal output after scraping