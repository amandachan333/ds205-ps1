# Waitrose Product API

FastAPI application serving Waitrose products enriched with NOVA classifications from OpenFoodFacts.

## Quick Start

**1. Activate environment:**
```bash
conda activate food
```

**2. Run enrichment (one-time setup):**

On Linux/macOS (including Nuvolos), make the pipeline script executable first:
```bash
chmod +x run_pipeline.py
```

Then run enrichment:
```bash
# Linux/macOS — enrich all products (~90 minutes)
./run_pipeline.py enrich

# Skip products already enriched from a previous run
./run_pipeline.py enrich --only-new

# Windows
python run_pipeline.py enrich
```
Output: `data/enriched/products_enriched.jsonl`

**3. Start API server:**
```bash
# Linux/macOS
./run_pipeline.py serve

# Windows
python run_pipeline.py serve
```

- **Local**: Access interactive docs and example responses at **http://localhost:8000/docs**
- **Nuvolos**: Access via your port forwarding URL, e.g. `https://<your-nuvolos-id>.app.az.nuvolos.cloud/proxy/8000/docs`

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /products` | List all products; filter by `nova_group` (1-4) or `category` slug (e.g. `bakery`); paginate with `limit` and `offset` |
| `GET /products/{id}` | Get a single product by Waitrose product ID (404 if not found) |
| `GET /stats` | NOVA classification counts, enrichment rate, and UPF proportion |

## Running Tests

5 pytest tests cover the core API behaviour (product listing, filtering, single product lookup, 404 handling, and stats shape).

From the project root:
```bash
PYTHONPATH=. pytest api/test_api.py -v
```

All tests use FastAPI's `TestClient` and run against the enriched data loaded at startup — no server needs to be running.

## Architecture Decisions

**Why pre-enrichment?** OpenFoodFacts is slow (~1s/request). Enrichment runs once; the API serves from local data.

**Matching strategy:** Three-step fallback to maximise match rate while minimising API calls:
1. **Barcode lookup** — exact match against OpenFoodFacts by EAN barcode; most reliable
2. **Local fuzzy match** — compares product name against products already classified in the same run; free, no API call
3. **Name search** — queries OpenFoodFacts search endpoint as a last resort; slowest and least precise

Products with no match have `nova_group: null` and `off_matched: false` in the response. Achieved ~96% match rate across 4,028 products.

**Data format:** JSONL (newline-delimited JSON) — consistent with the scraper output and easy to read incrementally.
