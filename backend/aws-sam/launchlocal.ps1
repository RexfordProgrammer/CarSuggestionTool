<#
.SYNOPSIS
  Launches the Car Suggestion Tool local SAM + WebSocket stack.
  - Loads credentials from aws.creds.ps1 (or AWS CLI profile if missing)
  - Optionally rebuilds SAM
  - Starts Lambda + WebSocket proxy + Frontend (parallel)
#>

Set-Location -Path $PSScriptRoot

# ==========================
# CONFIGURATION
# ==========================
$SAM_PORT      = 3001
$WS_PORT       = 8080
$REGION        = "us-east-1"
$ENV_FILE      = "env.local.json"
$TEMPLATE_FILE = "template.local.yaml"
$CRED_SCRIPT   = "aws.creds.ps1"
$PROFILE       = "default"

Write-Host "🚀 Launching local Car Suggestion Tool stack..." -ForegroundColor Cyan

# ==========================
# AWS CREDENTIAL LOADING
# ==========================
function Load-AWSCredentials {
    if (Test-Path $CRED_SCRIPT) {
        Write-Host "🔑 Loading AWS credentials from $CRED_SCRIPT"
        try {
            . "$PSScriptRoot\$CRED_SCRIPT"
            Write-Host "✅ Credentials injected from $CRED_SCRIPT"
        } catch {
            Write-Host "❌ Failed to execute $CRED_SCRIPT — check syntax." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "ℹ️ No $CRED_SCRIPT found. Attempting to load from AWS CLI profile '$PROFILE'..."
        try {
            $json = aws configure export-credentials --profile $PROFILE --format json | ConvertFrom-Json
            $env:AWS_ACCESS_KEY_ID     = $json.AccessKeyId
            $env:AWS_SECRET_ACCESS_KEY = $json.SecretAccessKey
            if ($json.SessionToken) { $env:AWS_SESSION_TOKEN = $json.SessionToken }

            # Optionally write them back to file for reuse
            $content = @"
`$Env:AWS_ACCESS_KEY_ID="$($env:AWS_ACCESS_KEY_ID)"
`$Env:AWS_SECRET_ACCESS_KEY="$($env:AWS_SECRET_ACCESS_KEY)"
`$Env:AWS_SESSION_TOKEN="$($env:AWS_SESSION_TOKEN)"
"@
            $content | Out-File -FilePath "$PSScriptRoot\$CRED_SCRIPT" -Encoding utf8
            Write-Host "💾 Exported fresh credentials to $CRED_SCRIPT for reuse."
        } catch {
            Write-Host "❌ Could not load credentials from AWS CLI or write file." -ForegroundColor Red
            exit 1
        }
    }

    # Verify credentials
    try {
        $identity = aws sts get-caller-identity | ConvertFrom-Json
        Write-Host "👤 Verified identity:"
        Write-Host "   Account: $($identity.Account)"
        Write-Host "   ARN:     $($identity.Arn)"
    } catch {
        Write-Host "⚠️ Unable to verify credentials. Continuing..." -ForegroundColor DarkYellow
    }
}
Load-AWSCredentials

# ==========================
# DOCKER CHECK
# ==========================
Write-Host "🐋 Checking Docker..."
docker version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker not running. Start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# ==========================
# CLEAN DUPLICATES USING WS PORT
# ==========================
Write-Host "🧹 Checking for processes using port $WS_PORT..."
$portInUse = netstat -ano | Select-String ":$WS_PORT\s"
if ($portInUse) {
    $pids = ($portInUse -split '\s+') | Where-Object { $_ -match '^\d+$' } | Select-Object -Unique
    foreach ($pid1 in $pids) {
        try {
            $proc = Get-Process -Id $pid1 -ErrorAction Stop
            Write-Host "⚙️ Killing process $($proc.ProcessName) (PID: $pid1) using port $WS_PORT..." -ForegroundColor Yellow
            Stop-Process -Id $pid1 -Force
        } catch {}
    }
    Write-Host "✅ Port $WS_PORT cleared."
} else {
    Write-Host "✅ Port $WS_PORT is free."
}

# ==========================
# OPTIONAL REBUILD
# ==========================
$rebuild = Read-Host "🔄 Rebuild SAM stack first? (y/n)"
if ($rebuild -match '^[Yy]') {
    Write-Host "🔧 Building SAM stack from '$TEMPLATE_FILE'..."
    sam build --template-file $TEMPLATE_FILE --cached --parallel
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Build failed. Fix errors and retry." -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Build complete." -ForegroundColor Green
} else {
    Write-Host "⏭️ Skipping rebuild; using existing .aws-sam/build output."
}

# ==========================
# START LAMBDA RUNTIME
# ==========================
Write-Host "🧠 Starting local Lambda runtime on port $SAM_PORT..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "sam local start-lambda --template $TEMPLATE_FILE --port $SAM_PORT --env-vars $ENV_FILE --region $REGION" -WindowStyle Minimized



# ==========================
# HEALTH CHECK LOOP
# ==========================
Write-Host "⏳ Waiting for Lambda runtime to become ready..."
$maxTries = 10
$lambdaReady = $false
for ($i = 1; $i -le $maxTries; $i++) {
    try {
        $res = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$SAM_PORT/2015-03-31/functions" -TimeoutSec 2
        if ($res.StatusCode -eq 200) {
            Write-Host "✅ Lambda service ready (after $i seconds)." -ForegroundColor Green
            $lambdaReady = $true
            break
        }
    } catch { Start-Sleep -Seconds 1 }
}
if (-not $lambdaReady) {
    Write-Host "⚠️ Lambda runtime did not respond after $maxTries seconds. Continuing..." -ForegroundColor DarkYellow
}

# ==========================
# START WEBSOCKET PROXY
# ==========================
Write-Host "🔗 Starting WebSocket proxy on port $WS_PORT..."
Start-Process "node" -ArgumentList "ws-stub.js" -NoNewWindow
Write-Host "✅ WebSocket proxy launched in background." -ForegroundColor Green

# ==========================
# FRONTEND CONNECTION INFO
# ==========================
$env:WS_URL = "ws://localhost:$WS_PORT"
Write-Host ""
Write-Host "🌐 WS_URL set to $($env:WS_URL)" -ForegroundColor Cyan
Write-Host "✅ Local WebSocket proxy ready on ws://localhost:$WS_PORT"
Write-Host ""
Write-Host "You can now run your frontend and connect using:"
Write-Host "    const ws = new WebSocket('ws://localhost:$WS_PORT');"
Write-Host ""
Write-Host "To stop everything: close the PowerShell windows or run:"
Write-Host "    Get-Process node, sam | Stop-Process"
Write-Host ""
