# Azure Resource Naming Conventions

This document defines the naming standards for all Azure resources in the Dirty Bird Industries environment. Consistent naming improves resource identification, cost tracking, and operational efficiency.

## 📐 Naming Pattern

```
<type>-<workload>-<environment>-<region>[-###]
```

### Components

| Component | Description | Example |
|-----------|-------------|---------|
| `<type>` | Resource type abbreviation | `rg`, `app`, `sql`, `st` |
| `<workload>` | Application or service name | `inventory`, `n8n`, `ecommerce` |
| `<environment>` | Deployment environment | `dev`, `stg`, `prd` |
| `<region>` | Azure region code | `eastus`, `westus`, `centralus` |
| `[-###]` | Optional instance number | `-001`, `-002` |

### Rules

1. **All lowercase** - Use only lowercase letters
2. **Hyphens as separators** - Use `-` between components
3. **No special characters** - Avoid underscores, spaces, or symbols (except storage accounts)
4. **Max length varies** - Respect resource-specific limits (see table below)
5. **Unique where required** - Some resources require globally unique names

---

## 🏷️ Resource Type Abbreviations

### Compute

| Resource Type | Abbreviation | Example | Max Length |
|---------------|--------------|---------|------------|
| Virtual Machine | `vm` | `vm-web-prd-eastus-001` | 15 (Windows), 64 (Linux) |
| Virtual Machine Scale Set | `vmss` | `vmss-api-prd-eastus` | 64 |
| Availability Set | `avail` | `avail-web-prd-eastus` | 80 |
| Azure Kubernetes Service | `aks` | `aks-platform-prd-eastus` | 63 |
| Container Instance | `aci` | `aci-worker-dev-eastus` | 63 |
| Container Registry | `cr` | `crdbipreastus` | 50 (no hyphens) |
| App Service | `app` | `app-api-prd-eastus` | 60 |
| Function App | `func` | `func-webhook-prd-eastus` | 60 |
| App Service Plan | `asp` | `asp-shared-prd-eastus` | 40 |

### Networking

| Resource Type | Abbreviation | Example | Max Length |
|---------------|--------------|---------|------------|
| Virtual Network | `vnet` | `vnet-main-prd-eastus` | 64 |
| Subnet | `snet` | `snet-web-prd-eastus` | 80 |
| Network Security Group | `nsg` | `nsg-web-prd-eastus` | 80 |
| Application Gateway | `agw` | `agw-ingress-prd-eastus` | 80 |
| Load Balancer | `lb` | `lb-api-prd-eastus` | 80 |
| Public IP | `pip` | `pip-agw-prd-eastus` | 80 |
| Private Endpoint | `pe` | `pe-sql-prd-eastus` | 80 |
| DNS Zone | `dns` | `dns-dirtybirdusa-com` | 63 |
| Traffic Manager | `tm` | `tm-global-prd` | 63 |
| Front Door | `fd` | `fd-global-prd` | 64 |

### Storage

| Resource Type | Abbreviation | Example | Max Length |
|---------------|--------------|---------|------------|
| Storage Account | `st` | `stinventoryprdeastus` | 24 (no hyphens, lowercase only) |
| Blob Container | `blob` | `blob-uploads` | 63 |
| File Share | `share` | `share-data` | 63 |
| Data Lake Storage | `dls` | `dlslogseastus` | 24 (no hyphens) |

### Databases

| Resource Type | Abbreviation | Example | Max Length |
|---------------|--------------|---------|------------|
| SQL Server | `sql` | `sql-main-prd-eastus` | 63 |
| SQL Database | `sqldb` | `sqldb-inventory-prd` | 128 |
| Cosmos DB | `cosmos` | `cosmos-app-prd-eastus` | 44 |
| MySQL Server | `mysql` | `mysql-app-prd-eastus` | 63 |
| PostgreSQL Server | `psql` | `psql-app-prd-eastus` | 63 |
| Redis Cache | `redis` | `redis-cache-prd-eastus` | 63 |

### Integration & Messaging

| Resource Type | Abbreviation | Example | Max Length |
|---------------|--------------|---------|------------|
| Service Bus | `sb` | `sb-messaging-prd-eastus` | 50 |
| Event Hub Namespace | `evhns` | `evhns-events-prd-eastus` | 50 |
| Event Hub | `evh` | `evh-orders-prd` | 256 |
| Logic App | `logic` | `logic-workflow-prd-eastus` | 80 |
| API Management | `apim` | `apim-platform-prd-eastus` | 50 |

### AI & Cognitive Services

| Resource Type | Abbreviation | Example | Max Length |
|---------------|--------------|---------|------------|
| Azure OpenAI | `oai` | `oai-dbi-prd-eastus` | 64 |
| Cognitive Services | `cog` | `cog-vision-prd-eastus` | 64 |
| AI Search | `srch` | `srch-knowledge-prd-eastus` | 60 |
| Machine Learning Workspace | `mlw` | `mlw-analytics-prd-eastus` | 260 |
| AI Agent (Container App) | `ca` | `ca-inventory-agent-prd-eastus` | 32 |
| AI Agent (App Service) | `app` | `app-support-agent-prd-eastus` | 60 |
| Bot Service | `bot` | `bot-assistant-prd-eastus` | 64 |
| Document Intelligence | `di` | `di-forms-prd-eastus` | 64 |

> 📘 See [AI Agents Best Practices](ai-agents-best-practices.md) for comprehensive AI deployment guidance.

### Security & Identity

| Resource Type | Abbreviation | Example | Max Length |
|---------------|--------------|---------|------------|
| Key Vault | `kv` | `kv-app-prd-eastus` | 24 |
| Managed Identity | `id` | `id-app-prd-eastus` | 128 |
| Application Registration | `appreg` | `appreg-api-prd` | 120 |

### Monitoring & Management

| Resource Type | Abbreviation | Example | Max Length |
|---------------|--------------|---------|------------|
| Resource Group | `rg` | `rg-inventory-prd-eastus` | 90 |
| Log Analytics Workspace | `log` | `log-central-prd-eastus` | 63 |
| Application Insights | `appi` | `appi-api-prd-eastus` | 255 |
| Action Group | `ag` | `ag-alerts-prd` | 260 |
| Automation Account | `aa` | `aa-ops-prd-eastus` | 50 |

---

## 🌍 Region Codes

| Azure Region | Code |
|--------------|------|
| East US | `eastus` |
| East US 2 | `eastus2` |
| West US | `westus` |
| West US 2 | `westus2` |
| Central US | `centralus` |
| North Central US | `northcentralus` |
| South Central US | `southcentralus` |
| West Europe | `westeurope` |
| North Europe | `northeurope` |

---

## 🔄 Environment Codes

| Environment | Code | Description |
|-------------|------|-------------|
| Development | `dev` | Development and testing |
| Staging | `stg` | Pre-production validation |
| Production | `prd` | Live production systems |
| Sandbox | `sbx` | Experimental/POC |
| Shared | `shd` | Cross-environment resources |

---

## 🔢 Instance Numbering

Use zero-padded three-digit numbers when multiple instances are needed:

```
vm-web-prd-eastus-001
vm-web-prd-eastus-002
vm-web-prd-eastus-003
```

### When to Use Numbering

- ✅ Virtual machines in a scale set or cluster
- ✅ Load-balanced instances
- ✅ Disaster recovery pairs
- ✅ Sharded databases
- ❌ Single-instance resources
- ❌ Unique services

---

## 📝 Special Cases

### Storage Accounts

Storage accounts have strict naming requirements:
- **No hyphens** - concatenate all components
- **Lowercase only** - no uppercase letters
- **3-24 characters** - keep names short
- **Globally unique** - must be unique across all Azure

Pattern: `st<workload><env><region>[###]`

Examples:
- `stlogsdeveastus`
- `stbackupprdeastus001`

### Container Registry

Similar to storage accounts:
- **No hyphens** - concatenate all components
- **5-50 characters**
- **Globally unique**

Pattern: `cr<workload><env><region>`

Examples:
- `crappsprdeastus`
- `crshareddeveastus`

### Key Vault

- **3-24 characters**
- **Globally unique**
- **Alphanumeric and hyphens only**

Pattern: `kv-<workload>-<env>-<region>`

Examples:
- `kv-app-prd-eastus`
- `kv-secrets-dev-eastus`

---

## 🏷️ Tagging Standards

In addition to naming, apply these standard tags to all resources:

### Standard Tags (All Resources)

| Tag Name | Required | Description | Example |
|----------|----------|-------------|---------|
| `Environment` | Yes | Deployment environment | `Production` |
| `Workload` | Yes | Application or service | `Inventory System` |
| `Owner` | Yes | Team or person responsible | `IT Operations` |
| `CostCenter` | Yes | Billing allocation | `IT-001` |
| `CreatedBy` | No | Who created the resource | `terraform`, `manual` |
| `CreatedDate` | No | When resource was created | `2026-01-15` |

### AI Agent Tags (Additional)

For AI agents and related resources, add these additional tags to enable per-agent cost tracking:

| Tag Name | Required | Description | Example |
|----------|----------|-------------|---------|
| `AgentId` | Yes* | Unique agent identifier | `agent-inventory-001` |
| `AgentName` | Yes* | Human-readable agent name | `Inventory Assistant` |
| `Model` | Yes* | AI model used | `gpt-4o` |

*Required for AI agent resources only.

> 📘 See [AI Agents Best Practices](ai-agents-best-practices.md#naming--tagging-standards) for detailed AI tagging guidance.

---

## ✅ Naming Checklist

Before creating a resource, verify:

- [ ] Follows the naming pattern
- [ ] Uses correct abbreviation
- [ ] Environment code is accurate
- [ ] Region code matches deployment location
- [ ] Respects character limits
- [ ] Is unique where required (storage, key vault, etc.)
- [ ] Required tags are applied

---

## 📚 References

- [Azure Naming Rules and Restrictions](https://docs.microsoft.com/en-us/azure/azure-resource-manager/management/resource-name-rules)
- [Azure Cloud Adoption Framework - Naming Convention](https://docs.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/naming-and-tagging)
- [Azure Abbreviation Recommendations](https://docs.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-abbreviations)
