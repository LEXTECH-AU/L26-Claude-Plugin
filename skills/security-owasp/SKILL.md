---
name: security-owasp
description: "OWASP Top 10 security patterns, error handling, and compliance for .NET microservices. Use when implementing security controls, error handling, or reviewing code for vulnerabilities."
---

# Security and OWASP Top 10 Patterns

This skill covers OWASP Top 10 security controls, the GlobalExceptionHandler pattern, ProblemDetails error responses, and security compliance for Lextech .NET 10 Clean Architecture microservices.

---

## A01: Broken Access Control

Every endpoint MUST have explicit authorization. Never rely on implicit security.

### RequireAuthorization on All Endpoints

```csharp
// CORRECT - explicit authorization on every endpoint
app.MapGet("/api/orders/{id}", GetOrderById)
    .RequireAuthorization("RequireOrdersRead")
    .WithName("GetOrderById");

app.MapPost("/api/orders", CreateOrder)
    .RequireAuthorization("RequireOrdersWrite")
    .WithName("CreateOrder");

app.MapDelete("/api/orders/{id}", DeleteOrder)
    .RequireAuthorization("RequireOrdersAdmin")
    .WithName("DeleteOrder");

// WRONG - no authorization, endpoint is publicly accessible
app.MapGet("/api/orders/{id}", GetOrderById)
    .WithName("GetOrderById");
```

### Policy-Based Authorization

```csharp
builder.Services.AddAuthorizationBuilder()
    .AddPolicy("RequireOrdersRead", policy =>
        policy.RequireClaim("scp", "Orders.Read"))
    .AddPolicy("RequireOrdersWrite", policy =>
        policy.RequireClaim("scp", "Orders.Write"))
    .AddPolicy("RequireOrdersAdmin", policy =>
        policy.RequireRole("Admin")
              .RequireClaim("scp", "Orders.Admin"));
```

### Resource-Level Authorization

Verify the requesting user has access to the specific resource, not just the endpoint:

```csharp
public async Task<Order> HandleAsync(GetOrderQuery query, CancellationToken cancellationToken)
{
    Order order = await _unitOfWork.Orders.GetByIdAsync(query.OrderId, cancellationToken)
        ?? throw new NotFoundException($"Order '{query.OrderId}' not found");

    // Verify the requesting user owns this order or is an admin
    if (order.OwnerId != query.RequestingUserId && !query.IsAdmin)
    {
        _logger.LogWarning("Access denied: user {UserId} attempted to access order {OrderId}",
            query.RequestingUserId, query.OrderId);
        throw new ForbiddenException("You do not have access to this order");
    }

    return order;
}
```

---

## A03: Injection

### Parameterized Queries ONLY

Always use `DynamicParameters` with Dapper. Never concatenate user input into SQL strings.

```csharp
// CORRECT - parameterized query with DynamicParameters
public async Task<Order?> GetByIdAsync(Guid id, CancellationToken cancellationToken)
{
    string sql = await _sqlFileService.LoadSqlAsync("Orders/GetById.sql");
    DynamicParameters parameters = new();
    parameters.Add("Id", id);
    return await _connection.QuerySingleOrDefaultAsync<Order>(sql, parameters);
}

// WRONG - SQL injection vulnerability via string concatenation
public async Task<Order?> GetByIdAsync(Guid id, CancellationToken cancellationToken)
{
    string sql = $"SELECT * FROM orders WHERE id = '{id}'";  // NEVER DO THIS
    return await _connection.QuerySingleOrDefaultAsync<Order>(sql);
}
```

### SQL File Pattern

SQL lives in `.sql` files loaded by `ISqlFileService`, never inline:

```sql
-- Orders/GetByJurisdiction.sql
SELECT id, customer_name, jurisdiction, status, created_at
FROM orders
WHERE jurisdiction = @Jurisdiction
  AND status = @Status
ORDER BY created_at DESC
LIMIT @PageSize OFFSET @Offset;
```

```csharp
DynamicParameters parameters = new();
parameters.Add("Jurisdiction", query.Jurisdiction);
parameters.Add("Status", query.Status.ToString());
parameters.Add("PageSize", query.PageSize);
parameters.Add("Offset", (query.Page - 1) * query.PageSize);
```

---

## A04: Insecure Design - GlobalExceptionHandler

The `GlobalExceptionHandler` ensures all exceptions produce consistent, safe RFC 9457 ProblemDetails responses. Internal details are never exposed to clients.

### Full GlobalExceptionHandler Implementation

```csharp
public class GlobalExceptionHandler(
    IOptions<GrafanaOptions> grafanaOptions,
    ILogger<GlobalExceptionHandler> logger) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        logger.LogError(exception, "An unhandled exception occurred: {Message}", exception.Message);

        ProblemDetails problemDetails = CreateProblemDetails(httpContext, exception);

        // Include Grafana dashboard link for debugging (uses traceId)
        string? dashboardUrl = grafanaOptions.Value.BuildDashboardUrl(httpContext.TraceIdentifier);
        if (dashboardUrl is not null)
        {
            problemDetails.Extensions["dashboardUrl"] = dashboardUrl;
        }

        // Always include traceId for correlation
        problemDetails.Extensions["traceId"] = httpContext.TraceIdentifier;

        httpContext.Response.StatusCode = problemDetails.Status ?? 500;
        httpContext.Response.ContentType = "application/problem+json";
        await httpContext.Response.WriteAsJsonAsync(problemDetails, cancellationToken);
        return true;
    }

    private static ProblemDetails CreateProblemDetails(HttpContext context, Exception exception) =>
        exception switch
        {
            ValidationException ve => new ProblemDetails
            {
                Status = StatusCodes.Status400BadRequest,
                Title = "Validation Error",
                Detail = ve.Message,
                Instance = context.Request.Path
            },
            NotFoundException nf => new ProblemDetails
            {
                Status = StatusCodes.Status404NotFound,
                Title = "Resource Not Found",
                Detail = nf.Message,
                Instance = context.Request.Path
            },
            ForbiddenException => new ProblemDetails
            {
                Status = StatusCodes.Status403Forbidden,
                Title = "Forbidden",
                Detail = "You do not have permission to access this resource",
                Instance = context.Request.Path
            },
            DomainException de => new ProblemDetails
            {
                Status = StatusCodes.Status400BadRequest,
                Title = "Domain Error",
                Detail = de.Message,
                Instance = context.Request.Path
            },
            HttpRequestException he => new ProblemDetails
            {
                Status = (int)(he.StatusCode ?? HttpStatusCode.BadGateway),
                Title = "Upstream Service Error",
                Detail = "An error occurred communicating with an upstream service",
                Instance = context.Request.Path
            },
            TimeoutRejectedException or TaskCanceledException { InnerException: TimeoutException } =>
                new ProblemDetails
                {
                    Status = StatusCodes.Status504GatewayTimeout,
                    Title = "Gateway Timeout",
                    Detail = "The upstream service did not respond in time",
                    Instance = context.Request.Path
                },
            _ => new ProblemDetails
            {
                Status = StatusCodes.Status500InternalServerError,
                Title = "Internal Server Error",
                Detail = "An unexpected error occurred",  // NEVER expose exception.Message for 500s
                Instance = context.Request.Path
            }
        };
}
```

### Registration in Program.cs

```csharp
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
builder.Services.AddProblemDetails();

// In middleware pipeline (before endpoint routing)
app.UseExceptionHandler();
```

### Key Rules

- 400/404/403 errors: safe to include user-facing detail messages
- 500 errors: NEVER expose `exception.Message` or stack traces to the client
- Always include `traceId` for support team correlation
- Always include `instance` (request path) for context
- Include Grafana dashboard URL for quick debugging access

---

## A05: Security Misconfiguration

### Key Vault for All Secrets

```csharp
// CORRECT - secrets from Key Vault
builder.Configuration.AddAzureKeyVault(
    new Uri(builder.Configuration["KeyVault:Url"]!),
    new DefaultAzureCredential());

string connectionString = builder.Configuration.GetConnectionString("Postgres")!;

// WRONG - hardcoded connection string
string connectionString = "Host=db.example.com;Database=mydb;Username=admin;Password=s3cr3t";

// WRONG - secrets in appsettings.json
"ConnectionStrings": {
    "Postgres": "Host=db.example.com;Password=s3cr3t"  // NEVER DO THIS
}
```

### appsettings.json: Only Non-Secret Configuration

```json
{
  "KeyVault": {
    "Url": "https://my-keyvault.vault.azure.net/"
  },
  "Serilog": {
    "MinimumLevel": "Information"
  },
  "TitleSearch": {
    "MaxConcurrentSearches": 5,
    "TimeoutSeconds": 30
  }
}
```

---

## A06: Vulnerable and Outdated Components

### NuGet Audit Rules

The solution uses `Directory.Packages.props` for centralized package management. Follow these rules:

```xml
<!-- Directory.Packages.props -->
<Project>
  <PropertyGroup>
    <ManagePackageVersionsCentrally>true</ManagePackageVersionsCentrally>
    <NuGetAuditMode>all</NuGetAuditMode>
    <NuGetAudit>true</NuGetAudit>
    <!-- Fail build on known vulnerabilities -->
    <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  </PropertyGroup>

  <ItemGroup>
    <PackageVersion Include="Dapper" Version="2.1.35" />
    <PackageVersion Include="Npgsql" Version="9.0.3" />
    <!-- etc. -->
  </ItemGroup>
</Project>
```

### Package Rules

- No preview or RC packages in production
- No LGPL-licensed packages (incompatible with proprietary code)
- All package versions managed in `Directory.Packages.props` (never in individual .csproj files)
- Run `dotnet list package --vulnerable` regularly
- Enable NuGet audit in CI pipeline

---

## A07: Identification and Authentication Failures

### Azure Entra ID + MSAL

```csharp
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddMicrosoftIdentityWebApi(builder.Configuration.GetSection("AzureAd"));
```

### Token Validation

```json
{
  "AzureAd": {
    "Instance": "https://login.microsoftonline.com/",
    "TenantId": "your-tenant-id",
    "ClientId": "your-client-id",
    "Audience": "api://your-api-id"
  }
}
```

### HttpOnly Secure Cookies (if applicable)

```csharp
builder.Services.ConfigureApplicationCookie(options =>
{
    options.Cookie.HttpOnly = true;
    options.Cookie.SecurePolicy = CookieSecurePolicy.Always;
    options.Cookie.SameSite = SameSiteMode.Strict;
    options.ExpireTimeSpan = TimeSpan.FromMinutes(30);
    options.SlidingExpiration = true;
});
```

---

## A08: Software and Data Integrity Failures

### GitHub Actions CI Checks

Every PR must pass:

1. `dotnet build` with TreatWarningsAsErrors
2. `dotnet test` with all tests passing
3. `dotnet list package --vulnerable` with zero vulnerabilities
4. NuGet audit via `NuGetAuditMode=all`
5. Static analysis / linting checks

### Signed Packages

Only use packages from trusted NuGet feeds. Pin package versions in `Directory.Packages.props`.

---

## A09: Security Logging and Monitoring Failures

### Serilog Structured Logging - No PII

```csharp
// CORRECT - log identifiers only
_logger.LogInformation("User {UserId} created order {OrderId}", userId, orderId);
_logger.LogWarning("Authentication failed for client {ClientId}", clientId);

// WRONG - PII exposure in logs
_logger.LogInformation("User {Email} with SSN {Ssn} logged in", email, ssn);
_logger.LogDebug("Request body: {Body}", JsonSerializer.Serialize(requestWithPasswords));
```

### Security Events to Log

Always log these events at the appropriate level:

| Event | Level | Example |
|---|---|---|
| Successful authentication | Information | `User {UserId} authenticated` |
| Failed authentication | Warning | `Authentication failed for client {ClientId}` |
| Authorization denied | Warning | `Access denied: user {UserId} to order {OrderId}` |
| Input validation failure | Information | `Validation failed for {CommandType}: {Errors}` |
| External service failure | Error | `Upstream service {Service} returned {StatusCode}` |
| Unhandled exception | Error | `Unhandled exception: {Message}` (with exception object) |

---

## A10: Server-Side Request Forgery (SSRF)

### Validate External URLs

Never allow user input to directly control outbound HTTP requests without validation.

```csharp
// CORRECT - use HttpClientFactory with pre-configured base addresses
builder.Services.AddHttpClient<IAsicPpsrService, AsicPpsrService>(client =>
{
    client.BaseAddress = new Uri(builder.Configuration["ExternalApis:AsicPpsr:BaseUrl"]!);
});

// WRONG - user-controlled URL
public async Task<string> FetchDocumentAsync(string url)
{
    HttpResponseMessage response = await _httpClient.GetAsync(url);  // SSRF vulnerability
    return await response.Content.ReadAsStringAsync();
}
```

### URL Allowlist Pattern

If you must accept URLs from external input, validate against an allowlist:

```csharp
public static class UrlValidator
{
    private static readonly HashSet<string> AllowedHosts = new(StringComparer.OrdinalIgnoreCase)
    {
        "api.asic.gov.au",
        "ppsr.gov.au",
        "api.partner-service.com.au"
    };

    public static bool IsAllowedUrl(string url)
    {
        if (!Uri.TryCreate(url, UriKind.Absolute, out Uri? uri))
            return false;

        if (uri.Scheme != "https")
            return false;

        return AllowedHosts.Contains(uri.Host);
    }
}
```

---

## WebhookIpAllowlistMiddleware

For webhook endpoints that receive callbacks from known external services, validate the source IP.

```csharp
public sealed class WebhookIpAllowlistMiddleware(
    RequestDelegate next,
    IOptions<WebhookOptions> options,
    ILogger<WebhookIpAllowlistMiddleware> logger)
{
    private readonly HashSet<IPAddress> _allowedIps = options.Value.AllowedIps
        .Select(IPAddress.Parse)
        .ToHashSet();

    public async Task InvokeAsync(HttpContext context)
    {
        if (context.Request.Path.StartsWithSegments("/api/webhooks"))
        {
            IPAddress? remoteIp = context.Connection.RemoteIpAddress;

            if (remoteIp is null || !_allowedIps.Contains(remoteIp))
            {
                logger.LogWarning(
                    "Webhook request rejected from IP {RemoteIp} to {Path}",
                    remoteIp, context.Request.Path);

                context.Response.StatusCode = StatusCodes.Status403Forbidden;
                await context.Response.WriteAsJsonAsync(new ProblemDetails
                {
                    Status = 403,
                    Title = "Forbidden",
                    Detail = "Source IP is not in the allowlist"
                });
                return;
            }

            logger.LogInformation("Webhook request accepted from IP {RemoteIp}", remoteIp);
        }

        await next(context);
    }
}
```

### Registration

```csharp
// appsettings.json (IPs only, not secrets)
"Webhook": {
    "AllowedIps": ["203.0.113.10", "203.0.113.11"]
}

// Program.cs - register before endpoint routing
app.UseMiddleware<WebhookIpAllowlistMiddleware>();
```

---

## ProblemDetails RFC 9457 Error Response Format

All error responses MUST use the `application/problem+json` content type and follow RFC 9457:

```json
{
    "type": "https://tools.ietf.org/html/rfc9110#section-15.5.1",
    "title": "Validation Error",
    "status": 400,
    "detail": "The 'Jurisdiction' field must be between 2 and 3 characters.",
    "instance": "/api/orders",
    "traceId": "00-abc123def456-789ghi-01",
    "dashboardUrl": "https://grafana.lextech.com.au/d/abc123?var-traceId=00-abc123def456-789ghi-01"
}
```

### Required Fields

| Field | Description |
|---|---|
| `status` | HTTP status code (integer) |
| `title` | Short, human-readable summary (same for all instances of this error type) |
| `detail` | Human-readable explanation specific to this occurrence |
| `instance` | URI reference identifying the specific occurrence (request path) |
| `traceId` | OpenTelemetry trace ID for correlation |

### Optional Fields

| Field | Description |
|---|---|
| `dashboardUrl` | Grafana dashboard URL pre-filtered to this trace |
| `errors` | Validation error dictionary (for 400 responses) |

---

## Security Review Checklist for New Integrations

Use this checklist when adding a new external service integration or endpoint:

### Authentication and Authorization
- [ ] All endpoints have `RequireAuthorization()` with appropriate policy
- [ ] Resource-level authorization verified (user owns the resource)
- [ ] Service-to-service auth uses OAuth2 client credentials via `OAuth2ClientCredentialsHandler`
- [ ] Tokens stored in Key Vault, never in code or appsettings

### Input Validation
- [ ] All user input validated by FluentValidation before reaching handler
- [ ] SQL queries use `DynamicParameters` exclusively (no string concatenation)
- [ ] External URLs validated against allowlist if user-provided
- [ ] File uploads validated for type, size, and content

### Error Handling
- [ ] `GlobalExceptionHandler` handles all exception types from new integration
- [ ] 500 errors never expose internal details (exception messages, stack traces)
- [ ] ProblemDetails includes `traceId` for correlation
- [ ] Error logging includes exception object as first parameter

### Secrets and Configuration
- [ ] All secrets stored in Azure Key Vault
- [ ] No connection strings or API keys in appsettings.json
- [ ] `DefaultAzureCredential` used for Azure service authentication
- [ ] Feature flag added for kill-switch capability

### Logging and Monitoring
- [ ] Structured logging with message templates (no string interpolation)
- [ ] No PII in log messages or metric tags
- [ ] Security events logged (auth failures, access denied, validation errors)
- [ ] BusinessMetrics updated with counters/histograms for new operations

### Network Security
- [ ] External HTTP calls go through `HttpClientFactory` with resilience pipeline
- [ ] Webhook endpoints protected by IP allowlist middleware
- [ ] All external communication over HTTPS
- [ ] Circuit breaker configured to prevent cascade failures

### Dependencies
- [ ] No preview/RC NuGet packages
- [ ] No LGPL-licensed packages
- [ ] Package versions pinned in `Directory.Packages.props`
- [ ] `dotnet list package --vulnerable` returns zero findings
