---
name: "[DEPLOY] ZeroClaw POC — VM deployment & service activation"
about: Deploy ZeroClaw agent runtime, Teams adapter, and supporting services to Azure VM
labels: "infra, deployment, POC"
assignees: rdominguesds
---

## Summary

Deploy the ZeroClaw Teammate Agent POC onto the provisioned Azure VM (`vm-zeroclaw-sbx-eastus`). This covers SSH-based setup of all runtime dependencies, building ZeroClaw from source, deploying the Teams adapter, configuring TLS termination, authenticating the m365 CLI, and validating the full stack with 5 acceptance tests.

**Why:** All Azure infrastructure is provisioned and all code artifacts are written. This is the final execution phase that brings the agent online — making it reachable via Teams DM/@mention and email at `Zero@dirtybirdusa.com`.

## Technical Context

### Current State (completed)
- Azure Resource Group `rg-zeroclaw-sbx-eastus` provisioned with all resources
- Key Vault `kv-zeroclaw-sbx-eastus` populated with secrets (OpenAI key, IMAP password, bot secret, m365 app ID)
- Azure OpenAI `oai-zeroclaw-sbx-eastus` deployed with GPT-4o model
- VM `vm-zeroclaw-sbx-eastus` (Standard_B2s, Ubuntu 24.04) running at `172.178.57.169`
- Bot Service `bot-zeroclaw-sbx-eastus` created with Teams channel enabled
- App Registrations: `appreg-zeroclaw-bot-sbx` (c28eaa4a) + `appreg-zeroclaw-m365-sbx` (836086a7)
- ZeroClaw forked to `pitcherco/zeroclaw-dbi`
- All code artifacts written: Teams adapter (`python/teams_adapter/`), infra scripts (`infra/`), docs (`docs/dbi/`)

### Target State (this card)
- ZeroClaw daemon running as systemd service, gateway healthy on `localhost:42617`
- Teams adapter running, receiving Bot Framework messages on `:3978`
- Caddy terminating TLS on `:443` with auto-renew Let's Encrypt cert
- m365 CLI authenticated via certificate as `Zero@dirtybirdusa.com`
- Email channel connected to `outlook.office365.com` via IMAP IDLE
- All 5 POC acceptance tests passing

## Functional Requirements

- [ ] **FR-1**: Employees can DM the ZeroClaw bot in Teams and receive responses
- [ ] **FR-2**: Employees can @mention the bot in a Teams channel and get a threaded reply
- [ ] **FR-3**: Emails to `Zero@dirtybirdusa.com` are processed and replied to automatically
- [ ] **FR-4**: The agent can read/write files in SharePoint/OneDrive via m365 CLI
- [ ] **FR-5**: The agent writes durable outputs to the `ZeroClaw-Outputs` SharePoint folder

## Technical Requirements

- [ ] **TR-1**: ZeroClaw built from source on VM (Rust binary at `/opt/zeroclaw/target/release/zeroclaw`)
- [ ] **TR-2**: ZeroClaw systemd service (`zeroclaw.service`) enabled and running as `zeroclaw` user
- [ ] **TR-3**: Teams adapter systemd service (`teams-adapter.service`) enabled and running
- [ ] **TR-4**: Caddy reverse proxy with auto-TLS on `vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com`
- [ ] **TR-5**: `load-secrets.sh` injects Key Vault secrets into `config.toml` at boot via Managed Identity
- [ ] **TR-6**: m365 CLI authenticated with certificate (cert-based auth, `appreg-zeroclaw-m365-sbx`)
- [ ] **TR-7**: Gateway pairing token generated, stored in Key Vault as `gateway-pairing-token`
- [ ] **TR-8**: NSG allows inbound HTTPS (443) + SSH (22 from admin IP only)
- [ ] **TR-9**: All services survive VM reboot (systemd enabled)
- [ ] **TR-10**: Config file permissions set to 600 (owner-only)

## Dependencies

- **Requires (all completed):**
  - [x] Azure Resource Group + Key Vault provisioned
  - [x] VM provisioned with Managed Identity
  - [x] Azure OpenAI deployed with GPT-4o
  - [x] Bot Service + Teams channel created
  - [x] App Registrations (bot + m365) created
  - [x] Key Vault secrets populated
  - [x] Code artifacts written (adapter, infra scripts, config templates)

- **Requires (admin tasks — may need manual intervention):**
  - [ ] Grant admin consent for Graph API permissions on `appreg-zeroclaw-m365-sbx`
  - [ ] Verify `Zero@dirtybirdusa.com` has Exchange mailbox active
  - [ ] Add `Zero@dirtybirdusa.com` to target Teams team(s)
  - [ ] Grant `Zero@dirtybirdusa.com` access to target SharePoint site(s)

## Implementation Phases

### Phase 1: VM Bootstrap (~20 min)
SSH into VM and install all runtime dependencies.

```bash
ssh zeroclaw@vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com
```

- [ ] SSH into VM successfully
- [ ] Upload `infra/vm-setup.sh` to VM
- [ ] Run `sudo bash vm-setup.sh` — installs: build-essential, Rust, Node.js 22 LTS, m365 CLI, Azure CLI, Caddy, Python 3.12 venv
- [ ] Verify installations: `cargo --version`, `node --version`, `m365 --help`, `az --version`, `caddy version`
- [ ] Verify `zeroclaw` system user created with home at `/home/zeroclaw`

### Phase 2: Build ZeroClaw (~15 min)
Clone the fork and build from source.

- [ ] `git clone https://github.com/pitcherco/zeroclaw-dbi.git /opt/zeroclaw`
- [ ] `cd /opt/zeroclaw && git checkout -b dbi/poc`
- [ ] `./bootstrap.sh --force-source-build`
- [ ] Verify binary: `/opt/zeroclaw/target/release/zeroclaw --version`
- [ ] Run diagnostics: `/opt/zeroclaw/target/release/zeroclaw doctor`

### Phase 3: m365 CLI Authentication (~15 min)
Generate certificate and authenticate for unattended M365 access.

- [ ] Generate certificate:
  ```bash
  openssl req -x509 -newkey rsa:4096 -keyout /etc/zeroclaw/m365-key.pem \
    -out /etc/zeroclaw/m365-cert.pem -days 365 -nodes \
    -subj "/CN=zeroclaw-m365-sbx"
  ```
- [ ] Upload public cert (`m365-cert.pem`) to App Registration `appreg-zeroclaw-m365-sbx` in Azure Portal
- [ ] Store private key in Key Vault:
  ```bash
  az keyvault secret set --vault-name kv-zeroclaw-sbx-eastus \
    --name m365-cert-pem --file /etc/zeroclaw/m365-key.pem
  ```
- [ ] Authenticate m365 CLI:
  ```bash
  m365 login --authType certificate \
    --certificateFile /etc/zeroclaw/m365-key.pem \
    --appId "836086a7-0308-4c57-a817-5699613f6d8c" \
    --tenant "dirtybirdusa.com"
  ```
- [ ] Verify: `m365 status` shows connected
- [ ] Test: `m365 spo site list` returns sites

### Phase 4: Deploy Configuration & Services (~15 min)
Deploy config templates, systemd units, and Caddy.

- [ ] Upload repo `infra/` directory to VM
- [ ] Deploy config template: `cp config.toml.template /etc/zeroclaw/`
- [ ] Deploy secrets loader: `cp load-secrets.sh /etc/zeroclaw/ && chmod +x /etc/zeroclaw/load-secrets.sh`
- [ ] Deploy Teams adapter code: `cp -r src/teams_adapter /opt/teams-adapter/`
- [ ] Install adapter Python deps: `/opt/teams-adapter/.venv/bin/pip install -r requirements.txt`
- [ ] Deploy systemd units:
  ```bash
  cp infra/zeroclaw.service /etc/systemd/system/
  cp infra/teams-adapter.service /etc/systemd/system/
  systemctl daemon-reload
  ```
- [ ] Deploy Caddy config: `cp infra/Caddyfile /etc/caddy/Caddyfile && systemctl restart caddy`
- [ ] Verify Caddy TLS: `curl -v https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/health`

### Phase 5: Start & Pair (~10 min)
Start ZeroClaw, pair the gateway, start the adapter.

- [ ] Start ZeroClaw: `systemctl enable --now zeroclaw`
- [ ] Verify health: `curl http://localhost:42617/health`
- [ ] Get pairing code: `journalctl -u zeroclaw | grep "pairing"`
- [ ] Exchange for bearer token:
  ```bash
  curl -X POST http://localhost:42617/pair -d '{"code":"<6-digit-code>"}'
  ```
- [ ] Store token in Key Vault:
  ```bash
  az keyvault secret set --vault-name kv-zeroclaw-sbx-eastus \
    --name gateway-pairing-token --value "<token>"
  ```
- [ ] Restart ZeroClaw (to inject new token): `systemctl restart zeroclaw`
- [ ] Start adapter: `systemctl enable --now teams-adapter`
- [ ] Verify adapter: `curl http://localhost:3978/health`

### Phase 6: Validate — SharePoint & Identity (~10 min)
Verify the agent user's M365 access and create the Outputs folder.

- [ ] Verify `Zero@dirtybirdusa.com` mailbox: `m365 outlook mail message list --top 5`
- [ ] Create Outputs folder:
  ```bash
  m365 spo folder add \
    --webUrl "https://dirtybirdusa.sharepoint.com/sites/<TargetSite>" \
    --parentFolderUrl "/Shared Documents" \
    --name "ZeroClaw-Outputs"
  ```
- [ ] Verify folder exists: `m365 spo file list --webUrl <url> --folder "Shared Documents/ZeroClaw-Outputs"`

### Phase 7: Teams App Sideload (~10 min)
Package and sideload the Teams app manifest.

- [ ] Create 192x192 `color.png` and 32x32 `outline.png` icons
- [ ] Zip: `manifest.json` + `color.png` + `outline.png` → `zeroclaw-teams-app.zip`
- [ ] Upload via Teams Admin Center → Manage Apps → Upload custom app
- [ ] Verify bot appears in Teams app catalog
- [ ] Install app for test users

## Acceptance Criteria (POC Tests)

| # | Test | Pass Criteria |
|---|------|---------------|
| **AT-1** | Teams DM: "Pull the numbers from the Q4 sales spreadsheet and summarize" | Bot responds in DM with spreadsheet summary |
| **AT-2** | Teams Channel: "@ZeroClaw produce a short status report from the docs in this site" | Bot responds in-thread (not new message) |
| **AT-3** | Email to `Zero@dirtybirdusa.com`: "Send me the weekly report" | Reply email with report content/link; file in ZeroClaw-Outputs |
| **AT-4** | Teams DM: "Read TestData.xlsx from Projects site, write summary to Outputs" | New file appears in ZeroClaw-Outputs with correct content |
| **AT-5** | Teams DM: "List all SharePoint sites I have access to" | Bot returns site list from `m365 spo site list` |

## Definition of Done

### Deployment
- [ ] All 3 systemd services running (zeroclaw, teams-adapter, caddy)
- [ ] Services survive VM reboot
- [ ] Gateway health check returns 200
- [ ] HTTPS endpoint returns valid TLS certificate

### Security
- [ ] Secrets injected at runtime from Key Vault (not on disk in plaintext)
- [ ] `config.toml` permissions: 600
- [ ] NSG restricts SSH to admin IP only
- [ ] ZeroClaw running in supervised autonomy mode (30 actions/hr)

### Observability
- [ ] `journalctl -u zeroclaw` shows clean startup logs
- [ ] `journalctl -u teams-adapter` shows clean startup logs
- [ ] Caddy access logs at `/var/log/caddy/access.log`
- [ ] ZeroClaw diagnostics pass: `zeroclaw doctor`

### Validation
- [ ] All 5 acceptance tests executed and documented
- [ ] Test results recorded in `docs/dbi/acceptance-tests.md`
- [ ] Screenshots captured for Teams interactions

### Documentation
- [ ] `docs/dbi/architecture.md` — up to date
- [ ] `docs/dbi/runbook.md` — up to date
- [ ] `docs/dbi/security.md` — up to date
- [ ] `docs/dbi/acceptance-tests.md` — created with test results

## Resources

| Resource | Location |
|----------|----------|
| VM SSH | `ssh zeroclaw@vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com` |
| VM IP | `172.178.57.169` |
| ZeroClaw fork | `pitcherco/zeroclaw-dbi` |
| Key Vault | `kv-zeroclaw-sbx-eastus` |
| Azure OpenAI | `oai-zeroclaw-sbx-eastus` |
| Bot Registration | `appreg-zeroclaw-bot-sbx` (c28eaa4a-e081-4de8-b9d8-81fbfc28feb2) |
| m365 Registration | `appreg-zeroclaw-m365-sbx` (836086a7-0308-4c57-a817-5699613f6d8c) |
| Agent user | `Zero@dirtybirdusa.com` |
| Tenant | `dirtybirdusa.com` (36e770ef-e6fd-4f9d-9ace-a949f98a0caa) |
| Setup script | `infra/vm-setup.sh` |
| Deploy script | `infra/deploy.sh` |
| Architecture | `docs/dbi/architecture.md` |
| Runbook | `docs/dbi/runbook.md` |
| Security model | `docs/dbi/security.md` |
