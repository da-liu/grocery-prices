# Grocery Prices Backlog

Product decisions (locked in):

- Browse shows one card per extracted product (default).
- Exact duplicate photos: warn, then skip or replace existing `IMG_XXXX`, or upload as new.
- Near-duplicate shelf photos: always create a new photo; match products by barcode/name and surface price history on cards.
- Empty extractions: keep the photo, show zero-product state with re-extract and manual add.
- No quick-check mode: upload always saves; product cards show similar/historical price information.

## P0 (completed)

- [x] Parallel upload processing (2 concurrent client uploads; server batch workers via `GROCERY_UPLOAD_WORKERS`)
- [x] Empty/failed extraction UX (placeholder card, re-extract, manual add)
- [x] Parsing improvements (tighter unit-price prompts; inline product edit; re-extract)
- [x] Duplicate photo detection (SHA-256 hash, skip/replace/new modal)
- [x] Price insights on product cards (barcode/name matching across catalog)

## P1 - Data model and price intelligence

- [ ] Introduce canonical products + price observations (stable IDs, separate identity from sightings)
- [ ] Price change detection and alerts ("price changed since last visit")
- [ ] Distinguish promo/sale vs permanent price change over time

## P1 - UX polish

- [ ] Settings UI to edit store name, radius, maps URL (`PUT` API exists)
- [ ] Create store from map pin when photo has no GPS
- [ ] Photo-grouped browse view toggle (one card per photo with expandable items)
- [ ] Optimistic processing cards in browse while extraction runs
- [ ] Estimated time remaining in upload queue

## P2 - AI agent and bulk operations

- [ ] Agent commands for bulk delete ("delete all photos from Store X before March")
- [ ] Agent-assisted merge of duplicate product names
- [ ] Multi-select delete for products/photos
- [ ] Archive old batches without deleting

## P3 - Platform and sharing

- [ ] Opt-in share link for store/date snapshot
- [ ] Anonymous aggregate export (no photos)
- [ ] Store API adapter for live retailer prices
- [ ] Flag when shelf photo price differs from API feed

## Maintenance

- [ ] Update READMEs (remove stale `GROCERY_AUTH_PASSWORD` docs)
- [ ] Perceptual hash for near-duplicate photo detection (beyond exact SHA-256)
- [ ] Wire receipt multi-select to true bulk endpoint for shelf uploads too
- [ ] Price history sparkline/chart in Compare view
