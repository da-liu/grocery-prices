# Photo type experiment: 2-step vs 1-step

Compare whether grocery photo handling works better as:

1. **two_step** (production today): classify with a dedicated LLM call, then extract with a type-specific prompt
2. **one_step**: classify and extract in a single unified prompt returning `{"type", "products"}`
3. **oracle** (optional control): extract with known photo type, no classification

## Dataset

| Subset | Shelf | Receipt | Total |
|--------|------:|--------:|------:|
| `quick` | 3 | 3 | 6 |
| `default` | 8 | 6 | 14 |
| `full` | 45 | 6 | 51 |

- Shelf ground truth: `extract_server/tests/fixtures/ground_truth_products.json`
- Receipt ground truth: `data/receipts/*.json` (co-located HEIC images)
- Manifest index: `experiment/manifest.json`

Regenerate manifest after adding images:

```bash
python experiment/dataset.py
```

## Run

From `grocery-prices/` (use the extract_server venv for dependencies):

```bash
cd extract_server
source .venv/bin/activate

# Cursor backend (default)
export CURSOR_API_KEY=...

python ../experiment/run.py \
  --approaches two_step one_step \
  --subset default \
  --backend cursor \
  --model auto \
  --scale 25 \
  --repeats 3

# Optional oracle control
python ../experiment/run.py --approaches two_step one_step oracle --subset quick

# Gemini direct backend
export GEMINI_API_KEY=...
python ../experiment/run.py --backend gemini_direct --model gemini-3.1-flash-lite
```

Output goes to `experiment/results/run_YYYYMMDD_HHMMSS/`:

- `config.json` - frozen run parameters
- `summary.json` / `summary.md` - comparison tables
- `logs/<image_id>/<approach>_repN.json` - per-run metrics and products

## Metrics

Per run:

- **type_correct** - predicted type matches ground truth label
- **f1**, **recall**, **precision**, **price_accuracy** - product extraction vs ground truth
- **total_llm_ms** - end-to-end LLM latency
- **llm_calls** - 2 for two_step, 1 for one_step/oracle

Summary includes confusion matrix (shelf vs receipt) and stratified F1 by photo type.

## Decision criteria

Recommend switching to 1-step in production if all of:

1. End-to-end F1 within 2% of 2-step on `--subset full`
2. Type accuracy >= 2-step (no receipt detection regression)
3. Total LLM latency meaningfully lower (~40-50% expected from one vision call vs two)

If 1-step wins on latency but loses on receipt extraction, consider a hybrid strategy.

## Tests

```bash
cd extract_server
.venv/bin/pytest ../experiment/tests/ -q
```

Tests cover dataset loading, manifest consistency, and unified response parsing (no LLM calls).

## Layout

```
experiment/
  dataset.py          # load eval images + ground truth
  manifest.json       # index of all 51 eval images
  prompts.py          # unified 1-step prompt
  parse_unified.py    # parse {"type", "products"} responses
  vision.py           # shared vision LLM wrapper
  approaches/
    two_step.py       # classify → extract (production mirror)
    one_step.py       # unified classify + extract
    oracle.py         # extract with known type
  run.py              # CLI entry point
  report.py           # aggregate metrics → summary
  results/            # gitignored run output
  tests/
```
