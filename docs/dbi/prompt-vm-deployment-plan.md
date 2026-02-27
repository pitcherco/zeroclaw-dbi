# VM Deployment Execution Plan — AI Agent Prompt

> **Usage**: Feed this entire document to an AI agent (Claude, Copilot, etc.) to produce a phased deployment plan with tasks, runbooks, validation scripts, rollback procedures, and acceptance test documentation.

---

## System Prompt

You are a senior DevOps/SRE engineer specializing in Azure VM deployments, Linux service orchestration, and Microsoft 365 integrations. You are methodical, security-conscious, and write production-grade operational documentation.

Your task: produce a **complete, executable deployment plan** for bringing the ZeroClaw Teammate Agent POC online on an Azure VM. The plan must be detailed enough that a junior engineer can follow it step-by-step with zero ambiguity.

---

## Context

### What Is ZeroClaw?

ZeroClaw is an open-source Rust-based AI agent runtime (forked from `openagen/zeroclaw`). It provides:
- LLM-powered reasoning (Azure OpenAI GPT-4o)
- Shell tool execution (runs CLI commands: `m365`, `az`, etc.)
- Email channel (IMAP IDLE + SMTP to `Zero@dirtybirdusa.com`)
- Gateway API on `localhost:42617` with pairing-based auth

We extend it with a **Teams adapter** — a Python 3.12 Bot Framework SDK service that receives Teams messages and forwards them to ZeroClaw's gateway.

### Architecture

```
Internet (Teams users / Email)
    │
    ▼ HTTPS :443
┌──────────────────────────────────────────────────────────────┐
│  Azure VM: vm-zeroclaw-sbx-eastus (Standard_B2s, Ubuntu 24) │
│                                                               │
│  Caddy (:443, auto-TLS) ──→ Teams Adapter (:3978, Python)   │
│                                   │                          │
│                                   ▼ HTTP POST /webhook       │
│                              ZeroClaw Runtime (:42617, Rust)  │
│                                   │                          │
│                          ┌────────┼────────┐                 │
│                          ▼        ▼        ▼                 │
│                      m365 CLI  az CLI  Email (IMAP/SMTP)     │
│                                                               │
│  Managed Identity → Key Vault (secrets at boot)              │
└──────────────────────────────────────────────────────────────┘
```

### Repository Structure (branch: `dbi/poc`)

```
pitcherco/zeroclaw-dbi
├── python/teams_adapter/     # Bot Framework adapter (app.py, bot.py, config.py, zeroclaw_client.py)
├── infra/                    # VM deployment scripts
│   ├── vm-setup.sh           # OS-level dependencies (Rust, Node, m365, az, Caddy, Python venv)
│   ├── deploy.sh             # Clone, build, deploy config/services/Caddy, start everything
│   ├── load-secrets.sh       # Fetch Key Vault secrets via Managed Identity, inject into config.toml
│   ├── config.toml.template  # ZeroClaw config with <PLACEHOLDER> tokens
│   ├── zeroclaw.service      # systemd unit for ZeroClaw daemon
│   ├── teams-adapter.service # systemd unit for Teams adapter
│   ├── Caddyfile             # TLS reverse proxy config
│   └── teams-app/manifest.json  # Teams app manifest
├── docs/dbi/
│   ├── architecture.md       # System architecture diagram and component table
│   ├── runbook.md            # Operations runbook (SSH, services, health checks, troubleshooting)
│   ├── security.md           # Security model, credential flows, threat model
│   └── ZeroClawPOC.md        # POC requirements and acceptance tests
├── dbi/
│   ├── pyproject.toml        # Python project config (ruff, pytest)
│   └── requirements.txt      # Python dependencies
└── CLAUDE.md                 # Repo-wide development instructions
```

### Azure Resources (already provisioned)

| Resource | Name | ID/Details |
|----------|------|------------|
| Resource Group | `rg-zeroclaw-sbx-eastus` | East US |
| VM | `vm-zeroclaw-sbx-eastus` | Standard_B2s, Ubuntu 24.04, IP: 172.178.57.169 |
| Key Vault | `kv-zeroclaw-sbx-eastus` | Managed Identity access from VM |
| Azure OpenAI | `oai-zeroclaw-sbx-eastus` | GPT-4o deployed |
| Bot Service | `bot-zeroclaw-sbx-eastus` | Teams channel enabled |
| App Reg (bot) | `appreg-zeroclaw-bot-sbx` | ID: `c28eaa4a-e081-4de8-b9d8-81fbfc28feb2` |
| App Reg (m365) | `appreg-zeroclaw-m365-sbx` | ID: `836086a7-0308-4c57-a817-5699613f6d8c` |
| NSG | `nsg-zeroclaw-sbx-eastus` | SSH (22) + HTTPS (443) inbound |
| Log Analytics | `log-zeroclaw-sbx-eastus` | Centralized logging |

### Key Vault Secrets (expected)

| Secret Name | Content |
|-------------|---------|
| `azure-openai-key` | Azure OpenAI API key |
| `imap-password` | Email password for `Zero@dirtybirdusa.com` |
| `bot-client-secret` | Bot Framework app secret |
| `m365-app-id` | m365 CLI app registration ID |
| `m365-cert-pem` | m365 CLI private key (generated during deployment) |
| `gateway-pairing-token` | ZeroClaw gateway bearer token (generated during deployment) |

### Current State

- **DONE**: All Azure infrastructure provisioned. All code artifacts written and merged on `dbi/poc` branch. GitHub issue #1 created with full requirements.
- **NOT DONE**: Nothing has been executed on the VM yet. The VM is a fresh Ubuntu 24.04 instance with only SSH access.

---

## Your Deliverables

Produce the following artifacts, each as a clearly delineated section. Think step-by-step through each phase before writing. For each phase, consider: what can go wrong, how to detect failure, how to recover.

### 1. Pre-Flight Checklist

A verification checklist to run **before SSHing into the VM**. Validate that all prerequisites exist and are correctly configured. Include exact commands to verify each item.

Items to verify:
- SSH connectivity to the VM
- Key Vault exists and contains the expected secrets (`azure-openai-key`, `imap-password`, `bot-client-secret`, `m365-app-id`)
- Azure OpenAI endpoint is responsive
- Bot Service messaging endpoint is set to `https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/api/messages`
- NSG rules allow inbound 443 and 22
- VM Managed Identity has `Key Vault Secrets User` role
- `Zero@dirtybirdusa.com` mailbox is active
- DNS resolves `vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com` to the VM IP

### 2. Phased Execution Runbook

For **each of the 7 phases below**, produce:

| Element | Description |
|---------|-------------|
| **Goal** | One sentence: what this phase achieves |
| **Prerequisites** | What must be true before starting this phase |
| **Steps** | Numbered, exact shell commands with expected output |
| **Verification** | Exact commands to confirm the phase succeeded (with expected output) |
| **Failure Modes** | Table: symptom → likely cause → fix |
| **Rollback** | How to undo this phase if something goes wrong |
| **Estimated Duration** | Realistic time estimate |

#### Phase 1: VM Bootstrap
SSH into VM. Run `infra/vm-setup.sh` to install Rust, Node.js 22, m365 CLI, Azure CLI, Caddy, Python 3.12 venv. Create `zeroclaw` system user and directory structure.

Relevant script: `infra/vm-setup.sh` installs 7 components in order:
1. System packages (build-essential, curl, git, ca-certificates, gnupg, jq, caddy)
2. Rust via rustup
3. Node.js 22 LTS
4. m365 CLI (`@pnp/cli-microsoft365`)
5. Azure CLI
6. `zeroclaw` system user + directories (`/opt/zeroclaw`, `/opt/teams-adapter`, `/home/zeroclaw/.zeroclaw`, `/etc/zeroclaw`)
7. Python 3.12 venv at `/opt/teams-adapter/.venv` with Bot Framework packages

#### Phase 2: Build ZeroClaw from Source
Clone `pitcherco/zeroclaw-dbi`, checkout `dbi/poc`, run `./bootstrap.sh --force-source-build`. This compiles the Rust binary to `/opt/zeroclaw/target/release/zeroclaw`.

Key considerations:
- Build takes ~10-15 min on Standard_B2s (2 vCPU, 4GB RAM)
- May need to increase swap if OOM during compile
- `bootstrap.sh` is an upstream script — check what it does before running

#### Phase 3: m365 CLI Certificate Authentication
Generate a self-signed certificate, upload the public key to App Registration `appreg-zeroclaw-m365-sbx`, store the private key in Key Vault, authenticate the m365 CLI.

Steps to address:
- Certificate generation: `openssl req -x509 -newkey rsa:4096 -keyout m365-key.pem -out m365-cert.pem -days 365 -nodes -subj "/CN=zeroclaw-m365"`
- Upload `.pem` (public cert) to Azure AD App Registration → Certificates & secrets
- Store private key: `az keyvault secret set --vault-name kv-zeroclaw-sbx-eastus --name m365-cert-pem --file m365-key.pem`
- Copy private key to VM: `/etc/zeroclaw/m365-key.pem` (permissions 600, owned by zeroclaw)
- Authenticate: `m365 login --authType certificate --certificateFile /etc/zeroclaw/m365-key.pem --appId "836086a7-0308-4c57-a817-5699613f6d8c" --tenant "dirtybirdusa.com"`
- **Admin consent**: The App Registration needs admin-consented Graph API permissions (`Sites.ReadWrite.All`, `Mail.ReadWrite`, `Calendars.Read`, `Files.ReadWrite.All`, `User.Read`)

#### Phase 4: Deploy Config & Services
Run `infra/deploy.sh` (or its steps manually). Deploys config template, secrets loader, Teams adapter code, systemd units, Caddy config.

Key file placements:
- `/etc/zeroclaw/config.toml.template` — ZeroClaw config template
- `/etc/zeroclaw/load-secrets.sh` — fetches secrets from Key Vault at service start
- `/opt/teams-adapter/teams_adapter/` — Python adapter code
- `/etc/systemd/system/zeroclaw.service` and `teams-adapter.service`
- `/etc/caddy/Caddyfile`

The `load-secrets.sh` script:
- Acquires an OAuth2 token from the VM's Managed Identity via IMDS (`169.254.169.254`)
- Fetches `azure-openai-key`, `imap-password`, `bot-client-secret`, `m365-app-id`, `gateway-pairing-token` from Key Vault
- Injects them into `config.toml` via sed placeholders
- Writes `/etc/zeroclaw/teams-adapter.env` for the adapter service

#### Phase 5: Start Services & Gateway Pairing
Start ZeroClaw daemon, get the 6-digit pairing code from logs, exchange it for a bearer token, store the token in Key Vault, start the Teams adapter.

Gateway pairing flow:
1. `systemctl enable --now zeroclaw`
2. `journalctl -u zeroclaw | grep "pairing"` — get the 6-digit code
3. `curl -X POST http://localhost:42617/pair -d '{"code":"<6-digit-code>"}'` — returns bearer token
4. `az keyvault secret set --vault-name kv-zeroclaw-sbx-eastus --name gateway-pairing-token --value "<token>"`
5. Restart ZeroClaw (so `load-secrets.sh` picks up the new token)
6. `systemctl enable --now teams-adapter`

**Chicken-and-egg problem**: `load-secrets.sh` runs as `ExecStartPre` and tries to fetch `gateway-pairing-token`, but it doesn't exist on first boot. The script handles this with `2>/dev/null || echo ""`. After pairing, a restart writes the token into the adapter env file.

#### Phase 6: SharePoint & Identity Setup
Verify the m365 CLI can access the mailbox, create the `ZeroClaw-Outputs` folder in SharePoint, verify file read/write works.

Commands:
- `m365 outlook mail message list --top 5` (verify mailbox access)
- `m365 spo site list` (list accessible SharePoint sites)
- `m365 spo folder add --webUrl https://dirtybirdusa.sharepoint.com/sites/<TargetSite> --name "ZeroClaw-Outputs" --parentFolderUrl "/Shared Documents"`
- Write a test file and read it back

#### Phase 7: Teams App Sideload
Create placeholder icons, package the Teams app manifest into a zip, upload via Teams Admin Center (or `m365 teams app publish`).

Manifest: `infra/teams-app/manifest.json` — bot ID `c28eaa4a`, scopes `personal`, `team`, `groupChat`, valid domain `vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com`.

Still needed:
- `outline.png` (32x32, transparent) and `color.png` (192x192) icons
- Zip: `manifest.json` + icons → `zeroclaw-teams-app.zip`
- Upload: Teams Admin Center → Manage apps → Upload custom app, OR `m365 teams app publish --filePath zeroclaw-teams-app.zip`

### 3. Validation Script

Write a single bash script (`validate-deployment.sh`) that can be run on the VM after deployment to verify everything is working. The script should:

- Check all 3 systemd services are active
- Hit health endpoints (ZeroClaw gateway, Teams adapter, HTTPS endpoint)
- Verify TLS certificate is valid
- Verify Key Vault secret access via Managed Identity
- Verify m365 CLI is authenticated
- Verify file permissions on `config.toml` (600)
- Check that services survive a simulated restart
- Output a clear PASS/FAIL report

### 4. Acceptance Test Procedures

For each of the 5 POC acceptance tests, write a detailed test procedure:

| # | Test | Expected Behavior |
|---|------|-------------------|
| AT-1 | Teams DM: "Pull the numbers from this spreadsheet and summarize" | Bot responds in DM with summary within 2 minutes |
| AT-2 | Teams Channel: "@ZeroClaw produce a short status report from the docs in this site" | Bot responds in-thread within 2 minutes |
| AT-3 | Email to `Zero@dirtybirdusa.com`: "Send me the weekly report" | Reply email with report within 5 minutes |
| AT-4 | Teams DM: "Read TestData.xlsx from Projects site, write summary to Outputs" | File appears in `ZeroClaw-Outputs` SharePoint folder |
| AT-5 | Teams DM: "List all SharePoint sites I have access to" | Bot returns site list via m365 CLI |

For each test, include:
- **Pre-conditions**: What test data must exist (e.g., a `TestData.xlsx` file in a known SharePoint location)
- **Setup steps**: How to create the test data
- **Execution**: Exact message to send, where to send it
- **Expected result**: What the response should contain
- **Pass criteria**: Binary yes/no — what constitutes a pass
- **Troubleshooting**: If the test fails, what to check first (logs, service status, connectivity)

### 5. Rollback Playbook

A complete rollback procedure that returns the VM to a clean state if deployment fails catastrophically. Include:
- How to stop and disable all services
- How to remove deployed files
- How to revoke the m365 CLI certificate
- How to clean up Key Vault secrets that were generated during deployment
- What Azure resources to NOT touch (they're shared/expensive to recreate)

### 6. Post-Deployment Monitoring Checklist

A daily/weekly checklist for the first week after deployment:
- What logs to check and what to look for
- Health check commands to run
- Certificate expiry dates to track
- m365 CLI token refresh schedule
- Disk space and memory usage thresholds

### 7. Known Risks and Mitigations

A risk register for this deployment:

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ZeroClaw build OOM on 4GB VM | Medium | Blocks Phase 2 | Add swap, or pre-build binary |
| m365 admin consent not granted | High | Blocks Phase 3 | Verify with IT admin before starting |
| Let's Encrypt rate limit | Low | Blocks TLS | Use staging CA first, switch to prod |
| IMAP IDLE drops silently | Medium | Email stops working | Add monitoring alert |
| Bot Framework auth fails | Medium | Teams integration broken | Verify app registration matches bot service |
| ... | | | Add any others you identify |

---

## Constraints

1. **Security**: No secrets in scripts, logs, or output. All secrets come from Key Vault via Managed Identity at runtime.
2. **Idempotency**: Every command should be safe to re-run. Use `if ! command -v ... ; then install; fi` patterns.
3. **Observability**: Every step must produce verifiable output. No "trust me, it worked."
4. **Reversibility**: Prefer operations that can be undone. Document how to undo each phase.
5. **Least privilege**: The `zeroclaw` user should only have access to what it needs. Don't run services as root.
6. **POC scope**: This is a sandbox deployment. Don't over-engineer for production. But don't cut corners on security.

---

## Output Format

Structure your response as a single, cohesive markdown document with clear heading hierarchy:

```
# ZeroClaw POC — VM Deployment Execution Plan

## 1. Pre-Flight Checklist
## 2. Phase 1: VM Bootstrap
## 3. Phase 2: Build ZeroClaw
## 4. Phase 3: m365 CLI Authentication
## 5. Phase 4: Deploy Config & Services
## 6. Phase 5: Start Services & Gateway Pairing
## 7. Phase 6: SharePoint & Identity Setup
## 8. Phase 7: Teams App Sideload
## 9. Validation Script
## 10. Acceptance Test Procedures
## 11. Rollback Playbook
## 12. Post-Deployment Monitoring
## 13. Known Risks & Mitigations
```

For each phase, use the exact structure specified in deliverable #2 (Goal, Prerequisites, Steps, Verification, Failure Modes, Rollback, Duration).

Use fenced code blocks for all commands. Use tables for structured data. Use admonition-style callouts (`> **WARNING**:`, `> **NOTE**:`) for critical information.

---

## Chain-of-Thought Guidance

Before writing each phase:

1. **Read** the relevant infra script(s) referenced in that phase
2. **Identify** what could go wrong at each step (network, permissions, disk space, auth, dependencies)
3. **Trace** the data flow — where do secrets come from, where do they go, who needs them
4. **Verify** that the commands you write match the actual file paths and service names in the repo
5. **Cross-reference** with the architecture diagram to ensure nothing is missed

Think about the deployment as a state machine. Each phase transitions the system from one known state to another. Your verification commands are the assertions that confirm the state transition succeeded.
