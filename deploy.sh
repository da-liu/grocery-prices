#!/usr/bin/env sh
set -e

# Deploy grocery-prices viewer to S3 + CloudFront at g.daliu.ca.
# Prerequisites: AWS CLI configured; infra created via deploy-infra.sh once.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

S3_BUCKET="${S3_BUCKET:-g.daliu.ca}"
DOMAIN="${DOMAIN:-g.daliu.ca}"
CF_DISTRIBUTION_ID="${CF_DISTRIBUTION_ID:-E25GSUYTAEDPYS}"

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

if [ "$CF_DISTRIBUTION_ID" != "None" ] && [ -n "$CF_DISTRIBUTION_ID" ]; then
  echo "Invalidating CloudFront distribution $CF_DISTRIBUTION_ID..."
  aws cloudfront create-invalidation --distribution-id "$CF_DISTRIBUTION_ID" --paths "/*" >/dev/null
  DIST_DOMAIN=$(aws cloudfront get-distribution --id "$CF_DISTRIBUTION_ID" \
    --query 'Distribution.DomainName' --output text)
  echo "Deploy complete."
  echo "  CloudFront: https://$DIST_DOMAIN"
  echo "  Custom domain: https://$DOMAIN"
else
  echo "Deploy complete (S3 only; CloudFront distribution not found)."
fi
