---
name: infra-provisioning
description: Infrastructure provisioning patterns for Lextech microservices via the Lextech_Microservice_Infra Terragrunt repo. Covers service configuration, templates, naming conventions, and CI/CD pipeline behavior.
---

# Infrastructure Provisioning Patterns

This skill documents the patterns, conventions, and templates used to provision Azure infrastructure for Lextech microservices via the `LEXTECH-AU/Lextech_Microservice_Infra` repository.

## Repository Overview

The infra repo is a **Terragrunt-based layered platform** managing Azure AKS infrastructure. Currently only the **dev** environment and a **shared** layer are deployed. Staging and prod environments will be added later as the platform matures. Each microservice gets its own Terraform state via split `modules/service/data` (persistent) and `modules/service/app` (ephemeral) modules.

### Repository Structure

```
environments/
  _service_data.hcl       # Shared Terragrunt include for service data layer
  _service_app.hcl        # Shared Terragrunt include for service app layer
  _env.hcl, _foundation.hcl, _data.hcl, _compute.hcl, _gateway.hcl
  dev/
    env.hcl, region.hcl, terraform.tfvars
    foundation/, shared/, data/, compute/, gateway/  # Platform layers
    services/
      _template/           # Template files for new services
      property-service/    # Reference implementation
      skeleton-service/
  shared/
    acr/                   # Shared container registry
    github-actions-identity/
modules/
  service/
    data/                  # Persistent resources (RG, KV, DB, Storage)
    app/                   # Ephemeral resources (Identity, APIM, K8s)
k8s/
  argocd/
    applicationset-services.yaml  # ApplicationSet for service discovery
charts/
  archetypes/api-service/  # Base Helm chart archetype
  overlays/dev/            # Dev environment value overrides
.github/workflows/
  deploy.yml               # Unified deploy (terragrunt run-all)
  plan.yml                 # PR plan + comment
  validate.yml             # PR lint, security scan, Helm validation
  test.yml                 # Terratest suite
  drift-detect.yml         # Weekly drift detection
```

## Adding a New Service -- Required Steps

1. Copy `data/terragrunt.hcl`, `app/terragrunt.hcl`, and `service.yaml` from `environments/dev/services/_template/`
2. Replace `__SERVICE_NAME__` and `__SERVICE_REPO__` in all files
3. Configure feature flags in `data/terragrunt.hcl` and `app/terragrunt.hcl`
4. Configure `service.yaml` (helm_pattern, database, service_bus, eso_enabled)
5. Leave `__PENDING__` sentinels for `client_id` and `key_vault_name`
6. Add `services/{service-name}/data` and `services/{service-name}/app` to `.github/workflows/deploy.yml` options list
7. PR to main -- CI auto-runs validate + plan
8. Merge -- auto-deploys to dev via `terragrunt run-all apply`
9. CI post-apply step auto-replaces `__PENDING__` sentinels with real Terraform outputs
10. ApplicationSet discovers `service.yaml` and generates ArgoCD Application

## Service Configuration

Service configuration is stored per-service in `environments/dev/services/{service-name}/service.yaml`. There is no central registry file.

### Existing Services

| Service | Database | Queue | Storage | APIM | App Reg | Pattern |
|---------|----------|-------|---------|------|---------|---------|
| property-service | Yes | Yes | Yes | Yes | Yes | B (service-repo) |
| skeleton-service | Yes | No | No | Yes | Yes | B (service-repo) |
| claude-plugin-microservice-a | Yes | No | No | Yes | Yes | A (platform-only) |

## Feature Flags Reference

| Flag | Module Default | `_service.hcl` Override | Creates |
|------|---------------|------------------------|---------|
| `create_database` | true | -- | PostgreSQL database on shared Flexible Server + AD admin |
| `create_service_bus_queue` | false | -- | Service Bus queue + dead letter queue |
| `create_storage_account` | false | -- | Storage account + blob containers |
| `create_apim_api` | false | **true** | APIM API + named backend + JWT policies |
| `create_app_registration` | false | **true** | Azure AD app registration + service principal |
| `create_helm_values_configmap` | false | -- | K8s ConfigMap with Helm values |
| `create_argocd_application` | false | -- | ArgoCD Application via Terraform (NOT used -- prefer GitOps) |
| `jwt_validation_enabled` | false | -- | JWT validation policy on APIM |
| `sync_to_github` | false | -- | Sync secrets/variables to GitHub repo environments |
| `create_client_secret` | false | **true** | Client secret for app registration (k6 testing) |

**Important**: The `_service.hcl` file overrides three defaults for ALL services: `create_apim_api=true`, `create_app_registration=true`, `create_client_secret=true`. You only need to explicitly set flags in `terragrunt.hcl` that differ from these effective defaults.

## Always-Created Resources (per service)

- Azure Resource Group: `{prefix}-{service}-rg`
- Azure Key Vault: `kv-{svc_short}-{env}-{4char}` (max 24 chars)
- User-Assigned Managed Identity: `{prefix}-{service}-id`
- Federated Identity Credential (K8s SA <-> Azure identity)
- Application Insights: `{prefix}-{service}-ai`
- ClusterSecretStore (External Secrets Operator)
- Private DNS A Record: `{service}.{dns_zone}`
- K8s Namespace with ResourceQuota, LimitRange, NetworkPolicy
- RBAC: Key Vault Secrets User, Certificate User, Administrator, AcrPull

## Template Files

The `environments/dev/services/_template/` directory contains:

| File | Copy? | Purpose |
|------|-------|---------|
| `data/terragrunt.hcl` | **Yes** | Data layer Terragrunt configuration (persistent resources) |
| `app/terragrunt.hcl` | **Yes** | App layer Terragrunt configuration (ephemeral resources) |
| `service.yaml` | **Yes** | ArgoCD ApplicationSet service configuration |
| `README.md` | No | Template usage docs |

### Placeholders in `terragrunt.hcl`

| Placeholder | Example Value | Description |
|-------------|---------------|-------------|
| `__SERVICE_NAME__` | `order-service` | Lowercase with hyphens |
| `__SERVICE_REPO__` | `OrderService` | GitHub repository name (PascalCase) |
| `__SERVICE_DISPLAY_NAME__` | `Order Service` | Human-readable name for APIM `api_display_name` |

### Placeholders in `service.yaml`

| Placeholder | Replaced By | When |
|-------------|-------------|------|
| `__SERVICE_NAME__` | You (manually) | Before committing |
| `__SERVICE_REPO__` | You (manually) | Before committing |
| `__PENDING__` (client_id) | CI post-apply step | After `terragrunt apply` |
| `__PENDING__` (key_vault_name) | CI post-apply step | After `terragrunt apply` |

Only `__SERVICE_NAME__` and `__SERVICE_REPO__` need manual replacement. The CI deploy workflow (`deploy.yml`) has a post-apply step that automatically replaces the `__PENDING__` sentinels with real Terraform output values and pushes a commit.

## `_service.hcl` Auto-Wired Variables

The `_service.hcl` file eliminates ~70% of boilerplate by auto-wiring these from platform layer dependencies. Services never need to set these:

| Category | Variables Auto-Wired |
|----------|---------------------|
| Identity | `name_prefix`, `environment`, `location`, `tags` |
| Networking | `vnet_id`, `private_endpoints_subnet_id`, `enable_private_endpoints`, `keyvault_private_dns_zone_id` |
| Monitoring | `log_analytics_workspace_id` |
| Kubernetes | `aks_oidc_issuer_url`, `eso_identity_principal_id` |
| Container Registry | `acr_id`, `acr_login_server` |
| Ingress | `internal_dns_zone_name`, `internal_dns_zone_resource_group`, `internal_ingress_ip`, `ingress_allowed_ips` |
| APIM | `apim_id`, `apim_name`, `apim_resource_group_name`, `apim_gateway_url`, `apim_subnet_prefix` |
| Data Layer | `postgresql_server_id/fqdn/name`, `postgresql_resource_group`, `postgresql_admin_login/password`, `service_bus_namespace_id`, `service_bus_connection_string`, `service_bus_namespace` |
| GitHub | `github_actions_client_id`, `github_actions_object_id` |
| Testing | `k6_cloud_token` |
| Azure AD | `azuread_allowed_tenants` |

### Feature Flag Defaults Set by `_service.hcl`

```hcl
create_apim_api         = true
create_app_registration = true
create_client_secret    = true
```

These are merged with the child service's inputs. Only override in your `terragrunt.hcl` if you need a different value.

## Terragrunt Template Structure

Each service has two `terragrunt.hcl` files using shared includes:
- `data/terragrunt.hcl` -- uses `include "service_data"` pulling in `_service_data.hcl`
- `app/terragrunt.hcl` -- uses `include "service_app"` pulling in `_service_app.hcl`

Both include:
- `include "root"` -- pulls in the root `terragrunt.hcl` (providers, backend, global inputs)

A minimal service `data/terragrunt.hcl` only needs:
```hcl
include "root" {
  path = find_in_parent_folders()
}

include "service_data" {
  path           = find_in_parent_folders("_service_data.hcl")
  merge_strategy = "deep"
  expose         = true
}

locals {
  service_name = "my-service"
  env_vars     = include.service_data.locals.env_vars
}

inputs = {
  service_name = local.service_name
  tags = merge(local.env_vars.tags, {
    Service = local.service_name
  })

  # Uncomment flags that differ from defaults:
  # create_database = true
}
```

## ArgoCD ApplicationSet Pattern

ArgoCD Applications are generated by an **ApplicationSet** (`k8s/argocd/applicationset-services.yaml`) using a Git file generator that scans `environments/dev/services/*/service.yaml`.

The ApplicationSet:
- Uses Go templates to generate Applications from service.yaml values
- Supports two Helm patterns: `service-repo` (Pattern B, with external helm chart) and `platform-only` (Pattern A, archetype only)
- Configures ArgoCD Image Updater via Application annotations (no separate ImageUpdater CRD needed)
- Handles all derivable values (ACR server, ingress host, APIM IP, ESO store name) from hardcoded platform values
- Only `client_id` and `key_vault_name` come from the per-service service.yaml

### How It Works

1. Service dir has `service.yaml` with `__PENDING__` sentinels
2. PR merged -> CI runs `terragrunt apply` -> creates Azure resources
3. CI post-apply step reads Terraform outputs and replaces `__PENDING__` sentinels
4. CI commits the updated `service.yaml`
5. ApplicationSet discovers it and generates the ArgoCD Application
6. ArgoCD Image Updater (configured via Application annotations) watches for new images

### Multi-Source Helm Architecture

ArgoCD apps use multi-source Helm with up to three sources:
1. **Archetype chart** from `charts/archetypes/api-service` in the infra repo
2. **Service-specific values** from the service's own repo (`helm/values.yaml`) -- optional, Pattern B only
3. **Environment overlay** from `charts/overlays/{env}/values.yaml` in the infra repo

**Pattern A (Platform-only)**: Service has no Helm chart. All values from archetype + overlay + inline parameters. This is the default.

**Pattern B (External repo)**: Service has its own `helm/` directory with `values.yaml`. The ApplicationSet template includes the service repo as an additional Helm source when `helm_pattern: service-repo`.

### ArgoCD Image Updater

Image Updater is configured via annotations on the generated Application (handled by the ApplicationSet template). No separate `image-updater.yaml` file is needed.

> **Note**: The Terraform module also supports `create_argocd_application = true` which creates the ArgoCD Application directly via `kubectl_manifest` with real values at apply time. This avoids the placeholder chicken-and-egg problem but is NOT currently used by any deployed service. All existing services use the ApplicationSet GitOps pattern.

## Naming Conventions

| Resource | Pattern | Example |
|----------|---------|---------|
| Name prefix | `lextech-{env}-aue` | `lextech-dev-aue` |
| Resource Group | `{prefix}-{service}-rg` | `lextech-dev-aue-property-service-rg` |
| Key Vault | `kv-{svc_short}-{env}-{4char}` | `kv-propertyse-dev-u6jv` |
| Managed Identity | `{prefix}-{service}-id` | `lextech-dev-aue-property-service-id` |
| App Insights | `{prefix}-{service}-ai` | `lextech-dev-aue-property-service-ai` |
| Database name | `{service_name}` (underscores) | `property_service` |
| K8s Namespace | `{service-name}` | `property-service` |
| Service Account | `{service}-sa` | `property-service-sa` |
| DNS | `{service}.{prefix}.internal` | `property-service.lextech-dev-aue.internal` |
| ESO Store | `azure-keyvault-{service-name}` | `azure-keyvault-property-service` |

## Environment Differences

Currently only **dev** is deployed for services. Staging and prod will be added later.

| Setting | Dev | Staging (planned) | Prod (planned) |
|---------|-----|---------|------|
| AKS Private | No | No | Yes |
| AKS Nodes | 1-3 | 2-5 | 3-20 (AZ) |
| PostgreSQL SKU | B_Standard_B2ms | GP_Standard_D2ds_v4 | GP_Standard_D4ds_v4 |
| PostgreSQL HA | None | None | Zone Redundant |
| Service Bus | Standard | Standard | Premium |
| Redis | Basic C0 | Standard C1 | Premium P1 |
| APIM | Developer_1 | Developer_1 | Premium_1 |
| Private Endpoints | Disabled | Enabled | Enabled |
| ArgoCD Auto-Sync | Yes | No (manual) | No (manual) |
| Resource Locks | No | Yes | Yes |

## CI/CD Pipeline Behavior

### Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `deploy.yml` | Push to main, workflow_dispatch | Unified deploy via `terragrunt run-all` with `--terragrunt-strict-include` |
| `plan.yml` | PR to main | Runs `terragrunt plan` per changed env/layer, posts PR summary comment |
| `validate.yml` | PR to main | TFLint, `terraform fmt`, Trivy security scan, Helm lint, kubeconform, OPA policies |
| `test.yml` | PR, push to main, weekly | Terratest suite (unit, component, integration, e2e) |
| `drift-detect.yml` | Weekly (Sunday 6am UTC) | Detects drift in infrastructure layers |

### Deploy Workflow Details

The `deploy.yml` workflow uses **filesystem auto-discovery** for services:
- On push to main: detects changed files, iterates `environments/${ENV}/services/*/` to find services with `terragrunt.hcl`
- On workflow_dispatch: uses the selected layer from the dropdown, or discovers all services when `layer=all`
- Services are deployed via `terragrunt run-all apply --terragrunt-strict-include` with dynamic `--include-dir` flags
- After apply, a post-apply step scans service `service.yaml` files for remaining `__PENDING__` sentinels and replaces them with Terraform outputs

### Pipeline Events

| Event | Action |
|-------|--------|
| PR to main | Validate (lint, security scan, Helm lint, K8s validation) + Plan (per affected env/layer) |
| Merge to main | Auto-deploy changed layers to dev via `terragrunt run-all apply` |
| workflow_dispatch | Manual deploy to any environment with layer selection |

## Key Vault Secrets (Auto-populated by Terraform)

- `db-connection-string` (if create_database)
- `BlobStorage--AccountUrl` (if create_storage_account)
- `BlobStorage--Container--{ContainerName}` (per container)
- `ServiceBus--ConnectionString` (if create_service_bus_queue)
- `ServiceBus--FullyQualifiedNamespace`
- `AzureAd--TenantId`, `AzureAd--Instance`, `AzureAd--AllowedTenants`
- `AzureAd--ClientId`, `AzureAd--Audience` (if create_app_registration)
- `CallbackConfig--TitleSearchCallbackUrl`
- `Webhook--AllowedIps`

## GitHub Secrets/Variables Synced (if sync_to_github)

**Variables**: `KEY_VAULT_NAME`, `WORKLOAD_IDENTITY_CLIENT_ID`, `ACR_NAME`, `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `APIM_NAME`, `APIM_RESOURCE_GROUP`, `K6_BASE_URL`, `K6_AZURE_CLIENT_ID`, `K6_AZURE_SCOPE`

**Secrets**: `K6_CLOUD_TOKEN`, `K6_AZURE_CLIENT_SECRET`

## Advanced Module Variables

These variables have sensible defaults but can be overridden in `terragrunt.hcl` for advanced use cases:

### Service Bus Tuning
| Variable | Default | Description |
|----------|---------|-------------|
| `service_bus_queue_max_delivery_count` | 10 | Max delivery attempts before dead-letter |
| `service_bus_queue_max_size_mb` | 1024 | Queue size limit |
| `service_bus_queue_message_ttl` | `P14D` | Message time-to-live |
| `service_bus_queue_lock_duration` | `PT1M` | Message lock duration |

### Namespace Hardening (enabled by default)
| Variable | Default | Description |
|----------|---------|-------------|
| `enable_resource_quota` | true | K8s ResourceQuota on namespace |
| `enable_limit_range` | true | K8s LimitRange on namespace |
| `enable_network_policies` | true | K8s NetworkPolicy (zero-trust) |

Override `resource_quota` or `limit_range` objects if the service needs more than the default limits (e.g., more than 20 pods or 2 CPU).

### App Registration
| Variable | Default | Description |
|----------|---------|-------------|
| `sign_in_audience` | `AzureADMultipleOrgs` | Azure AD sign-in audience |
| `create_app_role` | true | Create app role on registration |

## PR Conventions

- **Title**: `feat: Add {service-name} infrastructure`
- **Body**: Summary bullets, service configuration table, files changed, post-merge steps, test plan
- **Footer**: `Generated with [Claude Code](https://claude.com/claude-code)`
