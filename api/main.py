import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from api.models import WaitroseProduct

# Load enriched data at startup (not on every request)
DATA_FILE = Path("data/enriched/products_enriched.jsonl")

products: list[dict] = []

if DATA_FILE.exists():
    decoder = json.JSONDecoder()
    products = [decoder.raw_decode(line.strip())[0] for line in DATA_FILE.read_text(encoding="utf-8-sig").splitlines() if line.strip().startswith("{")]
    print(f"[OK] Loaded {len(products)} enriched products")
else:
    print(f"[WARNING] No enriched data found. Run enrichment script first.")

# Create FastAPI app with metadata
app = FastAPI(
    title="Waitrose Product API",
    description="Waitrose products enriched with NOVA classifications from OpenFoodFacts.",
    version="0.1.0",
)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get(
    "/products",
    summary="Browse and filter products",
    response_model=list[WaitroseProduct],
    tags=["Products"]
)
def get_products(
    nova_group: int | None = Query(
        default=None, ge=1, le=4, description="Filter by NOVA group (1-4)"
    ),
    category: str | None = Query(
        default=None, description="Filter by Waitrose category slug"
    ),
    limit: int | None = Query(
        default=None, ge=1, description="Max results to return (omit for all)"
    ),
    offset: int = Query(
        default=0, ge=0, description="Number of results to skip"
    ),
) -> list[WaitroseProduct]:
    results = products

    # Apply filters
    if nova_group is not None:
        results = [p for p in results if p.get("nova_group") == nova_group]
    if category:
        results = [p for p in results if p.get("category") == category]

    # Apply pagination
    page = results[offset:] if limit is None else results[offset : offset + limit]
    return [WaitroseProduct(**p) for p in page]


@app.get(
    "/products/{product_id}",
    summary="Get a single product by ID",
    response_model=WaitroseProduct,
    tags=["Products"]
)
def get_product(product_id: str) -> WaitroseProduct:
    matched = [p for p in products if str(p["product_id"]) == product_id]
    if not matched:
        raise HTTPException(status_code=404, detail="Product not found")
    return WaitroseProduct(**matched[0])


@app.get(
    "/stats",
    summary="Summary statistics on NOVA classification coverage",
    tags=["Statistics"]
)
def get_stats() -> dict:
    total = len(products)
    nova_counts = {1: 0, 2: 0, 3: 0, 4: 0, "unknown": 0}

    for p in products:
        group = p.get("nova_group")
        if group in [1, 2, 3, 4]:
            nova_counts[group] += 1
        else:
            nova_counts["unknown"] += 1

    matched_total = total - nova_counts["unknown"]

    return {
        "total_products": total,
        "nova_counts": nova_counts,
        "matched_products": matched_total,
        "enrichment_rate": round(matched_total / total, 3) if total > 0 else 0,
        "upf_proportion": round(nova_counts[4] / matched_total, 3) if matched_total > 0 else 0,
    }
