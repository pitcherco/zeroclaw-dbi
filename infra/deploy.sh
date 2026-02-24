#!/bin/bash
# Deploy ZeroClaw POC to vm-zeroclaw-sbx-eastus
# Run from the zeroclaw-dbi repo root on the VM
set -euo pipefail

echo "=== Deploying ZeroClaw POC ==="

# --- 1. Clone and build ZeroClaw ---
if [ ! -d /opt/zeroclaw/.git ]; then
    echo "[1/6] Cloning ZeroClaw..."
    git clone https://github.com/pitcherco/zeroclaw-dbi.git /opt/zeroclaw
    cd /opt/zeroclaw
    git checkout dbi/poc
    echo "[1/6] Building ZeroClaw..."
    ./bootstrap.sh --force-source-build
else
    echo "[1/6] ZeroClaw already cloned, skipping."
fi

# --- 2. Deploy config template ---
echo "[2/6] Deploying config template..."
sudo cp infra/config.toml.template /etc/zeroclaw/config.toml.template
sudo cp infra/load-secrets.sh /etc/zeroclaw/load-secrets.sh
sudo chmod +x /etc/zeroclaw/load-secrets.sh

# --- 3. Deploy Teams adapter ---
echo "[3/6] Deploying Teams adapter..."
sudo cp -r python/teams_adapter /opt/teams-adapter/
/opt/teams-adapter/.venv/bin/pip install -q -r dbi/requirements.txt

# --- 4. Deploy systemd services ---
echo "[4/6] Installing systemd services..."
sudo cp infra/zeroclaw.service /etc/systemd/system/
sudo cp infra/teams-adapter.service /etc/systemd/system/
sudo systemctl daemon-reload

# --- 5. Configure Caddy ---
echo "[5/6] Configuring Caddy reverse proxy..."
sudo cp infra/Caddyfile /etc/caddy/Caddyfile
sudo systemctl restart caddy

# --- 6. Start services ---
echo "[6/6] Starting services..."
sudo systemctl enable --now zeroclaw
sudo systemctl enable --now teams-adapter

echo ""
echo "=== Deployment Complete ==="
echo "Health check: curl http://localhost:42617/health"
echo "Teams adapter: curl https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/health"
echo "Logs: journalctl -u zeroclaw -f"
echo "      journalctl -u teams-adapter -f"
