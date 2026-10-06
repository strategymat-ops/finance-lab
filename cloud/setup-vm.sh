#!/bin/bash
# ============================================================================
# Finance Lab — Cloud VM / Cloud Shell Setup
# ============================================================================
# Устанавливает все зависимости для запуска Finance Lab в облаке
# ============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

header() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  $1${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════╝${NC}"
}

step() { echo -e "  ${YELLOW}[$1]${NC} $2"; }
ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
err()  { echo -e "  ${RED}✗${NC} $1"; }

# ── System packages ───────────────────────────────────────────────────────
header "Finance Lab — Environment Setup"

step "1/8" "Обновление системы..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq
ok "Система обновлена"

# ── Docker ────────────────────────────────────────────────────────────────
step "2/8" "Установка Docker..."
if command -v docker &> /dev/null; then
    ok "Docker уже установлен: $(docker --version)"
else
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    ok "Docker установлен"
fi

# ── Docker Compose ────────────────────────────────────────────────────────
step "3/8" "Установка Docker Compose..."
if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
    ok "Docker Compose уже установлен"
else
    sudo apt-get install -y docker-compose-v2
    ok "Docker Compose установлен"
fi

# ── Python 3.12+ ──────────────────────────────────────────────────────────
step "4/8" "Установка Python 3.12..."
if python3 --version 2>/dev/null | grep -q "3.1[2-9]"; then
    ok "Python уже установлен: $(python3 --version)"
else
    sudo apt-get install -y python3.12 python3.12-venv python3-pip
    ok "Python 3.12 установлен"
fi

# ── Rust ──────────────────────────────────────────────────────────────────
step "5/8" "Установка Rust..."
if command -v rustc &> /dev/null; then
    ok "Rust уже установлен: $(rustc --version)"
else
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
    ok "Rust установлен: $(rustc --version)"
fi

# ── Node.js 20+ ──────────────────────────────────────────────────────────
step "6/8" "Установка Node.js 20 LTS..."
if command -v node &> /dev/null && node -v | grep -q "v2[0-9]"; then
    ok "Node.js уже установлен: $(node -v)"
else
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
    ok "Node.js установлен: $(node -v)"
fi

# ── Julia ─────────────────────────────────────────────────────────────────
step "7/8" "Установка Julia..."
if command -v julia &> /dev/null; then
    ok "Julia уже установлена: $(julia --version)"
else
    curl -fsSL https://install.julialang.org | sh -s -- -y
    ok "Julia установлена"
fi

# ── Python виртуальное окружение ──────────────────────────────────────────
step "8/8" "Настройка Python окружения..."
LABDIR="$HOME/finance-lab"
if [ -d "$LABDIR" ]; then
    cd "$LABDIR"
else
    mkdir -p "$LABDIR"
    cd "$LABDIR"
fi

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip setuptools wheel

# Core dependencies
pip install \
    fastapi[standard] \
    uvicorn[standard] \
    websockets \
    pydantic \
    sqlalchemy[asyncio] \
    asyncpg \
    redis[hiredis] \
    httpx

# Simulation dependencies
pip install \
    mesa \
    abce \
    econpizza \
    pydsge \
    numpy \
    scipy \
    pandas \
    polars \
    matplotlib \
    networkx

# AI/ML dependencies
pip install \
    torch \
    gymnasium \
    pettingzoo \
    stable-baselines3 \
    langchain \
    langgraph

# Financial computing
pip install \
    QuantLib \
    fredapi \
    yfinance

# Rust/PyO3 build tools
pip install maturin

ok "Python окружение настроено"

# ── Summary ───────────────────────────────────────────────────────────────
header "Setup Complete!"
echo ""
echo -e "  ${GREEN}Все компоненты установлены:${NC}"
echo "    • Docker + Docker Compose"
echo "    • Python 3.12 + venv + все библиотеки"
echo "    • Rust + Cargo + Maturin (PyO3)"
echo "    • Node.js 20 LTS"
echo "    • Julia"
echo ""
echo -e "  ${YELLOW}Следующий шаг:${NC}"
echo "    cd ~/finance-lab && docker compose up -d"
echo ""
