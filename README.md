# lextech-dotnet

A Claude Code plugin that enforces .NET 10 Clean Architecture standards for Lextech microservices. It provides skills, commands, agents, and automated hooks to ensure every file written follows team conventions -- from layer dependency direction to Serilog structured logging.

## Installation

**From the marketplace (recommended):**

```bash
# Add the marketplace
/plugin marketplace add LEXTECH-AU/L26-Claude-Plugin

# Install the plugin
/plugin install lextech-dotnet@lextech-plugins
```

**Direct install from GitHub:**

```bash
claude plugin add --source github LEXTECH-AU/L26-Claude-Plugin
```

**From a local directory:**

```bash
claude plugin add /path/to/lextech-dotnet
```

**Via `--plugin-dir` flag:**

```bash
claude --plugin-dir /path/to/lextech-dotnet
```

**Auto-install for your team** -- add to your project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "lextech-plugins": {
      "source": {
        "source": "github",
        "repo": "LEXTECH-AU/L26-Claude-Plugin"
      }
    }
  },
  "enabledPlugins": {
    "lextech-dotnet@lextech-plugins": true
  }
}
```

Once installed, the plugin's `CLAUDE.md` is loaded automatically into every session, replacing the need for per-project `CLAUDE.md` files for .NET standards. Project-specific instructions can still be layered on top.

## CLAUDE.md Overview

The plugin ships a `CLAUDE.md` that injects the full Lextech .NET standards into Claude's context. This includes:

- **Technology stack**: .NET 10, Minimal APIs, Wolverine, Dapper, PostgreSQL, Azure services, Serilog, Grafana Cloud.
- **Non-negotiable rules**: No `var`, XML docs on public members, `CancellationToken` on async methods, sealed records for commands/queries, parameterized SQL only, structured logging only.
- **Architecture layers**: Domain (pure) > Application > Infrastructure > API with strict dependency direction.
- **Feature workflow**: An 11-step mandatory sequence from domain entity through unit/integration tests.
- **File naming conventions**: Consistent patterns for SQL, commands, queries, handlers, validators, repositories, and endpoints.
- **Contract-first OpenAPI**: NSwag DTO generation, API versioning, endpoint metadata requirements, and breaking change detection.
- **Skill reference table**: Directs Claude to load the right skill before writing code in each area.

## Skills

Skills are loaded on demand to provide deep context for specific technology areas. Reference them with `/lextech-dotnet:<skill-name>` or ask Claude to "read the X skill."

| Skill | Description | Trigger Phrases |
|-------|-------------|-----------------|
| `vertical-slice` | Vertical Slice feature development patterns for .NET 10 Clean Architecture | "create a feature", "scaffold a slice", "feature workflow" |
| `dapper-postgresql` | Dapper ORM, PostgreSQL, embedded SQL, Unit of Work, and pgschema migrations | "write SQL", "create a repository", "database migration" |
| `wolverine-cqrs` | Wolverine CQRS command/query handler and messaging patterns | "create a handler", "publish a message", "command handler" |
| `lixi-das-schema` | LIXI DAS Schema navigation and C# code generation for Australian lending | "LIXI lookup", "generate LIXI types", "DAS schema" |
| `azure-integration` | Azure Blob Storage, Redis, Service Bus, Key Vault, Entra ID patterns | "Azure integration", "Blob storage", "Service Bus" |
| `observability` | Serilog structured logging, Prometheus metrics, and Grafana dashboards | "add logging", "create metrics", "Grafana dashboard" |
| `testing-patterns` | xUnit, Moq, integration testing, and K6 load testing patterns | "write tests", "unit test", "load test" |
| `security-owasp` | Security review, OWASP compliance, and error handling patterns | "security review", "OWASP check", "error handling" |
| `openapi-contract-first` | OpenAPI contract-first API development with NSwag, Microsoft.AspNetCore.OpenApi, and API versioning | "OpenAPI contract", "NSwag", "API versioning", "contract-first" |

## Commands

Commands are invoked with `/lextech-dotnet:<command-name>` followed by arguments.

| Command | Description | Usage |
|---------|-------------|-------|
| `new-feature` | Scaffold a complete vertical slice feature across all architecture layers | `/lextech-dotnet:new-feature CompanySearch CompanySearchOrder both` |
| `new-test` | Generate unit or integration tests for a handler or repository | `/lextech-dotnet:new-test CreateCompanySearchCommandHandler handler` |
| `pre-pr` | Run all pre-pull-request checks: build, tests, architecture review | `/lextech-dotnet:pre-pr` |
| `lixi-lookup` | Search the LIXI DAS Schema for definitions and enums | `/lextech-dotnet:lixi-lookup PropertyAddress` |
| `lixi-codegen` | Generate C# sealed records from LIXI DAS Schema definitions | `/lextech-dotnet:lixi-codegen ValuationReport` |
| `add-endpoint` | Add a Minimal API endpoint for an existing command or query, mapped to the OpenAPI contract | `/lextech-dotnet:add-endpoint GetCompanySearchByIdQuery` |
| `add-migration` | Create a new pgschema SQL migration file with header template | `/lextech-dotnet:add-migration AddCompanySearchTable` |

## Agents

Agents are autonomous review processes triggered by context. Claude will invoke them automatically when conditions match, or you can request them directly.

| Agent | Description | Trigger Conditions |
|-------|-------------|--------------------|
| `architecture-reviewer` | Reviews code for Clean Architecture compliance, layer dependency violations, and vertical slice completeness | After implementing features, during PR reviews, when asked to review architecture |
| `security-auditor` | Scans for OWASP Top 10 vulnerabilities, injection risks, and authentication gaps | When reviewing security-sensitive code, before deployments |
| `test-coverage-analyzer` | Analyzes test coverage gaps and suggests missing test scenarios | After writing tests, when test coverage is questioned |
| `migration-validator` | Validates database migrations for safety, rollback support, and naming conventions | When creating or reviewing SQL migrations |

## Hooks

Hooks run automatically after file writes (`Edit`, `Write`, `MultiEdit`) to enforce standards in real time. They read the tool payload from stdin and either allow (exit 0) or block (exit 2) the operation.

| Hook | File Pattern | Checks | Enforcement |
|------|-------------|--------|-------------|
| `coding_standards_hook.py` | `*.cs` | `var` usage, missing XML docs on public members, missing `CancellationToken` on async methods, commands/queries not using `sealed record` | WARN (never blocks) |
| `sql_format_hook.py` | `*.sql` in `Infrastructure/` | Missing header comment, missing parameter docs, string concatenation (SQL injection risk), non-parameterized WHERE values | WARN for format issues; BLOCK for injection risk |
| `layer_dependency_hook.py` | `*.cs` | Layer detection by path, forbidden `using` statements per layer (Domain purity, Application isolation, API indirection) | BLOCK for Domain/Application violations; WARN for API |
| `serilog_enforcer_hook.py` | `*.cs` | String interpolation (`$"`) in Serilog log calls, PII-sensitive parameter names in log templates | WARN (never blocks) |
| `openapi_contract_hook.py` | `*Endpoint*.cs` | Missing .WithName(), .Produces<T>(), .WithTags(), .WithSummary(), missing authorization | WARN (never blocks) |

### Hook Behavior

- **WARN** (exit 0): The write proceeds. A warning is printed to stderr so Claude can self-correct.
- **BLOCK** (exit 2): The write is undone. Claude must fix the violation before the change is accepted.

Blocking is reserved for security-critical violations: SQL injection patterns and Clean Architecture layer breaches in Domain and Application layers.

## LIXI DAS Schema

The plugin includes the LIXI DAS 2.2.92 RFC annotated JSON schema (`schemas/LIXI-DAS-2_2_92_RFC-Annotated.json`) for the Australian lending industry. This schema provides:

- **286 definitions** covering property valuations, mortgage applications, borrower information, and settlement data.
- **235 enums** for standardized Australian financial codes, property types, and regulatory classifications.
- **JSON-only format** -- no XML generation. C# types are generated as sealed records with init properties.

Use the `lixi-das-schema` skill or the `/lextech-dotnet:lixi-lookup` and `/lextech-dotnet:lixi-codegen` commands to work with the schema.

## MCP Server References

The following MCP servers are expected to be available in the Claude Code environment and are referenced by skills and agents:

| MCP Server | Purpose |
|------------|---------|
| **Azure** (`azure-mcp-server`) | Azure resource management, Key Vault, App Configuration, AKS, ACR, Service Bus, Storage |
| **Grafana** (`grafana`) | Dashboard management, Prometheus queries, Loki log queries, alert rule management |
| **Terraform** (`terraform`) | Infrastructure-as-code module/provider search, AKS and Azure resource provisioning |
| **Context7** (`context7`) | Library documentation lookups for .NET, Wolverine, Dapper, and other dependencies |

These servers provide live data access used by skills such as `azure-integration` and `observability`.

## Configuration

### Customizing Hook Behavior

Hook scripts are located in `hooks/` and can be modified directly. Each script is a standalone Python 3 file that reads a JSON payload from stdin.

To disable a specific hook, remove its entry from `hooks/hooks.json`.

To adjust severity (e.g., make `var` usage a blocker instead of a warning), change the exit code in the corresponding hook script from `sys.exit(0)` to `sys.exit(2)`.

### Adding New Skills

Create a new directory under `skills/` with a `SKILL.md` file containing a YAML front matter block (`name`, `description`) and the skill content in Markdown. The skill becomes available as `/lextech-dotnet:<skill-name>`.

### Project-Specific Overrides

The plugin's `CLAUDE.md` provides the base standards. Individual projects can layer additional instructions by placing a `CLAUDE.md` in their repository root. Project-level instructions are additive and do not replace the plugin standards.
