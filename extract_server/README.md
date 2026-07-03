# Grocery price extraction server

HTTP service that accepts grocery shelf photos and extracts product names, prices, and metadata using the **Cursor SDK** vision agent.

## Architecture

```
Upload (HEIC/JPG)
  → exiftool (GPS, capture time)
  → Cursor SDK Agent.prompt + SDKImage (vision extraction)
  → JSON product list
```

Shared logic lives in `../grocery_extract/`:

| Module | Role |
|--------|------|
| `prompt.py` | Saved extraction prompt (same rules as manual agent workflow) |
| `cursor_extractor.py` | Cursor SDK vision call |
| `parse_response.py` | Parse and sanitize model JSON |
| `exif.py` | EXIF via exiftool, HEIC→JPG via sips |
| `scoring.py` | Benchmark metrics vs ground truth |
| `pipeline.py` | End-to-end upload pipeline |

Ground truth for benchmarks lives in `extract_server/tests/fixtures/ground_truth_products.json`.

## Setup

```bash
cd extract_server
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env   # then set CURSOR_API_KEY (and optional GROCERY_AUTH_PASSWORD)
```

Requires `exiftool` and `sips` (macOS) on PATH. The server loads `extract_server/.env` on startup.

## Run server

```bash
cd extract_server
PYTHONPATH=.. .venv/bin/python server.py
```

Server listens on http://127.0.0.1:8765

### API

**GET /health** - liveness check

**POST /api/auth/login** - `{ "password": "..." }` when `GROCERY_AUTH_PASSWORD` is set

**GET /api/auth/me** - check bearer token

**GET /api/products** - authenticated user's product catalog

**POST /api/photos/upload** - authenticated shelf photo ingest (save + extract + rebuild)

**POST /api/photos/bulk** - authenticated receipt bulk import (`files` field, multiple)

```bash
# Register/login first, then upload with bearer token
TOKEN=$(curl -s -X POST http://127.0.0.1:8765/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"you@example.com","password":"your-password"}' | jq -r .token)
curl -s -H "Authorization: Bearer $TOKEN" \
  -F "file=@../data/2026_06_30/jpg/IMG_2060.jpg" \
  http://127.0.0.1:8765/api/photos/upload | jq .
```

Response shape:

```json
{
  "image_id": "IMG_0001",
  "image_path": "api/media/IMG_0001",
  "meta": { "gps_latitude": 43.64, "captured_at": "2026-06-30T19:33:18", ... },
  "products": [{ "product_name": "...", "price": 1.79, "category": "canned-goods" }],
  "extractor": "cursor_sdk",
  "product_count": 12
}
```

## Tests

```bash
# Unit tests (scoring, no API key needed)
PYTHONPATH=.. pytest tests/test_scoring.py -v

# Integration: single image + 8-image benchmark vs ground truth (~3 min)
PYTHONPATH=.. pytest tests/test_benchmark.py -m integration -v

# Full 45-image benchmark (~20 min)
GROCERY_BENCHMARK_FULL=1 PYTHONPATH=.. pytest tests/test_benchmark.py -m slow -v
```

Results are cached in `.extract_cache/` to avoid re-billing on reruns.

### Benchmark thresholds

Compared against manual extractions in `tests/fixtures/ground_truth_products.json`:

| Metric | Threshold |
|--------|-----------|
| mean recall | ≥ 0.75 |
| mean F1 | ≥ 0.70 |
| price accuracy | ≥ 0.80 |
| category accuracy | ≥ 0.70 |

Latest subset run (8 images): recall 0.85, F1 0.854, price accuracy 0.905.
