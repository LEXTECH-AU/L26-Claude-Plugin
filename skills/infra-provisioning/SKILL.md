---
name: infra-provisioning
description: Infrastructure provisioning patterns for Lextech microservices via the Lextech_Microservice_Infra Terragrunt repo. Covers service registry, templates, naming conventions, and CI/CD pipeline behavior.
---

# Infrastructure Provisioning Patterns

This skill documents the patterns, conventions, and templates used to provision Azure infrastructure for Lextech microservices via the `LEXTECH-AU/Lextech_Microservice_Infra` repository.

## Repository Overview

The infra repo is a **Terragrunt-based layered platform** managing Azure AKS infrastructure across three environments (dev, staging, prod) plus a shared layer. It uses a modular architecture where each microservice gets its own Terraform state via `modules/service/combined`.

## Adding a New Service -- Required Steps

1. Add entry to `environments/services.yaml` with `create_argocd_application: true`
2. Copy `environments/{env}/services/_template/` to `environments/{env}/services/{service-name}/` for dev, staging, and prod
3. Replace placeholders in `terragrunt.hcl`, set `create_argocd_application = true`
4. Delete `argocd-app.yaml` from copied template directories (ArgoCD app is Terraform-managed)
5. Add `services/{service-name}` to `.github/workflows/deploy.yml` layer choices
6. PR to main -- CI auto-runs validate + plan
7. Merge -- auto-deploys to dev, Terraform creates ArgoCD Application with real values

## Service Registry (`environments/services.yaml`)

Single source of truth for all microservice configurations. Format:

```yaml
services:
  {service-name}:
    # Feature flags
    create_database: false
    create_service_bus_queue: false
    create_storage_account: false
    create_apim_api: true
    create_app_registration: false
    create_helm_values_configmap: true
    create_argocd_application: true
    jwt_validation_enabled: false
    sync_to_github: true

    # APIM
    api_path: {service-name}
    api_display_name: "{Service Display Name} API"
    # openapi_spec_path: "src/{Service}.Api/OpenApi/contract/openapi.yaml"

    # Storage (only if create_storage_account: true)
    # storage_containers:
    #   - documents
    #   - uploads

    # Webhooks (only if external callbacks needed)
    # webhook_allowed_ips:
    #   - "1.2.3.4"

    # GitHub / ArgoCD
    github_repository: {GitHubRepoName}
    helm_repo_url: "https://github.com/LEXTECH-AU/{GitHubRepoName}.git"
    helm_target_revision: main
    helm_path: helm
    argocd_auto_sync: true
```

## Feature Flags Reference

| Flag | Default | Creates |
|------|---------|---------|
| `create_database` | false | PostgreSQL database on shared Flexible Server + AD admin |
| `create_service_bus_queue` | false | Service Bus queue + dead letter queue |
| `create_storage_account` | false | Storage account + blob containers |
| `create_apim_api` | true | APIM API + named backend + JWT policies |
| `create_app_registration` | false | Azure AD app registration + service principal |
| `create_helm_values_configmap` | true | K8s ConfigMap with Helm values |
| `create_argocd_application` | true | ArgoCD Application via Terraform (uses real values) |
| `jwt_validation_enabled` | false | JWT validation policy on APIM |
| `sync_to_github` | true | Sync secrets/variables to GitHub repo environments |
| `create_client_secret` | false | Client secret for app registration (k6 testing) |

## Always-Created Resources (per service)

- Azure Resource Group: `{prefix}-{service}-rg`
- Azure Key Vault: `kv-{svc_short}-{env}-{4char}` (max 24 chars)
- User-Assigned Managed Identity: `{prefix}-{service}-id`
- Federated Identity Credential (K8s SA <-> Azure identity)
- Application Insights: `{prefix}-{service}-ai`
- Private DNS A Record: `{service}.{dns_zone}`
- RBAC: Key Vault Secrets User, Certificate User, Administrator, AcrPull

## Template Placeholders

The templates in `environments/{env}/services/_template/` use these placeholders in `terragrunt.hcl`:

| Placeholder | Example Value | Description |
|-------------|---------------|-------------|
| `__SERVICE_NAME__` | `order-service` | Lowercase with hyphens |
| `__SERVICE_REPO__` | `OrderService` | GitHub repository name (PascalCase) |
| `__SERVICE_DISPLAY_NAME__` | `Order Service` | Human-readable name for APIM |

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

## Environment Differences

| Setting | Dev | Staging | Prod |
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

| Event | Action |
|-------|--------|
| PR to main | Validate (lint, security scan, Helm lint, K8s validation) + Plan (per affected env/layer) |
| Merge to main | Auto-deploy changed layers to dev |
| workflow_dispatch | Manual deploy to staging/prod with approval |

The CI posts automated "Infrastructure Plan Summary" comments on PRs showing which env/layer combos will change.

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

## Terragrunt Template Structure

Each service's `terragrunt.hcl` uses two includes:
- `include "root"` -- pulls in the root `terragrunt.hcl` (providers, backend, global inputs)
- `include "service"` -- pulls in `_service.hcl` (shared wiring for dependencies, providers, module source)

The `_service.hcl` eliminates ~70% of boilerplate by auto-wiring dependencies on foundation, shared ACR, data, compute, gateway, and GitHub actions identity layers.

## ArgoCD Application Pattern

ArgoCD Applications are **Terraform-managed** via the `create_argocd_application = true` flag. The Terraform module (`modules/service/app/main.tf`) creates the ArgoCD Application using `kubectl_manifest` with real values resolved at apply time:

- **Managed Identity Client ID** -- from the identity module output
- **ACR Server** -- from the shared ACR dependency
- **Ingress Host** -- computed from service name and DNS zone
- **APIM IP** -- from the gateway dependency

This avoids the placeholder chicken-and-egg problem where `argocd-app.yaml` files with placeholders like `__INGRESS_HOST__` get auto-discovered by the `services-root` app-of-apps and fail to sync (e.g., `__INGRESS_HOST__` is not a valid RFC 1123 hostname).

ArgoCD apps use multi-source Helm with three sources:
1. **Archetype chart** from `charts/archetypes/api-service` in the infra repo
2. **Service-specific values** from the service's own repo (`helm/values.yaml`)
3. **Environment overlay** from `charts/overlays/{env}/values.yaml` in the infra repo

For **dev**, `argocd_auto_sync = true` enables automatic sync. For **staging** and **prod**, `argocd_auto_sync = false` requires manual sync approval.

> **Note**: Migration to GitOps-managed `argocd-app.yaml` files is possible later once the initial Terraform apply has populated all values and the service is running. This is optional and not required for initial provisioning.

## PR Conventions

- **Title**: `feat: Add {service-name} infrastructure`
- **Body**: Summary bullets, architecture notes, test plan checklist
- **Footer**: `Generated with [Claude Code](https://claude.com/claude-code)`
