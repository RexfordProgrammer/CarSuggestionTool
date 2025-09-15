Param(
  [string]$Bucket = $env:S3_BUCKET,
  [string]$DistributionId = $env:CLOUDFRONT_DISTRIBUTION_ID,
  [string]$Profile = $env:AWS_PROFILE,
  [string]$Region = $env:AWS_REGION
)

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
  Write-Error "AWS CLI not found. Install it: https://docs.aws.amazon.com/cli/latest/userguide/"
  exit 1
}

if (-not $Bucket) { Write-Error "Set S3_BUCKET (env var) or pass -Bucket"; exit 1 }
if (-not $Region) { $Region = "us-east-1" }

Write-Host "Building site..." -ForegroundColor Cyan
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$syncCmd = @("s3", "sync", "dist/", "s3://$Bucket/", "--delete", "--region", $Region)
if ($Profile) { $syncCmd = @("--profile", $Profile) + $syncCmd }
Write-Host "Uploading to s3://$Bucket ..." -ForegroundColor Cyan
aws $syncCmd
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($DistributionId) {
  $invCmd = @("cloudfront", "create-invalidation", "--distribution-id", $DistributionId, "--paths", "/*")
  if ($Profile) { $invCmd = @("--profile", $Profile) + $invCmd }
  Write-Host "Creating CloudFront invalidation /* ..." -ForegroundColor Cyan
  aws $invCmd
} else {
  Write-Warning "CLOUDFRONT_DISTRIBUTION_ID not set; skipping invalidation."
}
