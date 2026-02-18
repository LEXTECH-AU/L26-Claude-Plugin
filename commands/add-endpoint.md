---
name: add-endpoint
description: Add a Minimal API endpoint for an existing command or query, mapped to the OpenAPI contract
argument-hint: "[CommandOrQueryName]"
---

# Add a Minimal API Endpoint

You are adding a Minimal API endpoint for an existing command or query in a Lextech .NET 10 Clean Architecture microservice. The endpoint must conform to the OpenAPI contract. Follow every instruction below precisely.

## Step 1: Parse Arguments

Parse the argument provided by the user. Expect one positional argument:

1. **CommandOrQueryName** -- The full name of an existing command or query (e.g., `CreateCompanySearchCommand`, `GetCompanySearchQuery`). PascalCase.

If the argument is missing, ask the user for it interactively before proceeding.

Derive these values from the name:
- **Action** -- The verb prefix (e.g., `Create`, `Get`, `Update`, `Delete`).
- **EntityName** -- The entity portion (e.g., `CompanySearch`).
- **SliceType** -- `command` if the name ends with `Command`, `query` if it ends with `Query`.
- **FeatureName** -- Inferred from the entity or folder structure.

## Step 2: Locate the Command/Query

Search the Application layer project (`{Service}.Application`) for a file matching the provided name:

```
- Search pattern: **/{CommandOrQueryName}.cs
- If not found, list available commands/queries and ask the user to select one.
- Once found, read the file to understand its properties and return types.
```

Note the namespace to determine the feature area and folder structure.

## Step 3: Read the OpenAPI Spec

Find the OpenAPI spec file in the API project:

```
- Search path: {Service}.Api/Contracts/v1/openapi.yaml
- Fallback search: **/openapi.yaml or **/openapi.json
- If no spec file exists, warn the user and ask whether to create one (read the `openapi-contract-first` skill for the template).
```

Search the spec for an operation matching the command/query name. The convention is:
- `operationId` = command name without the `Command` or `Query` suffix (e.g., `CreateCompanySearchCommand` maps to `operationId: CreateCompanySearch`).

## Step 4: Determine Endpoint Details

### If the operation exists in the spec:

Extract from the spec:
- **HTTP method** -- from the operation key (`get`, `post`, `put`, `delete`, `patch`).
- **Route path** -- from the `paths` key (e.g., `/api/v1/company-searches`).
- **Request body schema** -- the `$ref` or inline schema under `requestBody`.
- **Response schemas** -- all status codes and their `$ref` or inline schemas.
- **Tags** -- the `tags` array for grouping.
- **Summary** -- the `summary` field.

### If the operation does NOT exist in the spec:

Ask the user for:
1. HTTP method (GET, POST, PUT, DELETE, PATCH).
2. Route path (e.g., `/api/v1/company-searches`).

Then add the operation to the spec file following the `openapi-contract-first` skill conventions. Run `dotnet build` in the API project to trigger NSwag DTO generation after updating the spec.

## Step 5: Check for Generated DTOs

Search for generated DTOs in the API project:

```
- Search path: {Service}.Api/Generated/Dtos.g.cs
- Look for request/response types matching the spec schema names.
```

If generated DTOs are found:
- Use the generated request DTO as the endpoint parameter type.
- Use the generated response DTO as the `Produces<T>()` type.

If generated DTOs are NOT found:
- Run `dotnet build` in the API project to trigger NSwag generation.
- Verify the DTOs now exist in `Generated/Dtos.g.cs`.
- If still missing, fall back to using the command/query directly as the endpoint parameter.

## Step 6: Generate the Endpoint File

**File**: `{Service}.Api/Endpoints/{FeatureName}/{Action}{EntityName}Endpoint.cs`

```csharp
using {Service}.Application.{FeatureName}.Commands.{Action}{EntityName};
using {Service}.Application.{FeatureName}.DTOs;
using Mapster;
using Microsoft.AspNetCore.Mvc;
using Wolverine;

namespace {Service}.Api.Endpoints.{FeatureName};

/// <summary>
/// Endpoint for the {Action}{EntityName} operation.
/// </summary>
public static class {Action}{EntityName}Endpoint
{
    /// <summary>
    /// Maps the {Action}{EntityName} endpoint to the route builder.
    /// </summary>
    /// <param name="app">The endpoint route builder.</param>
    public static void Map(IEndpointRouteBuilder app)
    {
        app.Map{HttpMethod}("{routePath}", HandleAsync)
            .RequireAuthorization()
            .WithName("{operationId}")
            .WithTags("{tag}")
            .WithSummary("{summary}")
            .Produces<{ResponseDto}>(StatusCodes.Status{SuccessCode})
            .ProducesValidationProblem()
            .ProducesProblem(StatusCodes.Status500InternalServerError);
    }

    /// <summary>
    /// Handles the {Action}{EntityName} request.
    /// </summary>
    private static async Task<IResult> HandleAsync(
        [{FromBody or FromRoute}] {RequestDto} request,
        [FromServices] IMessageBus messageBus,
        CancellationToken cancellationToken)
    {
        {Action}{EntityName}Command command = request.Adapt<{Action}{EntityName}Command>();

        {ResponseType} result = await messageBus.InvokeAsync<{ResponseType}>(
            command,
            cancellationToken);

        return Results.{ResultMethod}(result);
    }
}
```

Adapt the template based on the HTTP method:
- **POST**: Use `[FromBody]`, return `Results.Created($"/api/v1/{resource}/{result.Id}", result)`, add `.Produces<T>(StatusCodes.Status201Created)`.
- **GET**: Use `[FromRoute]`/`[FromQuery]` for parameters, return `Results.Ok(result)` or `Results.NotFound()`, add `.Produces<T>(StatusCodes.Status200OK)` and `.ProducesProblem(StatusCodes.Status404NotFound)`.
- **PUT/PATCH**: Use `[FromBody]` + `[FromRoute]` for ID, return `Results.Ok(result)` or `Results.NoContent()`.
- **DELETE**: Use `[FromRoute]` for ID, return `Results.NoContent()`, add `.Produces(StatusCodes.Status204NoContent)`.

Add `.Produces<T>()` for **every** response status code defined in the spec for this operation.

## Step 7: Generate Mapster Profile

If using generated DTOs from `Generated/Dtos.g.cs`, create or update the API-layer mapping configuration:

**File**: `{Service}.Api/Mapping/ApiContractMappingConfig.cs`

```csharp
using {Service}.Api.Generated;
using {Service}.Application.{FeatureName}.Commands.{Action}{EntityName};
using Mapster;

namespace {Service}.Api.Mapping;

/// <summary>
/// Mapster configuration for mapping OpenAPI contract DTOs to internal commands and queries.
/// </summary>
public sealed class ApiContractMappingConfig : IRegister
{
    /// <summary>
    /// Registers the DTO-to-command mappings.
    /// </summary>
    /// <param name="config">The Mapster type adapter configuration.</param>
    public void Register(TypeAdapterConfig config)
    {
        config.NewConfig<{GeneratedRequestDto}, {Action}{EntityName}Command>();
        // Add explicit .Map() calls if property names differ between DTO and command.
    }
}
```

If the file already exists, read it first and add the new mapping to the existing `Register` method instead of creating a new file.

## Step 8: Verify

After creating all files:

1. List every file created or modified with its full path.
2. Remind the user to:
   - Run `dotnet build` to verify compilation and regenerate DTOs.
   - Register the endpoint in `Program.cs` or the endpoint registration extension method.
   - Run existing unit tests: `dotnet test`
   - Verify the endpoint `.WithName()` matches the spec's `operationId`.
   - Run `oasdiff` to verify no breaking changes if modifying an existing operation.
3. Suggest running `/lextech-dotnet:pre-pr` to validate full contract compliance.

## Important Rules

- **No `var`** -- use explicit types everywhere.
- **XML docs** on every public class, method, and property.
- **CancellationToken** on every async method signature.
- **Structured logging only** -- never use `$""` inside Serilog log calls.
- **sealed** on all records, classes, and validators. Endpoint classes are `static`.
- **init** properties on all records, never `set`.
- `.WithName()` MUST match the `operationId` from the OpenAPI spec.
- `.WithTags()` MUST match the spec's tag grouping.
- `.WithSummary()` MUST match the spec's `summary` field.
- `.Produces<T>()` MUST cover every response status code defined in the spec for this operation.
- If any file already exists, read it first and ask the user before overwriting.
