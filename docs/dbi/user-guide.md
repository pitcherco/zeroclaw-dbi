# ZeroClaw Teammate Agent — User Guide

> **Audience:** Non-developer admin who needs to operate, customize, and maintain the ZeroClaw deployment at Dirtybird Industries.
>
> **Last updated:** February 2026

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Customizing the Agent Personality](#2-customizing-the-agent-personality)
3. [Customizing the System Prompt](#3-customizing-the-system-prompt)
4. [Managing Tools](#4-managing-tools)
5. [Managing Skills & Agents](#5-managing-skills--agents)
6. [Memory System](#6-memory-system)
7. [Channel Configuration](#7-channel-configuration)
8. [Azure OpenAI Configuration](#8-azure-openai-configuration)
9. [Secrets Management](#9-secrets-management)
10. [Common Operations Runbook](#10-common-operations-runbook)
11. [Architecture Diagram](#11-architecture-diagram)

---

## 1. Quick Start

### SSH into the VM

```bash
ssh zeroclaw@vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com
```

### Check service status

All four services run under systemd. Check them with:

```bash
sudo systemctl status zeroclaw
sudo systemctl status teams-adapter
sudo systemctl status email-bridge
sudo systemctl status caddy
```

A healthy service shows `Active: active (running)`.

### View logs (live tail)

```bash
# ZeroClaw gateway (core agent)
journalctl -u zeroclaw -f

# Teams adapter
journalctl -u teams-adapter -f

# Email bridge
journalctl -u email-bridge -f

# Caddy (TLS reverse proxy)
journalctl -u caddy -f
```

To see the last 100 lines instead of live tailing:

```bash
journalctl -u zeroclaw --no-pager -n 100
```

### Restart services

```bash
sudo systemctl restart zeroclaw
sudo systemctl restart teams-adapter
sudo systemctl restart email-bridge
sudo systemctl restart caddy
```

> **Warning:** Restarting `zeroclaw` clears the in-memory gateway pairing state. You will need to re-pair the gateway afterward. See [Re-pairing the Gateway](#re-pairing-the-gateway) in section 10.

### Run diagnostics

```bash
/opt/zeroclaw/target/release/zeroclaw doctor
/opt/zeroclaw/target/release/zeroclaw channel doctor
/opt/zeroclaw/target/release/zeroclaw status
```

### Health check endpoints

```bash
# Gateway health (from the VM)
curl http://localhost:3000/health

# Teams adapter health (from the VM)
curl http://localhost:3978/health

# External HTTPS endpoint (from anywhere)
curl https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/health
```

---

## 2. Customizing the Agent Personality

The agent's personality and behavior are defined by **bootstrap markdown files** located at:

```
/home/zeroclaw/.zeroclaw/
```

Each file controls a different aspect of the agent's identity:

| File | Purpose | What to change |
|------|---------|----------------|
| `SOUL.md` | Core personality, tone, values | How the agent talks (formal vs casual), ethical boundaries, communication style |
| `IDENTITY.md` | Name, role, company affiliation | Agent name, job title, company it represents |
| `USER.md` | Information about the users it serves | Department names, common user roles, org context |
| `TOOLS.md` | Guidance for how to use available tools | Instructions for using m365 CLI, file operations, etc. |
| `AGENTS.md` | Sub-agent descriptions and delegation rules | Which tasks to delegate and to whom |
| `BOOTSTRAP.md` | Additional startup instructions | Anything not covered by the other files |

### Example: Changing the agent's name

Edit `IDENTITY.md`:

```bash
sudo nano /home/zeroclaw/.zeroclaw/IDENTITY.md
```

Change the name/role as desired, then restart:

```bash
sudo systemctl restart zeroclaw
```

### Example: Making the agent more formal

Edit `SOUL.md` and adjust the tone section. For example, add:

```
- Always use formal English. Do not use contractions.
- Address users by their full name when known.
- Structure responses with clear headings and bullet points.
```

Then restart the service.

### Example: Adding user context

Edit `USER.md` to add information about your organization's users:

```
## Users
- **Operations team** — primary users, ask about orders, shipping, and inventory
- **Marketing team** — ask about campaigns, website analytics, and social media
- **Executive team** — ask for summaries, reports, and high-level dashboards
```

> **Important:** Always restart the `zeroclaw` service after editing any bootstrap file. The files are loaded once at startup.

---

## 3. Customizing the System Prompt

### How the system prompt is assembled

ZeroClaw builds its system prompt at runtime from multiple sources, layered in this order:

1. **Tool descriptions** — Auto-generated from `config.toml` tool settings and the built-in tool registry
2. **Safety guardrails** — Built-in security rules (not editable)
3. **Skills** — If any are configured in `config.toml`
4. **Bootstrap files** — `SOUL.md`, `IDENTITY.md`, `TOOLS.md`, `USER.md`, `AGENTS.md`, `BOOTSTRAP.md` (in that order)
5. **Date/time and runtime context** — Auto-injected
6. **Tool Use Protocol** — XML `<tool_call>` format instructions for the LLM (auto-injected for non-native-tool providers)

### What you can edit

You have full control over items 3 and 4 (skills and bootstrap files). Items 1, 2, 5, and 6 are managed by the runtime.

### Adding a new bootstrap section

Create a new `.md` file in the workspace directory:

```bash
sudo nano /home/zeroclaw/.zeroclaw/POLICIES.md
```

Add any content you want injected. Then reference it from `BOOTSTRAP.md`:

```markdown
## Company Policies
See POLICIES.md for company-specific policies and guidelines.
```

> **Note:** Only the standard files (`SOUL.md`, `IDENTITY.md`, `TOOLS.md`, `USER.md`, `AGENTS.md`, `BOOTSTRAP.md`) are automatically loaded. Additional files must be referenced from one of these standard files to be included.

### Controlling prompt size

If the system prompt becomes too large (causing rate-limit issues with Azure OpenAI S0 tier), you can:

1. **Trim bootstrap files** — Remove unnecessary detail from `TOOLS.md` or `AGENTS.md`
2. **Enable compact context** — In `config.toml`, set:
   ```toml
   [agent]
   compact_context = true
   ```
   This limits bootstrap content to 6,000 characters and reduces RAG chunk limits. Use this only if you are experiencing token budget issues.

---

## 4. Managing Tools

### Tool configuration in config.toml

Tools are enabled/disabled in `/home/zeroclaw/.zeroclaw/config.toml`. Each tool has its own section:

```bash
sudo nano /home/zeroclaw/.zeroclaw/config.toml
```

### Built-in tools (always available)

| Tool | Description |
|------|-------------|
| `shell` | Execute terminal commands (m365 CLI, az CLI, etc.) |
| `file_read` | Read file contents from the workspace |
| `file_write` | Write/create files in the workspace |
| `memory_store` | Save information to long-term memory |
| `memory_recall` | Search long-term memory |
| `memory_forget` | Delete a memory entry |

### Configurable tools

**Browser tool** — opens URLs for content extraction:

```toml
[browser]
enabled = true
allowed_domains = ["sharepoint.com", "dirtybirdusa.sharepoint.com"]
```

**HTTP Request tool** — makes API calls:

```toml
[http_request]
enabled = true
allowed_domains = ["graph.microsoft.com", "api.example.com"]
timeout_secs = 30
```

**Composio tool** — managed OAuth integrations (Google, Slack, etc.):

```toml
[composio]
enabled = true
api_key = "your-composio-api-key"
```

### Tool guidance in TOOLS.md

The `TOOLS.md` bootstrap file provides the agent with instructions on *how* to use its tools. Edit this to customize tool behavior:

```bash
sudo nano /home/zeroclaw/.zeroclaw/TOOLS.md
```

Example content:

```markdown
## m365 CLI Usage
- Always use `m365 spo file list` to check SharePoint before downloading
- Use `m365 planner task list` for project management queries
- Default SharePoint site: https://dirtybirdusa.sharepoint.com/sites/Operations

## Shell Commands
- Use `az` CLI for Azure resource queries
- Never run destructive commands (delete, purge) without explicit user confirmation
```

### Controlling tool iterations

The agent can execute multiple tool calls per user message (e.g., search SharePoint, then read a file, then summarize). Control the maximum iterations:

```toml
[agent]
max_tool_iterations = 10   # default: 10
```

Setting this too low may prevent multi-step tasks from completing. Setting it too high may increase response time and token usage.

After any config change, restart:

```bash
sudo systemctl restart zeroclaw
```

---

## 5. Managing Skills & Agents

### Sub-agents (delegate model)

ZeroClaw can delegate tasks to sub-agents — separate LLM configurations optimized for specific tasks. Configure them in `config.toml`:

```toml
[agents.researcher]
provider = "openrouter"
model = "anthropic/claude-sonnet-4-6"
system_prompt = "You are a research assistant specializing in market analysis."
max_depth = 2
agentic = true
allowed_tools = ["web_search", "http_request", "file_read"]
max_iterations = 8

[agents.coder]
provider = "ollama"
model = "qwen2.5-coder:32b"
temperature = 0.2
```

| Key | Description |
|-----|-------------|
| `provider` | Which LLM provider to use |
| `model` | Model identifier |
| `system_prompt` | Custom instructions for this sub-agent |
| `agentic` | `true` enables multi-step tool use; `false` is single prompt/response |
| `allowed_tools` | Which tools the sub-agent can use (required when `agentic = true`) |
| `max_iterations` | Max tool-call loops for the sub-agent |
| `max_depth` | Max recursion depth for nested delegation |

### Agent guidance in AGENTS.md

Edit `AGENTS.md` to tell the primary agent when and how to delegate:

```bash
sudo nano /home/zeroclaw/.zeroclaw/AGENTS.md
```

Example:

```markdown
## Delegation Rules
- Delegate research tasks (market analysis, competitor lookup) to the `researcher` agent
- Delegate code generation tasks to the `coder` agent
- Handle all M365/SharePoint tasks yourself (do not delegate)
```

### Skills system

Skills are optional add-on capabilities. Check available skills:

```bash
/opt/zeroclaw/target/release/zeroclaw skills list
```

To enable community skills:

```toml
[skills]
open_skills_enabled = true
```

> **Note:** Community skills download from an external repository. Review security implications before enabling in production.

---

## 6. Memory System

ZeroClaw has a persistent memory system that survives restarts. It stores facts, preferences, and context that the agent can recall in future conversations.

### How it works

| Tool | Action |
|------|--------|
| `memory_store` | Agent saves a fact (e.g., "User prefers weekly reports on Monday") |
| `memory_recall` | Agent searches memory by keyword or semantic similarity |
| `memory_forget` | Agent deletes a specific memory entry |

### Memory configuration

In `config.toml`:

```toml
[memory]
backend = "sqlite"            # sqlite (default), markdown, or none
auto_save = true              # auto-save user-stated inputs
embedding_provider = "none"   # none, openai (for semantic search)
```

**Backend options:**

| Backend | Storage | Best for |
|---------|---------|----------|
| `sqlite` | `~/.zeroclaw/memory.db` | Default, fast, queryable |
| `markdown` | `~/.zeroclaw/memory/` folder | Human-readable files |
| `none` | Disabled | When memory is not needed |

### Where memory files live

- **SQLite:** `/home/zeroclaw/.zeroclaw/memory.db`
- **Markdown:** `/home/zeroclaw/.zeroclaw/memory/` directory

### Manual editing

For the markdown backend, you can directly create, edit, or delete files:

```bash
ls /home/zeroclaw/.zeroclaw/memory/
cat /home/zeroclaw/.zeroclaw/memory/some-fact.md
nano /home/zeroclaw/.zeroclaw/memory/company-policies.md
```

For SQLite, use the `sqlite3` command-line tool:

```bash
sqlite3 /home/zeroclaw/.zeroclaw/memory.db ".tables"
sqlite3 /home/zeroclaw/.zeroclaw/memory.db "SELECT * FROM memories LIMIT 10;"
```

### Clearing all memory

> **Warning: This is destructive and irreversible.**

```bash
# SQLite backend
rm /home/zeroclaw/.zeroclaw/memory.db

# Markdown backend
rm -rf /home/zeroclaw/.zeroclaw/memory/*
```

Restart the service afterward.

---

## 7. Channel Configuration

ZeroClaw communicates through multiple channels. In the current deployment, three channels are active:

### Teams Adapter

The Teams adapter is a separate Python service that bridges Microsoft Teams to the ZeroClaw gateway.

**Config file:** `/etc/zeroclaw/teams-adapter.env`

```env
ZEROCLAW_ADAPTER_BOT_APP_ID=c28eaa4a-e081-4de8-b9d8-81fbfc28feb2
ZEROCLAW_ADAPTER_BOT_APP_SECRET=<secret>
ZEROCLAW_ADAPTER_ZEROCLAW_GATEWAY_URL=http://127.0.0.1:3000
ZEROCLAW_ADAPTER_ZEROCLAW_GATEWAY_TOKEN=<gateway-bearer-token>
ZEROCLAW_ADAPTER_BOT_TENANT_ID=36e770ef-e6fd-4f9d-9ace-a949f98a0caa
```

| Variable | Purpose |
|----------|---------|
| `BOT_APP_ID` | Bot app registration ID in Azure AD |
| `BOT_APP_SECRET` | Bot Framework client secret |
| `ZEROCLAW_GATEWAY_URL` | Where to forward messages (localhost) |
| `ZEROCLAW_GATEWAY_TOKEN` | Bearer token obtained from gateway pairing |
| `BOT_TENANT_ID` | Azure AD tenant ID (required for single-tenant bots) |

**Code location:** `/opt/teams-adapter/teams_adapter/`

**Service file:** `/etc/systemd/system/teams-adapter.service`

### Email Bridge

The email bridge polls Zero's M365 inbox via Graph API and forwards emails to the gateway. Responses are sent back as email replies.

**Config file:** `/etc/zeroclaw/email-bridge.env`

| Variable | Purpose | Default |
|----------|---------|---------|
| `TENANT_ID` | Azure AD tenant | `36e770ef-...` |
| `CLIENT_ID` | M365 app registration ID | `836086a7-...` |
| `CERT_KEY_PATH` | Path to m365 certificate key | `/etc/zeroclaw/m365-key.pem` |
| `CERT_THUMBPRINT` | Certificate thumbprint | `A2672B07...` |
| `ZERO_USER_ID` | Graph API user ID for Zero | `84e4cd1c-...` |
| `ZERO_UPN` | Zero's email address | `Zero@dirtybirdusa.com` |
| `ZEROCLAW_GATEWAY_URL` | Gateway endpoint | `http://127.0.0.1:3000` |
| `ZEROCLAW_GATEWAY_TOKEN` | Gateway bearer token | (from pairing) |
| `POLL_INTERVAL` | Seconds between inbox checks | `30` |

**Code location:** `/opt/zeroclaw/python/email_bridge/`

**Service file:** `/etc/systemd/system/email-bridge.service`

### Gateway Webhook

The gateway is part of the core ZeroClaw service. Both the Teams adapter and email bridge forward messages to it at `http://127.0.0.1:3000/webhook`.

**Config in** `config.toml`:

```toml
[gateway]
host = "127.0.0.1"
port = 3000
require_pairing = true
allow_public_bind = false
```

The gateway uses bearer token authentication. Tokens are issued during the pairing process.

### Adding new channels

ZeroClaw natively supports many additional channels (Telegram, Discord, Slack, WhatsApp, etc.). To add one, update `config.toml` with the appropriate section. For example, to add Telegram:

```toml
[channels_config.telegram]
bot_token = "123456:your-telegram-bot-token"
allowed_users = ["your_telegram_username"]
```

Then restart: `sudo systemctl restart zeroclaw`

See the full list of supported channels in the upstream [channels-reference.md](../channels-reference.md).

---

## 8. Azure OpenAI Configuration

### Current setup

The deployment uses Azure OpenAI with the following configuration:

| Setting | Value |
|---------|-------|
| Resource | `oai-zeroclaw-sbx-eastus` |
| Model | `gpt-4o` |
| Tier | S0 (Standard) |
| Region | East US |

The API key and endpoint are stored in Azure Key Vault and injected into `config.toml` at service startup by `load-secrets.sh`.

### Changing the model

Edit `config.toml`:

```bash
sudo nano /home/zeroclaw/.zeroclaw/config.toml
```

Change the model:

```toml
default_model = "gpt-4o"          # Current
# default_model = "gpt-4o-mini"   # Faster, cheaper, less capable
```

Then restart:

```bash
sudo systemctl restart zeroclaw
```

### Adjusting temperature

```toml
default_temperature = 0.7   # Default: balanced creativity
# default_temperature = 0.2  # More deterministic/factual
# default_temperature = 1.0  # More creative/varied
```

### Rate limits (S0 tier caveats)

The S0 (Standard) tier has per-minute token limits. Symptoms of hitting rate limits:

- `HTTP 429 Too Many Requests` in gateway logs
- `Agent error (HTTP 500)` shown to Teams users
- Errors on rapid successive messages

**Mitigations:**

1. **Wait between messages** — Allow 10-15 seconds between requests
2. **Upgrade quota** — In Azure Portal → Azure OpenAI → Deployments → Quotas, increase tokens per minute
3. **Enable compact context** — Reduces prompt size:
   ```toml
   [agent]
   compact_context = true
   ```
4. **Reduce tool descriptions** — Trim `TOOLS.md` to reduce system prompt size

### Switching providers

ZeroClaw supports many LLM providers beyond Azure OpenAI. To switch:

```toml
# Azure OpenAI (current)
default_provider = "azure"
api_key = "<azure-openai-key>"

# OpenRouter (multi-model gateway)
# default_provider = "openrouter"
# api_key = "<openrouter-key>"
# default_model = "anthropic/claude-sonnet-4-6"

# Anthropic direct
# default_provider = "anthropic"
# api_key = "<anthropic-key>"
# default_model = "claude-sonnet-4-6"
```

---

## 9. Secrets Management

### How secrets work

Secrets follow this flow:

```
Azure Key Vault (kv-zeroclaw-sbx-eastus)
        │
        ▼ (VM Managed Identity — no stored credential)
load-secrets.sh (runs at service startup)
        │
        ▼
config.toml + .env files (runtime only, file permissions 600)
```

### Key Vault secrets

| Secret Name | Content | Used By |
|-------------|---------|---------|
| `azure-openai-key` | Azure OpenAI API key | ZeroClaw config.toml |
| `azure-openai-endpoint` | Azure OpenAI endpoint URL | ZeroClaw config.toml |
| `bot-client-secret` | Bot Framework client secret | teams-adapter.env |
| `m365-cert-pem` | M365 certificate private key | /etc/zeroclaw/m365-key.pem |
| `m365-app-id` | M365 app registration ID | email-bridge.env |
| `imap-password` | Email password | ZeroClaw config.toml |
| `gateway-pairing-token` | Gateway bearer token | teams-adapter.env, email-bridge.env |

### Secret loader script

**Path:** `/etc/zeroclaw/load-secrets.sh`

This script runs before the `zeroclaw` service starts (configured as `ExecStartPre` in the systemd unit file). It:

1. Authenticates to Azure Key Vault using the VM's Managed Identity
2. Fetches each secret
3. Injects values into `config.toml` (replacing placeholder tokens)

### Env file structure

The Teams adapter and email bridge use separate `.env` files:

```
/etc/zeroclaw/teams-adapter.env
/etc/zeroclaw/email-bridge.env
```

These files use `KEY=VALUE` format (one per line). The systemd unit files reference them with `EnvironmentFile=`.

### Viewing secrets (safely)

```bash
# List Key Vault secrets (names only — does not show values)
az keyvault secret list --vault-name kv-zeroclaw-sbx-eastus --query "[].name" -o tsv

# Show a specific secret value
az keyvault secret show --vault-name kv-zeroclaw-sbx-eastus --name azure-openai-key --query value -o tsv
```

### Rotating a secret

> **Confirm with your team before rotating production secrets.**

1. Update the secret in Key Vault:
   ```bash
   az keyvault secret set --vault-name kv-zeroclaw-sbx-eastus \
       --name <secret-name> --value "<new-value>"
   ```

2. Restart the affected service(s) to pick up the new value:
   ```bash
   sudo systemctl restart zeroclaw
   sudo systemctl restart teams-adapter
   ```

---

## 10. Common Operations Runbook

### Updating code from git

When code changes are pushed to the `dbi/poc` branch:

```bash
cd /opt/zeroclaw
git pull origin dbi/poc
```

#### Rust changes (gateway, tools, agent runtime)

```bash
cargo build --release
sudo cp target/release/zeroclaw /usr/local/bin/zeroclaw
sudo systemctl restart zeroclaw
```

> **Note:** The build takes several minutes. The VM needs at least 2 GB RAM + swap for a release build.

#### Python adapter changes

```bash
# Teams adapter
cd /opt/teams-adapter
# Files are served directly from the directory — just restart
sudo systemctl restart teams-adapter

# Email bridge
cd /opt/zeroclaw/python/email_bridge
sudo systemctl restart email-bridge
```

#### Config-only changes (config.toml, bootstrap .md files)

```bash
# Edit files in place
sudo nano /home/zeroclaw/.zeroclaw/config.toml
# Then restart
sudo systemctl restart zeroclaw
```

### Re-pairing the gateway

The gateway pairing state is held **in memory** and is lost on every restart. After restarting `zeroclaw`:

1. Get the pairing code from the startup logs:
   ```bash
   journalctl -u zeroclaw | grep -i "pairing"
   ```
   Look for a line like: `Pairing code: 123456`

2. Exchange the code for a bearer token:
   ```bash
   curl -s -X POST http://localhost:3000/pair \
       -H "X-Pairing-Code: 123456" | python3 -m json.tool
   ```

3. Copy the token from the response and update both env files:
   ```bash
   # Update teams-adapter.env
   sudo nano /etc/zeroclaw/teams-adapter.env
   # Change ZEROCLAW_ADAPTER_ZEROCLAW_GATEWAY_TOKEN=<new-token>

   # Update email-bridge.env
   sudo nano /etc/zeroclaw/email-bridge.env
   # Change ZEROCLAW_GATEWAY_TOKEN=<new-token>
   ```

4. Restart the adapters:
   ```bash
   sudo systemctl restart teams-adapter
   sudo systemctl restart email-bridge
   ```

5. Optionally, store the token in Key Vault:
   ```bash
   az keyvault secret set --vault-name kv-zeroclaw-sbx-eastus \
       --name gateway-pairing-token --value "<new-token>"
   ```

### Checking logs for errors

```bash
# Recent errors across all services
journalctl -u zeroclaw --no-pager -n 50 --priority=err
journalctl -u teams-adapter --no-pager -n 50 --priority=err
journalctl -u email-bridge --no-pager -n 50 --priority=err

# Search for specific patterns
journalctl -u zeroclaw | grep -i "error\|panic\|429\|500"
journalctl -u teams-adapter | grep -i "AADSTS\|error\|401"
```

### Troubleshooting: Teams bot not responding

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No response at all | `teams-adapter` is down | `sudo systemctl restart teams-adapter` |
| AADSTS700016 in logs | Missing or wrong `BOT_TENANT_ID` | Verify `ZEROCLAW_ADAPTER_BOT_TENANT_ID` in `/etc/zeroclaw/teams-adapter.env` |
| "Agent error (HTTP 500)" | Azure OpenAI rate limit (429) | Wait 30s and retry; consider upgrading quota |
| "Agent is unreachable" | Gateway is down or token expired | Re-pair the gateway (see above) |
| Raw XML/JSON in response | Tool execution not working | Check gateway logs for tool errors |

### Troubleshooting: Email not working

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No emails processed | `email-bridge` is down | `sudo systemctl restart email-bridge` |
| Token acquisition failed | Certificate expired or wrong | Re-upload cert to `/etc/zeroclaw/m365-key.pem` |
| Graph GET errors (401) | M365 app permissions changed | Verify admin consent in Azure Portal |
| Reply not sent | Graph POST failed | Check `journalctl -u email-bridge` for Graph API errors |

### Troubleshooting: Azure OpenAI rate limits

Symptoms: `429 Too Many Requests` in logs, `HTTP 500` returned to users.

```bash
# Check current rate limit errors
journalctl -u zeroclaw | grep "429"
```

Short-term fix — wait and retry. Long-term fixes:

1. **Increase quota** — Azure Portal → Azure OpenAI → Deployments → Edit → increase tokens per minute
2. **Enable compact_context** — reduces system prompt token consumption
3. **Switch to a cheaper/faster model** — e.g., `gpt-4o-mini` for routine tasks

### Restarting after VM reboot

After a VM reboot, all systemd services should auto-start. Verify:

```bash
sudo systemctl status zeroclaw teams-adapter email-bridge caddy
```

If services are not running:

```bash
# Enable auto-start on boot
sudo systemctl enable zeroclaw teams-adapter email-bridge caddy

# Start them now
sudo systemctl start zeroclaw teams-adapter email-bridge caddy
```

After ZeroClaw starts, re-pair the gateway (pairing state is lost on reboot):

```bash
journalctl -u zeroclaw | grep -i "pairing"
# Then follow the re-pairing steps above
```

---

## 11. Architecture Diagram

### System overview

```
                    ┌──────────────────┐
                    │  Microsoft Teams  │
                    └────────┬─────────┘
                             │ Bot Framework
                             ▼
                    ┌──────────────────┐
                    │ Azure Bot Service│
                    │ (bot-zeroclaw-   │
                    │  sbx-eastus)     │
                    └────────┬─────────┘
                             │ HTTPS POST /api/messages
                             ▼
┌────────────────────────────────────────────────────────────────────┐
│  Azure VM: vm-zeroclaw-sbx-eastus (Ubuntu, Standard_B2s)          │
│                                                                    │
│  ┌──────────────┐                                                  │
│  │ Caddy :443   │ ─── auto-TLS (Let's Encrypt)                    │
│  │ reverse proxy│                                                  │
│  └──────┬───────┘                                                  │
│         │ proxy to :3978                                           │
│         ▼                                                          │
│  ┌──────────────────────┐    POST /webhook     ┌────────────────┐ │
│  │ Teams Adapter :3978  │ ──────────────────→   │ ZeroClaw :3000 │ │
│  │ (Python/Bot SDK)     │ ←── JSON response ──  │ (Rust gateway) │ │
│  └──────────────────────┘                       │                │ │
│                                                 │  ┌───────────┐ │ │
│  ┌──────────────────────┐    POST /webhook      │  │ Tools:    │ │ │
│  │ Email Bridge         │ ──────────────────→   │  │ • shell   │ │ │
│  │ (Python/Graph API)   │ ←── JSON response ──  │  │ • file_rw │ │ │
│  └──────────┬───────────┘                       │  │ • memory  │ │ │
│             │                                   │  │ • browser │ │ │
│             │ IMAP poll / SMTP reply            │  └───────────┘ │ │
│             ▼                                   │       │        │ │
│  outlook.office365.com                          │       ▼        │ │
│  (Zero@dirtybirdusa.com)                        │  ┌───────────┐ │ │
│                                                 │  │ m365 CLI  │ │ │
│                                                 │  │ az CLI    │ │ │
│                                                 │  └───────────┘ │ │
│                                                 └────────────────┘ │
│                                                        │           │
│                                                        ▼           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Azure Key Vault (kv-zeroclaw-sbx-eastus)                   │   │
│  │  accessed via VM Managed Identity at boot                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Azure OpenAI     │
                    │ (gpt-4o, S0)     │
                    │ oai-zeroclaw-    │
                    │ sbx-eastus       │
                    └──────────────────┘
```

### Message flow (Teams)

```
User DM/mention in Teams
  → Azure Bot Service
    → Caddy (HTTPS :443, auto-TLS)
      → Teams Adapter (:3978)
        → POST /webhook to ZeroClaw Gateway (:3000)
          → LLM reasoning (Azure OpenAI gpt-4o)
            → Tool execution loop (shell, file, memory, etc.)
              → m365 CLI / az CLI commands as needed
            ← Tool results fed back to LLM
          ← Final response (sanitized)
        ← JSON response to adapter
      ← Proactive message via Bot Framework
    ← Response shown in Teams
```

### Message flow (Email)

```
Email arrives at Zero@dirtybirdusa.com
  → Email Bridge polls via Graph API
    → POST /webhook to ZeroClaw Gateway (:3000)
      → LLM reasoning + tool execution
    ← JSON response
  → Graph API: reply to the original email
← Reply shown in sender's inbox
```

### Key file locations

| What | Path |
|------|------|
| ZeroClaw binary | `/opt/zeroclaw/target/release/zeroclaw` (also `/usr/local/bin/zeroclaw`) |
| ZeroClaw config | `/home/zeroclaw/.zeroclaw/config.toml` |
| Bootstrap files | `/home/zeroclaw/.zeroclaw/SOUL.md`, `IDENTITY.md`, `TOOLS.md`, `USER.md`, `AGENTS.md`, `BOOTSTRAP.md` |
| Memory (SQLite) | `/home/zeroclaw/.zeroclaw/memory.db` |
| Memory (Markdown) | `/home/zeroclaw/.zeroclaw/memory/` |
| Teams adapter code | `/opt/teams-adapter/teams_adapter/` |
| Email bridge code | `/opt/zeroclaw/python/email_bridge/` |
| Teams adapter env | `/etc/zeroclaw/teams-adapter.env` |
| Email bridge env | `/etc/zeroclaw/email-bridge.env` |
| Secret loader | `/etc/zeroclaw/load-secrets.sh` |
| Caddy config | `/etc/caddy/Caddyfile` |
| M365 certificate | `/etc/zeroclaw/m365-key.pem` |
| ZeroClaw service unit | `/etc/systemd/system/zeroclaw.service` |
| Teams adapter unit | `/etc/systemd/system/teams-adapter.service` |
| Email bridge unit | `/etc/systemd/system/email-bridge.service` |

### Azure resource summary

| Resource | Name | Purpose |
|----------|------|---------|
| Resource Group | `rg-zeroclaw-sbx-eastus` | Contains all POC resources |
| Virtual Machine | `vm-zeroclaw-sbx-eastus` | Compute host |
| Public IP | `pip-zeroclaw-sbx-eastus` | Static IP for bot endpoint |
| NSG | `nsg-zeroclaw-sbx-eastus` | Firewall (SSH + HTTPS inbound) |
| Key Vault | `kv-zeroclaw-sbx-eastus` | Secrets storage |
| Azure OpenAI | `oai-zeroclaw-sbx-eastus` | GPT-4o model (S0) |
| Bot Service | `bot-zeroclaw-sbx-eastus` | Teams routing (SingleTenant) |
| App Reg (Bot) | `c28eaa4a-...` | Bot Framework auth |
| App Reg (M365) | `836086a7-...` | Graph API access (certificate auth) |
| Log Analytics | `log-zeroclaw-sbx-eastus` | Centralized logging |
| App Insights | `appi-zeroclaw-sbx-eastus` | Telemetry |
