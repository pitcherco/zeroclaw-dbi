# Dirtybird Industries - Copilot Instructions

## Company Context
Dirtybird Industries is a US-based ecommerce company selling firearms and accessories. This workspace contains ETL pipelines, web scrapers, operations apps, AI agents, and Azure Functions.

## Tech Stack
- Database: PostgreSQL on Azure
- Languages: Python, SQL (PostgreSQL dialect), Node.js
- Frameworks: Flask, Django, Azure Functions v4, Streamlit, n8n
- Cloud: Microsoft Azure (ACR, App Service, Functions)
- CI/CD: GitHub Actions

## Database Dialect
Use **PostgreSQL** exclusively:
- JSONB, LATERAL, ON CONFLICT, RETURNING
- CASE WHEN (not IFF), no QUALIFY
- ::type for casting

## Identity and Access
- Git: GitHub (company account rdominguesds, email: rdomingues@pitcherco.com)
- Azure: tenant 36e770ef-..., subscription PPU (fbcc25e6-...)
- Verify: `git config user.email`, `gh auth status`, `az account show`

## Conventions
- Language: English
- Python: uv preferred, pip acceptable
- Testing: pytest
- Linting: ruff
- Docker: Azure Container Registry

## Environment
- OS: Windows, Shell: PowerShell
- Use PowerShell syntax for all terminal commands
- Do **not** run long multi-line code as inline `python -c "..."` or `bash -c "..."` — it fails and wastes tokens; always write a script file and run it (e.g. `python run_discovery.py`).

## Development RulesApply to all projects. **CLI Safety:** Blocked (never run): `az group delete`, `az keyvault delete`, `az storage account delete`, `az sql server delete`, `gh repo delete`, `git push --force` to main/master, `git reset --hard` on main/master, `rm -rf /` or `rm -rf ~`. **Confirm first:** `az deployment *`, `az webapp deploy`, `az sql db create`, `az role assignment *`, `az keyvault secret set`, `gh pr merge`, `gh release create`, `git push origin main/master`, any production writes or `--yes`/`--force` on remote. **Allowed:** Read-only (`az account show`, `gh pr list`, `git status`/`diff`/`log`), local ops (installs, branches, commits, tests), `git add`/`commit`, `gh pr create`. When in doubt, ask. **Security:** Untrusted by default; validate at boundaries. Code enforces, prompts guide. Least privilege. Use established libs for validation, auth, crypto. **Code quality:** Pydantic/Zod at boundaries; structured errors; no secrets in code. **Operations:** Deploy via GitHub Actions only; no sensitive data in production logs; timeouts on all external calls. **Infrastructure:** Azure-native; GitHub + Actions.
