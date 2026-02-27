# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Company Context
Dirtybird Industries -- US ecommerce (firearms). Multiple repos: ETL, scrapers, operations apps, AI agents, Azure Functions.

## Database
- **PostgreSQL** on Azure
- Use PostgreSQL dialect: JSONB, ON CONFLICT, LATERAL, RETURNING
- Do NOT use Snowflake (IFF, QUALIFY, VARIANT) or Spark SQL (explode)

## Identity (CRITICAL)
- Git: GitHub company account `rdominguesds`, email `rdomingues@pitcherco.com`
- Azure: subscription PPU (fbcc25e6-6d59-43ba-b7a2-7c606880a202)
- GitHub CLI: `gh auth switch --user rdominguesds` if wrong account

## Tech Stack
- Python: Flask, Django, Azure Functions v4, Streamlit, Crawl4AI
- Node.js: n8n workflow automation
- Docker + Azure Container Registry
- WooCommerce REST API integrations

## Development Commands
```powershell
uv venv --python 3.12
.venv\Scripts\activate
uv pip install -r requirements.txt
pytest
ruff check .
az account show  # Verify PPU subscription
```

## Environment
- OS: Windows, Shell: PowerShell
- Use PowerShell syntax for all terminal commands
- Use `$env:VAR` not `export`, `; ` not `&&`, backslash paths, `$null` not `/dev/null`
- String interpolation: `"$_:"` fails in PowerShell — use `"${_}:"` or `"$($_):"` or `-f` format operator
- Do **not** run long multi-line code as inline `python -c "..."` or `bash -c "..."` — write a script file and run it (avoids ScriptBlock error and token waste).

## Development Rules

Apply to all projects. **Blocked (never run):** `az group delete`, `az keyvault delete`, `az storage account delete`, `az sql server delete`, `gh repo delete`, `git push --force` to main/master, `git reset --hard` on main/master, `rm -rf /` or `rm -rf ~`. **Confirm first:** `az deployment *`, `az webapp deploy`, `az sql db create`, `az role assignment *`, `az keyvault secret set`, `gh pr merge`, `gh release create`, `git push origin main/master`, any production writes or `--yes`/`--force` on remote. **Allowed:** Read-only (`az account show`, `gh pr list`, `git status`/`diff`/`log`), local ops, `git add`/`commit`, `gh pr create`. When in doubt, ask. **Security:** Untrusted by default; code enforces, prompts guide; least privilege; use established libs. **Code quality:** Pydantic/Zod at boundaries; structured errors; no secrets in code. **Operations:** Deploy via GitHub Actions only; no sensitive data in logs; timeouts on external calls. **Infrastructure:** Azure-native; GitHub + Actions.