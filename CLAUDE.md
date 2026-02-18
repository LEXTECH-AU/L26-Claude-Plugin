# Lextech .NET Microservice Standards

## Project Identity

**.NET 10 Clean Architecture, Vertical Slice** microservices with Contract-First Minimal APIs.

| Area | Technologies |
|------|-------------|
| Runtime | .NET 10.0 |
| API | Minimal APIs, Microsoft.AspNetCore.OpenApi, NSwag (contract-first DTO gen), Asp.Versioning.Http |
| Messaging/CQRS | Wolverine, Azure Service Bus |
| Data | Dapper ORM, PostgreSQL, pgschema migrations |
| Caching | Azure Managed Redis |
| Storage | Azure Blob Storage |
| Mapping | Mapster |
| Config | Azure Key Vault, App Configuration, Feature Management |
| Observability | Serilog, Grafana Cloud (Prometheus, Loki, Tempo) |
| Testing | xUnit, Moq, Playwright, Grafana K6 |
| Auth | Azure Entra ID, MSAL, OAuth 2.0 via APIM |
| CI/CD | GitHub Actions, Terraform, AKS, Argo CD |

## Non-Negotiable Rules

- **Principles** (priority): SOLID > DRY > KISS > YAGNI > SoC
- **No `var`** — use explicit types for clarity
- **XML docs** on all public members
- **`CancellationToken`** on every async method
- **SQL files** must include header comments and parameter docs
- **No magic strings/numbers** — use constants or enums
- **Sealed records** for commands and queries
- **NuGet**: latest LTS-stable only, no preview/RC/nightly, no LGPL; check `Directory.Packages.props`
- **Unit tests must pass** before proceeding to next step
- **Structured logging only** — never string interpolation in Serilog calls
- **OpenAPI contract-first** — every endpoint must have a corresponding operation in the OpenAPI spec with matching `operationId`, response schemas, and request body schema

## Architecture Layers (Dependency Direction: API → Application → Domain ← Infrastructure)

| Layer | Allowed References | Forbidden |
|-------|-------------------|-----------|
| **Domain** | None (pure) | EF, ASP.NET, Dapper, JSON, Infrastructure |
| **Application** | Domain | Infrastructure, EF, Dapper |
| **Infrastructure** | Application, Domain | API |
| **API** | Application, Domain, Generated DTOs from OpenAPI contract | Infrastructure repositories directly |

## Feature Workflow (Mandatory Sequence)

1. Define/update the OpenAPI operation in the spec file → read `openapi-contract-first` skill
2. Generate DTOs from the spec (`dotnet build` triggers NSwag pre-build)
3. Domain entity (entities, value objects, domain events) → read `vertical-slice` skill
4. SQL files for data operations → read `dapper-postgresql` skill
5. Repository with embedded SQL → read `dapper-postgresql` skill
6. Command/Query + Handler → read `wolverine-cqrs` skill
7. FluentValidation validator
8. Minimal API endpoint mapping generated DTO to command → read `openapi-contract-first` skill
9. Unit tests for handler — **must pass before proceeding** → read `testing-patterns` skill
10. Integration tests for repository — **must pass before proceeding**
11. Serilog structured logging → read `observability` skill
12. Prometheus metrics for monitoring → read `observability` skill
13. Validate no breaking changes (`oasdiff`) → read `openapi-contract-first` skill

## File Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| SQL files | `{Entity}/{Operation}.sql` | `MatterCompanySearch/Insert.sql` |
| Commands | `{Action}{Entity}Command.cs` | `CreateCompanySearchCommand.cs` |
| Queries | `Get{Entity}{Criteria}Query.cs` | `GetOrdersByMatterQuery.cs` |
| Handlers | `{CommandOrQuery}Handler.cs` | `CreateCompanySearchCommandHandler.cs` |
| Validators | `{CommandOrQuery}Validator.cs` | `CreateCompanySearchCommandValidator.cs` |
| Repositories | `{Entity}Repository.cs` | `TitleSearchRepository.cs` |
| Endpoints | `{Entity}Endpoints.cs` | `CompanySearchEndpoints.cs` |
| OpenAPI specs | `openapi.yaml` or `openapi-v{N}.yaml` | `openapi.yaml` |
| NSwag config | `nswag.json` or `nswag-{purpose}.nswag.json` | `nswag.json` |
| Generated DTOs | `{Type}.g.cs` (in `Generated/` folder) | `Dtos.g.cs` |
| Generated clients | `{Service}Client.g.cs` | `PropertyServiceClient.g.cs` |

## Folder Structure (Vertical Slice)

```
{Layer}/
  {ServiceName}.Api/
    Contracts/
      v1/
        openapi.yaml
    Generated/
        Dtos.g.cs
    nswag.json
  {FeatureName}/
    Commands/{Action}{Entity}/
      {Action}{Entity}Command.cs
      {Action}{Entity}CommandHandler.cs
      {Action}{Entity}CommandValidator.cs
    Queries/Get{Entity}{Criteria}/
      Get{Entity}{Criteria}Query.cs
      Get{Entity}{Criteria}QueryHandler.cs
    DTOs/
    Repositories/
    SQL/
```

## Skill Reference — Load BEFORE Writing Code

| When working on... | Load this skill first |
|--------------------|----------------------|
| New features, scaffolding, vertical slices | `vertical-slice` |
| SQL files, repositories, Unit of Work, migrations | `dapper-postgresql` |
| Command/query handlers, Wolverine messaging | `wolverine-cqrs` |
| LIXI/DAS schema, Australian lending types | `lixi-das-schema` |
| Azure Blob, Redis, Service Bus, Key Vault, Entra ID | `azure-integration` |
| Serilog logging, Prometheus metrics, Grafana | `observability` |
| Unit tests, integration tests, K6 load tests | `testing-patterns` |
| Security reviews, OWASP, error handling | `security-owasp` |
| OpenAPI specs, NSwag, API contracts, versioning | `openapi-contract-first` |

## LIXI DAS Schema

- **Location**: `schemas/LIXI-DAS-2_2_92_RFC-Annotated.json`
- **Version**: 2.2.92 RFC — 286 definitions, 235 enums
- **Usage**: Run `/lextech-dotnet:lixi-lookup` to search, `/lextech-dotnet:lixi-codegen` to generate C# types
- **Format**: JSON only (no XML generation)

## Compliance

Failure to follow these standards results in **rejected pull requests**, required refactoring, and delayed releases. Run `/lextech-dotnet:pre-pr` before submitting PRs.
