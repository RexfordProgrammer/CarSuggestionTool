# Set working directory to script location
Set-Location -Path $PSScriptRoot

# Paths relative to script location
$LambdaFile = Join-Path $PSScriptRoot "lambda_function.py"
$PackageDir = Join-Path $PSScriptRoot "package"
$ZipFile    = Join-Path $PSScriptRoot "function.zip"

$Function   = "on_connect"
$Region     = "us-east-1"
$Profile1    = "Fall2025-CS410-Matrix-661364632619"

Write-Host "==> Packaging dependencies and code into $ZipFile"

# Remove old zip
if (Test-Path $ZipFile) { Remove-Item $ZipFile }

# Step 1: Add dependencies
if (Test-Path $PackageDir) {
    Compress-Archive -Path "$PackageDir\*" -DestinationPath $ZipFile -Force
}

# Step 2: Add lambda_function.py
Compress-Archive -Path $LambdaFile -Update -DestinationPath $ZipFile

# Step 3: Upload to Lambda
Write-Host "==> Uploading to AWS Lambda: $Function"
aws lambda update-function-code `
  --function-name $Function `
  --zip-file fileb://$ZipFile `
  --profile $Profile1 `
  --region $Region

Write-Host "==> Done!"
