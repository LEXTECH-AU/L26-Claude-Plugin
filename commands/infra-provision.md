---
name: infra-provision
description: Provision infrastructure for a new microservice by creating a PR in the Lextech_Microservice_Infra repo
argument-hint: "[service-name] [GitHubRepoName]"
---

# Provision Infrastructure for a New Microservice

You are provisioning Azure infrastructure for a new Lextech microservice by creating a PR in the `LEXTECH-AU/Lextech_Microservice_Infra` repository. Follow every step precisely.

## Step 1: Parse Arguments

Parse the arguments provided by the user. Expect up to two positional arguments:

1. **service-name** -- Lowercase with hyphens (e.g., `order-service`, `billing-service`). Must match pattern `^[a-z][a-z0-9-]*[a-z0-9]$` and be 50 chars or fewer.
2. **GitHubRepoName** -- The GitHub repository name in PascalCase (e.g., `OrderService`, `BillingService`). If not provided, derive it from the service name by removing hyphens and PascalCasing (e.g., `order-service` -> `OrderService`).

If service-name is missing, ask the user interactively. Confirm both values before proceeding.

Derive these additional values:
- **service_display_name**: Human-readable name with spaces (e.g., `Order Service`)
- **db_name**: Service name with hyphens replaced by underscores (e.g., `order_service`)

## Step 2: Select Azure Services

Ask the user which Azure services to enable for this microservice. Present each as a yes/no choice with the default shown:

1. **PostgreSQL Database** (`create_database`) -- Default: true
2. **Service Bus Queue** (`create_service_bus_queue`) -- Default: false
3. **Blob Storage** (`create_storage_account`) -- Default: false
4. **APIM API Registration** (`create_apim_api`) -- Default: true
5. **Azure AD App Registration** (`create_app_registration`) -- Default: false
6. **JWT Validation** (`jwt_validation_enabled`) -- Default: false (set true when app registration is enabled)
7. **k6 Client Secret** (`create_client_secret`) -- Default: false

If **Blob Storage** is enabled, ask for the container names (comma-separated). Default: `["documents"]`.

If **Webhooks** are needed, ask for the allowed IP addresses (comma-separated). Default: none.

Confirm the full configuration with the user before proceeding.

## Step 3: Load the Infra-Provisioning Skill

Read the `infra-provisioning` skill to load the naming conventions, template structure, feature flags reference, and environment differences. Use this as your reference for all subsequent steps.

## Step 4: Clone the Infra Repo

```bash
# Create a temporary working directory
WORK_DIR=$(mktemp -d)
cd "$WORK_DIR"

# Clone the infra repo (shallow clone for speed)
gh repo clone LEXTECH-AU/Lextech_Microservice_Infra -- --depth=1
cd Lextech_Microservice_Infra

# Create a feature branch
git checkout -b feat/add-{service-name}-infra
```

Verify the clone succeeded and the branch was created.

## Step 5: Add Service Entry to services.yaml

Edit `environments/services.yaml` to add the new service entry. Place it after the last existing service entry (before any commented-out templates).

Add a section header comment and the full service configuration using the feature flags chosen in Step 2. Follow the exact format of the existing `property-service` entry:

```yaml
  # ---------------------------------------------------------------------------
  # {Service Display Name}
  # ---------------------------------------------------------------------------
  {service-name}:
    # Feature flags
    create_database: {true|false}
    create_service_bus_queue: {true|false}
    create_storage_account: {true|false}
    create_apim_api: {true|false}
    create_app_registration: {true|false}
    create_helm_values_configmap: true
    create_argocd_application: true
    jwt_validation_enabled: {true|false}
    sync_to_github: true

    # Storage (only if create_storage_account: true)
    # storage_containers:
    #   - documents

    # APIM
    api_path: {service-name}
    api_display_name: "{Service Display Name} API"

    # GitHub / ArgoCD
    github_repository: {GitHubRepoName}
    helm_repo_url: "https://github.com/LEXTECH-AU/{GitHubRepoName}.git"
    helm_target_revision: main
    helm_path: helm
    argocd_auto_sync: true
```

If storage containers or webhook IPs were specified, uncomment and populate those sections.

## Step 6: Create Service Directories for All Environments

For each environment (dev, staging, prod):

### 6a. Copy the Template

```bash
cp -r environments/{env}/services/_template/ environments/{env}/services/{service-name}/
```

### 6b. Configure terragrunt.hcl

Edit `environments/{env}/services/{service-name}/terragrunt.hcl`:

1. Replace all `__SERVICE_NAME__` with the actual service name
2. Replace all `__SERVICE_REPO__` with the GitHub repo name
3. Replace `__SERVICE_DISPLAY_NAME__` with the display name
4. Set each feature flag (`create_database`, `create_service_bus_queue`, etc.) to the value chosen in Step 2
5. Set `create_argocd_application = true`
6. For **dev**: set `argocd_auto_sync = true`
7. For **staging** and **prod**: set `argocd_auto_sync = false`
8. If storage containers were specified, uncomment and populate the `storage_containers` list
9. If webhook IPs were specified, uncomment and populate the `webhook_allowed_ips` list
10. Remove the template onboarding checklist comment block at the top
11. Add a proper header comment matching the property-service pattern:

```hcl
# =============================================================================
# {Service Display Name} - {Env}
# =============================================================================
# Creates: Key Vault, Managed Identity, RBAC, K8s resources{, Database}{, Storage}{, Queue}
# =============================================================================
```

### 6c. Delete argocd-app.yaml if present

Delete `environments/{env}/services/{service-name}/argocd-app.yaml` if it exists in the copied template. The ArgoCD Application is now Terraform-managed via `create_argocd_application = true` -- no template file is needed.

```bash
rm -f environments/{env}/services/{service-name}/argocd-app.yaml
```

### 6d. Remove template README

Delete `environments/{env}/services/{service-name}/README.md` -- it's only useful in the `_template/` directory.

## Step 7: Update Deploy Workflow

Edit `.github/workflows/deploy.yml` to add the new service to the layer choices.

Find the `layer` input under `workflow_dispatch.inputs` and add `services/{service-name}` to the `options` list, placing it alphabetically among other service entries:

```yaml
      layer:
        description: 'Layer to deploy (or all)'
        required: true
        default: 'all'
        type: choice
        options:
          - all
          - foundation
          - shared
          - data
          - compute
          - gateway
          - services/{service-name}    # <-- ADD THIS
          - services/property-service
          - acr
          - github-actions-identity
```

## Step 8: Commit and Push

Stage all changes, create a commit, and push:

```bash
git add -A
git commit -m "feat: Add {service-name} infrastructure

- Add {service-name} to services.yaml with feature flags
- Create dev/staging/prod service configurations from template
- ArgoCD Application managed by Terraform (create_argocd_application = true)
- Add deploy workflow layer option

Services enabled: {list enabled services}

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

git push -u origin feat/add-{service-name}-infra
```

## Step 9: Create Pull Request

Create a PR in the infra repo using `gh`:

```bash
gh pr create \
  --repo LEXTECH-AU/Lextech_Microservice_Infra \
  --title "feat: Add {service-name} infrastructure" \
  --body "$(cat <<'EOF'
## Summary
- Add **{service-name}** microservice infrastructure configuration
- Configure service across dev, staging, and prod environments
- ArgoCD Application is Terraform-managed (`create_argocd_application = true`)
- Enable: {list of enabled Azure services}

### Service Configuration
| Setting | Value |
|---------|-------|
| Service Name | `{service-name}` |
| GitHub Repo | `{GitHubRepoName}` |
| Database | {yes/no} |
| Service Bus Queue | {yes/no} |
| Blob Storage | {yes/no} |
| APIM API | {yes/no} |
| App Registration | {yes/no} |
| JWT Validation | {yes/no} |

### Files Changed
- `environments/services.yaml` -- Added service entry
- `environments/dev/services/{service-name}/` -- Dev configuration
- `environments/staging/services/{service-name}/` -- Staging configuration
- `environments/prod/services/{service-name}/` -- Prod configuration
- `.github/workflows/deploy.yml` -- Added deploy layer option

## Post-Merge Steps
After the PR is merged and `terragrunt apply` completes for dev:
1. Terraform creates the ArgoCD Application automatically with correct values
2. Push the container image to ACR to trigger the first ArgoCD sync
3. Verify ArgoCD sync in the dev cluster

## Test plan
- [ ] CI validates Terraform format and lint
- [ ] CI runs security scan (Trivy)
- [ ] CI validates Helm charts and K8s manifests
- [ ] CI runs `terragrunt plan` for dev -- review plan output
- [ ] Verify plan shows only create operations (no unexpected changes)
- [ ] After merge: verify dev auto-deploy succeeds
- [ ] After merge: verify ArgoCD Application is created with correct values

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

## Step 10: Verify and Summarize

After the PR is created:

1. Display the PR URL.
2. List all files created/modified.
3. Remind the user of the post-merge workflow:
   - CI will automatically run validate + plan on the PR
   - Check the plan summary comment for expected resources
   - After merge, dev auto-deploys
   - Terraform creates the ArgoCD Application with real values (managed identity client ID, ACR server, ingress host, APIM IP)
   - Push container image to ACR
   - Verify ArgoCD sync in the dev cluster
4. Display a summary table of the service configuration.

## Important Rules

- **Never modify existing services** -- only add the new service entry.
- **All three environments** (dev, staging, prod) must be configured -- never skip one.
- **ArgoCD Application is Terraform-managed** -- set `create_argocd_application = true` in services.yaml and all terragrunt.hcl files. Delete any `argocd-app.yaml` template files. Terraform resolves all values (client ID, ACR server, ingress host, APIM IP) at apply time, avoiding placeholder sync failures.
- **Deploy workflow** must be updated or the service cannot be manually deployed.
- **services.yaml** is the single source of truth -- the entry here must match the terragrunt.hcl inputs exactly.
- **Staging and prod** must have `argocd_auto_sync = false` (manual sync only).
- **Do not run `terragrunt plan` or `terragrunt apply`** -- that happens via CI after the PR is merged.
- **Clean up**: remove the temporary clone directory after the PR is created.
