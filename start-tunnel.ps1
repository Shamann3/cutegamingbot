# ngrok tunnel for the Telegram Web App.
# Exposes Vite (port 5173) over HTTPS. Vite proxies /api, /admin/api and /health
# to the FastAPI server on port 8000, so only this one tunnel is needed.
Set-Location $PSScriptRoot

# ngrok must be installed and authenticated (ngrok config add-authtoken <token>).
$ngrok = (Get-Command ngrok -ErrorAction SilentlyContinue)
if (-not $ngrok) {
    Write-Host '[ERROR] ngrok not found on PATH.' -ForegroundColor Red
    Write-Host '        Install it: https://ngrok.com/download' -ForegroundColor Yellow
    Read-Host 'Press Enter to close'
    exit 1
}

# Keep the public URL stable by binding to the reserved domain from WEBAPP_URL.
# This way the URL always matches server/.env and the Telegram bot config.
$domain = 'musket-earthlike-army.ngrok-free.dev'
$envFile = Join-Path $PSScriptRoot '.env'
if (Test-Path $envFile) {
    $line = Select-String -Path $envFile -Pattern '^\s*WEBAPP_URL\s*=\s*(\S+)' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($line) {
        $url = $line.Matches[0].Groups[1].Value
        $parsed = $url -replace '^https?://', '' -replace '/.*$', ''
        if ($parsed) { $domain = $parsed }
    }
}

Write-Host ''
Write-Host "ngrok -> https://$domain  (forwarding to http://127.0.0.1:5173)" -ForegroundColor Cyan
Write-Host 'Web UI: http://127.0.0.1:4040   Stop: Ctrl+C' -ForegroundColor DarkGray
Write-Host ''

ngrok http "--url=https://$domain" 5173
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '[ERROR] ngrok exited with error.' -ForegroundColor Red
    Write-Host '        - Check your authtoken: ngrok config check' -ForegroundColor Yellow
    Write-Host "        - Make sure the domain '$domain' is reserved on your ngrok account" -ForegroundColor Yellow
    Write-Host '        - Only one ngrok agent can use a reserved domain at a time' -ForegroundColor Yellow
    Read-Host 'Press Enter to close'
}
