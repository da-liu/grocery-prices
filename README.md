# Grocery Prices

Photo-based grocery price tracking for Toronto stores.

## Data

- `extract_server/data/grocery.db` - users, sessions, store locations, photos, extractions, product sightings
- `extract_server/data/users/{id}/photos/` - per-user photo blobs (HEIC + JPEG), date-partitioned

Uploaded photos are stored on the API host filesystem; catalog metadata lives in SQLite. Product IDs are UUIDs; photo IDs remain `IMG_####`.

## Extraction server

Automated photo extraction (Cursor SDK vision) lives in `extract_server/`. See [extract_server/README.md](extract_server/README.md).

```bash
cd extract_server && PYTHONPATH=.. .venv/bin/python server.py
```

Authenticated upload endpoints used by the viewer:

| Endpoint | Purpose |
|----------|---------|
| `POST /api/auth/login` | Password login (`GROCERY_AUTH_PASSWORD`) |
| `POST /api/photos/bulk` | Photo upload + vision extraction + save (`files` field, one or more) |
| `GET /api/products` | User's live product catalog |

`POST /api/photos/bulk` saves photos to blob storage and writes extractions to SQLite.

### Tunnel hosting

Expose the API at **https://api-g.daliu.ca** via the shared Cloudflare tunnel (same as trackerV2):

```bash
./infra/setup-tunnel.sh
```

Add DNS once: CNAME `api-g` → `ed055d32-6cc4-482b-9aad-dac154f99551.cfargotunnel.com`

The viewer build defaults to `VITE_API_URL=https://api-g.daliu.ca` in `deploy.sh`.

### Auth

Users register with username + password. Each account has a private catalog under `extract_server/data/users/{id}/`.

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

`./deploy.sh` builds the viewer and syncs it to https://g.daliu.ca. Product photos are served by the API, not the static site.

## Stores

Each user saves store locations in SQLite (`user_store_locations`). Create stores from the label-location flow after upload, or pick an existing one. GPS from photo EXIF is matched against your saved stores within each store's `match_radius_m` (default 150 m). Unmatched photos stay as "Unknown store" until you label them.
