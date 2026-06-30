# Grocery Prices

Photo-based grocery price tracking for Toronto stores.

## Data

- `data/*.HEIC` - original iPhone photos
- `data/jpg/` - JPEG copies for the viewer
- `data/products.jsonl` - extracted products (one JSON object per line)

Regenerate JSONL after editing extractions:

```bash
python3 scripts/build_products.py
```

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

Store definitions live in `data/stores.json`. GPS coordinates from photo EXIF are matched to the nearest store within its `match_radius_m`.

| Store ID | GPS anchor | Match radius |
|----------|------------|--------------|
| `hua_sheng` | 43.65349, -79.39821 | 150 m |
| `lucky_moose` | 43.6539, -79.3942 | 120 m |
| `tt_downtown` | 43.6574, -79.4067 | 120 m |

Hua Sheng Supermarket: https://maps.app.goo.gl/wneauC4mmendbLyt9

Products with printed labels (herbs, meat, cauliflower) use `location_override: lucky_moose` when the sticker address overrides GPS.
