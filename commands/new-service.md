---
name: new-service
description: Create a new microservice from the skeleton template, create GitHub repo, and provision Azure infrastructure
argument-hint: "[service-name] [GitHubRepoName]"
---

# Create a New Microservice

You are creating a complete new Lextech microservice end-to-end: cloning the skeleton, renaming everything, creating the GitHub repo, and provisioning Azure infrastructure. Follow every step precisely.

## Step 1: Parse Arguments

Parse the arguments provided by the user. Expect up to two positional arguments:

1. **service-name** -- Lowercase with hyphens (e.g., `order-service`, `billing-service`). Must match pattern `^[a-z][a-z0-9-]*[a-z0-9]$` and be 50 chars or fewer.
2. **GitHubRepoName** -- The GitHub repository name in PascalCase (e.g., `OrderService`, `BillingService`). If not provided, derive it from the service name by removing hyphens and PascalCasing (e.g., `order-service` -> `OrderService`).

If service-name is missing, ask the user interactively. Confirm both values before proceeding.

Derive these additional values:
- **PascalName**: Same as GitHubRepoName (e.g., `OrderService`) -- used for namespace prefix (`OrderService.Api`)
- **kebab_name**: Same as service-name (e.g., `order-service`) -- used for Docker image, Helm, APIM
- **db_name**: Service name with hyphens replaced by underscores (e.g., `order_service`) -- PostgreSQL database name
- **display_name**: Human-readable name with spaces (e.g., `Order Service`)

## Step 2: Select Azure Services

Ask the user which Azure services to enable for this microservice. Present each as a yes/no choice with the default shown.

**Important**: The defaults below reflect what `_service.hcl` auto-wires. Only flags that differ from these defaults need to be explicitly set in `terragrunt.hcl`.

1. **PostgreSQL Database** (`create_database`) -- Default: true
2. **Service Bus Queue** (`create_service_bus_queue`) -- Default: false
3. **Blob Storage** (`create_storage_account`) -- Default: false
4. **APIM API Registration** (`create_apim_api`) -- Default: true (set by `_service.hcl`)
5. **Azure AD App Registration** (`create_app_registration`) -- Default: true (set by `_service.hcl`)
6. **JWT Validation** (`jwt_validation_enabled`) -- Default: false
7. **k6 Client Secret** (`create_client_secret`) -- Default: true (set by `_service.hcl`)

If **Blob Storage** is enabled, ask for the container names (comma-separated). Default: `["documents"]`.

If **Webhooks** are needed, ask for the allowed IP addresses (comma-separated). Default: none.

Confirm the full configuration with the user before proceeding.

## Step 3: Clone Skeleton from GitHub

```bash
WORK_DIR=$(mktemp -d)
cd "$WORK_DIR"
gh repo clone LEXTECH-AU/L26-Skeleton-Microservice -- --depth=1
mv L26-Skeleton-Microservice {GitHubRepoName}
cd {GitHubRepoName}
rm -rf .git
```

Verify the clone succeeded and the directory was renamed.

## Step 4: Strip Skeleton-Specific Files

Remove files that are skeleton-specific and shouldn't carry over to the new service:

```bash
rm -rf plans/ CONTEXT.md .claude/
```

## Step 5: Rename -- Directories

Rename all project directories from `L26SkeletonMicroservice.*` to `{PascalName}.*`:

```bash
# src/ directories
mv src/L26SkeletonMicroservice.Api src/{PascalName}.Api
mv src/L26SkeletonMicroservice.Application src/{PascalName}.Application
mv src/L26SkeletonMicroservice.Domain src/{PascalName}.Domain
mv src/L26SkeletonMicroservice.Infrastructure src/{PascalName}.Infrastructure

# test/ directories
mv tests/L26SkeletonMicroservice.UnitTests tests/{PascalName}.UnitTests
mv tests/L26SkeletonMicroservice.IntegrationTests tests/{PascalName}.IntegrationTests
```

## Step 6: Rename -- File Contents (Global Find-Replace)

Four sequential replacements across ALL files (respecting case):

1. `L26SkeletonMicroservice` -> `{PascalName}` (namespaces, project refs, assembly names -- ~219 occurrences)
2. `l26-skeleton-microservice` -> `{kebab_name}` (Docker image name in CI and Helm -- ~3 occurrences)
3. `skeleton-service` -> `{kebab_name}` (APIM, Helm SA, pod annotations -- ~6 occurrences)
4. `SkeletonService` -> `{PascalName}` (OpenTelemetry serviceName in Helm -- ~1 occurrence)

Files to process: `.sln`, `.csproj`, `.cs`, `.json`, `.yaml`, `.yml`, `Dockerfile` -- skip `.git/`, `bin/`, `obj/`.

Also rename the `.csproj` files themselves (they're inside the already-renamed directories but the filenames need updating too):

```bash
# Each .csproj file: mv L26SkeletonMicroservice.{Layer}.csproj {PascalName}.{Layer}.csproj
```

## Step 7: Generate New GUIDs for Solution

Replace the project GUIDs in `src/src.sln` with freshly generated GUIDs so the new solution doesn't collide with the skeleton.

## Step 8: Update UserSecretsId

In `{PascalName}.Api.csproj`, replace the `UserSecretsId` value `l26-skeleton-microservice-api` with `{kebab_name}-api`.

## Step 9: Build Verification

```bash
dotnet restore src/src.sln
dotnet build src/src.sln --no-restore
```

If the build fails, report the errors and stop. The user needs to fix before continuing.

## Step 10: Create GitHub Repo and Push

```bash
gh repo create LEXTECH-AU/{GitHubRepoName} --private --source=. --push
```

Push initial code to `main`:

```bash
git init
git add -A
git commit -m "feat: Initial scaffold from L26-Skeleton-Microservice

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
git branch -M main
gh repo create LEXTECH-AU/{GitHubRepoName} --private --source=. --push
```

## Step 11: Provision Infrastructure

Now provision the Azure infrastructure by creating a PR in the infra repo. This uses the Azure service selections from Step 2.

### 11a. Load the Infra-Provisioning Skill

Read the `infra-provisioning` skill to load the naming conventions, template structure, feature flags reference, and environment differences. Use this as your reference for all subsequent sub-steps.

### 11b. Clone the Infra Repo

```bash
INFRA_DIR=$(mktemp -d)
cd "$INFRA_DIR"

# Clone the infra repo (shallow clone for speed)
gh repo clone LEXTECH-AU/Lextech_Microservice_Infra -- --depth=1
cd Lextech_Microservice_Infra

# Create a feature branch
git checkout -b feat/add-{service-name}-infra
```

Verify the clone succeeded and the branch was created.

### 11c. Create Dev Service Directory

Only create the **dev** environment configuration. Staging and prod environments do not exist yet in the repo and are promoted separately later.

#### Copy Template Files

Copy the three required files from the template directory:

```bash
mkdir -p environments/dev/services/{service-name}/data
mkdir -p environments/dev/services/{service-name}/app
cp environments/dev/services/_template/data/terragrunt.hcl environments/dev/services/{service-name}/data/terragrunt.hcl
cp environments/dev/services/_template/app/terragrunt.hcl environments/dev/services/{service-name}/app/terragrunt.hcl
cp environments/dev/services/_template/service.yaml environments/dev/services/{service-name}/service.yaml
```

#### Configure data/terragrunt.hcl

Edit `environments/dev/services/{service-name}/data/terragrunt.hcl`:

1. Replace all `__SERVICE_NAME__` with the actual service name
2. Replace all `__SERVICE_REPO__` with the GitHub repo name
3. Replace `__SERVICE_DISPLAY_NAME__` with the display name (in the `api_display_name` field)
4. Remove the template onboarding checklist comment block at the top
5. Add a proper header comment:

```hcl
# =============================================================================
# {Service Display Name} - Dev (Data Layer)
# =============================================================================
# Creates: Key Vault, Database, Storage (persistent resources)
# =============================================================================
```

6. **Only uncomment feature flags that differ from defaults.** Only set flags like:
   - `create_database = true` (if enabled)
   - `create_service_bus_queue = true` (if enabled)
   - `create_storage_account = true` (if enabled, plus `storage_containers` list)

7. If storage containers were specified, uncomment and populate the `storage_containers` list

#### Configure app/terragrunt.hcl

Edit `environments/dev/services/{service-name}/app/terragrunt.hcl`:

1. Replace all `__SERVICE_NAME__` with the actual service name
2. Replace all `__SERVICE_REPO__` with the GitHub repo name
3. Replace `__SERVICE_DISPLAY_NAME__` with the display name
4. Remove the template onboarding checklist comment block at the top
5. Add a proper header comment:

```hcl
# =============================================================================
# {Service Display Name} - Dev (App Layer)
# =============================================================================
# Creates: Managed Identity, RBAC, K8s resources, APIM API (ephemeral resources)
# =============================================================================
```

6. **Only uncomment feature flags that differ from `_service.hcl` defaults.** The `_service.hcl` already sets these defaults for all services:
   - `create_apim_api = true`
   - `create_app_registration = true`
   - `create_client_secret = true`

   So you only need to uncomment/add flags like:
   - `jwt_validation_enabled = true` (if enabled)
   - Any flag the user wants to set to `false` that `_service.hcl` defaults to `true`

8. If webhook IPs were specified, uncomment and populate the `webhook_allowed_ips` list

#### Configure service.yaml

Edit `environments/dev/services/{service-name}/service.yaml`:

1. Replace all `__SERVICE_NAME__` with the actual service name
2. Replace `__SERVICE_REPO__` with the GitHub repo name (in `service_repo_url`)
3. Leave `__PENDING__` sentinels for `client_id` and `key_vault_name` -- CI auto-replaces these after `terragrunt apply`
4. If the service has its own `helm/` directory (Pattern B), keep `helm_pattern: service-repo` (default)
5. If the service has NO helm directory (Pattern A), change to `helm_pattern: platform-only` and remove `service_repo_url` and `service_repo_revision`
6. Uncomment and fill in `database:` block if `create_database: true`
7. Uncomment and fill in `service_bus:` block if `create_service_bus_queue: true`
8. Set `eso_enabled: true` (default) or `false` if the service doesn't use ESO

### 11d. Update Deploy Workflow

Edit `.github/workflows/deploy.yml` to add the new service to the manual dispatch layer choices.

Find the `layer` input under `workflow_dispatch.inputs` and add BOTH `services/{service-name}/data` and `services/{service-name}/app` to the `options` list, placing them **alphabetically** among the existing service entries:

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
          - services/{service-name}/data   # <-- ADD THIS (alphabetical)
          - services/{service-name}/app    # <-- ADD THIS (alphabetical)
          - services/property-service/data
          - services/property-service/app
          - services/skeleton-service/data
          - services/skeleton-service/app
          - acr
          - github-actions-identity
```

**Note**: This is the only change needed in the deploy workflow. The workflow uses `terragrunt run-all` with filesystem auto-discovery for push-to-main deploys, so creating the service directory (Step 11c) is what enables automatic deployment. The options list is only for manual `workflow_dispatch` deploys.

### 11e. Commit and Push

Stage all changes, create a commit, and push:

```bash
git add -A
git commit -m "feat: Add {service-name} infrastructure

- Create dev service data/app configuration from template
- Add service.yaml for ApplicationSet discovery
- CI auto-populates __PENDING__ sentinels after terragrunt apply
- Add deploy workflow layer options

Services enabled: {list enabled services}

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

git push -u origin feat/add-{service-name}-infra
```

### 11f. Create Pull Request

Create a PR in the infra repo using `gh`:

```bash
gh pr create \
  --repo LEXTECH-AU/Lextech_Microservice_Infra \
  --title "feat: Add {service-name} infrastructure" \
  --body "$(cat <<'EOF'
## Summary
- Add **{service-name}** microservice infrastructure configuration (dev environment)
- ApplicationSet-driven GitOps: `service.yaml` with CI-managed `__PENDING__` sentinel replacement
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
| k6 Client Secret | {yes/no} |

### Files Changed
- `environments/dev/services/{service-name}/data/terragrunt.hcl` -- Data layer Terragrunt configuration (persistent resources)
- `environments/dev/services/{service-name}/app/terragrunt.hcl` -- App layer Terragrunt configuration (ephemeral resources)
- `environments/dev/services/{service-name}/service.yaml` -- ArgoCD ApplicationSet service configuration
- `.github/workflows/deploy.yml` -- Added deploy layer options

### How It Works
1. CI runs validate + plan on this PR
2. After merge, push-to-main triggers `terragrunt apply` for dev
3. Terraform creates Azure resources (Key Vault, Identity, RBAC, etc.)
4. CI post-apply step replaces `__PENDING__` sentinels in `service.yaml` with real Terraform outputs and pushes a commit
5. ArgoCD ApplicationSet discovers `service.yaml` and generates the Application
6. Push a container image to ACR with the `main` tag to trigger first deployment
7. ArgoCD Image Updater detects the image and syncs

## Post-Merge Steps
1. Wait for CI deploy to complete successfully
2. Verify ArgoCD Application is created: `kubectl get applications -n argocd | grep {service-name}`
3. Push container image: `docker push lextechsharedacr.azurecr.io/{service-name}:main`
4. Verify pods are running: `kubectl get pods -n {service-name}`

## Test plan
- [ ] CI validates Terraform format and lint
- [ ] CI runs security scan (Trivy)
- [ ] CI validates Helm charts and K8s manifests
- [ ] CI runs `terragrunt plan` for dev -- review plan output
- [ ] Verify plan shows only create operations (no unexpected changes)
- [ ] After merge: verify dev auto-deploy succeeds
- [ ] After merge: verify `__PENDING__` sentinels in `service.yaml` are replaced by CI commit
- [ ] After merge: verify ArgoCD Application is discovered and syncs

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

### 11g. Clean Up

Remove the temporary infra clone directory:

```bash
rm -rf "$INFRA_DIR"
```

## Step 12: Summary and Next Steps

After everything is complete, display:

1. **GitHub repo URL**: `https://github.com/LEXTECH-AU/{GitHubRepoName}`
2. **Infra PR URL**: The PR created in Step 11f
3. **Service configuration table**: All the settings from Step 2
4. **Post-merge checklist**:
   - [ ] CI validates and plans the infra PR
   - [ ] Review Terraform plan output
   - [ ] Merge the infra PR
   - [ ] Wait for CI deploy to complete
   - [ ] Verify ArgoCD Application is created
   - [ ] Push container image to ACR with `main` tag
   - [ ] Verify pods are running in dev cluster
5. **Reminder**: "Run `/lextech-dotnet:new-feature` to scaffold your first feature"
6. **Note**: Staging/prod promotion is a separate step done later

## Important Rules

- **Never modify existing services** -- only add the new service entry.
- **Dev environment only** -- staging and prod directories do not exist yet. They are promoted separately after the service is running in dev.
- **Leave `__PENDING__` sentinels in service.yaml** -- CI auto-replaces `client_id` and `key_vault_name` after `terragrunt apply`.
- **Copy individual files from the template directory** -- `data/terragrunt.hcl`, `app/terragrunt.hcl`, and `service.yaml`. Do not use `cp -r`.
- **Minimal terragrunt.hcl overrides** -- `_service.hcl` auto-wires 31+ variables from platform layer dependencies. Only set flags that differ from `_service.hcl` defaults (`create_apim_api=true`, `create_app_registration=true`, `create_client_secret=true`).
- **Deploy workflow** -- add BOTH `services/{service-name}/data` and `services/{service-name}/app` to the `options` dropdown list. The workflow auto-discovers services from the filesystem for push-to-main deploys.
- **Do not run `terragrunt plan` or `terragrunt apply`** -- that happens via CI after the PR is merged.
- **Clean up**: remove all temporary clone directories after completion.
- **Build must pass** -- if the build fails in Step 9, stop and let the user fix before continuing.
