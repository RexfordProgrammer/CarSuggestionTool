#!/usr/bin/env bash
set -euo pipefail

: "${S3_BUCKET:?Set S3_BUCKET}"
: "${AWS_REGION:=us-east-1}"
# Optional
: "${CLOUDFRONT_DISTRIBUTION_ID:=}"
: "${AWS_PROFILE:=}"

echo "Building site..."
npm run build

if [[ -n "$AWS_PROFILE" ]]; then
  PROFILE=(--profile "$AWS_PROFILE")
else
  PROFILE=()
fi

echo "Syncing to s3://$S3_BUCKET ..."
aws "${PROFILE[@]}" s3 sync dist/ "s3://$S3_BUCKET/" --delete --region "$AWS_REGION"

if [[ -n "$CLOUDFRONT_DISTRIBUTION_ID" ]]; then
  echo "Creating CloudFront invalidation /* ..."
  aws "${PROFILE[@]}" cloudfront create-invalidation --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" --paths "/*"
else
  echo "CLOUDFRONT_DISTRIBUTION_ID not set; skipping invalidation."
fi
