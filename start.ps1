# Start the Information Verifier for real: the app in one window, the
# Telegram bot in a second. Starting costs nothing; each check someone sends
# costs real money (5 checks a day, shared by the bot and the web page).
#
#   Double-click start.cmd, or in a terminal in this folder:  .\start.ps1
#   Stop: Ctrl+C in each window (the bot first), or close both windows.
#
# Pure ASCII on purpose: Windows PowerShell 5.1 reads a .ps1 that has no BOM
# as ANSI, so any other character would print garbled (tests/test_launcher.py).

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$health = 'http://127.0.0.1:8000/health'

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "No virtual environment at $python - set the project up first." -ForegroundColor Red
    exit 1
}

function Get-PythonRunning([string]$pattern) {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match $pattern -and $_.CommandLine -notmatch '--check-token' }
}

function Test-AppUp {
    try {
        return (Invoke-RestMethod $health -TimeoutSec 2 -UseBasicParsing).status -eq 'ok'
    } catch {
        return $false
    }
}

function Quote([string]$text) { "'" + $text.Replace("'", "''") + "'" }

function Start-Window([string]$title, [string]$command) {
    # -EncodedCommand because the project path has spaces, and Start-Process
    # in PowerShell 5.1 joins its arguments without quoting them.
    $script = "`$Host.UI.RawUI.WindowTitle = $(Quote $title)`n" +
              "Set-Location -LiteralPath $(Quote $root)`n$command"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($script))
    Start-Process powershell.exe -WorkingDirectory $root -ArgumentList @(
        '-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encoded)
}

# The free demo serves the same app with simulated answers on the same port,
# and its /health says "ok" too. A bot wired to it would send people FAKE
# verdicts, so its process is what gets checked, not the port.
if (Get-PythonRunning 'serve_demo\.py') {
    Write-Host '>> The FREE demo server (serve_demo.py) is running on port 8000.' -ForegroundColor Red
    Write-Host '   Stop it first (Ctrl+C in its window), then run this again.'
    exit 1
}

# 1. The app. One worker: the stream registry and the rate limiter live in memory.
if (Test-AppUp) {
    Write-Host '>> The app is already running.' -ForegroundColor Green
} else {
    Write-Host '>> Starting the app...' -ForegroundColor Cyan
    Start-Window 'Verifier - app' "& $(Quote $python) -m uvicorn app.main:app"
    $deadline = (Get-Date).AddSeconds(60)
    while (-not (Test-AppUp)) {
        if ((Get-Date) -gt $deadline) {
            Write-Host '>> The app did not come up within 60 seconds - its window shows why.' -ForegroundColor Red
            Write-Host '   ("address already in use" means something else holds port 8000.)'
            exit 1
        }
        Start-Sleep -Milliseconds 500
    }
    Write-Host '>> The app is up.' -ForegroundColor Green
}

# 2. The bot, only once the app answers (it refuses to start before that).
# Telegram allows ONE poller per bot: a second copy would knock the first off.
if (Get-PythonRunning 'telegram_bot\.py') {
    Write-Host '>> The Telegram bot is already running.' -ForegroundColor Green
} else {
    Write-Host '>> Starting the Telegram bot...' -ForegroundColor Cyan
    Start-Window 'Verifier - Telegram bot' "& $(Quote $python) scripts\telegram_bot.py"
}

Write-Host ''
Write-Host 'Running. Keep both windows open and the PC awake.'
Write-Host '  Web page : http://127.0.0.1:8000   (this PC only)'
Write-Host '  Spending : http://127.0.0.1:8000/dashboard'
Write-Host '  Telegram : message @Information_Verifier_bot from any device'
Write-Host 'To stop: Ctrl+C in each window (bot first), or close both windows.'
