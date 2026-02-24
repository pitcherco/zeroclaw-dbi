# ZeroClaw POC — Operations Runbook

## SSH Access

```bash
ssh zeroclaw@vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com
```

## Service Management

### ZeroClaw Runtime
```bash
sudo systemctl start zeroclaw
sudo systemctl stop zeroclaw
sudo systemctl restart zeroclaw
sudo systemctl status zeroclaw
journalctl -u zeroclaw -f          # Tail logs
```

### Teams Adapter
```bash
sudo systemctl start teams-adapter
sudo systemctl stop teams-adapter
sudo systemctl restart teams-adapter
sudo systemctl status teams-adapter
journalctl -u teams-adapter -f
```

### Caddy (TLS Reverse Proxy)
```bash
sudo systemctl restart caddy
sudo systemctl status caddy
journalctl -u caddy -f
```

## Health Checks

```bash
# ZeroClaw gateway
curl http://localhost:42617/health

# Teams adapter
curl http://localhost:3978/health

# External HTTPS endpoint
curl https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/health

# m365 CLI auth
m365 status

# Azure CLI auth
az account show
```

## ZeroClaw Diagnostics

```bash
# Full diagnostics
/opt/zeroclaw/target/release/zeroclaw doctor

# Channel health
/opt/zeroclaw/target/release/zeroclaw channel doctor

# Current config
/opt/zeroclaw/target/release/zeroclaw status
```

## Common Troubleshooting

### ZeroClaw won't start
1. Check config: `zeroclaw doctor`
2. Check secrets were loaded: `cat /home/zeroclaw/.zeroclaw/config.toml | grep -v password`
3. Check systemd logs: `journalctl -u zeroclaw --no-pager -n 50`

### Email not receiving
1. Verify IMAP connectivity: `openssl s_client -connect outlook.office365.com:993`
2. Check ZeroClaw email channel: `zeroclaw channel doctor`
3. Verify credentials: check Key Vault secret `imap-password`

### Teams not responding
1. Check bot endpoint: `curl -v https://vm-zeroclaw-sbx-eastus.eastus.cloudapp.azure.com/api/messages`
2. Check Caddy is running: `systemctl status caddy`
3. Check adapter logs: `journalctl -u teams-adapter -f`
4. Test in Azure Portal: Bot Service → Test in Web Chat

### m365 CLI auth expired
```bash
m365 login --authType certificate \
    --certificateFile /etc/zeroclaw/m365-key.pem \
    --appId "836086a7-0308-4c57-a817-5699613f6d8c" \
    --tenant "dirtybirdusa.com"
m365 status
```

### Gateway pairing
If the gateway pairing token is lost:
```bash
# ZeroClaw prints the pairing code at startup
journalctl -u zeroclaw | grep "pairing"
# Exchange for bearer token
curl -X POST http://localhost:42617/pair -d '{"code":"<6-digit-code>"}'
# Store the token
az keyvault secret set --vault-name kv-zeroclaw-sbx-eastus --name gateway-pairing-token --value "<token>"
```

## Key File Locations

| File | Path |
|------|------|
| ZeroClaw binary | `/opt/zeroclaw/target/release/zeroclaw` |
| ZeroClaw config | `/home/zeroclaw/.zeroclaw/config.toml` |
| Config template | `/etc/zeroclaw/config.toml.template` |
| Secrets loader | `/etc/zeroclaw/load-secrets.sh` |
| Adapter env file | `/etc/zeroclaw/teams-adapter.env` |
| Teams adapter code | `/opt/teams-adapter/teams_adapter/` |
| Caddy config | `/etc/caddy/Caddyfile` |
| m365 certificate | `/etc/zeroclaw/m365-key.pem` |
| ZeroClaw service | `/etc/systemd/system/zeroclaw.service` |
| Adapter service | `/etc/systemd/system/teams-adapter.service` |

## Key Vault Secrets

| Secret | Content |
|--------|---------|
| `azure-openai-key` | Azure OpenAI API key |
| `azure-openai-endpoint` | Azure OpenAI endpoint URL |
| `bot-client-secret` | Bot Framework client secret |
| `m365-cert-pem` | m365 CLI certificate (private key) |
| `m365-app-id` | m365 CLI app registration ID |
| `imap-password` | Email password for Zero@dirtybirdusa.com |
| `gateway-pairing-token` | ZeroClaw gateway bearer token |
