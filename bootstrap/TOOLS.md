# Tools

You have access to shell commands on an Azure VM. The following CLI tools are installed and authenticated.

## Microsoft 365 CLI (m365)

The `m365` CLI is logged in as `appreg-zeroclaw-m365-sbx` (certificate auth, app-only permissions). Use it for all Microsoft 365 operations.

### Email

```bash
# List recent emails in a user's inbox
m365 outlook mail message list --userId "Zero@dirtybirdusa.com" --top 10 --output json

# Get a specific email by ID
m365 outlook mail message get --userId "Zero@dirtybirdusa.com" --id "<message-id>" --output json

# Search emails
m365 outlook mail message list --userId "Zero@dirtybirdusa.com" --filter "contains(subject,'quarterly report')" --output json

# Send an email
m365 outlook mail send --to "user@dirtybirdusa.com" --subject "Subject" --bodyContents "Body text" --sender "Zero@dirtybirdusa.com"

# List attachments on a message
m365 outlook mail message attachment list --userId "Zero@dirtybirdusa.com" --messageId "<message-id>" --output json
```

### SharePoint

```bash
# List files in a SharePoint document library
m365 spo file list --webUrl "https://dirtybirdusa.sharepoint.com/sites/Operations" --folder "Shared Documents" --output json

# Get file contents
m365 spo file get --webUrl "https://dirtybirdusa.sharepoint.com/sites/Operations" --url "/sites/Operations/Shared Documents/file.xlsx" --asFile --path "/tmp/file.xlsx"

# Search SharePoint
m365 spo search --queryText "quarterly report" --output json
```

### Planner / Tasks

```bash
# List plans in a group
m365 planner plan list --groupId "<group-id>" --output json

# List tasks in a plan
m365 planner task list --planId "<plan-id>" --output json
```

### Teams

```bash
# List teams
m365 teams team list --output json

# List channels in a team
m365 teams channel list --teamId "<team-id>" --output json

# Send a message to a channel
m365 teams message send --teamId "<team-id>" --channelId "<channel-id>" --message "Hello from Zero"
```

### Users / Directory

```bash
# Look up a user
m365 entra user get --id "user@dirtybirdusa.com" --output json

# List users
m365 entra user list --output json
```

### Important Notes

- Always use `--output json` for structured data you need to parse.
- For user-specific operations, use `--userId "Zero@dirtybirdusa.com"` (or the target user's UPN).
- The m365 CLI is authenticated with app-only permissions. Some user-delegated operations may not be available.
- For large result sets, use `--top N` to limit results.

## Azure CLI (az)

The `az` CLI is available but not currently logged in on this VM. The VM has a Managed Identity that can access Azure Key Vault and other Azure resources. For Azure resource queries, use:

```bash
# Login with managed identity (if needed)
az login --identity

# Query Key Vault (example)
az keyvault secret list --vault-name kv-zeroclaw-sbx-eastus --query "[].name" -o tsv
```

## File Operations

- Use `file_read` and `file_write` tools for workspace files.
- The workspace is at `/home/zeroclaw/.zeroclaw/workspace/`.
- For files outside the workspace, use shell commands (`cat`, `ls`, etc.).

## General Shell

- You can run any shell command via the `shell` tool.
- Prefer non-destructive commands. Ask before deleting, overwriting, or sending.
- Long-running commands may time out (60s limit). For large operations, break them into steps.
