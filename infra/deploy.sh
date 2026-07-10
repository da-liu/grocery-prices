#!/usr/bin/env sh
set -e

# Deploy grocery-prices viewer to S3 + CloudFront at g.daliu.ca.
# Prerequisites: AWS CLI configured; infra created via deploy-infra.sh once.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

S3_BUCKET="${S3_BUCKET:-g.daliu.ca}"
DOMAIN="${DOMAIN:-g.daliu.ca}"

if ! command -v aws >/dev/null 2>&1; then
  echo "Error: AWS CLI (aws) is not on PATH." >&2
  exit 1
fi

echo "Building viewer..."
VITE_API_URL="${VITE_API_URL:-https://api-g.daliu.ca}"
(cd viewer && VITE_API_URL="$VITE_API_URL" npm run build)

echo "Syncing viewer/dist to s3://$S3_BUCKET..."
aws s3 sync viewer/dist "s3://$S3_BUCKET" --delete \
  --cache-control "public, max-age=300"

# Caching is disabled on this CloudFront distribution (Managed-CachingDisabled),
# so no invalidation is needed after sync.
echo "Deploy complete."
echo "  Custom domain: https://$DOMAIN"
