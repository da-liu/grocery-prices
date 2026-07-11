# Grocery price extraction server

HTTP service that accepts grocery shelf photos and extracts product names, prices, and metadata using a configurable vision backend.

## Project layout

```
extract_server/
├── src/extract_server/       # Python package
│   ├── main.py               # FastAPI app factory + entrypoint
│   ├── core/                 # config, logging, middleware, exceptions
│   ├── api/routes/           # HTTP route handlers
│   ├── schemas/              # Pydantic request/response models
│   ├── db/                   # SQLite persistence
│   └── extraction/           # vision pipeline, ingest, worker
├── scripts/                  # CLI utilities (reset_db, remove_user)
├── tests/
├── data/                     # runtime SQLite + user uploads (gitignored)
├── pyproject.toml
└── start.sh
```

## Architecture

```
Upload (HEIC/JPG/WebP)
  → client EXIF metadata
  → store original + WebP/JPEG blob
  → scaled derivative for model input
  → Cursor SDK or direct Gemini API (vision extraction)
  → JSON product list → SQLite catalog
```

| Module | Role |
|--------|------|
| `extraction/prompt.py` | Saved extraction prompt |
| `extraction/cursor_extractor.py` | Vision backend routing (Cursor SDK or Gemini) |
| `extraction/parse_response.py` | Parse and sanitize model JSON |
| `extraction/scoring.py` | Benchmark metrics vs ground truth |
| `extraction/pipeline.py` | End-to-end upload pipeline |
| `extraction/ingest.py` | Bulk upload, async extraction queue |

## Setup

```bash
cd extract_server
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Requires `sips` (macOS) on PATH for some image conversions. The server loads `extract_server/.env` on startup. EXIF metadata is supplied by the viewer at upload time.

Set one of these backend configurations in `.env`:

```bash
# Cursor SDK
GROCERY_EXTRACT_BACKEND=cursor
CURSOR_API_KEY=cursor_your_key_here

# Direct Gemini
GROCERY_EXTRACT_BACKEND=gemini_direct
GEMINI_API_KEY=your_gemini_api_key_here

# Production LLM input image size
GROCERY_EXTRACT_SCALE_PCT=25
```

## Run server

```bash
cd extract_server
python -m extract_server.main
# or: grocery-api
```

Server listens on http://127.0.0.1:8765

Production (launchd): `./start.sh`

### API

**GET /health** - liveness check

**POST /api/auth/register** - create account

**POST /api/auth/login** - sign in

**GET /api/auth/me** - check bearer token

**GET /api/products** - authenticated user's product catalog

**POST /api/photos/bulk** - authenticated photo ingest (`files` field, one or more)

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8765/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"you@example.com","password":"your-password"}' | jq -r .token)
curl -s -H "Authorization: Bearer $TOKEN" \
  -F "files=@../data/2026_06_30/jpg/IMG_2060.jpg" \
  http://127.0.0.1:8765/api/photos/bulk | jq .
```

## Tests

```bash
cd extract_server
pip install -e .
pytest tests -v
```
