# ZeroClaw POC — VM Deployment Execution Plan

**Date**: 2026-02-24
**Target**: `vm-zeroclaw-sbx-eastus` (Standard_B2s, Ubuntu 24.04, East US)
**Branch**: `dbi/poc`
**Operator**: DBI DevOps team

---

## 1. Pre-Flight Checklist

Run every item below **from your local workstation** before SSHing into the VM. All checks must pass before proceeding.

### 1.1 SSH Connectivity

```bash
ssh -o ConnectTimeout=10 zeroclaw@vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com "echo OK"
```

**Expected output**: `OK`

> **If this fails**: Check NSG rule for port 22 and confirm the VM is running:
> ```bash
> az vm show -g rg-zeroclaw-sbx-eastus -n vm-zeroclaw-sbx-eastus --query "powerState" -o tsv
> ```

### 1.2 DNS Resolution

```bash
nslookup vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com
```

**Expected**: Resolves to `172.178.57.169`

### 1.3 Key Vault Exists and Contains Expected Secrets

```bash
az keyvault show --name kv-zeroclaw-sbx-eastus --query "properties.vaultUri" -o tsv
```

**Expected**: `https://kv-zeroclaw-sbx-eastus.vault.azure.net/`

```bash
for secret in azure-openai-key imap-password bot-client-secret m365-app-id; do
  echo -n "$secret: "
  az keyvault secret show --vault-name kv-zeroclaw-sbx-eastus --name "$secret" --query "name" -o tsv 2>/dev/null || echo "MISSING"
done
```

**Expected**: All four secrets print their names. If any say `MISSING`, create them before proceeding.

### 1.4 Azure OpenAI Endpoint Responsive

```bash
az cognitiveservices account show -g rg-zeroclaw-sbx-eastus -n oai-zeroclaw-sbx-eastus --query "properties.endpoint" -o tsv
```

**Expected**: `https://oai-zeroclaw-sbx-eastus.openai.azure.com/`

```bash
curl -s -o /dev/null -w "%{http_code}" \
  "https://oai-zeroclaw-sbx-eastus.openai.azure.com/openai/models?api-version=2024-02-01" \
  -H "api-key: $(az keyvault secret show --vault-name kv-zeroclaw-sbx-eastus --name azure-openai-key --query value -o tsv)"
```

**Expected**: `200`

### 1.5 Bot Service Messaging Endpoint

```bash
az bot show -g rg-zeroclaw-sbx-eastus -n bot-zeroclaw-sbx-eastus --query "properties.endpoint" -o tsv
```

**Expected**: `https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/api/messages`

> **If wrong**, update it:
> ```bash
> az bot update -g rg-zeroclaw-sbx-eastus -n bot-zeroclaw-sbx-eastus \
>   --endpoint "https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/api/messages"
> ```

### 1.6 NSG Rules Allow Inbound 443 and 22

```bash
az network nsg rule list -g rg-zeroclaw-sbx-eastus --nsg-name nsg-zeroclaw-sbx-eastus \
  --query "[?direction=='Inbound'].{Name:name, Port:destinationPortRange, Access:access}" -o table
```

**Expected**: Rules for ports `22` and `443` both with `Access: Allow`

### 1.7 VM Managed Identity Has Key Vault Secrets User Role

```bash
VM_PRINCIPAL=$(az vm show -g rg-zeroclaw-sbx-eastus -n vm-zeroclaw-sbx-eastus \
  --query "identity.principalId" -o tsv)
KV_ID=$(az keyvault show --name kv-zeroclaw-sbx-eastus --query "id" -o tsv)

az role assignment list --assignee "$VM_PRINCIPAL" --scope "$KV_ID" \
  --query "[].roleDefinitionName" -o tsv
```

**Expected**: Output includes `Key Vault Secrets User`

> **If missing**:
> ```bash
> az role assignment create --assignee "$VM_PRINCIPAL" --role "Key Vault Secrets User" --scope "$KV_ID"
> ```

### 1.8 Email Mailbox Active

Verify `Zero@dirtybirdusa.com` can be reached via IMAP:

```bash
openssl s_client -connect outlook.office365.com:993 -quiet 2>/dev/null <<EOF | head -1
EOF
```

**Expected**: `* OK The Microsoft Exchange IMAP4 service is ready.`

> **NOTE**: Actual IMAP auth cannot be tested from outside without credentials. This verifies the server is accepting connections. Full validation happens in Phase 5.

### 1.9 Pre-Flight Summary

| Check | Status |
|-------|--------|
| SSH connectivity | ☐ |
| DNS resolution | ☐ |
| Key Vault secrets (4/4) | ☐ |
| Azure OpenAI reachable | ☐ |
| Bot messaging endpoint correct | ☐ |
| NSG rules (22 + 443) | ☐ |
| Managed Identity → KV role | ☐ |
| IMAP server reachable | ☐ |

**Proceed only when all boxes are checked.**

---

## 2. Phase 1: VM Bootstrap

### Goal

Install all system-level dependencies (Rust, Node.js 22, m365 CLI, Azure CLI, Caddy, Python 3.12 venv) and create the `zeroclaw` system user with the correct directory structure.

### Prerequisites

- Pre-flight checklist complete (all ☐ → ☑)
- SSH access to the VM as a user with `sudo` privileges

### Steps

**Step 1**: SSH into the VM.

```bash
ssh zeroclaw@vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com
```

> **NOTE**: If `zeroclaw` user doesn't exist yet (fresh VM), SSH as the admin user provisioned during VM creation, then the script will create the `zeroclaw` user.

**Step 2**: Clone the repository to a temporary location for the infra scripts.

```bash
cd /tmp
git clone https://github.com/pitcherco/zeroclaw-dbi.git zeroclaw-dbi-infra
cd zeroclaw-dbi-infra
git checkout dbi/poc
```

**Step 3**: Add swap space (critical for the 4GB B2s VM — build will OOM without it).

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

**Step 4**: Run the VM setup script.

```bash
sudo bash infra/vm-setup.sh
```

**Expected output** (final lines):

```
=== VM Setup Complete ===
Next steps:
  1. Clone ZeroClaw:  git clone https://github.com/pitcherco/zeroclaw-dbi.git /opt/zeroclaw
  2. Build ZeroClaw:  cd /opt/zeroclaw && ./bootstrap.sh --force-source-build
  ...
```

The script installs 7 components in order:
1. System packages (`build-essential`, `curl`, `git`, `ca-certificates`, `gnupg`, `jq`, `caddy`)
2. Rust via `rustup` (for the `zeroclaw` admin user)
3. Node.js 22 LTS via NodeSource
4. m365 CLI (`@pnp/cli-microsoft365`) globally
5. Azure CLI
6. `zeroclaw` system user + directories (`/opt/zeroclaw`, `/opt/teams-adapter`, `/home/zeroclaw/.zeroclaw`, `/etc/zeroclaw`)
7. Python 3.12 venv at `/opt/teams-adapter/.venv` with Bot Framework packages

**Step 5**: Source the Rust environment (needed for the current shell session).

```bash
source "$HOME/.cargo/env"
```

### Verification

```bash
# All 7 components installed
cargo --version         # Expected: cargo 1.x.x
node --version          # Expected: v22.x.x
m365 --version          # Expected: x.x.x
az --version | head -1  # Expected: azure-cli x.x.x
caddy version           # Expected: v2.x.x
python3 --version       # Expected: Python 3.12.x
/opt/teams-adapter/.venv/bin/python --version  # Expected: Python 3.12.x

# User and directories
id zeroclaw             # Expected: uid=xxx(zeroclaw) gid=xxx(zeroclaw)
ls -la /opt/zeroclaw    # Expected: exists, owned by zeroclaw
ls -la /opt/teams-adapter/.venv/bin/python  # Expected: exists
ls -la /home/zeroclaw/.zeroclaw  # Expected: exists, owned by zeroclaw
ls -la /etc/zeroclaw    # Expected: exists

# Swap active
free -h | grep Swap     # Expected: Swap total >= 4.0G

# Python packages in venv
/opt/teams-adapter/.venv/bin/pip list | grep -E "botbuilder|aiohttp|pydantic"
# Expected: botbuilder-core, botbuilder-integration-aiohttp, aiohttp, pydantic-settings
```

### Failure Modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `apt-get update` fails | Stale package cache or DNS issue | `sudo apt-get clean && sudo apt-get update` |
| `rustup` install hangs | Network/proxy issue | Check `curl -sSf https://sh.rustup.rs` manually |
| Node.js install fails | NodeSource GPG key issue | Install manually: `curl -fsSL https://deb.nodesource.com/setup_22.x \| sudo -E bash -` |
| `npm install -g` fails with EACCES | npm global dir permissions | `sudo npm install -g @pnp/cli-microsoft365` |
| `python3.12-venv` not found | Ubuntu 24 changed package names | Try `sudo apt-get install python3-venv` |
| `useradd` fails | User already exists | OK — the script checks `if ! id zeroclaw` |
| Swap creation fails | Filesystem doesn't support fallocate | Use `sudo dd if=/dev/zero of=/swapfile bs=1G count=4` instead |

### Rollback

```bash
# Remove user and directories
sudo userdel -r zeroclaw
sudo rm -rf /opt/zeroclaw /opt/teams-adapter /etc/zeroclaw

# Remove swap
sudo swapoff /swapfile
sudo rm /swapfile
sudo sed -i '/swapfile/d' /etc/fstab

# Packages can be left installed (they don't affect anything)
```

### Estimated Duration

10–15 minutes (mostly package downloads)

---

## 3. Phase 2: Build ZeroClaw from Source

### Goal

Clone the ZeroClaw repository into `/opt/zeroclaw`, checkout the `dbi/poc` branch, and compile the Rust binary.

### Prerequisites

- Phase 1 complete (Rust toolchain, swap space, zeroclaw user and dirs exist)

### Steps

**Step 1**: Clone the repo into the production location.

```bash
sudo git clone https://github.com/pitcherco/zeroclaw-dbi.git /opt/zeroclaw
sudo chown -R zeroclaw:zeroclaw /opt/zeroclaw
```

**Step 2**: Switch to the zeroclaw user and checkout the correct branch.

```bash
sudo -u zeroclaw bash -c '
  cd /opt/zeroclaw
  git checkout dbi/poc
'
```

**Step 3**: Ensure Rust is available for the `zeroclaw` user.

```bash
# If rustup was installed as root during Phase 1, the zeroclaw user needs it too
sudo -u zeroclaw bash -c '
  if ! command -v cargo &>/dev/null; then
    curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
  fi
  cargo --version
'
```

**Step 4**: Run the bootstrap script to build from source.

```bash
sudo -u zeroclaw bash -c '
  source "$HOME/.cargo/env"
  cd /opt/zeroclaw
  ./bootstrap.sh --force-source-build
'
```

> **WARNING**: This will take **10–20 minutes** on a Standard_B2s (2 vCPU, 4 GB RAM + 4 GB swap). Monitor with `top` or `htop` in a second SSH session. If the process is killed (OOM), see failure modes below.

The `bootstrap.sh` script:
1. Delegates to `scripts/bootstrap.sh` via `zeroclaw_install.sh`
2. With `--force-source-build`, it runs `cargo build --release --locked`
3. Then `cargo install --path . --force --locked` (installs to `~/.cargo/bin/zeroclaw`)

> **NOTE**: The binary will be at `/home/zeroclaw/.cargo/bin/zeroclaw` after `cargo install`. The systemd unit expects it at `/opt/zeroclaw/target/release/zeroclaw`. Verify which location is populated after build and adjust accordingly.

**Step 5**: Verify the binary location and create a symlink if needed.

```bash
# Check where the binary ended up
sudo -u zeroclaw bash -c '
  ls -la /opt/zeroclaw/target/release/zeroclaw 2>/dev/null
  ls -la /home/zeroclaw/.cargo/bin/zeroclaw 2>/dev/null
'

# If the binary is only in ~/.cargo/bin, create the expected path
sudo -u zeroclaw bash -c '
  if [ ! -f /opt/zeroclaw/target/release/zeroclaw ] && [ -f /home/zeroclaw/.cargo/bin/zeroclaw ]; then
    mkdir -p /opt/zeroclaw/target/release
    cp /home/zeroclaw/.cargo/bin/zeroclaw /opt/zeroclaw/target/release/zeroclaw
  fi
'
```

### Verification

```bash
# Binary exists and is executable
ls -la /opt/zeroclaw/target/release/zeroclaw
# Expected: -rwxr-xr-x ... zeroclaw

# Binary runs
sudo -u zeroclaw /opt/zeroclaw/target/release/zeroclaw --version
# Expected: zeroclaw <version>

# Binary is not stripped (reasonable size)
du -h /opt/zeroclaw/target/release/zeroclaw
# Expected: ~20-50 MB

# Correct branch
cd /opt/zeroclaw && git branch --show-current
# Expected: dbi/poc
```

### Failure Modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Build killed (signal 9) | OOM — insufficient RAM + swap | Increase swap to 8 GB: `sudo fallocate -l 8G /swapfile2 && sudo mkswap /swapfile2 && sudo swapon /swapfile2`. Or set `CARGO_BUILD_JOBS=1` to limit parallelism. |
| `cargo build` fails with missing system lib | Missing C dependency | Check error for library name, install via `apt-get install libXXX-dev` |
| `error: failed to select a version for ...` | Cargo.lock mismatch | Run `cargo update` then retry |
| `git clone` auth fails | Private repo, no SSH key | Set up deploy key: `ssh-keygen -t ed25519` and add to GitHub repo settings |
| `cargo build --locked` fails | Cargo.lock out of date | Try without `--locked` for POC, or run `cargo generate-lockfile` first |
| Bootstrap script fails preflight checks | RAM/disk below thresholds | Set `ZEROCLAW_BOOTSTRAP_MIN_RAM_MB=1024` to lower the threshold (swap makes up the difference) |

### Rollback

```bash
sudo rm -rf /opt/zeroclaw
sudo -u zeroclaw rm -rf /home/zeroclaw/.cargo/registry
# Re-clone if needed
```

### Estimated Duration

10–20 minutes (Rust compilation on 2 vCPU)

---

## 4. Phase 3: m365 CLI Certificate Authentication

### Goal

Generate a self-signed certificate, attach it to the `appreg-zeroclaw-m365-sbx` App Registration, store the private key in Key Vault, and authenticate the m365 CLI on the VM.

### Prerequisites

- Phase 1 complete (m365 CLI installed, `zeroclaw` user exists)
- An Azure AD Global Admin or Application Admin must grant admin consent for the App Registration's API permissions

> **CRITICAL**: Before starting this phase, confirm with your IT admin that `appreg-zeroclaw-m365-sbx` (ID: `836086a7-0308-4c57-a817-5699613f6d8c`) has the following **Application** permissions with **admin consent granted**:
> - `Sites.ReadWrite.All`
> - `Mail.ReadWrite`
> - `Calendars.Read`
> - `Files.ReadWrite.All`
> - `User.Read.All`

### Steps

**Step 1**: Generate a self-signed certificate on the VM.

```bash
sudo mkdir -p /etc/zeroclaw
openssl req -x509 -newkey rsa:4096 \
  -keyout /tmp/m365-key.pem \
  -out /tmp/m365-cert.pem \
  -days 365 -nodes \
  -subj "/CN=zeroclaw-m365-sbx"
```

**Step 2**: Install the private key in the correct location with proper permissions.

```bash
sudo cp /tmp/m365-key.pem /etc/zeroclaw/m365-key.pem
sudo chown zeroclaw:zeroclaw /etc/zeroclaw/m365-key.pem
sudo chmod 600 /etc/zeroclaw/m365-key.pem
```

**Step 3**: Upload the public certificate to Azure AD App Registration.

> **This step must be done from a machine with Azure AD admin access.** It can be done from the portal or via CLI.

**Option A — Azure Portal**:
1. Go to Azure Portal → App registrations → `appreg-zeroclaw-m365-sbx`
2. Certificates & secrets → Certificates → Upload certificate
3. Upload `/tmp/m365-cert.pem` (the public cert, NOT the key)

**Option B — Azure CLI** (from a machine with admin access):

```bash
# Copy the cert to your local machine first, then:
az ad app credential reset \
  --id 836086a7-0308-4c57-a817-5699613f6d8c \
  --cert @m365-cert.pem \
  --append
```

> **WARNING**: `--append` is critical. Without it, existing credentials are replaced.

**Step 4**: Store the private key in Key Vault as a backup.

```bash
az keyvault secret set \
  --vault-name kv-zeroclaw-sbx-eastus \
  --name m365-cert-pem \
  --file /tmp/m365-key.pem
```

**Step 5**: Clean up temporary files.

```bash
rm -f /tmp/m365-key.pem /tmp/m365-cert.pem
```

**Step 6**: Authenticate the m365 CLI on the VM as the `zeroclaw` user.

```bash
sudo -u zeroclaw m365 login \
  --authType certificate \
  --certificateFile /etc/zeroclaw/m365-key.pem \
  --appId "836086a7-0308-4c57-a817-5699613f6d8c" \
  --tenant "dirtybirdusa.com"
```

**Expected output**: `Successfully logged in.` (or similar confirmation)

**Step 7**: Grant admin consent (if not already done).

> **This requires a Global Admin.** From the Azure Portal:
> 1. Go to App registrations → `appreg-zeroclaw-m365-sbx`
> 2. API permissions → Grant admin consent for Dirty Bird Industries
> 3. Confirm all permissions show green checkmarks

### Verification

```bash
# m365 CLI is authenticated
sudo -u zeroclaw m365 status
# Expected: Logged in to https://dirtybirdusa.com

# Can query Graph API
sudo -u zeroclaw m365 spo site list --output json | head -5
# Expected: JSON array of SharePoint sites (not an auth error)

# Certificate file has correct permissions
ls -la /etc/zeroclaw/m365-key.pem
# Expected: -rw------- 1 zeroclaw zeroclaw ...

# Certificate in Key Vault
az keyvault secret show --vault-name kv-zeroclaw-sbx-eastus --name m365-cert-pem --query "name" -o tsv
# Expected: m365-cert-pem
```

### Failure Modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `m365 login` returns `AADSTS700016` | App ID wrong or not found in tenant | Verify app ID: `az ad app show --id 836086a7-0308-4c57-a817-5699613f6d8c` |
| `m365 login` returns `AADSTS700027` | Certificate not uploaded to app registration or thumbprint mismatch | Re-upload the public cert to the app registration |
| `m365 spo site list` returns `Insufficient privileges` | Admin consent not granted | Ask Global Admin to grant consent in portal |
| `m365 login` returns `AADSTS50049` | Tenant name wrong | Use tenant ID instead: `--tenant <tenant-id>` |
| `az keyvault secret set` fails with 403 | Your identity lacks `Key Vault Secrets Officer` | Run this from a machine with the right role, or use portal |

### Rollback

```bash
# Remove certificate from app registration (portal or CLI)
az ad app credential delete --id 836086a7-0308-4c57-a817-5699613f6d8c --key-id <credential-key-id>

# Remove from Key Vault
az keyvault secret delete --vault-name kv-zeroclaw-sbx-eastus --name m365-cert-pem

# Remove from VM
sudo rm -f /etc/zeroclaw/m365-key.pem

# Logout m365 CLI
sudo -u zeroclaw m365 logout
```

### Estimated Duration

10–15 minutes (plus time waiting for admin consent if not pre-approved)

---

## 5. Phase 4: Deploy Config & Services

### Goal

Deploy the ZeroClaw config template, secrets loader, Teams adapter code, systemd unit files, and Caddy reverse proxy configuration.

### Prerequisites

- Phase 2 complete (ZeroClaw binary built at `/opt/zeroclaw/target/release/zeroclaw`)
- Phase 3 complete (m365 CLI authenticated)
- Key Vault contains: `azure-openai-key`, `imap-password`, `bot-client-secret`, `m365-app-id`

### Steps

**Step 1**: Deploy the config template and secrets loader.

```bash
sudo cp /opt/zeroclaw/infra/config.toml.template /etc/zeroclaw/config.toml.template
sudo cp /opt/zeroclaw/infra/load-secrets.sh /etc/zeroclaw/load-secrets.sh
sudo chmod +x /etc/zeroclaw/load-secrets.sh
sudo chown root:root /etc/zeroclaw/config.toml.template /etc/zeroclaw/load-secrets.sh
```

**Step 2**: Deploy the Teams adapter Python code.

```bash
sudo cp -r /opt/zeroclaw/python/teams_adapter /opt/teams-adapter/
sudo chown -R zeroclaw:zeroclaw /opt/teams-adapter/

# Install Python dependencies from the DBI requirements file
/opt/teams-adapter/.venv/bin/pip install -q -r /opt/zeroclaw/dbi/requirements.txt
```

**Step 3**: Deploy systemd service units.

```bash
sudo cp /opt/zeroclaw/infra/zeroclaw.service /etc/systemd/system/
sudo cp /opt/zeroclaw/infra/teams-adapter.service /etc/systemd/system/
sudo systemctl daemon-reload
```

**Step 4**: Deploy the Caddy reverse proxy configuration.

```bash
sudo cp /opt/zeroclaw/infra/Caddyfile /etc/caddy/Caddyfile
```

**Step 5**: Validate the Caddyfile syntax.

```bash
caddy validate --config /etc/caddy/Caddyfile
```

**Expected**: `Valid configuration`

**Step 6**: Create the Caddy log directory.

```bash
sudo mkdir -p /var/log/caddy
sudo chown caddy:caddy /var/log/caddy
```

**Step 7**: Test the secrets loader (dry run).

```bash
# Verify the VM can acquire a Managed Identity token
curl -s -H "Metadata: true" \
  "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://vault.azure.net" \
  | jq '.access_token | length'
```

**Expected**: A positive number (token string length), e.g., `1200` — confirms Managed Identity works.

**Step 8**: Run `load-secrets.sh` manually to verify it works.

```bash
sudo bash /etc/zeroclaw/load-secrets.sh
```

**Expected output**:

```
[load-secrets] Fetching Key Vault access token via Managed Identity...
[load-secrets] Fetching secrets...
[load-secrets] WARNING: Secret 'gateway-pairing-token' not found or empty
[load-secrets] Injecting secrets into config...
[load-secrets] Config written to /home/zeroclaw/.zeroclaw/config.toml
[load-secrets] Teams adapter env written to /etc/zeroclaw/teams-adapter.env
```

> **NOTE**: The `gateway-pairing-token` warning is expected — that secret doesn't exist yet. It will be created during Phase 5.

### Verification

```bash
# Config template deployed
ls -la /etc/zeroclaw/config.toml.template
# Expected: exists, readable

# Secrets loader is executable
ls -la /etc/zeroclaw/load-secrets.sh
# Expected: -rwxr-xr-x

# Config was generated with secrets injected (check it doesn't contain placeholders)
sudo grep -c '<AZURE_OPENAI_KEY>' /home/zeroclaw/.zeroclaw/config.toml
# Expected: 0 (zero occurrences — placeholder was replaced)

sudo grep -c '<IMAP_PASSWORD>' /home/zeroclaw/.zeroclaw/config.toml
# Expected: 0

# Config has correct permissions
ls -la /home/zeroclaw/.zeroclaw/config.toml
# Expected: -rw------- 1 zeroclaw zeroclaw

# Teams adapter code deployed
ls -la /opt/teams-adapter/teams_adapter/app.py
# Expected: exists

# Teams adapter env file exists
ls -la /etc/zeroclaw/teams-adapter.env
# Expected: -rw------- 1 root root

# Systemd units registered
systemctl list-unit-files | grep -E "zeroclaw|teams-adapter"
# Expected: zeroclaw.service  disabled
#           teams-adapter.service  disabled

# Caddyfile deployed
ls -la /etc/caddy/Caddyfile
# Expected: exists
```

### Failure Modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `load-secrets.sh` fails with "Failed to get Managed Identity token" | VM Managed Identity not configured | Assign system-managed identity: `az vm identity assign -g rg-zeroclaw-sbx-eastus -n vm-zeroclaw-sbx-eastus` |
| Token fetch returns `{"error":"..."}` | IMDS endpoint unreachable or wrong API version | Verify: `curl -s -H "Metadata:true" "http://169.254.169.254/metadata/instance?api-version=2021-02-01"` |
| Secret fetch returns `null` | Secret name mismatch or KV RBAC issue | Verify secret exists: `az keyvault secret list --vault-name kv-zeroclaw-sbx-eastus --query "[].name"` |
| `pip install` fails in venv | Network issue or package conflict | `pip install --no-cache-dir -r requirements.txt` |
| `caddy validate` fails | Syntax error in Caddyfile | Check Caddy docs; the Caddyfile format is sensitive to whitespace |
| Config still has `<GATEWAY_TOKEN>` placeholder | Expected — token doesn't exist yet | This is resolved in Phase 5 after gateway pairing |

### Rollback

```bash
sudo systemctl stop zeroclaw teams-adapter caddy 2>/dev/null
sudo rm -f /etc/systemd/system/zeroclaw.service /etc/systemd/system/teams-adapter.service
sudo systemctl daemon-reload
sudo rm -f /etc/zeroclaw/config.toml.template /etc/zeroclaw/load-secrets.sh
sudo rm -f /etc/zeroclaw/teams-adapter.env
sudo rm -f /home/zeroclaw/.zeroclaw/config.toml
sudo rm -rf /opt/teams-adapter/teams_adapter
sudo rm -f /etc/caddy/Caddyfile
```

### Estimated Duration

5–10 minutes

---

## 6. Phase 5: Start Services & Gateway Pairing

### Goal

Start the ZeroClaw daemon, complete the gateway pairing handshake, store the bearer token, restart services with the token, start the Teams adapter and Caddy.

### Prerequisites

- Phase 4 complete (all config, services, and Caddyfile deployed)
- `load-secrets.sh` ran successfully (at least `azure-openai-key` and `imap-password` injected)

### Steps

**Step 1**: Start Caddy first (so TLS is ready when Bot Service sends messages).

```bash
sudo systemctl enable --now caddy
```

**Step 2**: Start the ZeroClaw daemon.

```bash
sudo systemctl enable --now zeroclaw
```

**Step 3**: Wait ~10 seconds for ZeroClaw to start, then check logs for the pairing code.

```bash
# Wait for startup
sleep 10

# Find the pairing code
sudo journalctl -u zeroclaw --no-pager -n 50 | grep -i "pair"
```

**Expected**: A line containing a 6-digit pairing code, e.g.:

```
Gateway pairing code: 123456
```

> **NOTE**: The exact log format depends on the ZeroClaw version. If `grep "pair"` returns nothing, check the full startup log:
> ```bash
> sudo journalctl -u zeroclaw --no-pager -n 100
> ```
> Look for any mention of pairing, auth, gateway code, or token.

**Step 4**: Exchange the pairing code for a bearer token.

```bash
PAIR_CODE="<6-digit-code-from-step-3>"

curl -s -X POST http://localhost:42617/pair \
  -H "Content-Type: application/json" \
  -d "{\"code\":\"${PAIR_CODE}\"}"
```

**Expected**: JSON response containing a bearer token:

```json
{"token":"eyJ...long-jwt-or-opaque-token..."}
```

**Save this token** — you need it in the next steps.

**Step 5**: Store the gateway token in Key Vault.

```bash
GATEWAY_TOKEN="<token-from-step-4>"

az keyvault secret set \
  --vault-name kv-zeroclaw-sbx-eastus \
  --name gateway-pairing-token \
  --value "$GATEWAY_TOKEN"
```

> **WARNING**: Run this command and then immediately clear your shell history to avoid the token being in plaintext:
> ```bash
> history -c
> ```

**Step 6**: Restart ZeroClaw so `load-secrets.sh` picks up the new gateway token.

```bash
sudo systemctl restart zeroclaw
```

Wait ~10 seconds, then verify it came up clean:

```bash
sudo systemctl status zeroclaw --no-pager
```

**Expected**: `Active: active (running)`

**Step 7**: Verify the Teams adapter env file now has the gateway token.

```bash
sudo grep 'ZEROCLAW_ADAPTER_ZEROCLAW_GATEWAY_TOKEN' /etc/zeroclaw/teams-adapter.env | wc -c
```

**Expected**: A number > 40 (token + key name length), confirming the token was injected.

**Step 8**: Start the Teams adapter.

```bash
sudo systemctl enable --now teams-adapter
```

**Step 9**: Wait ~5 seconds and verify all three services are running.

```bash
sleep 5
for svc in caddy zeroclaw teams-adapter; do
  echo -n "$svc: "
  systemctl is-active "$svc"
done
```

**Expected**:

```
caddy: active
zeroclaw: active
teams-adapter: active
```

### Verification

```bash
# ZeroClaw gateway health
curl -s http://localhost:42617/health
# Expected: 200 OK (JSON body varies)

# Teams adapter health (checks both adapter + gateway reachability)
curl -s http://localhost:3978/health
# Expected: {"adapter": "ok", "zeroclaw_gateway": "ok"}

# External HTTPS endpoint
curl -s https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/health
# Expected: {"adapter": "ok", "zeroclaw_gateway": "ok"}

# TLS certificate is valid
curl -sI https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/health 2>&1 | grep -i "HTTP/"
# Expected: HTTP/2 200

# Check Caddy logs for TLS provisioning
sudo journalctl -u caddy --no-pager -n 30 | grep -i "tls\|certificate\|acme"
# Expected: Lines about obtaining certificate from Let's Encrypt

# No errors in service logs
sudo journalctl -u zeroclaw --no-pager -n 20 --priority err
# Expected: no output (no error-level log entries)

sudo journalctl -u teams-adapter --no-pager -n 20 --priority err
# Expected: no output
```

### Failure Modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| ZeroClaw exits immediately | Config parse error or missing required field | Check: `sudo journalctl -u zeroclaw --no-pager -n 50`. Run `sudo -u zeroclaw /opt/zeroclaw/target/release/zeroclaw doctor` |
| No pairing code in logs | Gateway pairing disabled or different auth mode in this build | Check ZeroClaw docs for gateway auth; may need `--pair` flag or config key |
| `curl /pair` returns 404 | Pairing endpoint not enabled | Check ZeroClaw gateway config; may need `[gateway] pairing = true` in config |
| `curl /pair` returns 401 | Code already used or expired | Restart ZeroClaw to get a new pairing code |
| Teams adapter fails to start | Missing env vars or Python import error | Check: `sudo journalctl -u teams-adapter --no-pager -n 50` |
| Caddy TLS fails | Let's Encrypt rate limit or DNS not resolving | Check: `sudo journalctl -u caddy --no-pager -n 50`. Try staging CA first: add `tls { issuer acme { ca https://acme-staging-v02.api.letsencrypt.org/directory } }` to Caddyfile |
| HTTPS endpoint returns 502 | Teams adapter not running or wrong port | Verify adapter is on port 3978: `ss -tlnp | grep 3978` |
| Gateway token empty after restart | `load-secrets.sh` failed to fetch new secret | Run `sudo bash /etc/zeroclaw/load-secrets.sh` manually and check output |

### Rollback

```bash
sudo systemctl stop teams-adapter zeroclaw caddy
sudo systemctl disable teams-adapter zeroclaw

# Remove gateway token from Key Vault
az keyvault secret delete --vault-name kv-zeroclaw-sbx-eastus --name gateway-pairing-token

# Clear generated config
sudo rm -f /home/zeroclaw/.zeroclaw/config.toml
sudo rm -f /etc/zeroclaw/teams-adapter.env
```

### Estimated Duration

10–15 minutes (including pairing ceremony and verification)

---

## 7. Phase 6: SharePoint & Identity Setup

### Goal

Verify the m365 CLI can access the mailbox and SharePoint, create the `ZeroClaw-Outputs` folder for agent output files, and confirm read/write operations work.

### Prerequisites

- Phase 3 complete (m365 CLI authenticated with certificate)
- Phase 5 complete (all services running)
- Admin consent granted for the App Registration's API permissions

### Steps

**Step 1**: Verify m365 CLI status.

```bash
sudo -u zeroclaw m365 status
```

**Expected**: `Logged in to https://dirtybirdusa.com`

**Step 2**: List accessible SharePoint sites.

```bash
sudo -u zeroclaw m365 spo site list --output json | jq '.[].Url'
```

**Expected**: A list of SharePoint site URLs. Identify the target site for the POC (e.g., `https://dirtybirdusa.sharepoint.com/sites/Projects`).

> **NOTE**: Record the target site URL — it's needed for the acceptance tests and the agent's system prompt. Replace `<TargetSite>` placeholders accordingly.

**Step 3**: Create the `ZeroClaw-Outputs` folder.

```bash
TARGET_SITE="https://dirtybirdusa.sharepoint.com/sites/<TargetSite>"

sudo -u zeroclaw m365 spo folder add \
  --webUrl "$TARGET_SITE" \
  --name "ZeroClaw-Outputs" \
  --parentFolderUrl "/Shared Documents"
```

**Expected**: JSON response with folder metadata (Name: `ZeroClaw-Outputs`).

> If the folder already exists, the command may error. That's OK — verify with:
> ```bash
> sudo -u zeroclaw m365 spo folder get \
>   --webUrl "$TARGET_SITE" \
>   --url "/Shared Documents/ZeroClaw-Outputs"
> ```

**Step 4**: Write a test file and read it back.

```bash
# Create a test file
echo "ZeroClaw POC test file - $(date)" > /tmp/zeroclaw-test.txt

# Upload to SharePoint
sudo -u zeroclaw m365 spo file add \
  --webUrl "$TARGET_SITE" \
  --folder "Shared Documents/ZeroClaw-Outputs" \
  --path /tmp/zeroclaw-test.txt

# Read it back
sudo -u zeroclaw m365 spo file get \
  --webUrl "$TARGET_SITE" \
  --url "/Shared Documents/ZeroClaw-Outputs/zeroclaw-test.txt" \
  --asFile \
  --path /tmp/zeroclaw-test-readback.txt

cat /tmp/zeroclaw-test-readback.txt
```

**Expected**: The content matches what was written.

**Step 5**: Verify email access (mailbox listing).

```bash
sudo -u zeroclaw m365 outlook mail message list --top 5 --output json | jq '.[].subject'
```

**Expected**: Recent email subjects from `Zero@dirtybirdusa.com` (or empty if no mail yet). The key is **no auth error**.

> **NOTE**: If this returns a permissions error, the app registration may need `Mail.ReadWrite` as an **Application** permission (not Delegated), and admin consent must be granted.

**Step 6**: Clean up test files.

```bash
rm -f /tmp/zeroclaw-test.txt /tmp/zeroclaw-test-readback.txt

# Optionally remove the test file from SharePoint
sudo -u zeroclaw m365 spo file remove \
  --webUrl "$TARGET_SITE" \
  --url "/Shared Documents/ZeroClaw-Outputs/zeroclaw-test.txt" \
  --force
```

### Verification

```bash
# m365 CLI authenticated
sudo -u zeroclaw m365 status
# Expected: Logged in

# Can list sites
sudo -u zeroclaw m365 spo site list --output text | head -5
# Expected: Site list output

# Outputs folder exists
sudo -u zeroclaw m365 spo folder get \
  --webUrl "$TARGET_SITE" \
  --url "/Shared Documents/ZeroClaw-Outputs" --output json | jq '.Name'
# Expected: "ZeroClaw-Outputs"

# ZeroClaw shell tool can call m365 (end-to-end through the agent)
curl -s -X POST http://localhost:42617/webhook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(sudo cat /etc/zeroclaw/teams-adapter.env | grep TOKEN | cut -d= -f2)" \
  -d '{"message":"List all SharePoint sites I have access to"}'
# Expected: JSON response with agent's answer containing site names
```

### Failure Modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Insufficient privileges` on spo commands | Missing admin consent for `Sites.ReadWrite.All` | Grant admin consent in Azure Portal |
| `Mail.ReadWrite` permission denied | Permission is Delegated instead of Application | Change to Application permission and re-grant consent |
| `spo folder add` returns 403 | Agent user doesn't have access to the site | Add the app to the site: portal → SharePoint Admin → Sites → Permissions |
| m365 CLI session expired | Certificate token expired | Re-login: `m365 login --authType certificate ...` |
| Webhook returns 401 | Gateway token mismatch | Check token in env file matches what's in Key Vault |

### Rollback

```bash
# Remove the outputs folder
sudo -u zeroclaw m365 spo folder remove \
  --webUrl "$TARGET_SITE" \
  --url "/Shared Documents/ZeroClaw-Outputs" \
  --force
```

### Estimated Duration

10–15 minutes

---

## 8. Phase 7: Teams App Sideload

### Goal

Package the Teams app manifest with placeholder icons and sideload it so users can DM and @mention ZeroClaw in Teams.

### Prerequisites

- Phase 5 complete (HTTPS endpoint live with valid TLS)
- Phase 6 complete (SharePoint access verified)
- Teams Admin Center access (or `m365 teams app publish` permissions)

### Steps

**Step 1**: Create placeholder icon images on the VM.

```bash
# Install ImageMagick for icon generation (lightweight)
sudo apt-get install -y -qq imagemagick

# Generate 192x192 color icon (orange background with "ZC" text)
convert -size 192x192 xc:"#FF6600" \
  -gravity center -pointsize 72 -fill white \
  -annotate 0 "ZC" \
  /tmp/color.png

# Generate 32x32 outline icon (transparent with orange border)
convert -size 32x32 xc:transparent \
  -stroke "#FF6600" -strokewidth 2 -fill none \
  -draw "roundrectangle 1,1 30,30 4,4" \
  -gravity center -pointsize 14 -fill "#FF6600" -stroke none \
  -annotate 0 "ZC" \
  /tmp/outline.png
```

> **NOTE**: If ImageMagick is not available or desired, create simple PNG icons on your local machine and SCP them to the VM. The icons are cosmetic for POC purposes.

**Step 2**: Package the Teams app manifest.

```bash
cd /tmp
mkdir -p zeroclaw-teams-app
cp /opt/zeroclaw/infra/teams-app/manifest.json zeroclaw-teams-app/
cp /tmp/color.png zeroclaw-teams-app/
cp /tmp/outline.png zeroclaw-teams-app/

cd zeroclaw-teams-app
zip -r /tmp/zeroclaw-teams-app.zip manifest.json color.png outline.png
```

**Step 3**: Validate the manifest package.

```bash
# Quick validation: check zip contents
unzip -l /tmp/zeroclaw-teams-app.zip
```

**Expected**:

```
  Length      Date    Time    Name
---------  ---------- -----   ----
     xxxx  2026-02-24 xx:xx   manifest.json
     xxxx  2026-02-24 xx:xx   color.png
     xxxx  2026-02-24 xx:xx   outline.png
---------                     -------
     xxxx                     3 files
```

**Step 4**: Upload the Teams app.

**Option A — m365 CLI** (recommended if permissions allow):

```bash
sudo -u zeroclaw m365 teams app publish \
  --filePath /tmp/zeroclaw-teams-app.zip
```

**Option B — Teams Admin Center** (if CLI publish lacks permissions):

1. Download the zip to your local machine: `scp zeroclaw@vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com:/tmp/zeroclaw-teams-app.zip .`
2. Go to [Teams Admin Center](https://admin.teams.microsoft.com) → Manage apps → Upload new app
3. Upload `zeroclaw-teams-app.zip`
4. Set availability: enable for the organization or specific users

**Option C — Direct sideload** (for testing only):

1. In Teams desktop/web, go to Apps → Manage your apps → Upload a custom app
2. Upload `zeroclaw-teams-app.zip`

**Step 5**: Verify the app appears in Teams.

1. Open Microsoft Teams
2. Search for "ZeroClaw Agent" in the Apps section
3. Install the app (Add to personal scope)
4. Open a DM with ZeroClaw Agent

**Expected**: The bot's welcome message appears:

> "Hi! I'm the ZeroClaw Teammate Agent. I can help you with M365 tasks — reading SharePoint files, generating reports, checking calendars, and more. Just DM me or @mention me in a channel."

### Verification

```bash
# App is published (via CLI)
sudo -u zeroclaw m365 teams app list --output json | jq '.[] | select(.displayName | test("ZeroClaw"))'
# Expected: JSON object for the ZeroClaw app

# Bot endpoint is reachable from the internet
curl -s -o /dev/null -w "%{http_code}" \
  https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/api/messages
# Expected: 405 (Method Not Allowed — it expects POST, this proves the endpoint is live)

# TLS certificate is valid
echo | openssl s_client -servername vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com \
  -connect vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com:443 2>/dev/null \
  | openssl x509 -noout -dates
# Expected: notBefore and notAfter dates showing valid certificate
```

### Failure Modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `teams app publish` returns 403 | Insufficient Teams admin permissions | Use Teams Admin Center instead |
| Manifest validation fails | Missing required fields or invalid bot ID | Verify `manifest.json` → `id` and `bots[0].botId` both match `c28eaa4a-e081-4de8-b9d8-81fbfc28feb2` |
| Bot doesn't respond in Teams | Bot Service endpoint wrong, or adapter not running | Verify endpoint in Bot Service; check `systemctl status teams-adapter` |
| Welcome message doesn't appear | `on_members_added_activity` not triggered | Try removing and re-adding the app |
| Icons look wrong | ImageMagick rendering issues | Replace with manually-created PNGs — any valid PNG of the right size works |

### Rollback

```bash
# Remove Teams app
sudo -u zeroclaw m365 teams app remove --id "<app-catalog-id>" --force

# Clean up packaging
rm -rf /tmp/zeroclaw-teams-app /tmp/zeroclaw-teams-app.zip /tmp/color.png /tmp/outline.png
```

### Estimated Duration

10–15 minutes

---

## 9. Validation Script

Save this as `/opt/zeroclaw/infra/validate-deployment.sh` on the VM and run after completing all phases.

```bash
#!/bin/bash
# ZeroClaw POC Deployment Validation Script
# Run as root or with sudo on the deployed VM
set -uo pipefail

PASS=0
FAIL=0
WARN=0

pass() { echo "  [PASS] $1"; ((PASS++)); }
fail() { echo "  [FAIL] $1"; ((FAIL++)); }
warn() { echo "  [WARN] $1"; ((WARN++)); }

echo "============================================="
echo "  ZeroClaw POC — Deployment Validation"
echo "  $(date -Iseconds)"
echo "============================================="
echo ""

# --- Section 1: Services ---
echo "--- 1. Systemd Services ---"

for svc in caddy zeroclaw teams-adapter; do
  if systemctl is-active --quiet "$svc"; then
    pass "$svc is active"
  else
    fail "$svc is NOT active"
  fi
done

for svc in caddy zeroclaw teams-adapter; do
  if systemctl is-enabled --quiet "$svc"; then
    pass "$svc is enabled (auto-start on boot)"
  else
    warn "$svc is NOT enabled for auto-start"
  fi
done

echo ""

# --- Section 2: Health Endpoints ---
echo "--- 2. Health Endpoints ---"

# ZeroClaw gateway
GW_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:42617/health 2>/dev/null)
if [ "$GW_STATUS" = "200" ]; then
  pass "ZeroClaw gateway /health → 200"
else
  fail "ZeroClaw gateway /health → $GW_STATUS (expected 200)"
fi

# Teams adapter local
ADAPTER_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3978/health 2>/dev/null)
if [ "$ADAPTER_STATUS" = "200" ]; then
  pass "Teams adapter /health → 200"
else
  fail "Teams adapter /health → $ADAPTER_STATUS (expected 200)"
fi

# Adapter health body check
ADAPTER_BODY=$(curl -s http://localhost:3978/health 2>/dev/null)
if echo "$ADAPTER_BODY" | grep -q '"zeroclaw_gateway": "ok"'; then
  pass "Adapter confirms gateway reachable"
elif echo "$ADAPTER_BODY" | grep -q '"zeroclaw_gateway":"ok"'; then
  pass "Adapter confirms gateway reachable"
else
  fail "Adapter reports gateway unreachable: $ADAPTER_BODY"
fi

# External HTTPS
HTTPS_STATUS=$(curl -sk -o /dev/null -w "%{http_code}" https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/health 2>/dev/null)
if [ "$HTTPS_STATUS" = "200" ]; then
  pass "HTTPS endpoint /health → 200"
else
  fail "HTTPS endpoint /health → $HTTPS_STATUS (expected 200)"
fi

echo ""

# --- Section 3: TLS Certificate ---
echo "--- 3. TLS Certificate ---"

CERT_INFO=$(echo | openssl s_client -servername vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com \
  -connect vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com:443 2>/dev/null \
  | openssl x509 -noout -dates 2>/dev/null)

if echo "$CERT_INFO" | grep -q "notAfter"; then
  EXPIRY=$(echo "$CERT_INFO" | grep "notAfter" | cut -d= -f2)
  EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || echo 0)
  NOW_EPOCH=$(date +%s)
  DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))
  if [ "$DAYS_LEFT" -gt 7 ]; then
    pass "TLS cert valid, expires in $DAYS_LEFT days ($EXPIRY)"
  elif [ "$DAYS_LEFT" -gt 0 ]; then
    warn "TLS cert expiring soon: $DAYS_LEFT days left ($EXPIRY)"
  else
    fail "TLS cert is expired or invalid"
  fi
else
  fail "Could not retrieve TLS certificate"
fi

echo ""

# --- Section 4: Key Vault Access ---
echo "--- 4. Key Vault Access (Managed Identity) ---"

TOKEN=$(curl -s \
  'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://vault.azure.net' \
  -H 'Metadata: true' 2>/dev/null | jq -r '.access_token' 2>/dev/null)

if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
  pass "Managed Identity token acquired"

  # Test fetching a known secret
  SECRET_CHECK=$(curl -s "https://kv-zeroclaw-sbx-eastus.vault.azure.net/secrets/azure-openai-key?api-version=7.4" \
    -H "Authorization: Bearer $TOKEN" 2>/dev/null | jq -r '.value' 2>/dev/null)
  if [ -n "$SECRET_CHECK" ] && [ "$SECRET_CHECK" != "null" ]; then
    pass "Key Vault secret fetch works (azure-openai-key)"
  else
    fail "Key Vault secret fetch failed"
  fi
else
  fail "Could not acquire Managed Identity token"
fi

echo ""

# --- Section 5: m365 CLI ---
echo "--- 5. m365 CLI Authentication ---"

M365_STATUS=$(sudo -u zeroclaw m365 status 2>&1)
if echo "$M365_STATUS" | grep -qi "logged in"; then
  pass "m365 CLI is authenticated"
else
  fail "m365 CLI is NOT authenticated: $M365_STATUS"
fi

echo ""

# --- Section 6: File Permissions ---
echo "--- 6. File Permissions ---"

CONFIG_PERMS=$(stat -c "%a" /home/zeroclaw/.zeroclaw/config.toml 2>/dev/null)
if [ "$CONFIG_PERMS" = "600" ]; then
  pass "config.toml permissions: 600"
else
  fail "config.toml permissions: $CONFIG_PERMS (expected 600)"
fi

ENV_PERMS=$(stat -c "%a" /etc/zeroclaw/teams-adapter.env 2>/dev/null)
if [ "$ENV_PERMS" = "600" ]; then
  pass "teams-adapter.env permissions: 600"
else
  fail "teams-adapter.env permissions: $ENV_PERMS (expected 600)"
fi

KEY_PERMS=$(stat -c "%a" /etc/zeroclaw/m365-key.pem 2>/dev/null)
if [ "$KEY_PERMS" = "600" ]; then
  pass "m365-key.pem permissions: 600"
else
  fail "m365-key.pem permissions: $KEY_PERMS (expected 600)"
fi

# Verify config has no plaintext placeholders
PLACEHOLDER_COUNT=$(grep -c '<AZURE_OPENAI_KEY>\|<IMAP_PASSWORD>\|<GATEWAY_TOKEN>' /home/zeroclaw/.zeroclaw/config.toml 2>/dev/null || echo 0)
if [ "$PLACEHOLDER_COUNT" = "0" ]; then
  pass "config.toml has no unresolved placeholders"
else
  fail "config.toml still has $PLACEHOLDER_COUNT unresolved placeholder(s)"
fi

echo ""

# --- Section 7: Service Restart Survival ---
echo "--- 7. Service Restart Test ---"

for svc in zeroclaw teams-adapter; do
  echo "  Restarting $svc..."
  systemctl restart "$svc"
  sleep 5
  if systemctl is-active --quiet "$svc"; then
    pass "$svc survived restart"
  else
    fail "$svc did NOT survive restart"
  fi
done

echo ""

# --- Section 8: Port Bindings ---
echo "--- 8. Port Bindings ---"

if ss -tlnp | grep -q ':443 '; then
  pass "Port 443 is listening (Caddy)"
else
  fail "Port 443 is NOT listening"
fi

if ss -tlnp | grep -q ':3978 '; then
  pass "Port 3978 is listening (Teams adapter)"
else
  fail "Port 3978 is NOT listening"
fi

if ss -tlnp | grep -q ':42617 '; then
  pass "Port 42617 is listening (ZeroClaw gateway)"
else
  fail "Port 42617 is NOT listening"
fi

echo ""

# --- Summary ---
echo "============================================="
echo "  RESULTS: $PASS passed, $FAIL failed, $WARN warnings"
echo "============================================="

if [ "$FAIL" -eq 0 ]; then
  echo "  >>> DEPLOYMENT VALIDATION: PASS <<<"
else
  echo "  >>> DEPLOYMENT VALIDATION: FAIL <<<"
  echo "  Review failures above before running acceptance tests."
fi

exit "$FAIL"
```

**Usage**:

```bash
sudo bash /opt/zeroclaw/infra/validate-deployment.sh
```

**Expected**: All checks `[PASS]`, final line `>>> DEPLOYMENT VALIDATION: PASS <<<`, exit code `0`.

---

## 10. Acceptance Test Procedures

### AT-1: Teams DM — Spreadsheet Summary

**Pre-conditions**:
- A file `TestData.xlsx` exists in a known SharePoint document library accessible to the m365 app registration
- The ZeroClaw agent is running and the Teams app is installed

**Setup steps**:

```bash
# Create test data locally
cat > /tmp/TestData.csv <<'EOF'
Month,Revenue,Expenses,Profit
Jan,120000,85000,35000
Feb,135000,90000,45000
Mar,128000,87000,41000
EOF

# Convert to XLSX (or just upload CSV; use xlsx if you have a converter)
# For POC, CSV is acceptable

# Upload to SharePoint
TARGET_SITE="https://dirtybirdusa.sharepoint.com/sites/<TargetSite>"
sudo -u zeroclaw m365 spo file add \
  --webUrl "$TARGET_SITE" \
  --folder "Shared Documents" \
  --path /tmp/TestData.csv
```

**Execution**:
1. Open Microsoft Teams
2. Open a DM with ZeroClaw Agent
3. Send: `Pull the numbers from TestData.csv in the <TargetSite> site and summarize`

**Expected result**: Bot responds in the DM with a summary of the spreadsheet data, mentioning the revenue, expenses, and profit numbers within **2 minutes**.

**Pass criteria**: Response arrives in the DM, contains numerical data from the file, and arrives within 2 minutes of the initial "Working on it..." message.

**Troubleshooting**:
1. Check `journalctl -u teams-adapter -f` — did the message arrive?
2. Check `journalctl -u zeroclaw -f` — did ZeroClaw process it?
3. Check `sudo -u zeroclaw m365 spo file list --webUrl "$TARGET_SITE" --folder "Shared Documents"` — is the file accessible?
4. Try the m365 command manually: `sudo -u zeroclaw m365 spo file get --webUrl "$TARGET_SITE" --url "/Shared Documents/TestData.csv" --asFile --path /tmp/test-dl.csv`

---

### AT-2: Teams Channel — @mention Status Report

**Pre-conditions**:
- ZeroClaw Agent is added to a Teams channel
- Documents exist in the channel's associated SharePoint site

**Setup steps**:

```bash
# Upload a doc to the site for the agent to summarize
cat > /tmp/ProjectStatus.txt <<'EOF'
Project Alpha: On track, 80% complete. Launch date: March 15.
Project Beta: Delayed by 2 weeks. Waiting on vendor approval.
Project Gamma: Complete. Final review pending.
EOF

sudo -u zeroclaw m365 spo file add \
  --webUrl "$TARGET_SITE" \
  --folder "Shared Documents" \
  --path /tmp/ProjectStatus.txt
```

**Execution**:
1. Open the Teams channel where ZeroClaw is added
2. Send: `@ZeroClaw Agent produce a short status report from the docs in the <TargetSite> site`

**Expected result**: Bot responds **in-thread** (reply to the message) with a summary of the documents within **2 minutes**.

**Pass criteria**: Response appears as a threaded reply, references document content, arrives within 2 minutes.

**Troubleshooting**:
1. Ensure the bot was added to the team (not just personal scope)
2. Check that `@ZeroClaw Agent` mention is properly detected — look at adapter logs for the cleaned message text
3. If no response, check `journalctl -u teams-adapter -f` for incoming activity

---

### AT-3: Email — Weekly Report Request

**Pre-conditions**:
- `Zero@dirtybirdusa.com` mailbox is active and ZeroClaw's email channel is running (IMAP IDLE connected)

**Setup steps**: No special setup needed beyond verified email channel.

**Execution**:
1. From any email account, send an email to `Zero@dirtybirdusa.com`
2. Subject: `Weekly Report Request`
3. Body: `Send me the weekly report`

**Expected result**: A reply email arrives within **5 minutes** with a generated report (or a response explaining what reports are available).

**Pass criteria**: Reply email arrives, is from `Zero@dirtybirdusa.com`, contains substantive content (not just an error message).

**Troubleshooting**:
1. Check IMAP connectivity: `openssl s_client -connect outlook.office365.com:993`
2. Check ZeroClaw email channel: `sudo -u zeroclaw /opt/zeroclaw/target/release/zeroclaw channel doctor`
3. Check logs: `journalctl -u zeroclaw -f | grep -i email`
4. Verify IMAP password: re-run `load-secrets.sh` and check for errors
5. Check spam/junk folders for the reply

---

### AT-4: Teams DM — Read File, Write Summary to SharePoint

**Pre-conditions**:
- `TestData.csv` (from AT-1) exists in SharePoint
- `ZeroClaw-Outputs` folder exists (created in Phase 6)

**Setup steps**: Use the test data from AT-1. Ensure the Outputs folder exists:

```bash
sudo -u zeroclaw m365 spo folder get \
  --webUrl "$TARGET_SITE" \
  --url "/Shared Documents/ZeroClaw-Outputs"
```

**Execution**:
1. Open a DM with ZeroClaw Agent in Teams
2. Send: `Read TestData.csv from the <TargetSite> site and write a summary to the ZeroClaw-Outputs folder`

**Expected result**: Bot responds confirming the file was written, and the file appears in the `ZeroClaw-Outputs` folder.

**Pass criteria**:
- Bot confirms the write in the DM response
- File exists in SharePoint:
  ```bash
  sudo -u zeroclaw m365 spo file list \
    --webUrl "$TARGET_SITE" \
    --folder "Shared Documents/ZeroClaw-Outputs" \
    --output json | jq '.[].Name'
  ```
  Output includes a new file (e.g., `summary.txt` or similar)

**Troubleshooting**:
1. Check ZeroClaw logs for the m365 commands it executed
2. Verify the agent's system prompt includes the correct SharePoint URL for writes
3. Try the write manually: `sudo -u zeroclaw m365 spo file add --webUrl "$TARGET_SITE" --folder "Shared Documents/ZeroClaw-Outputs" --path /tmp/test.txt`

---

### AT-5: Teams DM — List SharePoint Sites

**Pre-conditions**:
- m365 CLI authenticated
- ZeroClaw services running

**Setup steps**: None required.

**Execution**:
1. Open a DM with ZeroClaw Agent in Teams
2. Send: `List all SharePoint sites I have access to`

**Expected result**: Bot responds with a list of SharePoint site names/URLs.

**Pass criteria**: Response contains at least one SharePoint site URL, arrives within 1 minute.

**Troubleshooting**:
1. Run manually: `sudo -u zeroclaw m365 spo site list --output text`
2. If the agent says "no tool available", check that the shell tool is enabled in config
3. Check ZeroClaw logs to see if the m365 command was invoked

---

### Acceptance Test Summary

| Test | Message | Channel | Timeout | Key Verification |
|------|---------|---------|---------|------------------|
| AT-1 | "Pull the numbers from this spreadsheet and summarize" | Teams DM | 2 min | Response contains file data |
| AT-2 | "@ZeroClaw produce a short status report" | Teams Channel | 2 min | Threaded reply with document content |
| AT-3 | "Send me the weekly report" (email) | Email | 5 min | Reply email received |
| AT-4 | "Read TestData.csv, write summary to Outputs" | Teams DM | 2 min | New file in ZeroClaw-Outputs |
| AT-5 | "List all SharePoint sites" | Teams DM | 1 min | Response lists site URLs |

---

## 11. Rollback Playbook

Use this procedure to return the VM to a clean state if deployment fails catastrophically.

### Step 1: Stop and Disable All Services

```bash
sudo systemctl stop teams-adapter zeroclaw caddy
sudo systemctl disable teams-adapter zeroclaw caddy
```

### Step 2: Remove Systemd Units

```bash
sudo rm -f /etc/systemd/system/zeroclaw.service
sudo rm -f /etc/systemd/system/teams-adapter.service
sudo systemctl daemon-reload
```

### Step 3: Remove Deployed Files

```bash
# Config and secrets
sudo rm -rf /etc/zeroclaw

# Generated config
sudo rm -f /home/zeroclaw/.zeroclaw/config.toml

# ZeroClaw binary and source
sudo rm -rf /opt/zeroclaw

# Teams adapter code and venv
sudo rm -rf /opt/teams-adapter

# Caddy config (restore default)
sudo rm -f /etc/caddy/Caddyfile

# Temp build artifacts
sudo rm -rf /tmp/zeroclaw-*

# Swap (if desired)
sudo swapoff /swapfile 2>/dev/null
sudo rm -f /swapfile
sudo sed -i '/swapfile/d' /etc/fstab
```

### Step 4: Revoke m365 CLI Certificate

```bash
# Logout m365 CLI
sudo -u zeroclaw m365 logout 2>/dev/null

# Remove cert from App Registration (from an admin machine)
# First, find the credential key ID:
az ad app credential list --id 836086a7-0308-4c57-a817-5699613f6d8c --query "[].keyId" -o tsv

# Then delete it:
az ad app credential delete --id 836086a7-0308-4c57-a817-5699613f6d8c --key-id "<key-id>"
```

### Step 5: Clean Up Generated Key Vault Secrets

Only delete secrets that were **generated during deployment** (not pre-existing ones):

```bash
# These were generated during deployment:
az keyvault secret delete --vault-name kv-zeroclaw-sbx-eastus --name gateway-pairing-token
az keyvault secret delete --vault-name kv-zeroclaw-sbx-eastus --name m365-cert-pem
```

> **WARNING**: Do NOT delete these pre-existing secrets:
> - `azure-openai-key`
> - `imap-password`
> - `bot-client-secret`
> - `m365-app-id`

### Step 6: Remove Teams App

```bash
# From admin machine or Teams Admin Center
# Find the app catalog ID:
m365 teams app list --query "[?displayName=='ZeroClaw Agent'].id" -o tsv

# Delete it:
m365 teams app remove --id "<app-catalog-id>" --force
```

### What NOT to Touch

These Azure resources are expensive/shared and should **not** be deleted during rollback:

| Resource | Reason |
|----------|--------|
| Resource Group `rg-zeroclaw-sbx-eastus` | Contains all POC resources |
| VM `vm-zeroclaw-sbx-eastus` | Compute host (can be stopped, not deleted) |
| Key Vault `kv-zeroclaw-sbx-eastus` | Contains pre-provisioned secrets |
| Azure OpenAI `oai-zeroclaw-sbx-eastus` | Model deployment takes time to recreate |
| Bot Service `bot-zeroclaw-sbx-eastus` | Bot channel registration |
| App Registrations | Both `appreg-zeroclaw-bot-sbx` and `appreg-zeroclaw-m365-sbx` |
| NSG, Public IP, Log Analytics | Infrastructure plumbing |

### Post-Rollback State

After rollback, the VM should be in the same state as before Phase 1, with:
- System packages still installed (Rust, Node, etc.) — harmless to leave
- `zeroclaw` system user still exists — harmless to leave
- No services running
- No config or secrets on disk

---

## 12. Post-Deployment Monitoring

### Daily Checks (First Week)

| Check | Command | What to Look For |
|-------|---------|-----------------|
| Service status | `for svc in caddy zeroclaw teams-adapter; do systemctl status $svc --no-pager; done` | All three `active (running)`, no restart loops |
| Recent errors | `journalctl --since "24 hours ago" --priority err --no-pager` | Zero error entries (or only benign ones) |
| Gateway health | `curl -s http://localhost:42617/health` | 200 OK |
| Adapter health | `curl -s http://localhost:3978/health` | Both `adapter` and `zeroclaw_gateway` are `ok` |
| HTTPS endpoint | `curl -s https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/health` | 200 OK |
| m365 CLI status | `sudo -u zeroclaw m365 status` | `Logged in` |
| Disk usage | `df -h /` | < 80% used |
| Memory usage | `free -h` | Available > 500 MB |
| Swap usage | `free -h \| grep Swap` | Used < 2 GB normally |
| ZeroClaw restart count | `systemctl show zeroclaw --property=NRestarts` | Should be 0 (or low) |

### Weekly Checks

| Check | Command | What to Look For |
|-------|---------|-----------------|
| TLS certificate expiry | `echo \| openssl s_client -servername vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com -connect vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com:443 2>/dev/null \| openssl x509 -noout -enddate` | > 30 days remaining (Caddy auto-renews at 30 days) |
| m365 CLI certificate expiry | `openssl x509 -in /etc/zeroclaw/m365-key.pem -noout -enddate 2>/dev/null \|\| echo "No cert found"` | > 30 days remaining |
| Key Vault access | `curl -s -H "Metadata:true" "http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://vault.azure.net" \| jq '.expires_on'` | Token can be acquired |
| Log volume | `journalctl --disk-usage` | < 1 GB |
| Package updates | `apt list --upgradable 2>/dev/null \| wc -l` | Review security updates |

### Certificate Expiry Calendar

| Certificate | Expires | Auto-Renew | Action if Expired |
|-------------|---------|------------|-------------------|
| Caddy TLS (Let's Encrypt) | 90 days from issue | Yes (Caddy handles it) | Check Caddy logs: `journalctl -u caddy \| grep -i renew` |
| m365 CLI cert | 365 days from Phase 3 | No | Re-run Phase 3 (generate new cert, upload, re-login) |

### m365 CLI Token Refresh

The m365 CLI uses certificate-based auth, which acquires tokens automatically and refreshes them as needed. There is **no manual token refresh** required. However:

- The CLI stores its token cache in `~/.config/@pnp/cli-microsoft365/` (on the zeroclaw user home)
- If the token cache becomes corrupted, re-login: `m365 login --authType certificate ...`
- Monitor with: `sudo -u zeroclaw m365 status`

### Disk Space Thresholds

| Threshold | Action |
|-----------|--------|
| 80% disk usage | Investigate: `du -sh /var/log/* /home/zeroclaw/.zeroclaw/* /opt/zeroclaw/target/*` |
| 90% disk usage | Immediate: `journalctl --vacuum-time=3d`, clean cargo cache: `sudo -u zeroclaw cargo clean` in `/opt/zeroclaw` |
| Swap > 2 GB used | Check for memory leaks: `top -o %MEM` |

---

## 13. Known Risks & Mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | ZeroClaw build OOM on 4 GB VM | **High** | Blocks Phase 2 | Add 4 GB swap before building (Step 3 of Phase 1). If still OOM, set `CARGO_BUILD_JOBS=1` or pre-build binary on a larger machine and SCP to VM. |
| 2 | m365 admin consent not granted | **High** | Blocks Phase 6 (SharePoint/mail access) | Coordinate with IT admin **before** starting deployment. Have them pre-approve the app permissions in Azure Portal. |
| 3 | Let's Encrypt rate limit on `.cloudapp.azure.com` | **Low** | Blocks TLS (Phase 5) | Azure-managed DNS subdomains are typically fine. If hit, use the staging CA: add `tls { issuer acme { ca https://acme-staging-v02.api.letsencrypt.org/directory } }` to Caddyfile temporarily, then switch back. |
| 4 | IMAP IDLE connection drops silently | **Medium** | Email channel stops receiving | ZeroClaw's email channel has an `idle_timeout = 1740` (29 min, under the 30 min IMAP IDLE RFC limit). The service auto-restarts. Monitor: `journalctl -u zeroclaw \| grep -i idle`. |
| 5 | Bot Framework auth mismatch | **Medium** | Teams DMs get 401 errors | Verify: Bot Service → Settings → Microsoft App ID matches `c28eaa4a-e081-4de8-b9d8-81fbfc28feb2`. Verify the corresponding secret in Key Vault matches what's in the Bot Service App Registration. |
| 6 | ZeroClaw gateway pairing code not emitted | **Medium** | Blocks Phase 5 | The pairing flow depends on ZeroClaw's build. If no pairing code appears, check ZeroClaw docs for `--pair` flag or config setting. The `gateway-pairing-token` may need to be set manually. |
| 7 | `bootstrap.sh` preflight rejects 4 GB VM | **Medium** | Blocks Phase 2 | The script checks minimum RAM (default 2048 MB). With swap, total memory exceeds this. If it still rejects, override: `export ZEROCLAW_BOOTSTRAP_MIN_RAM_MB=1024`. |
| 8 | Private GitHub repo requires auth | **Low** | Blocks Phase 2 (clone) | Set up a deploy key: `ssh-keygen -t ed25519`, add public key to GitHub repo → Settings → Deploy keys. Or use a PAT: `git clone https://<PAT>@github.com/pitcherco/zeroclaw-dbi.git`. |
| 9 | m365 CLI certificate expires (365 days) | **Certain** (long-term) | Blocks all m365 operations | Calendar reminder at day 330. Re-run Phase 3 to generate a new cert. |
| 10 | VM reboots and services don't come back | **Low** | All services down | All services have `systemctl enable` and `Restart=always`. Validate with: `sudo reboot` then check services after boot. |
| 11 | Azure OpenAI quota exhausted | **Low** | Agent can't reason | Monitor usage in Azure Portal → OpenAI resource → Metrics. Set budget alerts. |
| 12 | Caddy fails to bind port 443 | **Low** | TLS termination broken | Check if another process holds port 443: `ss -tlnp \| grep :443`. Ubuntu's default Apache/nginx may interfere. Remove: `apt-get remove apache2 nginx`. |
| 13 | `allowed_from = ["*"]` in email config | **Certain** (by design) | Anyone can email the agent | Acceptable for POC. For production, restrict to `@dirtybirdusa.com` or specific addresses. |
| 14 | `ProtectSystem=strict` blocks m365 CLI operations | **Medium** | m365 CLI can't write temp files | The systemd unit allows `ReadWritePaths=/home/zeroclaw /tmp`. m365 CLI may need `/tmp` or its own cache dir. If blocked, add the path to `ReadWritePaths`. |
| 15 | Shell tool escapes sandbox | **Low** | Agent executes unintended commands | ZeroClaw runs in `supervised` mode with action budget of 30. Monitor shell tool invocations in logs. |

---

## Appendix A: Quick-Reference Command Sheet

```bash
# SSH
ssh zeroclaw@vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com

# Service control
sudo systemctl {start|stop|restart|status} {zeroclaw|teams-adapter|caddy}

# Logs
journalctl -u zeroclaw -f
journalctl -u teams-adapter -f
journalctl -u caddy -f

# Health checks
curl http://localhost:42617/health          # ZeroClaw gateway
curl http://localhost:3978/health           # Teams adapter
curl https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/health  # External

# ZeroClaw diagnostics
sudo -u zeroclaw /opt/zeroclaw/target/release/zeroclaw doctor
sudo -u zeroclaw /opt/zeroclaw/target/release/zeroclaw status

# m365 CLI
sudo -u zeroclaw m365 status
sudo -u zeroclaw m365 spo site list

# Secrets reload
sudo bash /etc/zeroclaw/load-secrets.sh
sudo systemctl restart zeroclaw teams-adapter

# Validation
sudo bash /opt/zeroclaw/infra/validate-deployment.sh
```

## Appendix B: Deployment State Machine

```
[Pre-Flight] ──pass──→ [Phase 1: Bootstrap]
                             │
                             ▼
                        [Phase 2: Build]
                             │
                             ▼
                        [Phase 3: m365 Cert Auth]
                             │
                             ▼
                        [Phase 4: Deploy Config]
                             │
                             ▼
                        [Phase 5: Start + Pair]
                             │
                             ▼
                        [Phase 6: SharePoint]
                             │
                             ▼
                        [Phase 7: Teams App]
                             │
                             ▼
                        [Validate] ──pass──→ [Acceptance Tests]
                             │
                          fail ──→ [Rollback Playbook]
```

Each phase is a discrete state transition. If a phase fails, address the failure mode before proceeding. If unrecoverable, use the rollback playbook and restart from the failed phase.
