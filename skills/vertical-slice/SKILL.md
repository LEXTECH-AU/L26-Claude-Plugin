---
name: vertical-slice
description: "Vertical Slice feature development patterns for .NET 10 Clean Architecture. Use when creating new features, scaffolding commands/queries, or implementing the feature workflow."
---

# Vertical Slice Feature Development

This skill defines the mandatory workflow, folder structure, and code templates for building features in Lextech .NET 10 Clean Architecture microservices. Every new feature follows a vertical slice approach: all layers (API, Application, Infrastructure) are built together for a single use case.

## Mandatory 13-Step Feature Workflow

Follow these steps in order for every new feature. Do not skip steps.

1. **Define/Update the OpenAPI Operation** -- Add or update the operation in the OpenAPI spec file. See `/lextech-dotnet:openapi-contract-first`.
2. **Generate DTOs from the Spec** -- Run `dotnet build` to trigger NSwag pre-build DTO generation.
3. **Define the Command or Query** -- Create a sealed record in the Application layer.
4. **Create the FluentValidation Validator** -- Validate all inputs before the handler runs.
5. **Write the SQL File** -- Embedded `.sql` resource for the database operation. See `/lextech-dotnet:dapper-postgresql`.
6. **Create or Update the Repository Interface** -- Define the contract in the Application layer.
7. **Implement the Repository** -- Dapper-based implementation in the Infrastructure layer.
8. **Register the Repository in Unit of Work** -- Add lazy property to `UnitOfWork`.
9. **Create the Handler** -- Wolverine handler with `HandleAsync`. See `/lextech-dotnet:wolverine-cqrs`.
10. **Create the Mapster Mapping Profile** -- Map between domain entities and DTOs/commands.
11. **Create the Minimal API Endpoint** -- Wire the HTTP route to the message bus.
12. **Write Unit Tests** -- Handler and validator tests. See `/lextech-dotnet:testing-patterns`.
13. **Write Integration Tests** -- End-to-end test against the real database.

## Folder Structure Per Layer

```
src/
  PropertyService.Api/
    Endpoints/
      CompanySearch/
        CreateCompanySearchEndpoint.cs
        GetCompanySearchEndpoint.cs
  PropertyService.Application/
    CompanySearch/
      Commands/
        CreateCompanySearch/
          CreateCompanySearchCommand.cs
          CreateCompanySearchHandler.cs
          CreateCompanySearchValidator.cs
      Queries/
        GetCompanySearch/
          GetCompanySearchQuery.cs
          GetCompanySearchHandler.cs
      Mapping/
        CompanySearchMappingConfig.cs
      Interfaces/
        ICompanySearchRepository.cs
  PropertyService.Infrastructure/
    Persistence/
      Repositories/
        CompanySearchRepository.cs
      Sql/
        CompanySearch/
          MatterCompanySearch_Insert.sql
          MatterCompanySearch_GetById.sql
      UnitOfWork.cs
```

## Command Sealed Record Template

Commands represent write operations that change state. Always use `sealed record` with `init` properties and XML doc comments on every property.

```csharp
namespace PropertyService.Application.CompanySearch.Commands.CreateCompanySearch;

/// <summary>
/// Command to create a new company search order.
/// </summary>
public sealed record CreateCompanySearchCommand
{
    /// <summary>
    /// The matter ID from the client system.
    /// </summary>
    public int MatterId { get; init; }

    /// <summary>
    /// The company identifier (ACN, ARBN, or ARSN).
    /// </summary>
    public string Identifier { get; init; } = string.Empty;

    /// <summary>
    /// The registered organisation name.
    /// </summary>
    public string OrganisationName { get; init; } = string.Empty;

    /// <summary>
    /// The type of identifier. Defaults to "acn".
    /// </summary>
    public string IdentifierType { get; init; } = "acn";

    /// <summary>
    /// Optional Australian Business Number.
    /// </summary>
    public string? Abn { get; init; }

    /// <summary>
    /// The extract type. Defaults to "current".
    /// </summary>
    public string ExtractType { get; init; } = "current";

    /// <summary>
    /// The client-side matter reference string.
    /// </summary>
    public string MatterReference { get; init; } = string.Empty;
}
```

### Rules for Commands

- Always `sealed record`, never `class`.
- All properties use `{ get; init; }` -- never `set`.
- Provide sensible defaults with `= string.Empty` or `= "value"` where applicable.
- Nullable properties use `?` suffix (e.g., `string? Abn`).
- Every property must have an XML `<summary>` doc comment.
- Namespace follows the pattern: `{Service}.Application.{Feature}.Commands.{CommandName}`.

## Query Sealed Record Template

Queries represent read operations with no side effects.

```csharp
namespace PropertyService.Application.CompanySearch.Queries.GetCompanySearch;

/// <summary>
/// Query to retrieve a company search order by matter ID and order ID.
/// </summary>
public sealed record GetCompanySearchQuery
{
    /// <summary>
    /// The matter ID from the client system.
    /// </summary>
    public int MatterId { get; init; }

    /// <summary>
    /// The Dye &amp; Durham order identifier.
    /// </summary>
    public string OrderId { get; init; } = string.Empty;
}
```

## Handler Template

Handlers use primary constructor dependency injection. Commands go through `IUnitOfWork` for transactional writes. Queries use repositories directly for reads.

### Command Handler

```csharp
namespace PropertyService.Application.CompanySearch.Commands.CreateCompanySearch;

/// <summary>
/// Handles the creation of a new company search order.
/// </summary>
public sealed class CreateCompanySearchHandler(
    IUnitOfWork unitOfWork,
    IMessageBus messageBus,
    ILogger<CreateCompanySearchHandler> logger)
{
    public async Task<CompanySearchResponse> HandleAsync(
        CreateCompanySearchCommand command,
        CancellationToken cancellationToken = default)
    {
        logger.LogInformation("Creating company search for matter {MatterId}", command.MatterId);

        await unitOfWork.BeginTransactionAsync(cancellationToken);
        try
        {
            var order = command.Adapt<CompanySearchOrder>();
            order.OrderStatus = OrderStatus.Pending;
            order.CreatedAt = DateTimeOffset.UtcNow;
            order.ModifiedAt = DateTimeOffset.UtcNow;

            await unitOfWork.CompanySearchRepository.CreateAsync(order, cancellationToken);
            await unitOfWork.CommitTransactionAsync(cancellationToken);

            // Publish a follow-up message to poll for results
            await messageBus.PublishAsync(new PollCompanySearchCommand
            {
                MatterId = command.MatterId,
                OrderId = order.OrderId
            });

            logger.LogInformation("Company search order {OrderId} created for matter {MatterId}",
                order.OrderId, command.MatterId);

            return order.Adapt<CompanySearchResponse>();
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Failed to create company search for matter {MatterId}", command.MatterId);
            await unitOfWork.RollbackTransactionAsync(cancellationToken);
            throw;
        }
    }
}
```

### Query Handler

```csharp
namespace PropertyService.Application.CompanySearch.Queries.GetCompanySearch;

/// <summary>
/// Handles retrieval of a company search order.
/// </summary>
public sealed class GetCompanySearchHandler(
    IUnitOfWork unitOfWork,
    ILogger<GetCompanySearchHandler> logger)
{
    public async Task<CompanySearchResponse?> HandleAsync(
        GetCompanySearchQuery query,
        CancellationToken cancellationToken = default)
    {
        logger.LogInformation("Retrieving company search for matter {MatterId}, order {OrderId}",
            query.MatterId, query.OrderId);

        var order = await unitOfWork.CompanySearchRepository
            .GetByMatterAndOrderIdAsync(query.MatterId, query.OrderId, cancellationToken);

        return order?.Adapt<CompanySearchResponse>();
    }
}
```

## FluentValidation Validator Template

Every command must have a validator. Use `AbstractValidator<T>` with clear error messages.

```csharp
namespace PropertyService.Application.CompanySearch.Commands.CreateCompanySearch;

/// <summary>
/// Validates the CreateCompanySearchCommand inputs.
/// </summary>
public sealed class CreateCompanySearchValidator : AbstractValidator<CreateCompanySearchCommand>
{
    public CreateCompanySearchValidator()
    {
        RuleFor(x => x.MatterId)
            .GreaterThan(0)
            .WithMessage("Matter ID must be a positive integer.");

        RuleFor(x => x.Identifier)
            .NotEmpty()
            .WithMessage("Company identifier is required.")
            .MaximumLength(20)
            .WithMessage("Company identifier must not exceed 20 characters.");

        RuleFor(x => x.OrganisationName)
            .NotEmpty()
            .WithMessage("Organisation name is required.")
            .MaximumLength(200)
            .WithMessage("Organisation name must not exceed 200 characters.");

        RuleFor(x => x.IdentifierType)
            .NotEmpty()
            .Must(type => type is "acn" or "arbn" or "arsn")
            .WithMessage("Identifier type must be 'acn', 'arbn', or 'arsn'.");

        RuleFor(x => x.Abn)
            .Length(11)
            .When(x => x.Abn is not null)
            .WithMessage("ABN must be exactly 11 digits.");

        RuleFor(x => x.ExtractType)
            .NotEmpty()
            .Must(type => type is "current" or "historical")
            .WithMessage("Extract type must be 'current' or 'historical'.");

        RuleFor(x => x.MatterReference)
            .NotEmpty()
            .MaximumLength(100)
            .WithMessage("Matter reference must not exceed 100 characters.");
    }
}
```

## Minimal API Endpoint Pattern

Endpoints are thin -- they validate, invoke the message bus, and return the result. They never contain business logic.

```csharp
namespace PropertyService.Api.Endpoints.CompanySearch;

/// <summary>
/// Endpoint for creating a new company search order.
/// </summary>
public static class CreateCompanySearchEndpoint
{
    public static void Map(IEndpointRouteBuilder app)
    {
        app.MapPost("/api/v1/company-search", HandleAsync)
            .RequireAuthorization()
            .WithName("CreateCompanySearch")
            .WithTags("CompanySearch")
            .Produces<CompanySearchResponse>(StatusCodes.Status201Created)
            .ProducesValidationProblem()
            .ProducesProblem(StatusCodes.Status500InternalServerError);
    }

    private static async Task<IResult> HandleAsync(
        CreateCompanySearchCommand command,
        IMessageBus messageBus,
        CancellationToken cancellationToken)
    {
        var result = await messageBus.InvokeAsync<CompanySearchResponse>(command, cancellationToken);
        return Results.Created($"/api/v1/company-search/{result.OrderId}", result);
    }
}
```

### GET Endpoint Example

```csharp
public static class GetCompanySearchEndpoint
{
    public static void Map(IEndpointRouteBuilder app)
    {
        app.MapGet("/api/v1/company-search/{matterId:int}/{orderId}", HandleAsync)
            .RequireAuthorization()
            .WithName("GetCompanySearch")
            .WithTags("CompanySearch")
            .Produces<CompanySearchResponse>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status404NotFound);
    }

    private static async Task<IResult> HandleAsync(
        int matterId,
        string orderId,
        IMessageBus messageBus,
        CancellationToken cancellationToken)
    {
        var query = new GetCompanySearchQuery { MatterId = matterId, OrderId = orderId };
        var result = await messageBus.InvokeAsync<CompanySearchResponse?>(query, cancellationToken);
        return result is not null ? Results.Ok(result) : Results.NotFound();
    }
}
```

## Mapster Mapping Profile

Use `IRegister` to configure mappings. Keep mapping logic centralized per feature.

```csharp
namespace PropertyService.Application.CompanySearch.Mapping;

/// <summary>
/// Mapster mapping configuration for company search entities and DTOs.
/// </summary>
public sealed class CompanySearchMappingConfig : IRegister
{
    public void Register(TypeAdapterConfig config)
    {
        config.NewConfig<CreateCompanySearchCommand, CompanySearchOrder>()
            .Map(dest => dest.CompanyIdentifier, src => src.Identifier)
            .Map(dest => dest.OrderStatus, _ => OrderStatus.Pending)
            .Map(dest => dest.CreatedAt, _ => DateTimeOffset.UtcNow)
            .Map(dest => dest.ModifiedAt, _ => DateTimeOffset.UtcNow);

        config.NewConfig<CompanySearchOrder, CompanySearchResponse>()
            .Map(dest => dest.Status, src => src.OrderStatus.ToString());
    }
}
```

## Cross-References

- **SQL and Repositories**: See `/lextech-dotnet:dapper-postgresql` for SQL file templates, repository patterns, and Unit of Work lifecycle.
- **Handlers and Messaging**: See `/lextech-dotnet:wolverine-cqrs` for handler conventions, message bus usage, and polling patterns.
- **Testing**: See `/lextech-dotnet:testing-patterns` for unit test and integration test templates.
- **LIXI Types**: See `/lextech-dotnet:lixi-das-schema` when the feature involves Australian lending data types.
