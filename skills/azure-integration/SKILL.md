---
name: azure-integration
description: "Azure service integration patterns including Blob Storage, Redis, Service Bus, Key Vault, SignalR, Entra ID, and App Configuration. Use when integrating with Azure services."
---

# Azure Service Integration Patterns

This skill covers all Azure service integration patterns used in Lextech .NET 10 Clean Architecture microservices. Follow these patterns exactly when integrating with Azure Blob Storage, Redis, Service Bus, Key Vault, SignalR, Entra ID, and App Configuration.

---

## Azure Blob Storage

Use `BlobServiceClient` from `Azure.Storage.Blobs`. Register in DI and inject where needed.

### Registration in Program.cs

```csharp
builder.Services.AddAzureClients(clientBuilder =>
{
    clientBuilder.AddBlobServiceClient(builder.Configuration.GetSection("AzureBlobStorage"));
    clientBuilder.UseCredential(new DefaultAzureCredential());
});
```

### Upload Pattern

```csharp
public sealed class BlobStorageService(BlobServiceClient blobServiceClient, ILogger<BlobStorageService> logger)
    : IBlobStorageService
{
    public async Task<string> UploadDocumentAsync(
        string containerName,
        string blobName,
        Stream content,
        string contentType,
        CancellationToken cancellationToken)
    {
        logger.LogInformation("Uploading blob {BlobName} to container {Container}", blobName, containerName);

        BlobContainerClient container = blobServiceClient.GetBlobContainerClient(containerName);
        await container.CreateIfNotExistsAsync(cancellationToken: cancellationToken);

        BlobClient blob = container.GetBlobClient(blobName);
        BlobHttpHeaders headers = new() { ContentType = contentType };

        await blob.UploadAsync(content, new BlobUploadOptions { HttpHeaders = headers }, cancellationToken);

        logger.LogInformation("Blob {BlobName} uploaded successfully to {Container}", blobName, containerName);
        return blob.Uri.ToString();
    }
}
```

### Download Pattern

```csharp
public async Task<Stream> DownloadDocumentAsync(
    string containerName,
    string blobName,
    CancellationToken cancellationToken)
{
    BlobContainerClient container = blobServiceClient.GetBlobContainerClient(containerName);
    BlobClient blob = container.GetBlobClient(blobName);

    if (!await blob.ExistsAsync(cancellationToken))
    {
        throw new NotFoundException($"Blob '{blobName}' not found in container '{containerName}'");
    }

    BlobDownloadInfo download = await blob.DownloadAsync(cancellationToken);
    return download.Content;
}
```

### Histogram Buckets for Blob Operations

```csharp
private static readonly double[] BlobDurationBuckets = [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30];
```

---

## Azure Managed Redis

Use `IDistributedCache` for simple key-value caching. Use `IConnectionMultiplexer` from StackExchange.Redis for advanced patterns.

### Registration in Program.cs

```csharp
builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = builder.Configuration.GetConnectionString("Redis");
    options.InstanceName = "PropertyService:";
});

// For advanced operations (pub/sub, scripting)
builder.Services.AddSingleton<IConnectionMultiplexer>(sp =>
    ConnectionMultiplexer.Connect(builder.Configuration.GetConnectionString("Redis")!));
```

### IDistributedCache Pattern

```csharp
public sealed class CachedJurisdictionService(
    IJurisdictionService inner,
    IDistributedCache cache,
    ILogger<CachedJurisdictionService> logger) : IJurisdictionService
{
    private static readonly DistributedCacheEntryOptions CacheOptions = new()
    {
        AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(30),
        SlidingExpiration = TimeSpan.FromMinutes(10)
    };

    public async Task<Jurisdiction?> GetByCodeAsync(string code, CancellationToken cancellationToken)
    {
        string cacheKey = $"jurisdiction:{code}";
        string? cached = await cache.GetStringAsync(cacheKey, cancellationToken);

        if (cached is not null)
        {
            logger.LogDebug("Cache hit for jurisdiction {Code}", code);
            return JsonSerializer.Deserialize<Jurisdiction>(cached);
        }

        logger.LogDebug("Cache miss for jurisdiction {Code}", code);
        Jurisdiction? jurisdiction = await inner.GetByCodeAsync(code, cancellationToken);

        if (jurisdiction is not null)
        {
            await cache.SetStringAsync(
                cacheKey,
                JsonSerializer.Serialize(jurisdiction),
                CacheOptions,
                cancellationToken);
        }

        return jurisdiction;
    }
}
```

### Cache Invalidation

```csharp
public async Task InvalidateJurisdictionCacheAsync(string code, CancellationToken cancellationToken)
{
    string cacheKey = $"jurisdiction:{code}";
    await cache.RemoveAsync(cacheKey, cancellationToken);
    logger.LogInformation("Cache invalidated for jurisdiction {Code}", code);
}
```

---

## Azure Service Bus with Wolverine Transactional Outbox

Wolverine handles Service Bus integration with built-in transactional outbox support.

### Registration in Program.cs

```csharp
builder.Host.UseWolverine(opts =>
{
    opts.UseAzureServiceBusTranport(builder.Configuration.GetConnectionString("AzureServiceBus")!)
        .AutoProvision();

    // Publish events to a topic
    opts.PublishMessage<OrderCompletedEvent>()
        .ToAzureServiceBusTopic("order-events");

    // Listen on a subscription
    opts.ListenToAzureServiceBusSubscription("order-events", "property-service")
        .ProcessInline();

    // Transactional outbox with Postgres
    opts.Durability.Mode = DurabilityMode.Solo;
});
```

### Publishing via IMessageBus

```csharp
public sealed class CompleteOrderCommandHandler(
    IUnitOfWork unitOfWork,
    IMessageBus messageBus,
    ILogger<CompleteOrderCommandHandler> logger)
{
    public async Task<CompleteOrderResult> HandleAsync(
        CompleteOrderCommand command,
        CancellationToken cancellationToken)
    {
        Order order = await unitOfWork.Orders.GetByIdAsync(command.OrderId, cancellationToken)
            ?? throw new NotFoundException($"Order '{command.OrderId}' not found");

        order.Complete();
        await unitOfWork.Orders.UpdateAsync(order, cancellationToken);
        await unitOfWork.CommitAsync(cancellationToken);

        // Published via transactional outbox - guaranteed delivery
        await messageBus.PublishAsync(new OrderCompletedEvent(order.Id, order.CompletedAt));

        logger.LogInformation("Order {OrderId} completed and event published", order.Id);
        return new CompleteOrderResult(order.Id);
    }
}
```

---

## Azure Key Vault Configuration

All secrets and connection strings come from Key Vault. Never hardcode secrets.

### Registration in Program.cs

```csharp
builder.Configuration.AddAzureKeyVault(
    new Uri(builder.Configuration["KeyVault:Url"]!),
    new DefaultAzureCredential());
```

### Connection String Management

Key Vault secret names map to configuration paths using `--` as the section separator:

| Key Vault Secret Name | Configuration Path |
|---|---|
| `ConnectionStrings--Postgres` | `ConnectionStrings:Postgres` |
| `ConnectionStrings--Redis` | `ConnectionStrings:Redis` |
| `ConnectionStrings--AzureServiceBus` | `ConnectionStrings:AzureServiceBus` |
| `ExternalApis--AsicPpsr--ApiKey` | `ExternalApis:AsicPpsr:ApiKey` |

Access in code via standard configuration:

```csharp
string connectionString = builder.Configuration.GetConnectionString("Postgres")!;
```

---

## Azure App Configuration with Feature Flags

### Registration in Program.cs

```csharp
builder.Configuration.AddAzureAppConfiguration(options =>
{
    options.Connect(builder.Configuration.GetConnectionString("AppConfiguration")!)
        .UseFeatureFlags(flagOptions =>
        {
            flagOptions.CacheExpirationInterval = TimeSpan.FromMinutes(5);
        })
        .Select(KeyFilter.Any, LabelFilter.Null)
        .Select(KeyFilter.Any, builder.Environment.EnvironmentName);
});

builder.Services.AddAzureAppConfiguration();
builder.Services.AddFeatureManagement();
```

### Feature Flag Naming Convention

Use the pattern `{Domain}.{Capability}.{Behavior}`:

```
PropertyService.TitleSearch.EnableBatchProcessing
PropertyService.CompanySearch.UseAsicV2Api
PropertyService.Orders.EnableAutoComplete
```

### Usage in Handlers

```csharp
public sealed class TitleSearchCommandHandler(
    IFeatureManager featureManager,
    ILogger<TitleSearchCommandHandler> logger)
{
    public async Task<TitleSearchResult> HandleAsync(
        TitleSearchCommand command,
        CancellationToken cancellationToken)
    {
        if (await featureManager.IsEnabledAsync("PropertyService.TitleSearch.EnableBatchProcessing"))
        {
            logger.LogInformation("Batch processing enabled for title search");
            return await ProcessBatchAsync(command, cancellationToken);
        }

        return await ProcessSingleAsync(command, cancellationToken);
    }
}
```

---

## OAuth2 Client Credentials Handler (Service-to-Service Auth)

### DelegatingHandler Pattern

```csharp
public sealed class OAuth2ClientCredentialsHandler(
    IConfidentialClientApplication msalClient,
    IOptions<OAuth2Options> options,
    ILogger<OAuth2ClientCredentialsHandler> logger) : DelegatingHandler
{
    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        AuthenticationResult authResult = await msalClient
            .AcquireTokenForClient(options.Value.Scopes)
            .ExecuteAsync(cancellationToken);

        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", authResult.AccessToken);

        logger.LogDebug("Attached bearer token to request {RequestUri}", request.RequestUri);
        return await base.SendAsync(request, cancellationToken);
    }
}
```

### Registration with HttpClientFactory

```csharp
builder.Services.AddSingleton<IConfidentialClientApplication>(sp =>
{
    OAuth2Options opts = sp.GetRequiredService<IOptions<OAuth2Options>>().Value;
    return ConfidentialClientApplicationBuilder
        .Create(opts.ClientId)
        .WithClientSecret(opts.ClientSecret)
        .WithAuthority(new Uri(opts.Authority))
        .Build();
});

builder.Services.AddTransient<OAuth2ClientCredentialsHandler>();

builder.Services.AddHttpClient<IAsicPpsrService, AsicPpsrService>(client =>
{
    client.BaseAddress = new Uri(builder.Configuration["ExternalApis:AsicPpsr:BaseUrl"]!);
})
.AddHttpMessageHandler<OAuth2ClientCredentialsHandler>();
```

---

## Azure Entra ID Authentication

### Registration in Program.cs

```csharp
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddMicrosoftIdentityWebApi(builder.Configuration.GetSection("AzureAd"));

builder.Services.AddAuthorizationBuilder()
    .AddPolicy("RequireOrdersRead", policy =>
        policy.RequireClaim("scp", "Orders.Read"))
    .AddPolicy("RequireOrdersWrite", policy =>
        policy.RequireClaim("scp", "Orders.Write"));
```

### Endpoint Authorization

```csharp
app.MapGet("/api/orders/{id}", GetOrderById)
    .RequireAuthorization("RequireOrdersRead")
    .WithName("GetOrderById");

app.MapPost("/api/orders", CreateOrder)
    .RequireAuthorization("RequireOrdersWrite")
    .WithName("CreateOrder");
```

---

## SignalR for Real-Time Event Push

### Hub Definition

```csharp
public sealed class OrderNotificationHub : Hub
{
    public override async Task OnConnectedAsync()
    {
        string? orderId = Context.GetHttpContext()?.Request.Query["orderId"];
        if (orderId is not null)
        {
            await Groups.AddToGroupAsync(Context.ConnectionId, $"order-{orderId}");
        }
        await base.OnConnectedAsync();
    }
}
```

### Registration and Push from Handler

```csharp
// Program.cs
builder.Services.AddSignalR().AddAzureSignalR();
app.MapHub<OrderNotificationHub>("/hubs/orders");

// In a handler or event consumer
public sealed class OrderStatusChangedHandler(
    IHubContext<OrderNotificationHub> hubContext,
    ILogger<OrderStatusChangedHandler> logger)
{
    public async Task HandleAsync(OrderStatusChangedEvent @event, CancellationToken cancellationToken)
    {
        await hubContext.Clients.Group($"order-{@event.OrderId}")
            .SendAsync("OrderStatusChanged", new
            {
                @event.OrderId,
                @event.NewStatus,
                @event.ChangedAt
            }, cancellationToken);

        logger.LogInformation("Pushed status change for order {OrderId} to {Status}",
            @event.OrderId, @event.NewStatus);
    }
}
```

---

## Polly Resilience Patterns for Azure Services

### HttpClient Resilience via Microsoft.Extensions.Http.Resilience

```csharp
builder.Services.AddHttpClient<IAsicPpsrService, AsicPpsrService>(client =>
{
    client.BaseAddress = new Uri(builder.Configuration["ExternalApis:AsicPpsr:BaseUrl"]!);
})
.AddHttpMessageHandler<OAuth2ClientCredentialsHandler>()
.AddResilienceHandler("asic-ppsr", pipeline =>
{
    pipeline.AddRetry(new HttpRetryStrategyOptions
    {
        MaxRetryAttempts = 3,
        Delay = TimeSpan.FromMilliseconds(500),
        BackoffType = DelayBackoffType.Exponential,
        ShouldHandle = new PredicateBuilder<HttpResponseMessage>()
            .HandleResult(r => r.StatusCode == HttpStatusCode.TooManyRequests
                            || r.StatusCode >= HttpStatusCode.InternalServerError)
    });

    pipeline.AddTimeout(TimeSpan.FromSeconds(30));

    pipeline.AddCircuitBreaker(new HttpCircuitBreakerStrategyOptions
    {
        SamplingDuration = TimeSpan.FromSeconds(60),
        FailureRatio = 0.5,
        MinimumThroughput = 10,
        BreakDuration = TimeSpan.FromSeconds(30)
    });
});
```

---

## Health Checks for Azure Dependencies

### Registration in Program.cs

```csharp
builder.Services.AddHealthChecks()
    .AddNpgSql(builder.Configuration.GetConnectionString("Postgres")!, name: "postgres",
        tags: ["ready"])
    .AddRedis(builder.Configuration.GetConnectionString("Redis")!, name: "redis",
        tags: ["ready"])
    .AddAzureBlobStorage(builder.Configuration.GetConnectionString("AzureBlobStorage")!,
        name: "blob-storage", tags: ["ready"])
    .AddAzureServiceBusTopic(builder.Configuration.GetConnectionString("AzureServiceBus")!,
        topicName: "order-events", name: "service-bus", tags: ["ready"]);

app.MapHealthChecks("/healthz/ready", new HealthCheckOptions
{
    Predicate = check => check.Tags.Contains("ready"),
    ResponseWriter = UIResponseWriter.WriteHealthCheckUIResponse
});

app.MapHealthChecks("/healthz/live", new HealthCheckOptions
{
    Predicate = _ => false // Liveness just confirms the app is running
});
```

---

## Checklist for New Azure Integration

1. Connection string stored in Key Vault (never in appsettings.json)
2. `DefaultAzureCredential` used for managed identity in production
3. Polly resilience pipeline configured (retry, timeout, circuit breaker)
4. Health check registered for the new dependency
5. BusinessMetrics histogram added for operation durations
6. Structured logging with operation context (no PII)
7. Feature flag added if the integration needs a kill switch
