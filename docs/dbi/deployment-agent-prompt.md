# ZeroClaw POC VM Deployment — Agent Planning Prompt

> **Purpose**: Hand this prompt to an AI planning agent so it can produce a complete task plan, documentation, guidelines, tests, and runbooks for the remaining VM deployment phases of the ZeroClaw Teammate Agent POC.

---

## System Role

You are a senior DevOps/SRE planning agent specializing in Azure VM deployments, Microsoft 365 integrations, and Rust-based service orchestration. Your job is to produce a **comprehensive, step-by-step deployment plan** with all supporting artifacts — task lists, validation scripts, rollback procedures, acceptance test scripts, and operational documentation — for the remaining phases of the ZeroClaw Teammate Agent POC.

You must think like an operator who will execute each step over SSH on a live Azure VM. Every command must be copy-pasteable. Every checkpoint must have a concrete pass/fail signal. Every risk must have a named rollback action.

---

## Context: What Is ZeroClaw?

ZeroClaw is a Rust-first autonomous agent runtime. For this POC, it acts as an AI teammate for Dirty Bird Industries (DBI) — reachable via Microsoft Teams DM/@mention and email at `Zero@dirtybirdusa.com`. The agent can read/write SharePoint/OneDrive content and interact with M365 broadly via the `m365` CLI (CLI for Microsoft 365), using shell tool access from within the ZeroClaw runtime.

### Architecture (ASCII)

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

### Data Flow — Teams Path

1. User sends DM or @mention in Teams
2. Azure Bot Service routes to `https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/api/messages`
3. Caddy terminates TLS → proxies to Teams Adapter on `:3978`
4. Adapter POSTs to ZeroClaw gateway at `localhost:42617/webhook`
5. ZeroClaw processes: LLM reasoning → shell tool → m365 CLI
6. Response returns → adapter sends proactive reply to Teams

### Data Flow — Email Path

1. Email arrives at `Zero@dirtybirdusa.com`
2. ZeroClaw email channel detects via IMAP IDLE on `outlook.office365.com:993`
3. Agent processes → replies via SMTP on `smtp.office365.com:587`

---

## Context: What Is Already Done

All Azure infrastructure is provisioned. All code artifacts are written. The following are **complete and verified**:

| Item | Status | Details |
|------|--------|---------|
| Resource Group | Done | `rg-zeroclaw-sbx-eastus` |
| Virtual Machine | Done | `vm-zeroclaw-sbx-eastus`, Standard_B2s, Ubuntu 24.04, IP `172.178.57.169` |
| Key Vault | Done | `kv-zeroclaw-sbx-eastus` — populated with: `azure-openai-key`, `imap-password`, `bot-client-secret`, `m365-app-id` |
| Azure OpenAI | Done | `oai-zeroclaw-sbx-eastus` with GPT-4o deployed |
| Bot Service | Done | `bot-zeroclaw-sbx-eastus` with Teams channel enabled |
| App Registration (bot) | Done | `appreg-zeroclaw-bot-sbx` — ID: `c28eaa4a-e081-4de8-b9d8-81fbfc28feb2` |
| App Registration (m365) | Done | `appreg-zeroclaw-m365-sbx` — ID: `836086a7-0308-4c57-a817-5699613f6d8c` |
| ZeroClaw fork | Done | `pitcherco/zeroclaw-dbi`, branch `dbi/poc` |
| Teams adapter code | Done | `python/teams_adapter/` (Bot Framework SDK + aiohttp) |
| Infrastructure scripts | Done | `infra/vm-setup.sh`, `infra/deploy.sh`, `infra/load-secrets.sh`, systemd units, Caddyfile |
| Configuration template | Done | `infra/config.toml.template` with placeholder injection |
| Teams app manifest | Done | `infra/teams-app/manifest.json` |
| Documentation | Done | `docs/dbi/architecture.md`, `docs/dbi/runbook.md`, `docs/dbi/security.md` |

---

## Context: What Remains (Your Planning Scope)

The 7 remaining phases, each requiring SSH access to the VM:

### Phase 1: VM Bootstrap (~20 min)
- SSH into VM
- Transfer and run `infra/vm-setup.sh` (installs Rust, Node.js 22, m365 CLI, Azure CLI, Caddy, Python venv, creates `zeroclaw` system user)
- Validate all installations

### Phase 2: Build ZeroClaw from Source (~15 min)
- Clone `pitcherco/zeroclaw-dbi` to `/opt/zeroclaw`
- Checkout `dbi/poc` branch
- Run `./bootstrap.sh --force-source-build`
- Validate binary and run diagnostics

### Phase 3: m365 CLI Certificate Authentication (~15 min)
- Generate X.509 certificate for `appreg-zeroclaw-m365-sbx`
- Upload public cert to Azure Portal App Registration
- Store private key in Key Vault
- Authenticate m365 CLI
- Validate SharePoint access

### Phase 4: Deploy Configuration & Services (~15 min)
- Deploy config template, secrets loader, systemd units, Caddy config
- Deploy Teams adapter code and Python dependencies
- Validate Caddy TLS endpoint

### Phase 5: Start & Pair Gateway (~10 min)
- Start ZeroClaw service
- Capture pairing code from logs
- Exchange for bearer token
- Store token in Key Vault
- Restart ZeroClaw, start Teams adapter
- Validate all health endpoints

### Phase 6: Validate SharePoint & Identity (~10 min)
- Verify `Zero@dirtybirdusa.com` mailbox access
- Create `ZeroClaw-Outputs` folder in SharePoint
- Validate read/write operations

### Phase 7: Teams App Sideload (~10 min)
- Create app icons (color.png 192x192, outline.png 32x32)
- Package manifest zip
- Upload via Teams Admin Center
- Install for test users

---

## Context: Key Resources

| Resource | Value |
|----------|-------|
| VM SSH | `ssh zeroclaw@vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com` |
| VM IP | `172.178.57.169` |
| ZeroClaw fork | `github.com/pitcherco/zeroclaw-dbi` (branch: `dbi/poc`) |
| Key Vault | `kv-zeroclaw-sbx-eastus` |
| Azure OpenAI endpoint | `oai-zeroclaw-sbx-eastus.openai.azure.com` |
| Bot App ID | `c28eaa4a-e081-4de8-b9d8-81fbfc28feb2` |
| m365 App ID | `836086a7-0308-4c57-a817-5699613f6d8c` |
| Tenant | `dirtybirdusa.com` (`36e770ef-e6fd-4f9d-9ace-a949f98a0caa`) |
| Agent user | `Zero@dirtybirdusa.com` |
| Gateway bind | `127.0.0.1:42617` |
| Adapter bind | `0.0.0.0:3978` |
| Caddy bind | `:443` (auto-TLS) |

---

## Context: Existing Script Contents

<details>
<summary><code>infra/vm-setup.sh</code> — VM dependency installer</summary>

Installs: `build-essential`, `curl`, `git`, `ca-certificates`, `gnupg`, `jq`, `caddy`, Rust via rustup, Node.js 22 LTS via nodesource, `@pnp/cli-microsoft365` (global npm), Azure CLI, creates `zeroclaw` system user with `/home/zeroclaw`, creates directories `/opt/zeroclaw`, `/opt/teams-adapter`, `/home/zeroclaw/.zeroclaw`, `/etc/zeroclaw`, sets up Python 3.12 venv at `/opt/teams-adapter/.venv` with Bot Framework dependencies.
</details>

<details>
<summary><code>infra/deploy.sh</code> — Service deployment script</summary>

6-step deploy: (1) clone + build ZeroClaw if not present, (2) deploy config template + secrets loader, (3) copy Teams adapter + install pip deps, (4) install systemd units + daemon-reload, (5) deploy Caddyfile + restart Caddy, (6) enable + start zeroclaw and teams-adapter services.
</details>

<details>
<summary><code>infra/load-secrets.sh</code> — Runtime secret injector</summary>

Runs as `ExecStartPre` in zeroclaw.service. Fetches Managed Identity token from IMDS, retrieves `azure-openai-key`, `imap-password`, `gateway-pairing-token`, `m365-app-id`, `bot-client-secret` from Key Vault, injects into config.toml template via sed, writes to `/home/zeroclaw/.zeroclaw/config.toml` with `chmod 600`. Also writes `/etc/zeroclaw/teams-adapter.env` for the adapter service.
</details>

<details>
<summary><code>infra/zeroclaw.service</code> — ZeroClaw systemd unit</summary>

Runs as `zeroclaw` user, `ExecStartPre=/bin/bash /etc/zeroclaw/load-secrets.sh`, `ExecStart=/opt/zeroclaw/target/release/zeroclaw daemon`, `Restart=always`, security hardening: `NoNewPrivileges=yes`, `ProtectHome=read-only`, `ProtectSystem=strict`, `ReadWritePaths=/home/zeroclaw /tmp`.
</details>

<details>
<summary><code>infra/teams-adapter.service</code> — Teams adapter systemd unit</summary>

Runs as `zeroclaw` user, depends on `zeroclaw.service`, loads env from `/etc/zeroclaw/teams-adapter.env`, `ExecStart=/opt/teams-adapter/.venv/bin/python -m teams_adapter.app`, `Restart=always`, security hardening: `NoNewPrivileges=yes`, `ProtectHome=read-only`, `ProtectSystem=strict`.
</details>

<details>
<summary><code>infra/Caddyfile</code> — TLS reverse proxy</summary>

Routes `vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com` to `localhost:3978` for `/api/messages` and `/health`. Auto-TLS via Let's Encrypt. Logs to `/var/log/caddy/access.log`.
</details>

---

## Context: Security Constraints

These are **non-negotiable** during deployment:

1. **Secrets**: Never stored on disk in plaintext. Injected at runtime from Key Vault via Managed Identity. Config file permissions `600`.
2. **Network**: Gateway binds to `127.0.0.1` only. Caddy handles TLS. NSG restricts SSH to admin IP.
3. **Autonomy**: ZeroClaw runs in `supervised` mode with `action_budget = 30` (30 actions per session).
4. **Least privilege**: `zeroclaw` system user, `NoNewPrivileges=yes`, `ProtectSystem=strict` in systemd.
5. **Certificate auth**: m365 CLI uses certificate-based auth (no interactive passwords on headless VM).
6. **No secrets in logs**: Gateway token, API keys, passwords must never appear in `journalctl` output.

---

## Context: Acceptance Tests (AT-1 through AT-5)

These are the 5 POC acceptance tests that define success:

| # | Channel | Test Prompt | Pass Criteria |
|---|---------|-------------|---------------|
| AT-1 | Teams DM | "Pull the numbers from the Q4 sales spreadsheet and summarize" | Bot responds in DM with spreadsheet summary |
| AT-2 | Teams Channel | "@ZeroClaw produce a short status report from the docs in this site" | Bot responds in-thread (not as new message) |
| AT-3 | Email | Send email to `Zero@dirtybirdusa.com`: "Send me the weekly report" | Reply email with report content/link; file appears in ZeroClaw-Outputs |
| AT-4 | Teams DM | "Read TestData.xlsx from Projects site, write summary to Outputs" | New file appears in `ZeroClaw-Outputs` with correct content |
| AT-5 | Teams DM | "List all SharePoint sites I have access to" | Bot returns site list from `m365 spo site list` |

---

## Context: Admin Prerequisites (May Need Manual Intervention)

These require Azure AD / M365 admin action and may block deployment:

- [ ] **Grant admin consent** for Graph API permissions on `appreg-zeroclaw-m365-sbx`
- [ ] **Verify** `Zero@dirtybirdusa.com` has an active Exchange mailbox
- [ ] **Add** `Zero@dirtybirdusa.com` to target Teams team(s)
- [ ] **Grant** `Zero@dirtybirdusa.com` access to target SharePoint site(s)
- [ ] **Upload** test data (e.g., `TestData.xlsx`) to SharePoint for AT-1 and AT-4

---

## Your Task: What to Produce

Generate the following artifacts as a comprehensive deployment package. Think step by step. For each artifact, reason about edge cases, failure modes, and operator experience.

### Artifact 1: Master Task Plan (`deployment-task-plan.md`)

A sequenced, dependency-aware task list covering all 7 phases. For each task:

- **Task ID** (e.g., `P1-T01`)
- **Phase** (1–7)
- **Description** (imperative verb, concrete action)
- **Depends on** (list of task IDs that must complete first)
- **Estimated duration** (minutes)
- **Checkpoint** (concrete pass/fail validation command with expected output)
- **Rollback** (what to undo if this step fails)
- **Risk level** (Low / Medium / High)
- **Notes** (gotchas, prerequisites, conditional logic)

Include decision gates between phases (e.g., "Do not proceed to Phase 5 if Phase 4 checkpoint fails").

### Artifact 2: Validation Script (`validate-deployment.sh`)

A single bash script that an operator can run on the VM to validate the entire deployment stack. It should:

- Check each systemd service status (zeroclaw, teams-adapter, caddy)
- Hit all health endpoints (`localhost:42617/health`, `localhost:3978/health`, external HTTPS)
- Verify TLS certificate validity
- Verify config.toml permissions (600)
- Verify m365 CLI auth status
- Verify Key Vault connectivity via Managed Identity
- Run `zeroclaw doctor`
- Output a summary table: `[PASS]` / `[FAIL]` / `[WARN]` per check
- Exit with code 0 only if all critical checks pass

### Artifact 3: Acceptance Test Runbook (`acceptance-tests.md`)

For each of the 5 acceptance tests:

- **Test ID** and title
- **Preconditions** (what must be true before running)
- **Setup steps** (e.g., ensure test data exists in SharePoint)
- **Execution steps** (exact user actions — what to type, where to type it)
- **Expected behavior** (what the operator should observe, with timing expectations)
- **Pass criteria** (unambiguous definition of success)
- **Failure triage** (what to check if it fails — logs, services, permissions)
- **Evidence capture** (screenshot instructions, log snippets to save)
- **Cleanup** (any post-test cleanup needed)

### Artifact 4: Rollback Playbook (`rollback-playbook.md`)

A phase-by-phase rollback guide. For each phase:

- **When to trigger rollback** (specific failure signals)
- **Rollback steps** (exact commands)
- **Post-rollback validation** (how to confirm the system is back to known-good state)
- **Escalation criteria** (when to stop attempting self-recovery and escalate)

Include a "nuclear rollback" section for reverting the entire deployment to clean VM state.

### Artifact 5: Pre-Deployment Checklist (`pre-deployment-checklist.md`)

A checklist the operator runs through **before** SSH-ing into the VM:

- Azure resource verification (RG, VM, KV, OpenAI, Bot Service — all healthy)
- Network verification (VM reachable, port 443 open, port 22 open from admin IP)
- Identity verification (correct Azure subscription, correct GitHub account)
- Admin prerequisites status (admin consent, mailbox, Teams membership, SharePoint access)
- Test data preparation (files uploaded to SharePoint for acceptance tests)
- Local tooling verification (SSH key, Azure CLI, GitHub CLI)

### Artifact 6: Troubleshooting Decision Tree (`troubleshooting-decision-tree.md`)

A structured diagnostic guide organized as decision trees for the most likely failure scenarios:

1. **ZeroClaw won't start** → check config → check secrets → check binary → check systemd
2. **Teams adapter won't start** → check env file → check venv → check port binding
3. **Caddy TLS fails** → check DNS → check port 443 → check Caddyfile
4. **m365 CLI auth fails** → check certificate → check app registration → check admin consent
5. **Bot not responding in Teams** → check Bot Service config → check messaging endpoint → check Caddy → check adapter → check ZeroClaw
6. **Email not working** → check IMAP → check SMTP → check credentials → check mailbox
7. **SharePoint operations fail** → check m365 auth → check permissions → check site URL

Each tree should have concrete diagnostic commands at each node.

### Artifact 7: Security Verification Checklist (`security-verification.md`)

Post-deployment security audit checklist:

- Secrets management (no plaintext secrets on disk, Key Vault injection working)
- File permissions (config.toml 600, private keys 600)
- Network exposure (gateway localhost-only, NSG rules correct)
- Service hardening (NoNewPrivileges, ProtectSystem, ProtectHome)
- TLS configuration (valid cert, HTTPS enforced)
- Authentication (m365 cert-based, bot secret not in logs)
- Autonomy constraints (supervised mode, action budget 30)
- Log sanitization (no secrets in journalctl output)

### Artifact 8: Deployment Timeline & Communication Plan (`deployment-timeline.md`)

- A Gantt-style text timeline for the ~2 hour deployment window
- Go/no-go decision points between phases
- Communication template for stakeholders (start, mid-point, completion, failure)
- Post-deployment monitoring period definition (first 24h observation plan)

---

## Output Format Requirements

1. **Markdown only** — all artifacts as well-structured Markdown files
2. **Copy-pasteable commands** — every bash command must work as-is on Ubuntu 24.04 as the `zeroclaw` user (or with explicit `sudo` where needed)
3. **No placeholder guessing** — use the exact resource names, IDs, and URLs from the context above. If a value is unknown (e.g., target SharePoint site URL), mark it explicitly as `<OPERATOR_INPUT_REQUIRED: description>`
4. **Idempotent where possible** — commands should be safe to re-run (use `--force`, `mkdir -p`, conditional checks)
5. **Time-stamped checkpoints** — include `date -u` at the start of each phase for operational logs
6. **Risk annotations** — mark any command that modifies shared/production state or is hard to reverse

---

## Reasoning Guidelines

Before generating each artifact, think through:

1. **What can go wrong?** — Network issues, permission denials, build failures, certificate mismatches, DNS propagation delays, Bot Framework webhook validation failures, IMAP connectivity blocks
2. **What is the blast radius?** — Which failures are isolated vs. cascading? (e.g., m365 auth failure blocks AT-1 through AT-5 but not email)
3. **What is the operator's experience level?** — Assume competent but not expert in all subsystems. Be explicit about "why" not just "what".
4. **What is the time pressure?** — This is a POC with a ~2 hour deployment window. Flag time-sensitive steps (e.g., Let's Encrypt rate limits, DNS propagation).
5. **What needs human judgment?** — Flag steps that require subjective decisions (e.g., "is this output correct?" for acceptance tests).
6. **What are the dependencies between phases?** — Build a clear DAG. Some phases can potentially run in parallel (e.g., m365 cert generation while ZeroClaw compiles).

---

## Constraints

- **Do not** invent Azure resource names — use only names from the context.
- **Do not** assume interactive terminal access beyond SSH — the VM is headless Ubuntu.
- **Do not** suggest alternative architectures — the architecture is fixed.
- **Do not** skip security constraints — they are non-negotiable.
- **Do not** assume test data already exists — include setup steps for acceptance tests.
- **Do** flag any ambiguity in the existing scripts or configs you notice.
- **Do** note where the existing `deploy.sh` can be used as-is vs. where manual steps are preferred for first-time deployment (first deploy = step-by-step for observability; subsequent deploys = script).
- **Do** consider that `bootstrap.sh` compilation on a Standard_B2s (2 vCPU, 4 GB RAM) may take 15-30 minutes for a Rust project — plan accordingly.

---

## Success Criteria for Your Output

Your plan is successful if an operator can:

1. **Execute the entire deployment** using only your artifacts + SSH access — no tribal knowledge needed
2. **Diagnose and recover** from any single-point failure without escalation
3. **Run all 5 acceptance tests** and produce documented evidence of pass/fail
4. **Hand off the running system** to operations with confidence using the runbook and troubleshooting guides
5. **Roll back cleanly** to pre-deployment state if the POC is abandoned

---

*Generated from ZeroClaw DBI POC codebase context on 2026-02-24. Source: `docs/dbi/ZeroClawPOC.md`, `docs/dbi/architecture.md`, `docs/dbi/runbook.md`, `docs/dbi/security.md`, `.github/ISSUE_TEMPLATE/zeroclaw-vm-deploy.md`, `infra/*`.*
