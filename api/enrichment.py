import json
import time
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path

import click
import requests

# File paths
SCRAPED_DATA = Path("data/scraped/waitrose_products_20260215_023602.jsonl")
ENRICHED_OUTPUT = Path("data/enriched/products_enriched.jsonl")

# OpenFoodFacts API configuration
OFF_API_BASE = "https://world.openfoodfacts.org/api/v2/product"
OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
REQUEST_DELAY = 1.0  # seconds between requests (be respectful)

def _load_products(path: Path) -> list[dict]:
    """Load a JSON array or JSONL file, ignoring trailing characters on each line."""
    text = path.read_text(encoding="utf-8-sig").strip()
    if text.startswith("["):
        return json.loads(text)
    decoder = json.JSONDecoder()
    return [decoder.raw_decode(line.strip())[0] for line in text.splitlines() if line.strip().startswith("{")]


# NOVA group names for enrichment
NOVA_NAMES = {
    1: "Unprocessed or minimally processed",
    2: "Processed culinary ingredients",
    3: "Processed foods",
    4: "Ultra-processed foods"
}


def get_nova_classification(barcode: str) -> int | None:
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


def fuzzy_match_local(name: str, local_cache: dict, cutoff: float = 0.5) -> int | None:
    """
    Fuzzy match product name against locally classified products.
    Returns the NOVA group of the closest matching product, or None.
    """
    matches = get_close_matches(name, local_cache.keys(), n=1, cutoff=cutoff)
    return local_cache[matches[0]] if matches else None


def search_nova_by_name(name: str, cache: dict) -> int | None:
    """
    Search OpenFoodFacts by product name, with caching to avoid duplicate requests.

    Returns:
        NOVA group (1-4) if a match is found, None otherwise
    """
    if name in cache:
        return cache[name]

    try:
        response = requests.get(
            OFF_SEARCH_URL,
            params={"search_terms": name, "search_simple": 1, "json": 1, "fields": "nova_group", "page_size": 1},
            timeout=5
        )
        if response.status_code == 200:
            products = response.json().get("products", [])
            if products:
                nova_group = products[0].get("nova_group")
                if nova_group and 1 <= int(nova_group) <= 4:
                    cache[name] = int(nova_group)
                    return int(nova_group)
    except requests.exceptions.RequestException as e:
        print(f"  [WARNING] Name search error for '{name}': {e}")

    cache[name] = None
    return None


def enrich_products(only_new: bool = False):
    """
    Main enrichment process.

    Reads scraped products, queries OpenFoodFacts for NOVA classification,
    and saves enriched data to JSONL file.
    """
    # Ensure output directory exists
    ENRICHED_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Load scraped products
    print(f"Loading scraped data from {SCRAPED_DATA}...")
    products = _load_products(SCRAPED_DATA)
    total = len(products)
    print(f"[OK] Loaded {total} products")

    # Skip already-enriched products if --only-new
    already_done: set = set()
    if only_new and ENRICHED_OUTPUT.exists():
        existing = _load_products(ENRICHED_OUTPUT)
        already_done = set(str(p["product_id"]) for p in existing)
        print(f"[SKIP] {len(already_done)} products already enriched")
        products = [p for p in products if str(p.get("product_id", "")) not in already_done]
        print(f"[OK] {len(products)} products remaining\n")
    else:
        print()

    # Statistics tracking
    stats = {
        "matched_barcode": 0,
        "matched_local": 0,
        "matched_name": 0,
        "not_found": 0,
        "nova_counts": {1: 0, 2: 0, 3: 0, 4: 0}
    }

    # Local cache of already-classified products for fuzzy matching
    local_nova_cache: dict = {}
    # Cache for OpenFoodFacts name searches to avoid duplicate API calls
    name_cache: dict = {}

    # Open output file for writing (append mode with flush)
    enriched_count = 0
    start_time = time.time()

    file_mode = "a" if only_new and ENRICHED_OUTPUT.exists() else "w"
    with open(ENRICHED_OUTPUT, file_mode, encoding="utf-8") as f:
        for idx, product in enumerate(products, 1):
            barcode = product.get("barcode", "")
            product_id = product.get("product_id", "unknown")
            name = product.get("name", "Unknown Product")

            # Progress indicator every 100 products
            if idx % 100 == 0:
                elapsed = time.time() - start_time
                rate = idx / elapsed
                remaining = (total - idx) / rate if rate > 0 else 0
                matched = stats["matched_barcode"] + stats["matched_local"] + stats["matched_name"]
                print(f"Progress: {idx}/{total} ({idx/total*100:.1f}%) | "
                      f"Matched: {matched} | "
                      f"ETA: {remaining/60:.1f} min")

            # 1. Try barcode lookup
            nova_group = get_nova_classification(barcode) if barcode else None
            if barcode:
                time.sleep(REQUEST_DELAY)

            if nova_group:
                stats["matched_barcode"] += 1
            else:
                # 2. Fuzzy match against our own already-classified products
                nova_group = fuzzy_match_local(name, local_nova_cache)
                if nova_group:
                    stats["matched_local"] += 1
                else:
                    # 3. Fallback: OpenFoodFacts name search
                    nova_group = search_nova_by_name(name, name_cache)
                    if nova_group:
                        stats["matched_name"] += 1
                        time.sleep(REQUEST_DELAY)
                    else:
                        stats["not_found"] += 1

            if nova_group:
                stats["nova_counts"][nova_group] += 1
                local_nova_cache[name] = nova_group  # add to local cache for future matches

            off_matched = nova_group is not None

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
    print(f"[SUCCESS] Enrichment complete!")
    print(f"{'='*60}")
    matched = stats["matched_barcode"] + stats["matched_local"] + stats["matched_name"]
    print(f"Total products processed: {total}")
    print(f"Matched with OpenFoodFacts: {matched} ({matched/total*100:.1f}%)")
    print(f"  - by barcode: {stats['matched_barcode']}")
    print(f"  - by local fuzzy match: {stats['matched_local']}")
    print(f"  - by name search: {stats['matched_name']}")
    print(f"Not found in OpenFoodFacts: {stats['not_found']} ({stats['not_found']/total*100:.1f}%)")
    print(f"\nNOVA Classification Distribution:")
    for group in [1, 2, 3, 4]:
        count = stats['nova_counts'][group]
        pct = count / matched * 100 if matched > 0 else 0
        print(f"  Group {group} ({NOVA_NAMES[group]}): {count} ({pct:.1f}%)")

    # Calculate UPF proportion (answers the PS1 driving question!)
    if matched > 0:
        upf_count = stats['nova_counts'][4]
        upf_proportion = upf_count / matched
        print(f"\n[RESULT] Ultra-Processed Foods (UPF) Proportion: {upf_proportion:.1%}")

    print(f"\nTime elapsed: {elapsed_time/60:.1f} minutes")
    print(f"Output saved to: {ENRICHED_OUTPUT}")
    print(f"{'='*60}\n")


@click.command()
@click.option("--only-new/--all", default=False, help="Skip already-enriched products")
def main(only_new: bool):
    """Match scraped products against OpenFoodFacts and save to data/enriched/."""
    print("\n" + "="*60)
    print("OpenFoodFacts Enrichment Script")
    print("="*60 + "\n")

    if not SCRAPED_DATA.exists():
        print(f"[ERROR] Scraped data not found at {SCRAPED_DATA}")
        exit(1)

    enrich_products(only_new=only_new)


if __name__ == "__main__":
    main()
