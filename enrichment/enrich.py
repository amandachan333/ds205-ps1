"""Pre-enrich scraped Waitrose products with NOVA data from Open Food Facts.

Run this once before starting the API server:
    python enrich.py

Reads:  data/scraped/waitrose_products_*.jsonl  (most recent file)
Writes: data/enriched/enriched_products.jsonl
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

OFF_URL = "https://world.openfoodfacts.org/api/v2/product"
OFF_FIELDS = "product_name,nova_group,nova_groups_tags,ingredients_text,nutriments"
HEADERS = {"User-Agent": "DS205-Waitrose-NOVA-Enricher/1.0 (academic project)"}

SCRAPED_DIR = Path(__file__).parent.parent / "data" / "scraped"
ENRICHED_DIR = Path(__file__).parent.parent / "data" / "enriched"


def load_scraped_products() -> list[dict]:
    """Load products from the most recent JSONL file in data/scraped/."""
    files = sorted(SCRAPED_DIR.glob("waitrose_products_*.jsonl"))
    if not files:
        raise FileNotFoundError(f"No scraped JSONL files found in {SCRAPED_DIR}")
    latest = files[-1]
    print(f"Loading from: {latest}")
    products = [json.loads(line) for line in latest.read_text().splitlines() if line.strip()]
    print(f"Loaded {len(products)} products")
    return products


def query_off(barcode: str) -> dict | None:
    """Query Open Food Facts for a single barcode. Returns NOVA data or None."""
    try:
        r = httpx.get(
            f"{OFF_URL}/{barcode}.json",
            params={"fields": OFF_FIELDS},
            headers=HEADERS,
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("status") != 1:
            return None
        p = data.get("product", {})
        return {
            "off_name": p.get("product_name"),
            "nova_group": p.get("nova_group"),
            "nova_tags": p.get("nova_groups_tags"),
            "ingredients_text": p.get("ingredients_text"),
        }
    except (httpx.RequestError, json.JSONDecodeError):
        return None


def enrich_all(products: list[dict]) -> list[dict]:
    """Enrich each product with NOVA data from Open Food Facts."""
    enriched = []
    matched = 0

    for idx, product in enumerate(products, 1):
        barcode = product.get("barcode")
        nova_data = None

        if barcode:
            nova_data = query_off(barcode)
            time.sleep(0.5)  # respect rate limits

        enriched_product = {
            **product,
            "nova_group": nova_data["nova_group"] if nova_data else None,
            "nova_tags": nova_data["nova_tags"] if nova_data else None,
            "off_name": nova_data["off_name"] if nova_data else None,
            "ingredients_text": nova_data["ingredients_text"] if nova_data else None,
            "off_matched": nova_data is not None,
        }
        enriched.append(enriched_product)

        if nova_data:
            matched += 1

        if idx % 50 == 0 or idx == len(products):
            print(f"  {idx}/{len(products)} | Matched: {matched}")

    return enriched


def save_enriched(products: list[dict]) -> Path:
    """Save enriched products to data/enriched/ as JSONL."""
    ENRICHED_DIR.mkdir(parents=True, exist_ok=True)
    filepath = ENRICHED_DIR / "enriched_products.jsonl"

    with open(filepath, "w", encoding="utf-8") as f:
        for p in products:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"\nSaved {len(products)} enriched products to: {filepath}")

    # Summary
    total = len(products)
    with_nova = sum(1 for p in products if p.get("nova_group"))
    matched = sum(1 for p in products if p.get("off_matched"))
    print(f"  OFF matched:  {matched}/{total}")
    print(f"  With NOVA:    {with_nova}/{total}")
    for group in range(1, 5):
        count = sum(1 for p in products if p.get("nova_group") == group)
        print(f"    NOVA {group}: {count}")

    return filepath


def main():
    print("=" * 60)
    print("NOVA Enrichment via Open Food Facts")
    print("=" * 60 + "\n")

    products = load_scraped_products()
    enriched = enrich_all(products)
    save_enriched(enriched)


if __name__ == "__main__":
    main()