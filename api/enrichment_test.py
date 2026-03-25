"""
OpenFoodFacts Enrichment Script - TEST VERSION

Tests enrichment on first 20 products only.
Use this to verify the enrichment logic before running the full script.

Usage:
    python api/enrichment_test.py

Output:
    data/enriched/products_enriched_test.jsonl
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

# File paths
SCRAPED_DATA = Path("data/scraped/waitrose_products_20260215_023602.jsonl")
ENRICHED_OUTPUT = Path("data/enriched/products_enriched_test.jsonl")

# OpenFoodFacts API configuration
OFF_API_BASE = "https://world.openfoodfacts.org/api/v2/product"
REQUEST_DELAY = 0.5  # seconds between requests (be respectful)

# TEST MODE: Only process first N products
TEST_LIMIT = 20

# NOVA group names for enrichment
NOVA_NAMES = {
    1: "Unprocessed or minimally processed",
    2: "Processed culinary ingredients",
    3: "Processed foods",
    4: "Ultra-processed foods"
}


def get_nova_classification(barcode: str) -> Optional[int]:
    """
    Query OpenFoodFacts API for NOVA classification by barcode.

    Args:
        barcode: Product EAN barcode

    Returns:
        NOVA group (1-4) if found, None if product not in OpenFoodFacts
    """
    url = f"{OFF_API_BASE}/{barcode}"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()

            # Check if product was found
            if data.get("status") == 1:
                product = data.get("product", {})
                nova_group = product.get("nova_group")

                # Validate NOVA group is in valid range
                if nova_group and 1 <= nova_group <= 4:
                    return nova_group

        return None

    except requests.exceptions.RequestException as e:
        print(f"  [WARNING] Error fetching {barcode}: {e}")
        return None


def enrich_products():
    """
    Main enrichment process (TEST MODE - first 20 products only).

    Reads scraped products, queries OpenFoodFacts for NOVA classification,
    and saves enriched data to JSONL file.
    """
    # Ensure output directory exists
    ENRICHED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Load scraped products
    print(f"Loading scraped data from {SCRAPED_DATA}...")
    df = pd.read_json(SCRAPED_DATA, lines=True)

    # TEST MODE: Take only first 20 products
    df = df.head(TEST_LIMIT)
    products = df.to_dict(orient="records")
    total = len(products)

    print(f"[OK] Loaded {total} products (TEST MODE - limited to {TEST_LIMIT})\n")

    # Statistics tracking
    stats = {
        "matched": 0,
        "not_found": 0,
        "nova_counts": {1: 0, 2: 0, 3: 0, 4: 0}
    }

    # Open output file for writing (append mode with flush)
    enriched_count = 0
    start_time = time.time()

    with open(ENRICHED_OUTPUT, "w", encoding="utf-8") as f:
        for idx, product in enumerate(products, 1):
            barcode = product.get("barcode", "")
            product_id = product.get("product_id", "unknown")
            name = product.get("name", "Unknown Product")

            # Show each product in test mode
            print(f"[{idx}/{total}] Processing: {name[:50]}...")
            print(f"  Product ID: {product_id}")
            print(f"  Barcode: {barcode}")

            # Query OpenFoodFacts API
            nova_group = None
            off_matched = False

            if barcode:
                nova_group = get_nova_classification(barcode)

                if nova_group:
                    stats["matched"] += 1
                    stats["nova_counts"][nova_group] += 1
                    off_matched = True
                    print(f"  [OK] NOVA Group: {nova_group} ({NOVA_NAMES[nova_group]})")
                else:
                    stats["not_found"] += 1
                    print(f"  [NOT FOUND] Not found in OpenFoodFacts")

                # Respectful delay between requests
                time.sleep(REQUEST_DELAY)
            else:
                # No barcode available
                stats["not_found"] += 1
                print(f"  [WARNING] No barcode available")

            print()  # Blank line for readability

            # Enrich product with NOVA data
            enriched_product = {
                **product,
                "nova_group": nova_group,
                "nova_group_name": NOVA_NAMES.get(nova_group) if nova_group else None,
                "off_matched": off_matched,
                "enriched_at": datetime.now().isoformat()
            }

            # Convert any datetime objects to strings for JSON serialization
            if "scraped_at" in enriched_product and hasattr(enriched_product["scraped_at"], "isoformat"):
                enriched_product["scraped_at"] = enriched_product["scraped_at"].isoformat()

            # Write to file immediately (flush to disk)
            f.write(json.dumps(enriched_product) + "\n")
            f.flush()
            enriched_count += 1

    # Final statistics
    elapsed_time = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"[SUCCESS] Test enrichment complete!")
    print(f"{'='*60}")
    print(f"Total products processed: {total}")
    print(f"Matched with OpenFoodFacts: {stats['matched']} ({stats['matched']/total*100:.1f}%)")
    print(f"Not found in OpenFoodFacts: {stats['not_found']} ({stats['not_found']/total*100:.1f}%)")
    print(f"\nNOVA Classification Distribution:")
    for group in [1, 2, 3, 4]:
        count = stats['nova_counts'][group]
        pct = count / stats['matched'] * 100 if stats['matched'] > 0 else 0
        print(f"  Group {group} ({NOVA_NAMES[group]}): {count} ({pct:.1f}%)")

    # Calculate UPF proportion (answers the PS1 driving question!)
    if stats['matched'] > 0:
        upf_count = stats['nova_counts'][4]
        upf_proportion = upf_count / stats['matched']
        print(f"\n[RESULT] Ultra-Processed Foods (UPF) Proportion: {upf_proportion:.1%}")

    print(f"\nTime elapsed: {elapsed_time:.1f} seconds")
    print(f"Output saved to: {ENRICHED_OUTPUT}")

    print(f"\nNext steps:")
    print(f"   1. Inspect the test output: {ENRICHED_OUTPUT}")
    print(f"   2. If everything looks good, run: python api/enrichment.py")
    print(f"   3. Full enrichment will take ~30-40 minutes for all products")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("TEST MODE: OpenFoodFacts Enrichment Script")
    print("="*60 + "\n")

    # Check if scraped data exists
    if not SCRAPED_DATA.exists():
        print(f"[ERROR] Scraped data not found at {SCRAPED_DATA}")
        print("Please run the scraper first (Part A)")
        exit(1)

    # Run enrichment
    enrich_products()
