---
name: wolverine-cqrs
description: "Wolverine CQRS command/query handler and messaging patterns. Use when implementing handlers, publishing messages, or configuring the message bus."
---

# Wolverine CQRS and Messaging

This skill covers Wolverine handler patterns, message bus usage, and messaging infrastructure for Lextech .NET 10 microservices. Wolverine provides CQRS command/query dispatch, asynchronous messaging, and transactional outbox support.

## Command Handler Pattern

Command handlers perform write operations with side effects. They receive an `IUnitOfWork` for transactional data access, `IMessageBus` for publishing follow-up messages, and `ILogger` for structured logging. Use primary constructor DI.

### Handler Naming Convention

- File: `{CommandName}Handler.cs`
- Class: `{CommandName}Handler`
- Method: `HandleAsync`
- Wolverine discovers handlers by convention -- no manual registration needed.

### Full Command Handler

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
        logger.LogInformation("Creating company search for matter {MatterId}, identifier {Identifier}",
            command.MatterId, command.Identifier);

        await unitOfWork.BeginTransactionAsync(cancellationToken);
        try
        {
            var order = command.Adapt<CompanySearchOrder>();
            order.OrderId = Guid.NewGuid().ToString("N");
            order.OrderStatus = OrderStatus.Pending;
            order.CreatedAt = DateTimeOffset.UtcNow;
            order.ModifiedAt = DateTimeOffset.UtcNow;

            await unitOfWork.CompanySearchRepository.CreateAsync(order, cancellationToken);
            await unitOfWork.CommitTransactionAsync(cancellationToken);

            // Fire-and-forget: poll for the order result
            await messageBus.PublishAsync(new PollCompanySearchCommand
            {
                MatterId = command.MatterId,
                OrderId = order.OrderId
            });

            logger.LogInformation("Company search order {OrderId} created successfully", order.OrderId);
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

## Query Handler Pattern

Query handlers are read-only and must never produce side effects. They do not begin transactions and do not publish messages.

```csharp
namespace PropertyService.Application.CompanySearch.Queries.GetCompanySearch;

/// <summary>
/// Handles retrieval of a company search order by matter and order ID.
/// </summary>
public sealed class GetCompanySearchHandler(
    IUnitOfWork unitOfWork,
    ILogger<GetCompanySearchHandler> logger)
{
    public async Task<CompanySearchResponse?> HandleAsync(
        GetCompanySearchQuery query,
        CancellationToken cancellationToken = default)
    {
        logger.LogInformation("Fetching company search: matter {MatterId}, order {OrderId}",
            query.MatterId, query.OrderId);

        var order = await unitOfWork.CompanySearchRepository
            .GetByMatterAndOrderIdAsync(query.MatterId, query.OrderId, cancellationToken);

        if (order is null)
        {
            logger.LogWarning("Company search not found: matter {MatterId}, order {OrderId}",
                query.MatterId, query.OrderId);
            return null;
        }

        return order.Adapt<CompanySearchResponse>();
    }
}
```

### Query Handler Rules

- Never call `BeginTransactionAsync` or `CommitTransactionAsync`.
- Never call `messageBus.PublishAsync` or `messageBus.InvokeAsync`.
- Return `null` or an empty collection when no results are found -- do not throw.
- Use `IUnitOfWork` for repository access (the connection is shared, no transaction opened).

## IMessageBus.InvokeAsync -- Request/Response

Use `InvokeAsync<T>` when you need the handler's return value. This is the pattern used by API endpoints to dispatch commands and queries.

```csharp
// In a Minimal API endpoint -- synchronous request/response
var result = await messageBus.InvokeAsync<CompanySearchResponse>(command, cancellationToken);

// For queries
var result = await messageBus.InvokeAsync<CompanySearchResponse?>(query, cancellationToken);
```

`InvokeAsync<T>` executes the handler in-process and returns the result directly. It does not go through the message transport.

## IMessageBus.PublishAsync -- Fire-and-Forget

Use `PublishAsync` when you do not need the result and the message should be processed asynchronously. The message goes through the configured transport (in-memory or Azure Service Bus).

```csharp
// Publish a follow-up command after creating an order
await messageBus.PublishAsync(new PollCompanySearchCommand
{
    MatterId = command.MatterId,
    OrderId = order.OrderId
});

// Publish a notification event
await messageBus.PublishAsync(new CompanySearchCompletedEvent
{
    MatterId = order.MatterId,
    OrderId = order.OrderId,
    Status = order.OrderStatus.ToString()
});
```

### When to Use InvokeAsync vs PublishAsync

| Scenario | Method | Reason |
|----------|--------|--------|
| API endpoint dispatching a command | `InvokeAsync<T>` | Endpoint needs the response |
| API endpoint dispatching a query | `InvokeAsync<T>` | Endpoint needs the data |
| Handler triggering a follow-up command | `PublishAsync` | Asynchronous, no response needed |
| Handler emitting a domain event | `PublishAsync` | Decoupled notification |
| Handler needing a sub-result from another handler | `InvokeAsync<T>` | Synchronous dependency |

## DeliveryOptions with ScheduleDelay

Use `DeliveryOptions` to delay message processing. This is the mechanism for retry-with-backoff in polling scenarios.

```csharp
// Schedule a retry after 30 seconds
await messageBus.PublishAsync(
    new PollCompanySearchCommand
    {
        MatterId = command.MatterId,
        OrderId = command.OrderId,
        AttemptNumber = command.AttemptNumber + 1
    },
    new DeliveryOptions
    {
        ScheduleDelay = TimeSpan.FromSeconds(30)
    });
```

### Exponential Backoff Pattern

```csharp
var delay = TimeSpan.FromSeconds(Math.Pow(2, command.AttemptNumber) * 5);
// Attempt 1: 10s, Attempt 2: 20s, Attempt 3: 40s, etc.

await messageBus.PublishAsync(
    command with { AttemptNumber = command.AttemptNumber + 1 },
    new DeliveryOptions { ScheduleDelay = delay });
```

## Polling Handler Pattern

Polling handlers check an external API for status, then either complete or re-enqueue with a delay. They must enforce a maximum attempt count to avoid infinite loops.

```csharp
namespace PropertyService.Application.CompanySearch.Commands.PollCompanySearch;

/// <summary>
/// Command to poll the external API for company search results.
/// </summary>
public sealed record PollCompanySearchCommand
{
    public int MatterId { get; init; }
    public string OrderId { get; init; } = string.Empty;
    public int AttemptNumber { get; init; } = 1;
}

/// <summary>
/// Polls for company search results with retry logic.
/// </summary>
public sealed class PollCompanySearchHandler(
    IUnitOfWork unitOfWork,
    IMessageBus messageBus,
    ICompanySearchApiClient apiClient,
    ILogger<PollCompanySearchHandler> logger)
{
    private const int MaxAttempts = 10;

    public async Task HandleAsync(
        PollCompanySearchCommand command,
        CancellationToken cancellationToken = default)
    {
        logger.LogInformation(
            "Polling company search {OrderId}, attempt {Attempt}/{MaxAttempts}",
            command.OrderId, command.AttemptNumber, MaxAttempts);

        if (command.AttemptNumber > MaxAttempts)
        {
            logger.LogWarning("Max polling attempts reached for order {OrderId}", command.OrderId);
            await unitOfWork.CompanySearchRepository.UpdateStatusAsync(
                command.OrderId, OrderStatus.TimedOut, "Max polling attempts exceeded", cancellationToken);
            return;
        }

        var result = await apiClient.GetOrderStatusAsync(command.OrderId, cancellationToken);

        if (result.IsComplete)
        {
            logger.LogInformation("Company search {OrderId} completed", command.OrderId);

            await unitOfWork.BeginTransactionAsync(cancellationToken);
            try
            {
                await unitOfWork.CompanySearchRepository.UpdateStatusAsync(
                    command.OrderId, OrderStatus.Completed, null, cancellationToken);
                await unitOfWork.CommitTransactionAsync(cancellationToken);
            }
            catch
            {
                await unitOfWork.RollbackTransactionAsync(cancellationToken);
                throw;
            }

            // Publish completion event
            await messageBus.PublishAsync(new CompanySearchCompletedEvent
            {
                MatterId = command.MatterId,
                OrderId = command.OrderId
            });

            return;
        }

        // Not ready -- re-enqueue with delay
        var delay = TimeSpan.FromSeconds(Math.Pow(2, command.AttemptNumber) * 5);
        logger.LogInformation("Order {OrderId} not ready, retrying in {Delay}", command.OrderId, delay);

        await messageBus.PublishAsync(
            command with { AttemptNumber = command.AttemptNumber + 1 },
            new DeliveryOptions { ScheduleDelay = delay });
    }
}
```

## Fallback and Error Handler Patterns

Wolverine supports static `HandleAsync` methods on error types for specific exception handling.

```csharp
namespace PropertyService.Application.CompanySearch.Commands.CreateCompanySearch;

/// <summary>
/// Handles failures for CreateCompanySearchCommand.
/// </summary>
public static class CreateCompanySearchFallback
{
    public static async Task HandleAsync(
        CreateCompanySearchCommand command,
        Exception exception,
        IUnitOfWork unitOfWork,
        ILogger logger)
    {
        logger.LogError(exception,
            "CreateCompanySearch failed for matter {MatterId}. Recording error.",
            command.MatterId);

        await unitOfWork.CompanySearchRepository.UpdateStatusAsync(
            command.MatterId.ToString(),
            OrderStatus.Failed,
            exception.Message);
    }
}
```

## Transactional Outbox with Azure Service Bus

For reliable messaging between services, enable the Wolverine transactional outbox with Azure Service Bus. Messages are persisted in the database and delivered after the transaction commits.

### Program.cs Configuration

```csharp
builder.Host.UseWolverine(opts =>
{
    // Azure Service Bus transport
    opts.UseAzureServiceBus(builder.Configuration.GetConnectionString("AzureServiceBus")!)
        .AutoProvision();

    // Enable the transactional outbox
    opts.Policies.UseDurableOutboxOnAllSendingEndpoints();

    // Configure specific endpoints
    opts.PublishMessage<CompanySearchCompletedEvent>()
        .ToAzureServiceBusTopic("company-search-completed");

    opts.ListenToAzureServiceBusQueue("property-service-commands");
});
```

### Wolverine Endpoint Configuration

```csharp
builder.Host.UseWolverine(opts =>
{
    // Local queue for in-process commands (fire-and-forget within the service)
    opts.LocalQueue("polling")
        .MaximumParallelMessages(5)
        .UseDurableInbox();

    // Route polling commands to the local queue
    opts.PublishMessage<PollCompanySearchCommand>()
        .ToLocalQueue("polling");

    // Route cross-service events to Azure Service Bus
    opts.PublishMessage<CompanySearchCompletedEvent>()
        .ToAzureServiceBusTopic("company-search-completed");

    // Listen for inbound commands from other services
    opts.ListenToAzureServiceBusQueue("property-service-commands")
        .MaximumParallelMessages(10);
});
```

## Idempotency Requirements

All handlers that process messages from the bus must be idempotent. Repeated delivery of the same message must not produce duplicate side effects.

### Idempotency Strategies

1. **ON CONFLICT DO NOTHING** -- Use PostgreSQL upsert to silently skip duplicate inserts.
2. **Check-then-act** -- Query current state before performing the operation.
3. **Idempotency key** -- Include a unique key in the command and check it before processing.

```csharp
public async Task HandleAsync(
    PollCompanySearchCommand command,
    CancellationToken cancellationToken = default)
{
    // Check current state -- if already completed, skip
    var existing = await unitOfWork.CompanySearchRepository
        .GetByMatterAndOrderIdAsync(command.MatterId, command.OrderId, cancellationToken);

    if (existing?.OrderStatus is OrderStatus.Completed or OrderStatus.Failed)
    {
        logger.LogInformation("Order {OrderId} already in terminal state, skipping", command.OrderId);
        return;
    }

    // Proceed with the operation...
}
```

## Handler Discovery and Conventions

Wolverine discovers handlers automatically. Follow these conventions:

- Handler class must be `public` (or `public sealed`).
- Handler method must be named `HandleAsync` (or `Handle` for synchronous).
- First parameter is the message type (command or query).
- Return type is `Task<T>` for request/response, `Task` for fire-and-forget.
- Remaining parameters are injected by Wolverine's IoC container.
- Handler class lives in the same namespace as the command/query it handles.

```
Application/
  CompanySearch/
    Commands/
      CreateCompanySearch/
        CreateCompanySearchCommand.cs      <-- message
        CreateCompanySearchHandler.cs      <-- handler (auto-discovered)
        CreateCompanySearchValidator.cs    <-- FluentValidation (auto-discovered)
```

## Cross-References

- **Feature Workflow**: See `/lextech-dotnet:vertical-slice` for the end-to-end feature development process.
- **Data Access**: See `/lextech-dotnet:dapper-postgresql` for repository patterns and Unit of Work lifecycle.
- **Testing**: See `/lextech-dotnet:testing-patterns` for handler unit test patterns and message bus mocking.
