# ==========================
# START FRONTEND (LocalTest, PARALLEL)
# ==========================
Write-Host "🧩 Launching frontend (LocalTest) in parallel..."
try {
    $frontendPath = Join-Path $PSScriptRoot "..\..\frontend (LocalTest)"
    if (Test-Path (Join-Path $frontendPath "package.json")) {
        Write-Host "📦 Installing dependencies (if needed)..."
        Start-Process "cmd.exe" -ArgumentList "/c npm install --no-fund --no-audit && npm run dev" -WorkingDirectory $frontendPath -WindowStyle Minimized
        Write-Host "🚀 Frontend launched in background." -ForegroundColor Green
    } else {
        Write-Host "⚠️ No package.json found in LocalTest — skipping frontend startup." -ForegroundColor DarkYellow
    }
} catch {
    Write-Host "❌ Failed to start frontend: $($_.Exception.Message)" -ForegroundColor Red
}