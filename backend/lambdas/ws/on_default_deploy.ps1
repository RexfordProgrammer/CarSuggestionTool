# Set working directory to script location
Set-Location -Path $PSScriptRoot

# Paths relative to script location
$LambdaFile = Join-Path $PSScriptRoot "on_default.py"
$ZipFile    = Join-Path $PSScriptRoot "function.zip"
$Function   = "on_default"   # AWS Lambda function name
$Region     = "us-east-1"    # AWS region

Write-Host "==> Packaging $LambdaFile into $ZipFile"
if (Test-Path $ZipFile) { Remove-Item $ZipFile }
Compress-Archive -Path $LambdaFile -DestinationPath $ZipFile -Force

Write-Host "==> Uploading to AWS Lambda: $Function"
aws lambda update-function-code `
  --function-name $Function `
  --zip-file fileb://$ZipFile `
  --region $Region

Write-Host "==> Done!"
