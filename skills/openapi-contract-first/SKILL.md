---
name: openapi-contract-first
description: "OpenAPI contract-first API development with NSwag, Microsoft.AspNetCore.OpenApi, and API versioning. Use when defining API contracts, generating DTOs, configuring NSwag, or setting up API versioning."
---

# OpenAPI Contract-First API Development

This skill defines the contract-first workflow for Lextech .NET 10 microservices. The OpenAPI specification is the single source of truth for all API contracts. It is written **before** any implementation code. NSwag generates DTOs from the spec, endpoints consume those DTOs, and Mapster maps them to internal command/query sealed records. This ensures the API contract evolves independently of the domain model.

## Contract-First Workflow Overview

The OpenAPI spec drives all API development. No endpoint code is written until the spec is defined and reviewed.

```
openapi.yaml (source of truth)
    |
    v
NSwag pre-build target
    |
    v
Generated DTOs (Dtos.g.cs)
    |
    v
Endpoint receives generated DTO as parameter
    |
    v
Mapster maps generated DTO --> internal Command sealed record
    |
    v
Wolverine IMessageBus.InvokeAsync dispatches to handler
    |
    v
Handler returns response --> Mapster maps to generated response DTO
    |
    v
Endpoint returns HTTP result with generated response DTO
```

### Key Principles

- The spec is written first, reviewed, and committed before implementation begins.
- Generated DTOs are **never hand-edited**. If you need a different shape, change the spec.
- Internal command/query sealed records are separate from generated DTOs. The API contract must not leak into the domain.
- Breaking changes to the spec require explicit review and approval.

## OpenAPI Spec Template

The authoritative spec lives at `{Service}.Api/Contracts/v1/openapi.yaml`. This file defines all paths, request/response schemas, and standard error responses.

```yaml
openapi: "3.0.3"
info:
  title: PropertyService API
  description: Property search and ordering service for Australian property data.
  version: "1.0.0"
  contact:
    name: Lextech Engineering
servers:
  - url: /api/v1
    description: Version 1

paths:
  /company-search:
    post:
      operationId: CreateCompanySearch
      summary: Create a new company search order.
      tags:
        - CompanySearch
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/CreateCompanySearchRequest"
      responses:
        "201":
          description: Company search order created.
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/CompanySearchResponse"
        "400":
          description: Validation error.
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ValidationProblemDetails"
        "401":
          description: Unauthorized.
        "500":
          description: Internal server error.
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ProblemDetails"

  /company-search/{matterId}/{orderId}:
    get:
      operationId: GetCompanySearch
      summary: Retrieve a company search order by matter ID and order ID.
      tags:
        - CompanySearch
      parameters:
        - name: matterId
          in: path
          required: true
          schema:
            type: integer
            format: int32
          description: The matter ID from the client system.
        - name: orderId
          in: path
          required: true
          schema:
            type: string
          description: The Dye & Durham order identifier.
      responses:
        "200":
          description: Company search order found.
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/CompanySearchResponse"
        "401":
          description: Unauthorized.
        "404":
          description: Company search order not found.
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/ProblemDetails"

components:
  schemas:
    CreateCompanySearchRequest:
      type: object
      required:
        - matterId
        - identifier
        - organisationName
        - identifierType
        - extractType
        - matterReference
      properties:
        matterId:
          type: integer
          format: int32
          description: The matter ID from the client system.
        identifier:
          type: string
          maxLength: 20
          description: The company identifier (ACN, ARBN, or ARSN).
        organisationName:
          type: string
          maxLength: 200
          description: The registered organisation name.
        identifierType:
          type: string
          enum: [acn, arbn, arsn]
          description: The type of identifier.
        abn:
          type: string
          maxLength: 11
          nullable: true
          description: Optional Australian Business Number.
        extractType:
          type: string
          enum: [current, historical]
          description: The extract type.
        matterReference:
          type: string
          maxLength: 100
          description: The client-side matter reference string.

    CompanySearchResponse:
      type: object
      properties:
        orderId:
          type: string
          description: The Dye & Durham order identifier.
        matterId:
          type: integer
          format: int32
          description: The matter ID.
        companyIdentifier:
          type: string
          description: The company identifier.
        organisationName:
          type: string
          description: The registered organisation name.
        status:
          type: string
          description: The current order status.
        createdAt:
          type: string
          format: date-time
          description: When the order was created.

    ProblemDetails:
      type: object
      properties:
        type:
          type: string
          nullable: true
        title:
          type: string
          nullable: true
        status:
          type: integer
          format: int32
          nullable: true
        detail:
          type: string
          nullable: true
        instance:
          type: string
          nullable: true

    ValidationProblemDetails:
      allOf:
        - $ref: "#/components/schemas/ProblemDetails"
        - type: object
          properties:
            errors:
              type: object
              additionalProperties:
                type: array
                items:
                  type: string

  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

security:
  - bearerAuth: []
```

### Spec Writing Rules

- `operationId` must match the `.WithName()` value on the endpoint (e.g., `CreateCompanySearch`).
- Use `camelCase` for all property names in schemas.
- Always include `ProblemDetails` and `ValidationProblemDetails` in components for reuse.
- Mark nullable properties with `nullable: true`.
- Use `format: int32` for integer types and `format: date-time` for timestamps.
- Use `enum` for constrained string values.

## NSwag Configuration

NSwag generates C# DTOs from the OpenAPI spec. We generate **DTOs only** -- NSwag does not generate controllers or clients because we use Minimal APIs.

### nswag.json Template

Place this file at `{Service}.Api/nswag.json`.

```json
{
  "runtime": "Net90",
  "documentGenerator": {
    "fromDocument": {
      "url": "Contracts/v1/openapi.yaml",
      "output": null
    }
  },
  "codeGenerators": {
    "openApiToCSharpClient": {
      "generateClientClasses": false,
      "generateDtoTypes": true,
      "generateClientInterfaces": false,
      "generateOptionalParameters": false,
      "generateJsonMethods": false,
      "generateDefaultValues": true,
      "generateDataAnnotations": false,
      "output": "Generated/Dtos.g.cs",
      "namespace": "PropertyService.Api.Generated",
      "jsonLibrary": "SystemTextJson",
      "generateNullableReferenceTypes": true,
      "dateType": "System.DateTimeOffset",
      "dateTimeType": "System.DateTimeOffset",
      "arrayType": "System.Collections.Generic.IReadOnlyList",
      "dictionaryType": "System.Collections.Generic.IDictionary",
      "classStyle": "Record",
      "typeAccessModifier": "public"
    }
  }
}
```

### Critical NSwag Settings

| Setting | Value | Reason |
|---------|-------|--------|
| `generateClientClasses` | `false` | No HTTP clients -- we use Minimal API endpoints |
| `generateDtoTypes` | `true` | DTOs are the only generated artifacts |
| `jsonLibrary` | `SystemTextJson` | .NET 10 default serializer |
| `generateNullableReferenceTypes` | `true` | Matches project nullable context |
| `classStyle` | `Record` | Generates records matching our sealed record convention |
| `runtime` | `Net90` | NSwag 14.6.3 does not yet have `Net100` |
| `dateType` / `dateTimeType` | `System.DateTimeOffset` | Consistent with PostgreSQL `TIMESTAMPTZ` |

## NuGet Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `Microsoft.AspNetCore.OpenApi` | `10.0.*` | Runtime OpenAPI document generation, replaces NSwag middleware |
| `Microsoft.Extensions.ApiDescription.Server` | `10.0.*` | Build-time spec generation for validation |
| `NSwag.MSBuild` | `14.6.3` | Pre-build DTO generation from authoritative spec |
| `Asp.Versioning.Http` | `8.1.*` | API versioning for Minimal APIs |

### Packages to NOT Install

- **NSwag.AspNetCore** -- Replaced by `Microsoft.AspNetCore.OpenApi` in .NET 10.
- **Swashbuckle.AspNetCore** -- Removed from .NET 10 templates; `Microsoft.AspNetCore.OpenApi` is the replacement.
- **NSwag.CodeGeneration.CSharp** -- Only needed for programmatic generation; we use `NSwag.MSBuild` via `.csproj` targets.

## MSBuild Integration

### Pre-Build NSwag DTO Generation

Add this target to the `{Service}.Api.csproj` to generate DTOs before compilation. The target uses incremental build support so it only regenerates when the spec or config changes.

```xml
<ItemGroup>
  <PackageReference Include="NSwag.MSBuild" Version="14.6.3">
    <PrivateAssets>all</PrivateAssets>
    <IncludeAssets>runtime; build; native; contentfiles; analyzers</IncludeAssets>
  </PackageReference>
</ItemGroup>

<Target Name="NSwagGenerateDtos" BeforeTargets="BeforeBuild"
        Inputs="Contracts/v1/openapi.yaml;nswag.json"
        Outputs="Generated/Dtos.g.cs">
  <Exec Command="$(NSwagExe) run nswag.json /runtime:Net90" />
</Target>
```

### Post-Build Spec Generation for Validation

Use `Microsoft.Extensions.ApiDescription.Server` to generate a spec from the running API at build time. This generated spec can be diffed against the authoritative spec to detect drift.

```xml
<PropertyGroup>
  <OpenApiDocumentsDirectory>$(OutputPath)</OpenApiDocumentsDirectory>
  <OpenApiGenerateDocuments>true</OpenApiGenerateDocuments>
  <OpenApiGenerateDocumentsOnBuild>true</OpenApiGenerateDocumentsOnBuild>
</PropertyGroup>

<ItemGroup>
  <PackageReference Include="Microsoft.Extensions.ApiDescription.Server" Version="10.0.0">
    <PrivateAssets>all</PrivateAssets>
    <IncludeAssets>runtime; build; native; contentfiles; analyzers</IncludeAssets>
  </PackageReference>
</ItemGroup>
```

### Incremental Build Notes

- The `Inputs`/`Outputs` on the NSwag target ensure the code generator runs only when `openapi.yaml` or `nswag.json` changes.
- If the generated file is missing (clean build), MSBuild always runs the target.
- Run `dotnet build` to regenerate DTOs after editing the spec.

## Program.cs Registration

### OpenAPI Document Registration

```csharp
// In Program.cs -- Service registration
builder.Services.AddOpenApi("v1", options =>
{
    options.AddDocumentTransformer((document, context, cancellationToken) =>
    {
        document.Info.Title = "PropertyService API";
        document.Info.Version = "1.0.0";
        return Task.CompletedTask;
    });
});
```

### OpenAPI Endpoint Mapping

```csharp
// In Program.cs -- Middleware pipeline (development only)
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}
```

### API Versioning Registration

```csharp
// In Program.cs -- Service registration
builder.Services.AddApiVersioning(options =>
{
    options.DefaultApiVersion = new ApiVersion(1, 0);
    options.AssumeDefaultVersionWhenUnspecified = true;
    options.ReportApiVersions = true;
    options.ApiVersionReader = new UrlSegmentApiVersionReader();
});
```

### Versioned Route Groups

```csharp
// In Program.cs -- Route mapping
ApiVersionSet apiVersionSet = app.NewApiVersionSet()
    .HasApiVersion(new ApiVersion(1, 0))
    .Build();

RouteGroupBuilder v1Group = app
    .MapGroup("/api/v{version:apiVersion}")
    .WithApiVersionSet(apiVersionSet)
    .MapToApiVersion(new ApiVersion(1, 0));

// Map endpoints to the versioned group
CreateCompanySearchEndpoint.Map(v1Group);
GetCompanySearchEndpoint.Map(v1Group);
```

## Generated DTO Location and Rules

### File Location

Generated DTOs are placed at `{Service}.Api/Generated/Dtos.g.cs`. The `.g.cs` suffix follows the .NET convention for generated code.

### Rules for Generated Files

1. **Never hand-edit** `Dtos.g.cs` or any file in the `Generated/` folder.
2. If the generated shape is wrong, fix the OpenAPI spec and regenerate.
3. Add `Generated/` to `.gitignore` if your team prefers build-time generation. Alternatively, commit the generated file if you want visibility in code review.
4. The generated file header includes a warning comment -- do not remove it.
5. Treat generated types as **API boundary types only**. Never pass them deeper than the endpoint layer.

### .gitignore Entry (if not committing generated files)

```gitignore
# NSwag generated DTOs
**/Generated/Dtos.g.cs
```

## Endpoint Pattern with Generated DTOs

Endpoints consume generated DTOs as input parameters and return generated response types. They map to internal commands using Mapster, then dispatch via Wolverine.

### POST Endpoint -- Create Operation

```csharp
namespace PropertyService.Api.Endpoints.CompanySearch;

/// <summary>
/// Endpoint for creating a new company search order.
/// </summary>
public static class CreateCompanySearchEndpoint
{
    /// <summary>
    /// Maps the POST /company-search route to this endpoint.
    /// </summary>
    public static void Map(IEndpointRouteBuilder app)
    {
        app.MapPost("/company-search", HandleAsync)
            .RequireAuthorization()
            .WithName("CreateCompanySearch")
            .WithTags("CompanySearch")
            .WithSummary("Create a new company search order.")
            .WithGroupName("v1")
            .Accepts<CreateCompanySearchRequest>("application/json")
            .Produces<CompanySearchResponse>(StatusCodes.Status201Created)
            .ProducesValidationProblem()
            .ProducesProblem(StatusCodes.Status500InternalServerError);
    }

    /// <summary>
    /// Handles the incoming request by mapping the generated DTO to an internal command.
    /// </summary>
    private static async Task<IResult> HandleAsync(
        CreateCompanySearchRequest request,
        IMessageBus messageBus,
        CancellationToken cancellationToken)
    {
        CreateCompanySearchCommand command = request.Adapt<CreateCompanySearchCommand>();

        CompanySearchResponse result = await messageBus
            .InvokeAsync<CompanySearchResponse>(command, cancellationToken);

        return Results.Created($"/api/v1/company-search/{result.MatterId}/{result.OrderId}", result);
    }
}
```

### GET Endpoint -- Retrieve Operation

```csharp
namespace PropertyService.Api.Endpoints.CompanySearch;

/// <summary>
/// Endpoint for retrieving a company search order.
/// </summary>
public static class GetCompanySearchEndpoint
{
    /// <summary>
    /// Maps the GET /company-search/{matterId}/{orderId} route to this endpoint.
    /// </summary>
    public static void Map(IEndpointRouteBuilder app)
    {
        app.MapGet("/company-search/{matterId:int}/{orderId}", HandleAsync)
            .RequireAuthorization()
            .WithName("GetCompanySearch")
            .WithTags("CompanySearch")
            .WithSummary("Retrieve a company search order by matter ID and order ID.")
            .WithGroupName("v1")
            .Produces<CompanySearchResponse>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status404NotFound);
    }

    /// <summary>
    /// Handles the incoming request by constructing an internal query.
    /// </summary>
    private static async Task<IResult> HandleAsync(
        int matterId,
        string orderId,
        IMessageBus messageBus,
        CancellationToken cancellationToken)
    {
        GetCompanySearchQuery query = new GetCompanySearchQuery
        {
            MatterId = matterId,
            OrderId = orderId
        };

        CompanySearchResponse? result = await messageBus
            .InvokeAsync<CompanySearchResponse?>(query, cancellationToken);

        return result is not null ? Results.Ok(result) : Results.NotFound();
    }
}
```

### Endpoint Metadata Checklist

Every endpoint must include all of these metadata calls:

| Method | Purpose |
|--------|---------|
| `.RequireAuthorization()` | Enforce JWT bearer auth |
| `.WithName("OperationId")` | Must match `operationId` in the OpenAPI spec |
| `.WithTags("FeatureName")` | Groups endpoints in the OpenAPI document |
| `.WithSummary("...")` | Human-readable description |
| `.WithGroupName("v1")` | Associates endpoint with the versioned OpenAPI document |
| `.Produces<T>(statusCode)` | Declares success response type |
| `.ProducesValidationProblem()` | Declares 400 response for POST/PUT/PATCH |
| `.ProducesProblem(statusCode)` | Declares error response types (404, 500) |

## Mapster Profile for DTO-to-Command Mapping

Generated DTOs and internal command/query sealed records are separate types. Mapster bridges them at the API boundary.

### Why Separate Types?

- The OpenAPI spec (and generated DTOs) represent the **external contract**. It changes when the API version changes.
- Internal commands and queries represent the **application intent**. They change when business logic changes.
- Decoupling these allows the API contract to evolve independently of the domain model. A property rename in the spec does not cascade into handlers, repositories, and SQL files.

### Mapping Configuration

```csharp
namespace PropertyService.Api.Mapping;

/// <summary>
/// Mapster mapping configuration between generated API DTOs and internal command/query types.
/// </summary>
public sealed class ApiContractMappingConfig : IRegister
{
    /// <summary>
    /// Registers mappings between generated DTOs and application commands/queries.
    /// </summary>
    public void Register(TypeAdapterConfig config)
    {
        // Generated request DTO --> Internal command
        config.NewConfig<CreateCompanySearchRequest, CreateCompanySearchCommand>()
            .Map(dest => dest.Identifier, src => src.Identifier)
            .Map(dest => dest.OrganisationName, src => src.OrganisationName)
            .Map(dest => dest.IdentifierType, src => src.IdentifierType)
            .Map(dest => dest.ExtractType, src => src.ExtractType)
            .Map(dest => dest.MatterReference, src => src.MatterReference)
            .Map(dest => dest.Abn, src => src.Abn);

        // Internal domain entity --> Generated response DTO
        config.NewConfig<CompanySearchOrder, CompanySearchResponse>()
            .Map(dest => dest.CompanyIdentifier, src => src.CompanyIdentifier)
            .Map(dest => dest.Status, src => src.OrderStatus.ToString());
    }
}
```

### Mapping Registration in Program.cs

```csharp
// In Program.cs -- Service registration
TypeAdapterConfig.GlobalSettings.Scan(typeof(Program).Assembly);
```

## API Versioning

URL path versioning is the standard for Lextech services. Each version has its own OpenAPI document and route group.

### Version Strategy: URL Path Segment

All routes follow the pattern `/api/v{version}/...`. This is explicit, cache-friendly, and easy to route at the API gateway (APIM) level.

### ApiVersionSet Configuration

```csharp
// Define the version set (supports multiple versions)
ApiVersionSet apiVersionSet = app.NewApiVersionSet()
    .HasApiVersion(new ApiVersion(1, 0))
    .HasApiVersion(new ApiVersion(2, 0))
    .Build();
```

### Route Groups Per Version

```csharp
// Version 1 group
RouteGroupBuilder v1Group = app
    .MapGroup("/api/v{version:apiVersion}")
    .WithApiVersionSet(apiVersionSet)
    .MapToApiVersion(new ApiVersion(1, 0));

// Version 2 group
RouteGroupBuilder v2Group = app
    .MapGroup("/api/v{version:apiVersion}")
    .WithApiVersionSet(apiVersionSet)
    .MapToApiVersion(new ApiVersion(2, 0));

// Map endpoints to their respective versions
CreateCompanySearchEndpoint.Map(v1Group);
GetCompanySearchEndpoint.Map(v1Group);

// V2 endpoints (when they exist)
// CreateCompanySearchV2Endpoint.Map(v2Group);
```

### Version-Specific OpenAPI Documents

```csharp
// Register separate OpenAPI documents per version
builder.Services.AddOpenApi("v1", options =>
{
    options.AddDocumentTransformer((document, context, cancellationToken) =>
    {
        document.Info.Title = "PropertyService API";
        document.Info.Version = "1.0.0";
        return Task.CompletedTask;
    });
});

builder.Services.AddOpenApi("v2", options =>
{
    options.AddDocumentTransformer((document, context, cancellationToken) =>
    {
        document.Info.Title = "PropertyService API";
        document.Info.Version = "2.0.0";
        return Task.CompletedTask;
    });
});
```

### `.WithGroupName()` on Endpoints

Every endpoint must declare its version group so it appears in the correct OpenAPI document:

```csharp
app.MapPost("/company-search", HandleAsync)
    .WithGroupName("v1")  // Associates with the v1 OpenAPI document
    .WithApiVersionSet(apiVersionSet)
    .MapToApiVersion(new ApiVersion(1, 0));
```

## Breaking Change Detection

Use `oasdiff` to detect breaking changes between the authoritative spec and a previous version. This catches accidental removals of endpoints, required field additions, and type changes.

### Local Usage with oasdiff CLI

```bash
# Install oasdiff
go install github.com/tufin/oasdiff@latest

# Detect breaking changes between the committed spec and the current spec
oasdiff breaking Contracts/v1/openapi.yaml.bak Contracts/v1/openapi.yaml

# Full changelog
oasdiff changelog Contracts/v1/openapi.yaml.bak Contracts/v1/openapi.yaml
```

### GitHub Actions Integration

```yaml
# .github/workflows/api-contract-check.yml
name: API Contract Check

on:
  pull_request:
    paths:
      - "**/Contracts/**/*.yaml"

jobs:
  breaking-change-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Get base spec
        run: git show origin/main:src/PropertyService.Api/Contracts/v1/openapi.yaml > /tmp/base-spec.yaml

      - name: Check for breaking changes
        uses: oasdiff/oasdiff-action/breaking@main
        with:
          base: /tmp/base-spec.yaml
          revision: src/PropertyService.Api/Contracts/v1/openapi.yaml

      - name: Generate changelog
        if: always()
        uses: oasdiff/oasdiff-action/changelog@main
        with:
          base: /tmp/base-spec.yaml
          revision: src/PropertyService.Api/Contracts/v1/openapi.yaml
```

### Diff Authoritative Spec vs Generated Live Spec

After building, compare the authoritative spec against the spec generated by `Microsoft.Extensions.ApiDescription.Server` to detect contract drift:

```bash
# Build to generate the live spec
dotnet build

# Compare authoritative spec vs generated spec
oasdiff diff \
  src/PropertyService.Api/Contracts/v1/openapi.yaml \
  src/PropertyService.Api/bin/Debug/net10.0/PropertyService.Api.json
```

If there is drift, either update the authoritative spec or fix the endpoint metadata to match.

## Folder Structure

The complete contract-first folder layout within the API project:

```
PropertyService.Api/
  Contracts/
    v1/
      openapi.yaml                          <-- Authoritative spec (source of truth)
  Generated/
    Dtos.g.cs                               <-- NSwag-generated DTOs (never hand-edit)
  Endpoints/
    CompanySearch/
      CreateCompanySearchEndpoint.cs        <-- POST endpoint
      GetCompanySearchEndpoint.cs           <-- GET endpoint
  Mapping/
    ApiContractMappingConfig.cs             <-- Mapster profile: generated DTO <-> command
  nswag.json                                <-- NSwag configuration for DTO generation
  PropertyService.Api.csproj                <-- MSBuild targets for NSwag + ApiDescription
```

### Relationship to Other Layers

The generated DTOs exist only in the API layer. They never cross into Application or Infrastructure:

```
API Layer:          Generated DTO --> Mapster --> Command sealed record
Application Layer:  Command sealed record --> Handler --> Domain Entity
Infrastructure:     Domain Entity --> Repository --> SQL
```

## Checklist for New API Operations

Follow this checklist for every new endpoint. Steps must be completed in order.

1. **Define the operation in the OpenAPI spec** -- Add the path, request/response schemas, and standard error responses to `Contracts/v1/openapi.yaml`.
2. **Regenerate DTOs** -- Run `dotnet build` to trigger the NSwag pre-build target. Verify `Generated/Dtos.g.cs` includes the new types.
3. **Create the internal command or query** -- Sealed record in the Application layer. See `/lextech-dotnet:vertical-slice`.
4. **Create the FluentValidation validator** -- Validate the internal command. See `/lextech-dotnet:vertical-slice`.
5. **Create the Wolverine handler** -- `HandleAsync` method with `CancellationToken`. See `/lextech-dotnet:wolverine-cqrs`.
6. **Add Mapster mapping** -- Map generated request DTO to internal command and domain entity to generated response DTO in `ApiContractMappingConfig.cs`.
7. **Create the endpoint** -- Consume the generated DTO, map to command, dispatch via `IMessageBus`, return the generated response type.
8. **Wire up endpoint metadata** -- `.WithName()` matching `operationId`, `.WithTags()`, `.WithSummary()`, `.WithGroupName()`, `.Produces<T>()`, `.ProducesValidationProblem()`, `.ProducesProblem()`, `.RequireAuthorization()`.
9. **Map the endpoint in Program.cs** -- Add to the versioned `RouteGroupBuilder`.
10. **Run unit tests** -- Handler and validator tests must pass. See `/lextech-dotnet:testing-patterns`.
11. **Run integration tests** -- End-to-end tests must pass.
12. **Verify contract consistency** -- Build and diff the authoritative spec against the generated spec. Fix any drift.
13. **Run breaking change detection** -- Compare against the `main` branch spec using `oasdiff`.

## Cross-References

- **Feature Workflow**: See `/lextech-dotnet:vertical-slice` for the full 11-step feature development process and folder structure.
- **Handlers and Messaging**: See `/lextech-dotnet:wolverine-cqrs` for handler conventions, `IMessageBus` usage, and polling patterns.
- **Testing**: See `/lextech-dotnet:testing-patterns` for endpoint contract tests, handler unit tests, and integration test templates.
- **Security**: See `/lextech-dotnet:security-owasp` for endpoint authorization, input validation, and OWASP compliance.
