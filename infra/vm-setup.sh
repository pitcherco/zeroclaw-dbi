#!/bin/bash
# VM Setup Script for ZeroClaw POC
# Run on vm-zeroclaw-sbx-eastus after first SSH
# Usage: sudo bash vm-setup.sh
set -euo pipefail

echo "=== ZeroClaw POC VM Setup ==="

# --- System packages ---
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq build-essential curl git ca-certificates gnupg jq caddy

# --- Rust (for building ZeroClaw) ---
echo "[2/7] Installing Rust..."
if ! command -v cargo &>/dev/null; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
fi

# --- Node.js 22 LTS (for m365 CLI) ---
echo "[3/7] Installing Node.js 22 LTS..."
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y -qq nodejs
fi

# --- m365 CLI ---
echo "[4/7] Installing CLI for Microsoft 365..."
if ! command -v m365 &>/dev/null; then
    npm install -g @pnp/cli-microsoft365
fi

# --- Azure CLI ---
echo "[5/7] Installing Azure CLI..."
if ! command -v az &>/dev/null; then
    curl -sL https://aka.ms/InstallAzureCLIDeb | bash
fi

# --- Create zeroclaw system user ---
echo "[6/7] Creating zeroclaw user and directories..."
if ! id zeroclaw &>/dev/null; then
    useradd -r -m -d /home/zeroclaw -s /bin/bash zeroclaw
fi
mkdir -p /opt/zeroclaw /opt/teams-adapter /home/zeroclaw/.zeroclaw /etc/zeroclaw
chown -R zeroclaw:zeroclaw /opt/zeroclaw /home/zeroclaw

# --- Python venv for Teams adapter ---
echo "[7/7] Setting up Python venv for Teams adapter..."
apt-get install -y -qq python3.12-venv
python3 -m venv /opt/teams-adapter/.venv
/opt/teams-adapter/.venv/bin/pip install -q \
    botbuilder-core \
    botbuilder-integration-aiohttp \
    aiohttp \
    pydantic-settings

echo ""
echo "=== VM Setup Complete ==="
echo "Next steps:"
echo "  1. Clone ZeroClaw:  git clone https://github.com/pitcherco/zeroclaw-dbi.git /opt/zeroclaw"
echo "  2. Build ZeroClaw:  cd /opt/zeroclaw && ./bootstrap.sh --force-source-build"
echo "  3. Deploy config:   cp config.toml /home/zeroclaw/.zeroclaw/"
echo "  4. Deploy adapter:  cp -r teams_adapter /opt/teams-adapter/"
echo "  5. Start services:  systemctl enable --now zeroclaw teams-adapter"
