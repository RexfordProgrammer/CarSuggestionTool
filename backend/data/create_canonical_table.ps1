# === CONFIG ===
$region = "us-east-1"
$csv = "nhtsa.csv"
$prefix = "nhtsa/"

aws s3 cp "nhtsa.csv" "s3://vehicle-data-for-chatbot/$($prefix)$csv" --region $region

aws dynamodb import-table `
  --input-format CSV `
  --s3-bucket-source S3Bucket="vehicle-data-for-chatbot",S3KeyPrefix="$prefix" `
  --table-creation-parameters file://table-schema.json `
  --region $region
