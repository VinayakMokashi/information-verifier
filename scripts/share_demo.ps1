# Share the verifier with friends over a temporary public link (cloudflared
# quick tunnel — free, no account). REAL mode: every check spends API money
# (~$0.05-0.12 per claim), and ANYONE with the link can submit checks, so
# share it privately and Ctrl+C when you're done (the link dies with it).
#
# Run from the project root:   .\scripts\share_demo.ps1
# Free UI-only variant:        .\scripts\share_demo.ps1 -DemoMode

param([switch]$DemoMode)

$cloudflared = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cloudflared) {
    $fallback = "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe"
    if (Test-Path $fallback) { $cloudflared = $fallback }
    else { Write-Error "cloudflared not found. Install: winget install -e --id Cloudflare.cloudflared"; exit 1 }
}

# Visitors arrive through the tunnel under its random *.trycloudflare.com
# name, and the app refuses paid checks addressed to a name it does not know
# (a DNS-rebinding page sends its own). Set for the server started here only;
# the console gets its old value back at the end.
$previousHosts = $env:PUBLIC_HOSTS
$env:PUBLIC_HOSTS = (@($env:PUBLIC_HOSTS, ".trycloudflare.com") | Where-Object { $_ }) -join ","

if ($DemoMode) {
    Write-Host ">> FREE demo mode (simulated verdicts, `$0)." -ForegroundColor Green
    $server = Start-Process -PassThru -NoNewWindow ".\.venv\Scripts\python.exe" "scripts\serve_demo.py"
} else {
    Write-Host ">> REAL mode: each check costs ~`$0.05-0.12. Ctrl+C here stops the tunnel;" -ForegroundColor Yellow
    Write-Host ">> close the server window (or stop-process) when finished." -ForegroundColor Yellow
    $server = Start-Process -PassThru -NoNewWindow ".\.venv\Scripts\python.exe" `
        "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"
}

Start-Sleep -Seconds 3
Write-Host ">> Starting tunnel - the https://....trycloudflare.com line below is your share link:" -ForegroundColor Cyan
try {
    & $cloudflared tunnel --url http://127.0.0.1:8000
} finally {
    if ($server -and -not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    $env:PUBLIC_HOSTS = $previousHosts
}
