# POC: ZeroClaw "Teammate Agent" (Teams + Email) with M365 Reach via Terminal/CLI

## Overview

### Purpose

Stand up a ZeroClaw-powered teammate agent that users can DM or @mention in Teams and email like a person, and that can operate across Microsoft 365 content as a licensed Microsoft 365 user (the "agent user"). The agent must be able to read/write OneDrive + SharePoint content and use other M365 surfaces (calendar, etc.) to the extent that the agent user has access.

### Design Principle

> Don't build Microsoft Graph access "tool-by-tool." Instead, the agent uses terminal access and CLI tooling to reach M365 broadly.

---

## POC Deliverables

### 1. ZeroClaw Runtime (the "Brain")

- ZeroClaw runs as the long-lived agent runtime with tools enabled.
- **Shell tool access** is required so it can run terminal commands.
- ZeroClaw's tool system includes a shell tool in its registry design.

### 2. Channels (How Humans Talk to the Agent)

#### 2A. Email (Required) — Built into ZeroClaw

- ZeroClaw has an Email channel implementation using **IMAP IDLE + SMTP**.
- Configure the agent mailbox (licensed user mailbox) so the agent can receive requests and reply with reports.

#### 2B. Teams (Required) — Integrate Teams as a Front-End That Forwards to ZeroClaw

Teams is not listed among ZeroClaw's built-in channel implementations, whereas Email is.

**POC approach:** Implement Teams as a thin adapter/service (Teams bot/app) that:

1. Forwards inbound messages to ZeroClaw (HTTP webhook)
2. Posts the response back to Teams

This keeps ZeroClaw as the agent core while letting Teams be the UX.

### 3. Identity & Access (Licensed-User Model)

- Create a **dedicated licensed Microsoft 365 user** (e.g., `agent@…`).
- Grant it access to the Teams/SharePoint/OneDrive locations where the agent will operate.
- Storage model: Teams files are backed by SharePoint sites; OneDrive is the user workspace.
- The agent's "reach" is defined by that user's permissions.

### 4. Broad Graph Access Without Bespoke Code

**Primary approach:** Terminal + CLI

| Tool | Purpose |
|------|---------|
| **CLI for Microsoft 365** (`m365`) | Main Microsoft 365/Graph abstraction — broad workload coverage, unified login |
| **Azure CLI** (`az`) | Optional — Azure-side needs (e.g., secrets retrieval) |

This matches the established pattern of using CLI rather than portals for operational work.

**Why this satisfies the requirement:** The agent can "touch everything that user can touch" through a stable CLI surface, rather than implementing and maintaining a bespoke Graph client for each workload.

### 5. ZeroClaw Execution & Security Posture

- Run ZeroClaw in a **supervised posture** where appropriate.
- ZeroClaw supports autonomy levels and workspace scoping (execution can be constrained while still allowing shell access).
- ZeroClaw's gateway binds to localhost by default and uses a pairing/auth model.
- If exposing externally, use a **tunnel provider** rather than public bind — minimal "don't leave the door open" posture.

---

## POC Acceptance Tests

| Category | Scenario | Success Criteria |
|----------|----------|------------------|
| **Teams** | DM: "Pull the numbers from this spreadsheet and summarize" | Response in DM |
| **Teams** | Channel: "@agent produce a short status report from the docs in this site" | Response in-thread |
| **Email** | Email: "Send me the weekly report" | Reply by email with report attachment or link |
| **M365 Reach** | Read SharePoint/OneDrive file; write output to ODSP folder | Agent reads accessible file and writes to agreed folder |
| **M365 Reach** | Run `m365` via shell from inside ZeroClaw | Retrieve file list, site info, or calendar items |

---

## Implementation Checklist

1. **Provision the agent user**
   - Licensed Microsoft 365 user
   - Mailbox
   - ODSP access (sites/folders)

2. **Deploy ZeroClaw** as the runtime (service/daemon) with:
   - Email channel enabled
   - Shell tool enabled (to run `m365`, optionally `az`)

3. **Install `m365` CLI** on the host; authenticate it as the agent user (method left to implementer).

4. **Build a minimal Teams adapter:**
   - Teams bot receives DM / @mention
   - Forwards text to ZeroClaw gateway webhook
   - Posts response back to Teams

5. **Define one "Outputs" location** in ODSP where the agent writes reports for durability and searchability.
