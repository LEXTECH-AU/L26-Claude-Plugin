---
name: observability
description: "Serilog structured logging, OpenTelemetry Prometheus metrics, and Grafana dashboard patterns. Use when adding logging, metrics, or monitoring."
---

# Observability Patterns

This skill covers Serilog structured logging, OpenTelemetry/Prometheus metrics via BusinessMetrics, and Grafana dashboard patterns for Lextech .NET 10 Clean Architecture microservices.

---

## Serilog Structured Logging Rules

### NEVER Use String Interpolation

This is the single most important rule. Serilog uses message templates for structured logging. String interpolation destroys the structured data.

```csharp
// CORRECT - structured logging with message template
_logger.LogInformation("Order {OrderId} created for customer {CustomerId}", orderId, customerId);

// WRONG - string interpolation loses structure, produces unqueryable logs
_logger.LogInformation($"Order {orderId} created for customer {customerId}");
```

### Log Levels

| Level | Purpose | Example |
|---|---|---|
| `Debug` | Development details, diagnostic data | `LogDebug("Cache hit for key {CacheKey}", key)` |
| `Information` | Business flow, state transitions | `LogInformation("Order {OrderId} completed", id)` |
| `Warning` | Recoverable issues, degraded operation | `LogWarning("Retry {Attempt} for {Service}", attempt, svc)` |
| `Error` | Failures requiring attention | `LogError(ex, "Failed to process order {OrderId}", id)` |

### Always Include Exception Objects

When logging errors, pass the exception as the first argument so Serilog captures the full stack trace:

```csharp
// CORRECT - exception is first argument
_logger.LogError(exception, "Failed to process order {OrderId}", orderId);

// WRONG - exception details lost
_logger.LogError("Failed to process order {OrderId}: {Message}", orderId, exception.Message);
```

### Correlation IDs via LogContext

Use `LogContext.PushProperty` to add correlation context that applies to all log entries within a scope:

```csharp
public async Task<TitleSearchResult> HandleAsync(
    TitleSearchCommand command,
    CancellationToken cancellationToken)
{
    using (LogContext.PushProperty("OrderId", command.OrderId))
    using (LogContext.PushProperty("Jurisdiction", command.Jurisdiction))
    {
        _logger.LogInformation("Starting title search");

        TitleSearchResult result = await _titleSearchService.SearchAsync(command, cancellationToken);

        _logger.LogInformation("Title search completed with {ResultCount} results", result.Count);
        return result;
    }
}
```

### Log Scopes for Related Operations

```csharp
using (_logger.BeginScope(new Dictionary<string, object>
{
    ["OperationType"] = "TitleSearch",
    ["BatchId"] = batchId
}))
{
    _logger.LogInformation("Processing batch of {Count} searches", commands.Count);
    // All log entries within this block include OperationType and BatchId
}
```

### PII Sanitization

Never log sensitive data. Mask or omit passwords, tokens, personal data, and financial information.

```csharp
// CORRECT - log only identifiers, not personal data
_logger.LogInformation("User {UserId} authenticated successfully", user.Id);

// WRONG - PII exposure
_logger.LogInformation("User {Email} logged in with token {Token}", user.Email, token);

// CORRECT - mask partial data if context is needed
_logger.LogDebug("Processing card ending in {CardLast4}", cardNumber[^4..]);
```

---

## Serilog Registration in Program.cs

```csharp
builder.Host.UseSerilog((context, services, configuration) =>
{
    configuration
        .ReadFrom.Configuration(context.Configuration)
        .ReadFrom.Services(services)
        .Enrich.FromLogContext()
        .Enrich.WithMachineName()
        .Enrich.WithEnvironmentName()
        .Enrich.WithProperty("ServiceName", "PropertyService")
        .WriteTo.Console(new RenderedCompactJsonFormatter())
        .WriteTo.GrafanaLoki(
            context.Configuration["Loki:Url"]!,
            labels: new[] { new LokiLabel { Key = "service", Value = "property-service" } });
});

// Request logging middleware (add after routing, before endpoints)
app.UseSerilogRequestLogging(options =>
{
    options.EnrichDiagnosticContext = (diagnosticContext, httpContext) =>
    {
        diagnosticContext.Set("RequestHost", httpContext.Request.Host.Value);
        diagnosticContext.Set("UserAgent", httpContext.Request.Headers.UserAgent.ToString());
    };
});
```

---

## BusinessMetrics Pattern (OpenTelemetry Prometheus)

Every service has a `BusinessMetrics.cs` in the Infrastructure layer that implements `IBusinessMetrics`.

### Naming Conventions

- Meter name: `{ServiceName}.Business` (e.g., `PropertyService.Business`)
- Metric name: `{service}.{domain}.{metric}_{unit}` (e.g., `propertyservice.titlesearch.requests_total`)
- Units follow OpenTelemetry conventions: `{request}`, `s` (seconds), `By` (bytes), `{item}`

### Instrument Types

| Type | Use Case | Example |
|---|---|---|
| `Counter<long>` | Monotonically increasing totals | Request counts, error counts |
| `Histogram<double>` | Duration/size distributions | Response time, payload size |
| `UpDownCounter<long>` | Values that go up and down | Active connections, queue depth |

### Full BusinessMetrics Implementation

```csharp
public sealed class BusinessMetrics : IBusinessMetrics
{
    public const string MeterName = "PropertyService.Business";

    private static readonly double[] HttpDurationBuckets =
        [0, 0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1, 2.5, 5, 7.5, 10];

    private static readonly double[] DbDurationBuckets =
        [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1];

    private static readonly double[] BlobDurationBuckets =
        [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30];

    private readonly Meter _meter;

    // Counters
    private readonly Counter<long> _titleSearchRequestsTotal;
    private readonly Counter<long> _companySearchRequestsTotal;
    private readonly Counter<long> _orderCreatedTotal;

    // Histograms
    private readonly Histogram<double> _titleSearchDurationSeconds;
    private readonly Histogram<double> _dbQueryDurationSeconds;
    private readonly Histogram<double> _externalApiDurationSeconds;
    private readonly Histogram<double> _blobOperationDurationSeconds;

    // Gauges
    private readonly UpDownCounter<long> _activeOrders;

    public BusinessMetrics()
    {
        _meter = new Meter(MeterName, "1.0.0");

        _titleSearchRequestsTotal = _meter.CreateCounter<long>(
            name: "propertyservice.titlesearch.requests_total",
            unit: "{request}",
            description: "Total number of title search requests");

        _titleSearchDurationSeconds = _meter.CreateHistogram<double>(
            name: "propertyservice.titlesearch.duration_seconds",
            unit: "s",
            description: "Duration of title search operations",
            advice: new InstrumentAdvice<double> { HistogramBucketBoundaries = HttpDurationBuckets });

        _dbQueryDurationSeconds = _meter.CreateHistogram<double>(
            name: "propertyservice.db.query_duration_seconds",
            unit: "s",
            description: "Duration of database queries",
            advice: new InstrumentAdvice<double> { HistogramBucketBoundaries = DbDurationBuckets });

        _externalApiDurationSeconds = _meter.CreateHistogram<double>(
            name: "propertyservice.externalapi.duration_seconds",
            unit: "s",
            description: "Duration of external API calls",
            advice: new InstrumentAdvice<double> { HistogramBucketBoundaries = HttpDurationBuckets });

        _blobOperationDurationSeconds = _meter.CreateHistogram<double>(
            name: "propertyservice.blob.operation_duration_seconds",
            unit: "s",
            description: "Duration of blob storage operations",
            advice: new InstrumentAdvice<double> { HistogramBucketBoundaries = BlobDurationBuckets });

        _activeOrders = _meter.CreateUpDownCounter<long>(
            name: "propertyservice.orders.active",
            unit: "{order}",
            description: "Number of currently active orders");
    }

    public void RecordTitleSearchRequest(string jurisdiction, bool success)
    {
        TagList tags = new()
        {
            { "jurisdiction", jurisdiction ?? "unknown" },
            { "status", success ? "success" : "failure" }
        };
        _titleSearchRequestsTotal.Add(1, tags);
    }

    public void RecordTitleSearchDuration(string jurisdiction, double durationSeconds)
    {
        TagList tags = new() { { "jurisdiction", jurisdiction ?? "unknown" } };
        _titleSearchDurationSeconds.Record(durationSeconds, tags);
    }

    public void RecordDbQueryDuration(string queryName, double durationSeconds)
    {
        TagList tags = new() { { "query", queryName } };
        _dbQueryDurationSeconds.Record(durationSeconds, tags);
    }

    public void RecordExternalApiDuration(string service, string operation, double durationSeconds, bool success)
    {
        TagList tags = new()
        {
            { "service", service },
            { "operation", operation },
            { "status", success ? "success" : "failure" }
        };
        _externalApiDurationSeconds.Record(durationSeconds, tags);
    }

    public void IncrementActiveOrders() => _activeOrders.Add(1);
    public void DecrementActiveOrders() => _activeOrders.Add(-1);
}
```

### Measuring Duration with Stopwatch

```csharp
public async Task<TitleSearchResult> HandleAsync(
    TitleSearchCommand command,
    CancellationToken cancellationToken)
{
    long startTimestamp = Stopwatch.GetTimestamp();
    bool success = false;

    try
    {
        TitleSearchResult result = await _titleSearchService.SearchAsync(command, cancellationToken);
        success = true;
        return result;
    }
    finally
    {
        double elapsed = Stopwatch.GetElapsedTime(startTimestamp).TotalSeconds;
        _businessMetrics.RecordTitleSearchRequest(command.Jurisdiction, success);
        _businessMetrics.RecordTitleSearchDuration(command.Jurisdiction, elapsed);
    }
}
```

---

## OpenTelemetry Registration in Program.cs

```csharp
builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService(
            serviceName: "PropertyService",
            serviceVersion: typeof(Program).Assembly.GetName().Version?.ToString() ?? "0.0.0"))
    .WithMetrics(metrics => metrics
        .AddMeter(BusinessMetrics.MeterName)
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddRuntimeInstrumentation()
        .AddPrometheusExporter())
    .WithTracing(tracing => tracing
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddNpgsql()
        .AddSource("Wolverine")
        .AddOtlpExporter(opts =>
        {
            opts.Endpoint = new Uri(builder.Configuration["Tempo:Endpoint"]!);
        }));

// Expose Prometheus scrape endpoint
app.MapPrometheusScrapingEndpoint();
```

---

## Common PromQL Queries for Grafana Dashboards

### Request Rate (per second)

```promql
rate(propertyservice_titlesearch_requests_total[5m])
```

### Error Rate

```promql
sum(rate(propertyservice_titlesearch_requests_total{status="failure"}[5m]))
/ sum(rate(propertyservice_titlesearch_requests_total[5m]))
```

### P95 Latency

```promql
histogram_quantile(0.95, sum(rate(propertyservice_titlesearch_duration_seconds_bucket[5m])) by (le))
```

### P99 Latency by Jurisdiction

```promql
histogram_quantile(0.99,
    sum(rate(propertyservice_titlesearch_duration_seconds_bucket[5m])) by (le, jurisdiction)
)
```

### Active Orders Gauge

```promql
propertyservice_orders_active
```

### Database Query Duration P95

```promql
histogram_quantile(0.95,
    sum(rate(propertyservice_db_query_duration_seconds_bucket[5m])) by (le, query)
)
```

---

## Common LogQL Queries for Loki

### All Errors for a Service

```logql
{service="property-service"} |= "Error"
```

### Errors with JSON Parsing

```logql
{service="property-service"} | json | level="Error"
```

### Specific Order by Correlation ID

```logql
{service="property-service"} | json | OrderId="ORD-12345"
```

### Slow Requests (parse duration from structured logs)

```logql
{service="property-service"} | json | Elapsed > 5
```

### Error Rate Over Time

```logql
sum(rate({service="property-service"} | json | level="Error" [5m]))
```

---

## Grafana Dashboard Template Structure

A standard service dashboard includes these panels:

1. **Request Rate** - `rate(requests_total[5m])` by status
2. **Error Rate %** - failures / total * 100
3. **P50 / P95 / P99 Latency** - `histogram_quantile` at each percentile
4. **Active Orders** - UpDownCounter gauge
5. **Database Query Duration** - histogram by query name
6. **External API Duration** - histogram by service/operation
7. **Blob Operation Duration** - histogram by operation type
8. **Error Logs** - Loki panel filtered to Error level
9. **Pod Resource Usage** - CPU and memory from Kubernetes metrics

### Dashboard JSON Model (key fields)

```json
{
  "dashboard": {
    "title": "PropertyService - Business Metrics",
    "tags": ["property-service", "business"],
    "panels": [
      {
        "title": "Request Rate",
        "type": "timeseries",
        "targets": [
          {
            "expr": "sum(rate(propertyservice_titlesearch_requests_total[5m])) by (status)",
            "legendFormat": "{{status}}"
          }
        ]
      }
    ]
  }
}
```

---

## Grafana MCP Server for Live Queries

When the Grafana MCP server is available, use it to query live metrics and logs:

- `query_prometheus` - Run PromQL queries against Grafana's Prometheus datasource
- `query_loki_logs` - Run LogQL queries against Grafana's Loki datasource
- `search_dashboards` - Find existing dashboards by name or tag
- `get_dashboard_by_uid` - Retrieve full dashboard configuration
- `list_prometheus_metric_names` - Discover available metrics

Use these tools to validate that new metrics are being scraped correctly after deployment.

---

## Checklist for Adding New Observability

1. Add structured log statements at Information level for business flow
2. Add Error level logging with exception objects for failure paths
3. Add Counter metric for request/event totals with status tag
4. Add Histogram metric for duration with appropriate bucket configuration
5. Use `Stopwatch.GetTimestamp()` / `Stopwatch.GetElapsedTime()` for timing
6. Register new Meter in OpenTelemetry configuration if needed
7. Create or update Grafana dashboard panel for the new metric
8. Verify no PII in log messages or metric tags
9. Add alert rules for error rate thresholds if business-critical
