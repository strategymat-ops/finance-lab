# ============================================================================
# Finance Lab — Google Cloud Shell Fast Connector & Terminal Mirror
# ============================================================================

param(
    [switch]$Interactive = $true
)

# 1. Auto-detect Google Cloud SDK Path
$sdkBin = "$env:USERPROFILE\Downloads\google-cloud-sdk-587.0.0-windows-x86_64-bundled-python\bin"
if ((Test-Path $sdkBin) -and ($env:PATH -notlike "*$sdkBin*")) {
    $env:PATH = "$sdkBin;$env:PATH"
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "     Finance Lab -- Google Cloud Shell Connector & Mirror       " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

$gcloudCmd = Get-Command gcloud -ErrorAction SilentlyContinue

if (-not $gcloudCmd) {
    Write-Host "[!] gcloud CLI not found in PATH." -ForegroundColor Red
    Write-Host "    Expected at: $sdkBin" -ForegroundColor Gray
    exit 1
}

Write-Host "[OK] Google Cloud SDK detected: $($gcloudCmd.Source)" -ForegroundColor Green

# 2. Check login status
$activeAccount = (& gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>$null)

if (-not $activeAccount) {
    Write-Host ""
    Write-Host "[*] No active Google Cloud account detected." -ForegroundColor Yellow
    Write-Host "    Launching Google login in your browser..." -ForegroundColor Cyan
    Write-Host "    Please select your Google account in the browser window that opens." -ForegroundColor Gray
    Write-Host ""
    
    & gcloud auth login
    
    $activeAccount = (& gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>$null)
    if (-not $activeAccount) {
        Write-Host "[!] Login was not completed." -ForegroundColor Red
        exit 1
    }
}

Write-Host "[OK] Authenticated as: $activeAccount" -ForegroundColor Green

# 3. Port Forwarding & Connection
Write-Host ""
Write-Host "[*] Setting up port forwards: 8000 (FastAPI), 8001 (WS), 8888 (Jupyter)..." -ForegroundColor Yellow
Write-Host "[*] Connecting to Google Cloud Shell..." -ForegroundColor Cyan
Write-Host "    (Terminal session will open directly inside this window)" -ForegroundColor DarkGray
Write-Host ""

$portFlags = "-L 8000:localhost:8000 -L 8001:localhost:8001 -L 8888:localhost:8888"

& gcloud cloud-shell ssh --authorize-session --ssh-flag="$portFlags"
