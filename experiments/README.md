# Grocery Prices Experiments

Exploratory tools that are not part of the production viewer or API.

| Folder | Purpose |
|--------|---------|
| `match-explorer/` | React app to inspect photo extractions and step-by-step product matching scores |

## Match Explorer

Visualizes extraction JSON for each photo and runs the production matching algorithm (`extract_server/extraction/matching.py`) against every product pair.

```bash
cd experiments/match-explorer
npm install
python3 scripts/build_data.py   # reads ../../data extractions + embedding cache
npm run dev                     # http://localhost:41874
```

Rebuild `public/data/manifest.json` after adding or changing extraction JSON under `data/`. HEIC originals are converted to JPEG previews in `grocery-prices/.tmp-jpg/` for browser viewing.
