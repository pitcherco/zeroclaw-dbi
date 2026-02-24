#!/bin/bash
# Load secrets from Azure Key Vault via VM Managed Identity
# Called as ExecStartPre in the zeroclaw.service systemd unit
set -euo pipefail

VAULT_NAME="kv-zeroclaw-sbx-eastus"
CONFIG_TEMPLATE="/etc/zeroclaw/config.toml.template"
CONFIG_TARGET="/home/zeroclaw/.zeroclaw/config.toml"

echo "[load-secrets] Fetching Key Vault access token via Managed Identity..."
TOKEN=$(curl -s \
    'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://vault.azure.net' \
    -H 'Metadata: true' | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
    echo "[load-secrets] ERROR: Failed to get Managed Identity token"
    exit 1
fi

VAULT="https://${VAULT_NAME}.vault.azure.net"

fetch_secret() {
    local name=$1
    local value
    value=$(curl -s "${VAULT}/secrets/${name}?api-version=7.4" \
        -H "Authorization: Bearer ${TOKEN}" | jq -r '.value')
    if [ -z "$value" ] || [ "$value" = "null" ]; then
        echo "[load-secrets] WARNING: Secret '${name}' not found or empty"
        return 1
    fi
    echo "$value"
}

echo "[load-secrets] Fetching secrets..."
AZURE_OPENAI_KEY=$(fetch_secret "azure-openai-key")
IMAP_PASSWORD=$(fetch_secret "imap-password")
GATEWAY_TOKEN=$(fetch_secret "gateway-pairing-token" 2>/dev/null || echo "")

echo "[load-secrets] Injecting secrets into config..."
cp "$CONFIG_TEMPLATE" "$CONFIG_TARGET"
sed -i "s|<AZURE_OPENAI_KEY>|${AZURE_OPENAI_KEY}|g" "$CONFIG_TARGET"
sed -i "s|<IMAP_PASSWORD>|${IMAP_PASSWORD}|g" "$CONFIG_TARGET"
if [ -n "$GATEWAY_TOKEN" ]; then
    sed -i "s|<GATEWAY_TOKEN>|${GATEWAY_TOKEN}|g" "$CONFIG_TARGET"
fi

chown zeroclaw:zeroclaw "$CONFIG_TARGET"
chmod 600 "$CONFIG_TARGET"

echo "[load-secrets] Config written to ${CONFIG_TARGET}"

# Also export secrets for the Teams adapter service
ENV_FILE="/etc/zeroclaw/teams-adapter.env"
BOT_APP_ID=$(fetch_secret "m365-app-id" 2>/dev/null || echo "")
BOT_SECRET=$(fetch_secret "bot-client-secret")

cat > "$ENV_FILE" <<EOF
ZEROCLAW_ADAPTER_BOT_APP_ID=${BOT_APP_ID}
ZEROCLAW_ADAPTER_BOT_APP_SECRET=${BOT_SECRET}
ZEROCLAW_ADAPTER_ZEROCLAW_GATEWAY_URL=http://127.0.0.1:42617
ZEROCLAW_ADAPTER_ZEROCLAW_GATEWAY_TOKEN=${GATEWAY_TOKEN}
EOF

chmod 600 "$ENV_FILE"
echo "[load-secrets] Teams adapter env written to ${ENV_FILE}"
