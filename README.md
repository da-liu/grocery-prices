# Grocery Prices

Photo-based grocery price tracking for Toronto stores.

## Data

- `data/YYYY_MM_DD/*.HEIC` - original iPhone photos, grouped by import/capture date
- `data/YYYY_MM_DD/jpg/` - JPEG copies for the viewer
- `data/products.jsonl` - extracted products (one JSON object per line)

Drop new HEIC files into today's date folder (e.g. `data/2026_06_30/`) so filenames like `IMG_2027` do not collide across import batches.

Regenerate JSONL after editing extractions:

```bash
python3 scripts/build_products.py
```

## Extraction server

Automated photo extraction (Cursor SDK vision) lives in `extract_server/`. See [extract_server/README.md](extract_server/README.md).

```bash
cd extract_server && PYTHONPATH=.. .venv/bin/python server.py
curl -F "file=@data/2026_06_30/jpg/IMG_2060.jpg" http://127.0.0.1:8765/extract
```

### Next phase API

The server also exposes authenticated upload endpoints used by the viewer:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/auth/login` | Password login (`GROCERY_AUTH_PASSWORD`) |
| `POST /api/photos/upload` | Shelf photo upload + vision extraction + save |
| `POST /api/photos/bulk` | Receipt bulk import |
| `GET /api/products` | Live `products.jsonl` data |

Uploaded extractions are saved under `data/extractions/` and merged into `products.jsonl` on rebuild.

### Tunnel hosting

Expose the API at **https://api-g.daliu.ca** via the shared Cloudflare tunnel (same as trackerV2):

```bash
./infra/setup-tunnel.sh
```

Add DNS once: CNAME `api-g` → `ed055d32-6cc4-482b-9aad-dac154f99551.cfargotunnel.com`

The viewer build defaults to `VITE_API_URL=https://api-g.daliu.ca` in `deploy.sh`.

### Auth

Users register with username + password. Each account has a private product catalog under `data/users/{id}/`.

| Endpoint | Purpose |
|----------|---------|
| `POST /api/auth/register` | Create account |
| `POST /api/auth/login` | Sign in (returns token + sets session cookie) |
| `GET /api/auth/me` | Current user profile |
| `GET /api/products` | User's products (auth required) |
| `GET /api/media/{image_id}` | User's photo JPEG (auth required) |

Browse, Compare, and Upload in the viewer require sign-in. New users see an onboarding guide for their first upload.

## Viewer

React + Vite app in `viewer/`:

```bash
cd viewer
npm install
npm run dev
```

Open http://localhost:41873

## Deploy

Static site at **https://g.daliu.ca** (S3 + CloudFront).

```bash
./deploy-infra.sh   # once
./deploy.sh         # build + sync
```

The build script copies `products.jsonl` and JPEGs into `viewer/public/`.

## Stores

Each user saves store locations in SQLite (`user_store_locations`). Create stores from the label-location flow after upload, or pick an existing one. GPS from photo EXIF is matched against your saved stores within each store's `match_radius_m` (default 150 m). Unmatched photos stay as "Unknown store" until you label them.
