# Waitrose Scraper

Web scraper for Waitrose grocery products, collecting product data suitable for NOVA classification analysis via the Open Food Facts API.

Scraped **6 food categories** from Waitrose (configurable via `max_categories`):

| Category | Slug |
|---|---|
| Fresh & Chilled | `fresh_and_chilled` |
| Bakery | `bakery` |
| Food Cupboard | `food_cupboard` |
| Frozen | `frozen` |
| Beer, Wine & Spirits | `beer_wine_and_spirits` |
| Tea, Coffee & Soft Drinks | `tea_coffee_and_soft_drinks` |

Total products scraped: ~4,000 across all categories.

## Quick Start

```bash
cd scraper/supermarkets/spiders
python waitrose_scraper.py
```

Output: `data/scraped/waitrose_products_TIMESTAMP.jsonl`

## Requirements

- Python 3.9+
- Chrome and ChromeDriver installed
- `selenium` (`pip install selenium`)

## How It Works

The scraper runs in two phases:

### Phase 1: Collect Product URLs

1. Navigates to the [Waitrose groceries page](https://www.waitrose.com/ecom/shop/browse/groceries)
2. Discovers food categories using an allowlist of known food category slugs
3. For each category, **recursively drills into subcategories** (e.g. Bakery → Bread → White Bread) until reaching leaf pages with actual product listings
4. Extracts product URLs from `article[data-testid="product-pod"]` elements
5. Deduplicates products by `product_id` across categories

### Phase 2: Enrich Products

1. Visits each product page individually
2. Extracts structured data from the embedded `<script id="__NEXT_DATA__">` JSON (not from HTML elements)
3. Writes each product to the JSONL file **immediately** with `flush()`, so partial results survive interruption
4. Parses data from `props.pageProps.product` in the JSON blob

### Why Subcategory Drilling?

Waitrose uses a hybrid page structure: some category pages (like Bakery) show a few featured products *and* subcategory navigation links, while others (like individual bread types) are flat product listings. The scraper always checks for subcategory links first and drills into them recursively. This avoids relying on the "Load more" button, which is blocked by anti-bot detection.

## Data Fields

Each product in the JSONL output contains:

| Field | Description | Example |
|---|---|---|
| `product_id` | Waitrose line number | `"058581"` |
| `name` | Product name | `"Waitrose White Sourdough"` |
| `brand` | Brand name | `"Waitrose"` |
| `price` | Display price | `"£2.20"` |
| `size` | Weight/quantity | `"400g"` |
| `url` | Product page URL | `"https://www.waitrose.com/..."` |
| `category` | Leaf subcategory slug | `"sourdough_bread"` |
| `barcode` | EAN barcode (for Open Food Facts matching) | `"5000169576458"` |
| `image_url` | Product image URL | `"https://..."` |
| `product_type` | Waitrose product type | `"Grocery"` |
| `scraped_at` | ISO timestamp | `"2026-02-14T18:12:30"` |

Fields like `ingredients`, `nutrition_info`, `description`, and `allergens` are intentionally excluded — Student B retrieves these from Open Food Facts during NOVA enrichment.

## Architecture Decisions

### Selenium over Scrapy

Waitrose uses JavaScript rendering via React. Product data is loaded dynamically and only accessible through the `__NEXT_DATA__` JSON blob embedded in the page after JavaScript execution. Scrapy cannot execute JavaScript, so Selenium is required.

### Data from `__NEXT_DATA__` JSON, not HTML

All product fields are extracted from the structured JSON in `<script id="__NEXT_DATA__">` rather than from rendered HTML elements. This is more reliable — HTML class names change frequently, but the API data structure is stable.

### JSONL Format

JSON Lines (one JSON object per line) rather than a JSON array:
- Each line is independently parseable — partial files from interrupted runs are still valid
- Supports incremental writing with `flush()` so no data is lost if the scraper is stopped
- Standard format for data pipelines and easy to load with `pandas.read_json(lines=True)`

### Allowlist for Food Categories

Categories are filtered using a hardcoded allowlist (`FOOD_CATEGORY_SLUGS`) rather than a blocklist. This prevents promotional pages (e.g. "New", "Everyday Value", "Valentine's Day") from being scraped.

### Duplicate Handling

Products are deduplicated by `product_id` using a set (`seen_product_ids`). A product appearing in multiple subcategories is only scraped once.

## Pre-scraped Data

Latest scrape available at: `data/scraped/waitrose_products_TIMESTAMP.jsonl`

## For Student B (API Developer)

### Loading the Data

```python
import pandas as pd
df = pd.read_json('data/scraped/waitrose_products_TIMESTAMP.jsonl', lines=True)
```

Or without pandas:

```python
import json
products = [json.loads(line) for line in open('data/scraped/waitrose_products_TIMESTAMP.jsonl')]
```

### NOVA Matching Strategy

Use the `barcode` field for exact matching with Open Food Facts:

```python
import requests

def get_nova(barcode):
    r = requests.get(f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json")
    if r.ok:
        return r.json().get('product', {}).get('nova_group')
```

For products without barcodes, fall back to fuzzy matching on `name` + `brand`.

### Required API Endpoints

- `GET /products` — all products
- `GET /products/{id}` — single product with NOVA classification
- `GET /products?nova_group=4` — filter by NOVA group

Save enriched data to `data/enriched/`.

## Performance

- Phase 1 (URL collection): ~15–20 minutes across all categories
- Phase 2 (detail enrichment): ~2–3 hours (~4,000 products × 2–3s each)
- Output is saved incrementally, so the scraper can be safely interrupted

## Troubleshooting

| Problem | Solution |
|---|---|
| No data scraped | Ensure Chrome + ChromeDriver are installed. Run with `headless=False` to debug visually. |
| Missing subcategories | Check that subcategory links exist on the page. The scraper derives names from URL slugs when link text is hidden in nav menus. |
| Missing barcodes | Some products (especially loose fruit/veg) don't have barcodes in Waitrose's system. Use name+brand matching as a fallback. |