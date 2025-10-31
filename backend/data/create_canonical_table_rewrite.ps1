# Always run relative to this script
Set-Location $PSScriptRoot

# === CONFIG ===
$region = "us-east-1"
$file   = "nhtsa_prepared.csv"
$table  = "nhtsa_data"

# === Upload the CSV to S3 ===
Write-Host "Uploading $file to s3://vehicle-data-for-chatbot/nhtsa_auto/$file ..."
aws s3 cp $file "s3://vehicle-data-for-chatbot/nhtsa_auto/$file" --region $region

# === Load the working table schema ===
Write-Host "Loading schema from nhtsa_schema.json ..."
$json = Get-Content "nhtsa_schema.json" -Raw

# === Delete existing table if it exists ===
Write-Host "Checking for existing table $table ..."
aws dynamodb describe-table --table-name $table --region $region >$null 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "Deleting existing table $table ..."
    aws dynamodb delete-table --table-name $table --region $region
    Write-Host "Waiting for deletion to complete ..."
    aws dynamodb wait table-not-exists --table-name $table --region $region
}

# === Import into DynamoDB ===
Write-Host "Importing $file into DynamoDB table $table ..."
aws dynamodb import-table `
  --input-format CSV `
  --s3-bucket-source S3Bucket="vehicle-data-for-chatbot",S3KeyPrefix="nhtsa_auto" `
  --table-creation-parameters "$json" `
  --region $region

Write-Host "✅ Import completed for $table."
