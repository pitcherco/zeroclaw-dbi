# ZeroClaw POC — Security Model

## Credential Management

- **No secrets in code** — all credentials stored in Azure Key Vault (`kv-zeroclaw-sbx-eastus`)
- **Managed Identity** — VM authenticates to Key Vault without stored credentials
- **Runtime injection** — `load-secrets.sh` fetches secrets at service startup and injects into config
- **File permissions** — config.toml set to `600` (owner-only read/write)

## Network Security

- **ZeroClaw gateway** binds to `127.0.0.1:42617` — not exposed externally
- **Teams adapter** listens on `:3978` — only Caddy connects locally
- **Caddy** terminates TLS on `:443` — auto-renew via Let's Encrypt
- **NSG rules**:
  - Inbound: SSH (22) from admin IP, HTTPS (443) from Azure Bot Service
  - Outbound: all allowed (IMAP, SMTP, Graph API, Azure OpenAI)
- **Bot Framework auth** — all messages validated via Bot Framework Connector auth

## Authentication Flows

| Service | Auth Method | Credential Location |
|---------|-------------|---------------------|
| Azure Key Vault | VM Managed Identity | No stored credential |
| Azure OpenAI | API key | Key Vault → config.toml |
| Email (IMAP/SMTP) | Username/password | Key Vault → config.toml |
| m365 CLI | Certificate-based | Key Vault → /etc/zeroclaw/m365-key.pem |
| Bot Framework | App ID + secret | Key Vault → teams-adapter.env |
| ZeroClaw gateway | Bearer token (pairing) | Key Vault → teams-adapter.env |

## ZeroClaw Security Controls

- **Autonomy level**: `supervised` — requires approval for destructive operations
- **Action budget**: 30 actions/hour — rate limits automated operations
- **Shell tool**: environment isolation (clears env vars), 60s timeout, 1MB output cap
- **Workspace scoping**: agent operates within its designated workspace directory

## Threat Model (POC Scope)

| Threat | Mitigation |
|--------|------------|
| Unauthorized Teams messages | Bot Framework validates all incoming messages |
| Secret exposure in logs | Secrets injected at runtime, not logged |
| VM compromise | Managed Identity scoped to KV only; NSG limits access |
| m365 CLI abuse | Certificate auth; app permissions are auditable |
| ZeroClaw prompt injection | Supervised mode + action budget limit blast radius |
| Email impersonation | `allowed_from = ["*"]` in POC — tighten for production |

## Production Hardening (Beyond POC)

1. Restrict `allowed_from` in email channel to known senders
2. Add Azure AD Conditional Access policies for the agent user
3. Enable audit logging to PostgreSQL
4. Implement IP-based NSG rules for SSH (remove password auth)
5. Add Azure DDoS Protection to the public IP
6. Use Container Apps with VNet injection instead of VM
7. Add XOAUTH2 for email instead of basic auth
