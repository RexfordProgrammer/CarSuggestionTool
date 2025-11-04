# build-and-deploy.ps1
Set-Location -Path $PSScriptRoot

# === CONFIG ===
$templateFile = "template.yaml"  # or "template.yml"
Write-Host "📄 Scanning $templateFile for available functions..."

$functions = (Get-Content $templateFile) -match "^\s{2,}([A-Za-z0-9_]+):\s*$" |
                 ForEach-Object { ($_ -split ":")[0].Trim() }

if (-not $functions -or $functions.Count -eq 0) {
    Write-Host "❌ No functions found in $templateFile"
    exit 1
}

# === Let user pick function ===
Write-Host "`nAvailable functions:`n"
for ($i = 0; $i -lt $functions.Count; $i++) {
    Write-Host "[$($i+1)] $($functions[$i])"
}

$choice = Read-Host "`nEnter the number or name of the function to build/deploy"
if ($choice -match '^\d+$') {
    $functionName = $functions[$choice - 1]
} else {
    $functionName = $choice
}

if (-not $functions -contains $functionName) {
    Write-Host "❌ '$functionName' not found in SAM template."
    exit 1
}

Write-Host "`n🚧 Building function: $functionName ..."
sam build $functionName

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n🚀 Deploying function: $functionName ..."
    sam deploy --resource $functionName
} else {
    Write-Host "❌ Build failed. Deployment skipped."
}
