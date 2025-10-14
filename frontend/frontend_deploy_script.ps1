# Stop on error

Set-Location -Path $PSScriptRoot

# Find the right name using 
$ErrorActionPreference = "Stop"

$BucketName = "vehiclechatbotsite"
$BuildDir = Join-Path $PSScriptRoot "dist"

Write-Host " Deploying contents of $BuildDir to s3://$BucketName"

# Replace all contents in the bucket with dist/
aws s3 sync $BuildDir "s3://$BucketName" --delete --exact-timestamps