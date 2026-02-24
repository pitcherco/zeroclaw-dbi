# ZeroClaw Teammate Agent — Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Azure VM: vm-zeroclaw-sbx-eastus (Standard_B2s, Ubuntu 24.04)  │
│                                                                  │
│  ┌──────────────┐    localhost:42617     ┌───────────────────┐  │
│  │ Teams        │ ────/webhook──────→    │ ZeroClaw Runtime  │  │
│  │ Adapter      │ ←───response───────    │ (Rust daemon)     │  │
│  │ :3978 (HTTP) │                        │                   │  │
│  └──────┬───────┘                        │  ┌─────────────┐  │  │
│         │                                │  │ Email Chan. │  │  │
│  ┌──────┴───────┐                        │  │ IMAP IDLE   │  │  │
│  │ Caddy        │                        │  └─────────────┘  │  │
│  │ :443 (HTTPS) │                        │                   │  │
│  │ auto-TLS     │                        │  ┌─────────────┐  │  │
│  └──────────────┘                        │  │ Shell Tool  │  │  │
│                                          │  │ → m365 CLI  │  │  │
│                                          │  │ → az CLI    │  │  │
│                                          │  └─────────────┘  │  │
│                                          └───────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Managed Identity → Key Vault (secrets at boot)           │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
       │ HTTPS :443                    │ IMAP/SMTP (outbound)
       ▼                               ▼
  Azure Bot Service              outlook.office365.com
       │                               │
       ▼                               ▼
  Microsoft Teams              Zero@dirtybirdusa.com mailbox
```

## Components

| Component | Technology | Location | Purpose |
|-----------|-----------|----------|---------|
| ZeroClaw Runtime | Rust binary | `/opt/zeroclaw` | AI agent brain — LLM reasoning, tool execution, email channel |
| Teams Adapter | Python 3.12 + Bot Framework SDK | `/opt/teams-adapter` | Receives Teams DMs/@mentions, forwards to ZeroClaw gateway |
| Caddy | Go reverse proxy | System service | TLS termination (Let's Encrypt) for the bot endpoint |
| m365 CLI | Node.js | Global npm | Broad M365/Graph access (SharePoint, OneDrive, calendar) |
| Azure CLI | Python | System package | Azure operations (Key Vault secret retrieval) |

## Data Flow

### Teams Message Flow
1. User sends DM or @mention in Teams
2. Azure Bot Service routes message to `https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/api/messages`
3. Caddy terminates TLS, proxies to Teams Adapter on `:3978`
4. Adapter POSTs message to ZeroClaw gateway `localhost:42617/webhook`
5. ZeroClaw processes: LLM reasoning → shell tool → m365 CLI commands
6. Response returned to adapter → proactive message sent back to Teams

### Email Flow
1. Email arrives at `Zero@dirtybirdusa.com` mailbox
2. ZeroClaw's email channel detects via IMAP IDLE
3. Agent processes the email content
4. Response sent via SMTP back to the sender

## Azure Resources

| Resource | Name | Purpose |
|----------|------|---------|
| Resource Group | `rg-zeroclaw-sbx-eastus` | Container for all POC resources |
| Virtual Machine | `vm-zeroclaw-sbx-eastus` | Compute host |
| Public IP | `pip-zeroclaw-sbx-eastus` | Static IP for bot endpoint |
| NSG | `nsg-zeroclaw-sbx-eastus` | Firewall rules |
| Key Vault | `kv-zeroclaw-sbx-eastus` | Secrets storage |
| Azure OpenAI | `oai-zeroclaw-sbx-eastus` | GPT-4o model |
| Bot Service | `bot-zeroclaw-sbx-eastus` | Teams routing |
| App Registration (m365) | `appreg-zeroclaw-m365-sbx` | Graph API access |
| App Registration (bot) | `appreg-zeroclaw-bot-sbx` | Bot Framework auth |
| Log Analytics | `log-zeroclaw-sbx-eastus` | Centralized logging |
| App Insights | `appi-zeroclaw-sbx-eastus` | Telemetry |
