#!/bin/bash
# ============================================================================
# Finance Lab — Automated Google Cloud Shell Deployment & Self-Test Script
# ============================================================================
# This script deploys the complete laboratory inside Google Cloud Shell,
# runs the full verification test suite for all quantitative engines,
# starts the FastAPI backend + WebSocket server, and establishes terminal mirroring.
# ============================================================================

set -e

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${CYAN}${BOLD}"
echo "╔═══════════════════════════════════════════════════════════════════╗"
echo "║          Finance Lab — Google Cloud Shell Deployment Engine       ║"
echo "╚═══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo -e "${YELLOW}[1/5] Checking environment and system packages...${NC}"
sudo apt-get update -qq
sudo apt-get install -y -qq python3-pip python3-venv build-essential pkg-config libssl-dev tmate curl git

echo -e "${YELLOW}[2/5] Setting up isolated Python virtual environment...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

echo -e "${YELLOW}[3/5] Installing professional quantitative & economics toolchain...${NC}"
pip install --upgrade pip setuptools wheel -q

# Install requirements with progress
pip install -r backend/requirements.txt -q

echo -e "${GREEN}✓ All professional packages installed successfully.${NC}"

echo -e "${YELLOW}[4/5] Executing full self-test verification suite...${NC}"
python3 cloud/test-all-engines.py

echo -e "${YELLOW}[5/5] Launching Finance Lab Server on port 8000...${NC}"
# Kill any existing server on 8000
fuser -k 8000/tcp 2>/dev/null || true

cd backend
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > ../finance-lab.log 2>&1 &
SERVER_PID=$!
cd "$ROOT_DIR"

sleep 3

# Check if server is running
if curl -s http://localhost:8000/api/status > /dev/null; then
    echo -e "${GREEN}${BOLD}✓ FINANCE LAB IS SUCCESSFULLY RUNNING IN GOOGLE CLOUD SHELL! (PID: $SERVER_PID)${NC}"
else
    echo -e "${RED}✗ Server failed to start. Showing logs:${NC}"
    cat finance-lab.log
    exit 1
fi

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}КАК ОТКРЫТЬ ВЕБ-ПАНЕЛЬ ИЗ GOOGLE CLOUD SHELL:${NC}"
echo -e "1. Нажмите кнопку ${YELLOW}«Веб-просмотр» (Web Preview)${NC} в правом верхнем углу Cloud Shell."
echo -e "2. Выберите ${BOLD}«Изменить порт» (Change port) -> 8000${NC} и нажмите «Открыть»."
echo -e "   Или перейдите по ссылке прямо в браузере."
echo ""
echo -e "${BOLD}ДУБЛИРОВАНИЕ ТЕРМИНАЛА:${NC}"
echo -e "Запуск tmate для зеркалирования терминала в локальную командную строку Windows..."
echo -e "${CYAN}═══════════════════════════════════════════════════════════════════${NC}"
echo ""

tmate -F
