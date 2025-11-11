# Set working directory to script location
Set-Location -Path $PSScriptRoot

# Paths relative to script location
$LambdaFile = Join-Path $PSScriptRoot "lambda_function.py"
$PackageDir = Join-Path $PSScriptRoot "package"
$SharedDir  = Join-Path $PSScriptRoot "..\..\shared_helpers"
$ZipFile    = Join-Path $PSScriptRoot "function.zip"

$Function   = "on_send_message"
$Region     = "us-east-1"

Write-Host "==> Packaging Lambda: $Function"
Write-Host "==> Creating archive at $ZipFile"

# Remove old zip
if (Test-Path $ZipFile) { Remove-Item $ZipFile }

# Step 1: Add dependency packages (if they exist)
if (Test-Path $PackageDir) {
    Write-Host "  • Adding dependencies from $PackageDir"
    Compress-Archive -Path "$PackageDir\*" -DestinationPath $ZipFile -Force
}

# Step 2: Add main lambda file
Write-Host "  • Adding lambda_function.py"
Compress-Archive -Path $LambdaFile -Update -DestinationPath $ZipFile

# Step 3: Add shared helper files
if (Test-Path $SharedDir) {
    Write-Host "  • Adding shared helpers from $SharedDir"
    Compress-Archive -Path "$SharedDir\*" -Update -DestinationPath $ZipFile
}

# Step 4: Upload to AWS Lambda
Write-Host "==> Uploading to AWS Lambda function: $Function"
aws lambda update-function-code `
  --function-name $Function `
  --zip-file fileb://$ZipFile `
  --region $Region `

Write-Host "==> Done!"
