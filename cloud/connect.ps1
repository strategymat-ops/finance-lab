# ============================================================================
# Finance Lab — Google Cloud Shell Tunnel
# ============================================================================
# Устанавливает SSH-туннель к Google Cloud Shell / VM
# и пробрасывает порты для всех сервисов лаборатории
# ============================================================================

param(
    [string]$Action = "connect",      # connect | setup | tunnel | status | stop
    [string]$ProjectId = "",          # Google Cloud Project ID
    [string]$Zone = "us-central1-a",  # VM Zone
    [string]$VMName = "finance-lab",  # VM instance name
    [switch]$UseCloudShell,           # Use Cloud Shell instead of VM
    [switch]$Interactive              # Open interactive terminal
)

# ── Auto-detect Google Cloud SDK Path ──────────────────────────────────────
$sdkBin = "C:\Users\Мати\Downloads\google-cloud-sdk-587.0.0-windows-x86_64-bundled-python\bin"
if ((Test-Path $sdkBin) -and ($env:PATH -notlike "*$sdkBin*")) {
    $env:PATH = "$sdkBin;$env:PATH"
}

# ── Цвета и стили ──────────────────────────────────────────────────────────
function Write-Header { param([string]$text)
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║  $text" -ForegroundColor Cyan -NoNewline
    $padding = 54 - $text.Length
    Write-Host (" " * [Math]::Max(0, $padding)) -NoNewline
    Write-Host "║" -ForegroundColor Cyan
    Write-Host "  ╚══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
}

function Write-Step { param([string]$step, [string]$desc)
    Write-Host "  [$step] " -ForegroundColor Yellow -NoNewline
    Write-Host $desc -ForegroundColor White
}

function Write-OK { param([string]$msg)
    Write-Host "  ✓ " -ForegroundColor Green -NoNewline
    Write-Host $msg
}

function Write-Err { param([string]$msg)
    Write-Host "  ✗ " -ForegroundColor Red -NoNewline
    Write-Host $msg
}

# ── Конфигурация портов ────────────────────────────────────────────────────
$Ports = @{
    "FastAPI Backend"    = 8000
    "Next.js Frontend"   = 3000
    "WebSocket"          = 8001
    "PostgreSQL"         = 5432
    "Redis"              = 6379
    "Jupyter Lab"        = 8888
    "Grafana Monitoring" = 3001
}

# ── Проверка gcloud CLI ───────────────────────────────────────────────────
function Test-GCloudInstalled {
    try {
        $null = Get-Command gcloud -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Get-ActiveProject {
    try {
        $project = gcloud config get-value project 2>$null
        return $project
    } catch {
        return $null
    }
}

# ── Действие: Setup — Создание VM в Google Cloud ──────────────────────────
function Invoke-Setup {
    Write-Header "Finance Lab — Cloud VM Setup"

    if (-not (Test-GCloudInstalled)) {
        Write-Err "Google Cloud SDK не установлен!"
        Write-Host "  Установите: https://cloud.google.com/sdk/docs/install" -ForegroundColor Gray
        return
    }

    # Проверка проекта
    $project = if ($ProjectId) { $ProjectId } else { Get-ActiveProject }
    if (-not $project) {
        Write-Err "Не указан Project ID. Используйте -ProjectId или gcloud config set project PROJECT_ID"
        return
    }
    Write-OK "Проект: $project"

    # Включаем необходимые API
    Write-Step "1/5" "Включение Compute Engine API..."
    gcloud services enable compute.googleapis.com --project=$project 2>$null
    Write-OK "Compute Engine API активирован"

    Write-Step "2/5" "Включение IAP API..."
    gcloud services enable iap.googleapis.com --project=$project 2>$null
    Write-OK "IAP API активирован"

    # Создание VM
    Write-Step "3/5" "Создание VM: $VMName (zone: $Zone)..."
    $vmExists = gcloud compute instances describe $VMName --zone=$Zone --project=$project 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-OK "VM уже существует, пропускаем создание"
    } else {
        gcloud compute instances create $VMName `
            --zone=$Zone `
            --project=$project `
            --machine-type=e2-standard-4 `
            --boot-disk-size=100GB `
            --boot-disk-type=pd-ssd `
            --image-family=ubuntu-2404-lts-amd64 `
            --image-project=ubuntu-os-cloud `
            --metadata=startup-script='#!/bin/bash
                apt-get update
                apt-get install -y docker.io docker-compose-v2 python3-pip rustc cargo nodejs npm
                systemctl enable docker
                systemctl start docker
                usermod -aG docker $(whoami)
            ' `
            --tags=finance-lab `
            --scopes=cloud-platform

        if ($LASTEXITCODE -eq 0) {
            Write-OK "VM создана успешно"
        } else {
            Write-Err "Ошибка создания VM"
            return
        }
    }

    # Firewall rules
    Write-Step "4/5" "Настройка firewall..."
    gcloud compute firewall-rules create finance-lab-ports `
        --project=$project `
        --allow=tcp:3000,tcp:8000,tcp:8001,tcp:8888 `
        --target-tags=finance-lab `
        --description="Finance Lab service ports" 2>$null
    Write-OK "Firewall настроен"

    # Копирование проекта
    Write-Step "5/5" "Загрузка проекта на VM..."
    $labPath = Split-Path -Parent $PSScriptRoot
    gcloud compute scp --recurse "$labPath" "${VMName}:~/finance-lab" `
        --zone=$Zone --project=$project --tunnel-through-iap 2>$null
    Write-OK "Проект загружен"

    Write-Host ""
    Write-OK "Setup завершён! Запустите: .\connect.ps1 -Action connect"
}

# ── Действие: Connect — Подключение с туннелем ────────────────────────────
function Invoke-Connect {
    Write-Header "Finance Lab — Cloud Connection"

    if (-not (Test-GCloudInstalled)) {
        Write-Err "Google Cloud SDK не установлен!"
        return
    }

    $project = if ($ProjectId) { $ProjectId } else { Get-ActiveProject }
    if (-not $project) {
        Write-Err "Не указан Project ID"
        return
    }

    if ($UseCloudShell) {
        # ── Cloud Shell режим ──────────────────────────────────────────
        Write-Step "MODE" "Google Cloud Shell (бесплатный)"
        Write-Host ""
        Write-Host "  Открытие Cloud Shell..." -ForegroundColor Gray

        # Cloud Shell SSH
        if ($Interactive) {
            gcloud cloud-shell ssh --authorize-session
        } else {
            # Туннель через Cloud Shell
            Write-Step "TUNNEL" "Пробрасываем порты..."
            $portArgs = @()
            foreach ($entry in $Ports.GetEnumerator()) {
                $port = $entry.Value
                $portArgs += "-L ${port}:localhost:${port}"
                Write-Host "    → $($entry.Key): localhost:$port" -ForegroundColor DarkGray
            }
            $sshArgs = $portArgs -join " "

            Write-Host ""
            Write-OK "Туннель активен! Сервисы доступны на localhost"
            Write-Host ""

            gcloud cloud-shell ssh --authorize-session --ssh-flag="$sshArgs"
        }
    } else {
        # ── VM режим ──────────────────────────────────────────────────
        Write-Step "MODE" "Compute Engine VM: $VMName"
        Write-Host ""

        if ($Interactive) {
            Write-Step "SSH" "Подключение к VM..."
            gcloud compute ssh $VMName `
                --zone=$Zone `
                --project=$project `
                --tunnel-through-iap
        } else {
            # Полный туннель со всеми портами
            Write-Step "TUNNEL" "Устанавливаем SSH-туннель с пробросом портов..."
            $portArgs = @()
            foreach ($entry in $Ports.GetEnumerator()) {
                $port = $entry.Value
                $portArgs += "-L ${port}:localhost:${port}"
                Write-Host "    → $($entry.Key): localhost:$port" -ForegroundColor DarkGray
            }

            Write-Host ""
            Write-OK "Все сервисы будут доступны на localhost"
            Write-Host "  Ctrl+C для отключения" -ForegroundColor DarkGray
            Write-Host ""

            $sshFlags = ($portArgs -join " ") + " -N"

            gcloud compute ssh $VMName `
                --zone=$Zone `
                --project=$project `
                --tunnel-through-iap `
                '--' $sshFlags
        }
    }
}

# ── Действие: Tunnel — Только проброс портов ──────────────────────────────
function Invoke-Tunnel {
    Write-Header "Finance Lab — Port Tunnel"

    $project = if ($ProjectId) { $ProjectId } else { Get-ActiveProject }

    Write-Step "PORTS" "Пробрасываемые порты:"
    foreach ($entry in $Ports.GetEnumerator()) {
        Write-Host "    $($entry.Key) → localhost:$($entry.Value)" -ForegroundColor DarkGray
    }
    Write-Host ""

    $portArgs = ($Ports.Values | ForEach-Object { "-L ${_}:localhost:${_}" }) -join " "

    if ($UseCloudShell) {
        gcloud cloud-shell ssh --authorize-session --ssh-flag="$portArgs -N"
    } else {
        gcloud compute ssh $VMName `
            --zone=$Zone `
            --project=$project `
            --tunnel-through-iap `
            '--' $portArgs -N
    }
}

# ── Действие: Status — Проверка статуса ───────────────────────────────────
function Invoke-Status {
    Write-Header "Finance Lab — Status"

    $project = if ($ProjectId) { $ProjectId } else { Get-ActiveProject }
    Write-Step "PROJECT" $project

    # Проверка VM
    Write-Step "VM" "Проверка..."
    $vmInfo = gcloud compute instances describe $VMName `
        --zone=$Zone --project=$project --format="json" 2>$null | ConvertFrom-Json

    if ($vmInfo) {
        $status = $vmInfo.status
        $ip = $vmInfo.networkInterfaces[0].accessConfigs[0].natIP
        if ($status -eq "RUNNING") {
            Write-OK "VM: $VMName — $status (IP: $ip)"
        } else {
            Write-Err "VM: $VMName — $status"
        }
    } else {
        Write-Err "VM не найдена"
    }

    # Проверка локальных портов
    Write-Host ""
    Write-Step "PORTS" "Локальные порты:"
    foreach ($entry in $Ports.GetEnumerator()) {
        $port = $entry.Value
        $conn = Test-NetConnection -ComputerName localhost -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue 2>$null
        if ($conn) {
            Write-OK "$($entry.Key) (port $port) — ACTIVE"
        } else {
            Write-Host "    ○ $($entry.Key) (port $port) — inactive" -ForegroundColor DarkGray
        }
    }
}

# ── Действие: Stop — Остановка VM ─────────────────────────────────────────
function Invoke-Stop {
    Write-Header "Finance Lab — Stop VM"

    $project = if ($ProjectId) { $ProjectId } else { Get-ActiveProject }

    Write-Step "STOP" "Остановка VM: $VMName..."
    gcloud compute instances stop $VMName --zone=$Zone --project=$project

    if ($LASTEXITCODE -eq 0) {
        Write-OK "VM остановлена (биллинг вычислений прекращён)"
    } else {
        Write-Err "Ошибка остановки VM"
    }
}

# ── Маршрутизация действий ────────────────────────────────────────────────
Write-Header "Finance Lab — Cloud Manager"
Write-Host ""

switch ($Action.ToLower()) {
    "setup"   { Invoke-Setup }
    "connect" { Invoke-Connect }
    "tunnel"  { Invoke-Tunnel }
    "status"  { Invoke-Status }
    "stop"    { Invoke-Stop }
    default   {
        Write-Host "  Доступные действия:" -ForegroundColor Yellow
        Write-Host "    setup    — Создать VM в Google Cloud" -ForegroundColor Gray
        Write-Host "    connect  — Подключиться к VM/Cloud Shell" -ForegroundColor Gray
        Write-Host "    tunnel   — Только проброс портов" -ForegroundColor Gray
        Write-Host "    status   — Проверить статус" -ForegroundColor Gray
        Write-Host "    stop     — Остановить VM" -ForegroundColor Gray
        Write-Host ""
        Write-Host "  Примеры:" -ForegroundColor Yellow
        Write-Host "    .\connect.ps1 -Action setup -ProjectId my-project" -ForegroundColor DarkGray
        Write-Host "    .\connect.ps1 -Action connect -UseCloudShell" -ForegroundColor DarkGray
        Write-Host "    .\connect.ps1 -Action connect -Interactive" -ForegroundColor DarkGray
        Write-Host "    .\connect.ps1 -Action tunnel" -ForegroundColor DarkGray
    }
}
