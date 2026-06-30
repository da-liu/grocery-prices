#!/usr/bin/env bash
set -euo pipefail

# One-time AWS infra for g.daliu.ca (S3 website + CloudFront, no WAF).
# Uses existing *.daliu.ca ACM cert and Managed-CachingDisabled policy.

DOMAIN="g.daliu.ca"
BUCKET="g.daliu.ca"
REGION="us-east-1"
CERT_ARN="arn:aws:acm:us-east-1:578915024316:certificate/ea38570e-c68d-4ac8-bef5-faea5491a4cd"
CACHE_POLICY="4135ea2d-6df8-44a3-9df3-4b5a84be39ad"

if ! command -v aws >/dev/null 2>&1; then
  echo "Error: AWS CLI (aws) is not on PATH." >&2
  exit 1
fi

echo "Setting up S3 bucket s3://$BUCKET..."

if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "Bucket already exists."
else
  aws s3 mb "s3://$BUCKET" --region "$REGION"
fi

aws s3 website "s3://$BUCKET" --index-document index.html --error-document index.html

aws s3api put-public-access-block \
  --bucket "$BUCKET" \
  --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"

aws s3api put-bucket-policy --bucket "$BUCKET" --policy "$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::$BUCKET/*"
    }
  ]
}
EOF
)"

DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?contains(Aliases.Items || \`[]\`, '$DOMAIN')].Id | [0]" \
  --output text)

if [ "$DIST_ID" = "None" ] || [ -z "$DIST_ID" ]; then
  echo "Creating CloudFront distribution..."
  DIST_CONFIG=$(cat <<EOF
{
  "CallerReference": "grocery-prices-g-daliu-ca-$(date +%s)",
  "Comment": "grocery-prices static site at $DOMAIN",
  "Enabled": true,
  "DefaultRootObject": "index.html",
  "PriceClass": "PriceClass_100",
  "Aliases": {
    "Quantity": 1,
    "Items": ["$DOMAIN"]
  },
  "Origins": {
    "Quantity": 1,
    "Items": [
      {
        "Id": "S3-g-daliu-website",
        "DomainName": "$BUCKET.s3-website-$REGION.amazonaws.com",
        "CustomOriginConfig": {
          "HTTPPort": 80,
          "HTTPSPort": 443,
          "OriginProtocolPolicy": "http-only",
          "OriginReadTimeout": 30,
          "OriginKeepaliveTimeout": 5
        }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "S3-g-daliu-website",
    "ViewerProtocolPolicy": "redirect-to-https",
    "AllowedMethods": {
      "Quantity": 2,
      "Items": ["GET", "HEAD"],
      "CachedMethods": {
        "Quantity": 2,
        "Items": ["GET", "HEAD"]
      }
    },
    "CachePolicyId": "$CACHE_POLICY",
    "Compress": true
  },
  "CustomErrorResponses": {
    "Quantity": 2,
    "Items": [
      {
        "ErrorCode": 403,
        "ResponsePagePath": "/index.html",
        "ResponseCode": "200",
        "ErrorCachingMinTTL": 0
      },
      {
        "ErrorCode": 404,
        "ResponsePagePath": "/index.html",
        "ResponseCode": "200",
        "ErrorCachingMinTTL": 0
      }
    ]
  },
  "ViewerCertificate": {
    "ACMCertificateArn": "$CERT_ARN",
    "SSLSupportMethod": "sni-only",
    "MinimumProtocolVersion": "TLSv1.2_2021"
  }
}
EOF
)
  CREATE_OUTPUT=$(aws cloudfront create-distribution --distribution-config "$DIST_CONFIG" --query 'Distribution.[Id,DomainName]' --output text)
  DIST_ID=$(echo "$CREATE_OUTPUT" | awk '{print $1}')
  DIST_DOMAIN=$(echo "$CREATE_OUTPUT" | awk '{print $2}')
else
  DIST_DOMAIN=$(aws cloudfront get-distribution --id "$DIST_ID" --query 'Distribution.DomainName' --output text)
  echo "CloudFront distribution already exists: $DIST_ID"
fi

echo
echo "Infrastructure ready."
echo "  S3 bucket:      s3://$BUCKET"
echo "  CloudFront ID:  $DIST_ID"
echo "  CloudFront URL: https://$DIST_DOMAIN"
echo
echo "Add DNS (Google Domains / Squarespace for daliu.ca):"
echo "  Host:  g"
echo "  Type:  CNAME"
echo "  Value: $DIST_DOMAIN"
echo
echo "Then deploy the app:"
echo "  ./deploy.sh"
