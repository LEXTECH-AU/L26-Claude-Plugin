---
name: new-feature
description: Scaffold a complete vertical slice feature across all architecture layers
argument-hint: "[FeatureName] [EntityName] [command|query|both]"
---

# Scaffold a New Vertical Slice Feature

You are scaffolding a complete vertical slice feature for a Lextech .NET 10 Clean Architecture microservice. Follow every instruction below precisely.

## Step 1: Parse Arguments

Parse the arguments provided by the user. Expect up to three positional arguments:

1. **FeatureName** -- The feature area name (e.g., `CompanySearch`, `TitleSearch`, `PropertyValuation`). PascalCase, no spaces.
2. **EntityName** -- The primary domain entity (e.g., `CompanySearchOrder`, `TitleSearchResult`). PascalCase.
3. **SliceType** -- One of `command`, `query`, or `both`. Determines which slices to scaffold.

If any argument is missing, ask the user for it interactively before proceeding. Confirm all three values with the user before generating any files.

## Step 2: Check the OpenAPI Contract

Before writing any code, check the OpenAPI spec at `{Service}.Api/Contracts/v1/openapi.yaml`:

1. Search for an existing operation matching the feature name (by operationId convention).
2. If the operation exists: use its path, HTTP method, request body schema, and response schemas as the source of truth for all subsequent scaffolding.
3. If the operation does NOT exist: add the operation to the spec file with the correct path, method, and schemas before proceeding. Read the `openapi-contract-first` skill for the spec template.
4. Run `dotnet build` in the API project to trigger NSwag pre-build DTO generation from the updated spec.
5. Verify that generated DTOs appear in `{Service}.Api/Generated/Dtos.g.cs`.

## Step 3: Load the Vertical Slice Skill

Read the `vertical-slice` skill to load the canonical folder structure, templates, and naming conventions. This skill defines the 11-step feature workflow that every feature must follow. Also read the `dapper-postgresql` skill if it has content, and the `wolverine-cqrs` skill if it has content, so you understand handler and repository patterns.

## Step 4: Detect the Solution Structure

Search the current working directory for `.sln` and `.csproj` files to determine:

- The solution root directory.
- The service name prefix (e.g., `PropertyService`).
- The four layer projects: `{Service}.Domain`, `{Service}.Application`, `{Service}.Infrastructure`, `{Service}.Api`.
- Verify all four layer projects exist. If any are missing, warn the user and ask how to proceed.

## Step 5: Determine the Action Verb

For **command** slices, ask the user for the action verb if not obvious from the feature name. Common verbs: `Create`, `Update`, `Delete`, `Submit`, `Cancel`, `Process`. The verb becomes the prefix of the command name (e.g., `Create` + `CompanySearch` = `CreateCompanySearchCommand`).

For **query** slices, determine the query pattern. Common patterns: `GetById`, `GetByMatter`, `Search`, `List`. Ask the user if unclear.

## Step 6: Create Files -- Domain Layer

If the entity does not already exist in the Domain project, create it:

**File**: `{Service}.Domain/{FeatureName}/{EntityName}.cs`

```
- Namespace: {Service}.Domain.{FeatureName}
- sealed record with init properties
- XML docs on the class and every property
- Include: Id (Guid), standard audit fields (CreatedAt, ModifiedAt, IsDeleted)
- Include entity-specific properties based on the feature context
- No EF, no Dapper, no JSON attributes -- pure domain
```

If the entity already exists, skip this step and inform the user.

## Step 7: Create Files -- Application Layer (Command Slice)

Only create these if SliceType is `command` or `both`.

### 7a. Command Record

**File**: `{Service}.Application/{FeatureName}/Commands/{Action}{EntityName}/{Action}{EntityName}Command.cs`

```
- sealed record, not class
- All properties use { get; init; }
- Sensible defaults: string.Empty for strings, 0 for ints
- Nullable properties use ? suffix
- XML doc <summary> on every property
- Namespace: {Service}.Application.{FeatureName}.Commands.{Action}{EntityName}
```

### 7b. Command Handler

**File**: `{Service}.Application/{FeatureName}/Commands/{Action}{EntityName}/{Action}{EntityName}CommandHandler.cs`

```
- sealed class with primary constructor DI
- Inject: IUnitOfWork, IMessageBus, ILogger<{Handler}>
- HandleAsync method with CancellationToken
- Begin/Commit/Rollback transaction pattern
- Structured logging (no string interpolation in log calls)
- Mapster for entity-to-DTO mapping
```

### 7c. Command Validator

**File**: `{Service}.Application/{FeatureName}/Commands/{Action}{EntityName}/{Action}{EntityName}CommandValidator.cs`

```
- sealed class extending AbstractValidator<{Command}>
- Rules for every property: NotEmpty, MaximumLength, GreaterThan, etc.
- Clear .WithMessage() on every rule
- Pattern validation where applicable (email, phone, ABN, etc.)
```

## Step 8: Create Files -- Application Layer (Query Slice)

Only create these if SliceType is `query` or `both`.

### 8a. Query Record

**File**: `{Service}.Application/{FeatureName}/Queries/{QueryName}/{QueryName}Query.cs`

```
- sealed record with init properties
- XML docs on class and all properties
- Namespace: {Service}.Application.{FeatureName}.Queries.{QueryName}
```

### 8b. Query Handler

**File**: `{Service}.Application/{FeatureName}/Queries/{QueryName}/{QueryName}QueryHandler.cs`

```
- sealed class with primary constructor DI
- Inject: IUnitOfWork, ILogger<{Handler}>
- HandleAsync returning nullable DTO (for single) or IReadOnlyList<DTO> (for list)
- CancellationToken parameter
- Structured logging
```

## Step 9: Create Files -- Application Layer (Shared)

### 9a. Repository Interface

**File**: `{Service}.Application/{FeatureName}/Interfaces/I{EntityName}Repository.cs`

```
- Interface in Application layer (not Infrastructure)
- Async methods with CancellationToken
- Return domain entities, not DTOs
- Methods matching the command/query operations being scaffolded
```

### 9b. DTOs

**File**: `{Service}.Application/{FeatureName}/DTOs/{EntityName}Response.cs`

```
- sealed record for the response DTO
- Only properties needed by the API consumer
- XML docs on all properties
```

### 9c. Mapping Profile

**File**: `{Service}.Application/{FeatureName}/Mapping/{FeatureName}MappingConfig.cs`

```
- sealed class implementing IRegister
- Map command -> entity
- Map entity -> response DTO
- Explicit property mappings where names differ
```

## Step 10: Create Files -- Infrastructure Layer

### 10a. SQL Files

For each database operation needed by the repository:

**File**: `{Service}.Infrastructure/Persistence/Sql/{FeatureName}/{EntityName}_{Operation}.sql`

```
- Header comment block: purpose, parameters, author info
- Parameterized queries with @-prefixed parameters
- INSERT: Use ON CONFLICT for upsert support
- SELECT: Include WHERE is_deleted = false, explicit ORDER BY
- UPDATE: Set modified_at = @ModifiedAt
- DELETE: Soft delete (SET is_deleted = true)
- Set Build Action to Embedded Resource in .csproj
```

### 10b. Repository Implementation

**File**: `{Service}.Infrastructure/Persistence/Repositories/{EntityName}Repository.cs`

```
- sealed class with primary constructor DI: IDbConnection, ISqlFileService
- Implement the Application layer interface
- Load SQL via ISqlFileService.GetSql("{EntityName}/{Operation}")
- Use DynamicParameters for all queries
- CancellationToken on all async methods
- XML docs on the class and all public methods
```

### 10c. Register in Unit of Work

Find the existing `UnitOfWork.cs` file and add a lazy property for the new repository:

```
private I{EntityName}Repository? _{camelCase}Repository;
public I{EntityName}Repository {EntityName}Repository =>
    _{camelCase}Repository ??= new {EntityName}Repository(_connection, _sqlFileService);
```

## Step 11: Create Files -- API Layer

### 11a. Endpoint Class(es)

For each command/query, create an endpoint:

**File**: `{Service}.Api/Endpoints/{FeatureName}/{Action}{EntityName}Endpoint.cs`

```
- static class with Map(IEndpointRouteBuilder) method
- RequireAuthorization() on every endpoint
- WithName() and WithTags() for OpenAPI
- Produces<T>() for success, ProducesValidationProblem(), ProducesProblem()
- Thin handler: validate -> invoke message bus -> return result
- POST returns 201 Created with location header
- GET returns 200 OK or 404 Not Found
- DELETE returns 204 No Content
- If generated DTOs exist in `Generated/Dtos.g.cs`, use the generated request DTO as the endpoint parameter type instead of the command directly.
- Add a Mapster mapping from the generated DTO to the internal command in `{Service}.Api/Mapping/ApiContractMappingConfig.cs`.
- `.WithName()` MUST match the `operationId` from the OpenAPI spec.
- `.WithTags()` MUST match the spec's tag grouping.
- `.WithSummary()` MUST match the spec's `summary` field.
- `.Produces<T>()` MUST cover every response status code defined in the spec for this operation.
```

## Step 12: Verify and Summarize

After creating all files:

1. List every file created with its full path.
2. Remind the user about the remaining manual steps:
   - Ensure SQL files are set as `EmbeddedResource` in the `.csproj` file.
   - Register the endpoint in `Program.cs` or the endpoint registration extension.
   - Run `dotnet build` to check for compilation errors.
   - Write and run unit tests: `/lextech-dotnet:new-test {Handler} handler`
   - Write and run integration tests: `/lextech-dotnet:new-test {Repository} integration`
3. Verify OpenAPI contract alignment:
   - OpenAPI spec has been updated with the new operation.
   - Generated DTOs match the spec (run `dotnet build` to regenerate).
   - Endpoint `.WithName()` matches the spec's `operationId`.
   - Run `oasdiff` to verify no breaking changes if modifying an existing operation.
4. Display the 12-step workflow checklist with checkmarks for completed steps and empty boxes for remaining steps.
5. Remind: **Unit tests must pass before proceeding to the next feature.**

## Important Rules

- **No `var`** -- use explicit types everywhere.
- **XML docs** on every public class, method, and property.
- **CancellationToken** on every async method signature.
- **Structured logging only** -- never use `$""` inside Serilog log calls.
- **sealed** on all records, classes, and validators.
- **init** properties on all records, never `set`.
- Follow the exact namespace and folder conventions from the vertical-slice skill.
- If any file already exists, ask the user before overwriting.
