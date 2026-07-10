# Grocery Prices

Photo-based grocery price tracking for Toronto stores.

## Layout

| Path | Role |
|------|------|
| `viewer/` | React app: browse catalog, upload photos, manage stores |
| `extract_server/` | FastAPI: auth, storage, vision extraction ([docs](extract_server/README.md)) |
| `experiments/` | Dev tools ([docs](experiments/README.md)) |

## Local dev

```bash
# API — http://127.0.0.1:8765
cd extract_server && pip install -e . && python -m extract_server.main

# Viewer — http://localhost:41873 (proxies /api to the server above)
cd viewer && npm install && npm run dev
```

## Deploy

| Service | URL | Command |
|---------|-----|---------|
| Viewer | https://g.daliu.ca | `./infra/deploy.sh` |
| API | https://api-g.daliu.ca | `./infra/setup-tunnel.sh` |

First-time infra: `./infra/deploy-infra.sh`
