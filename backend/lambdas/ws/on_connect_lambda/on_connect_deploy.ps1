
# (.venv) PS C:\Users\Rexford\Documents\CarSuggestionTool\backend\lambdas\ws\on_default_lambda> aws configure sso
# SSO session name (Recommended): school
# SSO start URL [None]: https://d-906794ad98.awsapps.com/start/
# SSO region [None]: us-east-1
# SSO registration scopes [sso:account:access]:
# Attempting to automatically open the SSO authorization page in your default browser.
# If the browser does not open, open the following URL:


# Set working directory to script location
Set-Location -Path $PSScriptRoot

# Paths relative to script location
$LambdaFile = Join-Path $PSScriptRoot "lambda_function.py"
$ZipFile    = Join-Path $PSScriptRoot "function.zip"
# Find the right name using 
# aws lambda list-functions --region us-east-1
# aws lambda list-functions --region us-east-1 --profile Fall2025-CS410-Matrix-661364632619
$Function   = "on_connect"   
$Region     = "us-east-1" 

Write-Host "==> Packaging $LambdaFile into $ZipFile"
if (Test-Path $ZipFile) { Remove-Item $ZipFile }
Compress-Archive -Path $LambdaFile -DestinationPath $ZipFile -Force

Write-Host "==> Uploading to AWS Lambda: $Function"
aws lambda update-function-code `
  --function-name $Function `
  --zip-file fileb://$ZipFile `
  --profile Fall2025-CS410-Matrix-661364632619 `
  --region $Region
Write-Host "==> Done!"
