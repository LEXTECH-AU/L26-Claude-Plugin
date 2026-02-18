---
name: testing-patterns
description: "xUnit, Moq, integration testing, and K6 load testing patterns. Use when writing unit tests, integration tests, or load test scenarios."
---

# Testing Patterns

This skill covers xUnit unit testing with Moq, integration testing with Postgres test containers, and K6 load testing patterns for Lextech .NET 10 Clean Architecture microservices.

---

## Handler Unit Test Pattern

Every CQRS handler gets a corresponding test class. Follow this structure exactly.

### Full Handler Test Example

```csharp
public class CreateCompanySearchCommandHandlerTests
{
    private readonly Mock<IUnitOfWork> _unitOfWorkMock;
    private readonly Mock<ICompanySearchRepository> _companySearchRepoMock;
    private readonly Mock<IAsicPpsrService> _asicPpsrServiceMock;
    private readonly Mock<IMessageBus> _messageBusMock;
    private readonly Mock<IBusinessMetrics> _businessMetricsMock;
    private readonly Mock<ILogger<CreateCompanySearchCommandHandler>> _loggerMock;
    private readonly CreateCompanySearchCommandHandler _handler;

    public CreateCompanySearchCommandHandlerTests()
    {
        _unitOfWorkMock = new Mock<IUnitOfWork>();
        _companySearchRepoMock = new Mock<ICompanySearchRepository>();
        _asicPpsrServiceMock = new Mock<IAsicPpsrService>();
        _messageBusMock = new Mock<IMessageBus>();
        _businessMetricsMock = new Mock<IBusinessMetrics>();
        _loggerMock = new Mock<ILogger<CreateCompanySearchCommandHandler>>();

        // Wire up nested repository via IUnitOfWork
        _unitOfWorkMock.Setup(u => u.CompanySearches).Returns(_companySearchRepoMock.Object);

        _handler = new CreateCompanySearchCommandHandler(
            _unitOfWorkMock.Object,
            _asicPpsrServiceMock.Object,
            _messageBusMock.Object,
            _businessMetricsMock.Object,
            _loggerMock.Object);
    }

    [Fact]
    public async Task HandleAsync_WithValidCommand_ReturnsSuccessResponse()
    {
        // Arrange
        CreateCompanySearchCommand command = CreateValidCommand();
        AsicPpsrResult searchResult = CreateSearchResult();

        _asicPpsrServiceMock
            .Setup(x => x.GetAsicPlusPpsrReportAsync(
                command.CompanyName,
                command.Acn,
                It.IsAny<CancellationToken>()))
            .ReturnsAsync(searchResult);

        _companySearchRepoMock
            .Setup(x => x.InsertAsync(It.IsAny<CompanySearch>(), It.IsAny<CancellationToken>()))
            .Returns(Task.CompletedTask);

        _unitOfWorkMock
            .Setup(x => x.CommitAsync(It.IsAny<CancellationToken>()))
            .Returns(Task.CompletedTask);

        // Act
        CreateCompanySearchResult result = await _handler.HandleAsync(command, CancellationToken.None);

        // Assert
        Assert.NotNull(result);
        Assert.Equal(command.CompanyName, result.CompanyName);
        _unitOfWorkMock.Verify(x => x.CommitAsync(It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task HandleAsync_WhenExternalServiceFails_ThrowsAndDoesNotCommit()
    {
        // Arrange
        CreateCompanySearchCommand command = CreateValidCommand();

        _asicPpsrServiceMock
            .Setup(x => x.GetAsicPlusPpsrReportAsync(
                It.IsAny<string>(),
                It.IsAny<string>(),
                It.IsAny<CancellationToken>()))
            .ThrowsAsync(new HttpRequestException("Service unavailable"));

        // Act & Assert
        await Assert.ThrowsAsync<HttpRequestException>(
            () => _handler.HandleAsync(command, CancellationToken.None));

        _unitOfWorkMock.Verify(x => x.CommitAsync(It.IsAny<CancellationToken>()), Times.Never);
    }

    [Fact]
    public async Task HandleAsync_PublishesEventAfterCommit()
    {
        // Arrange
        CreateCompanySearchCommand command = CreateValidCommand();
        _asicPpsrServiceMock
            .Setup(x => x.GetAsicPlusPpsrReportAsync(
                It.IsAny<string>(), It.IsAny<string>(), It.IsAny<CancellationToken>()))
            .ReturnsAsync(CreateSearchResult());

        CompanySearchCreatedEvent? capturedEvent = null;
        _messageBusMock
            .Setup(x => x.PublishAsync(It.IsAny<CompanySearchCreatedEvent>()))
            .Callback<CompanySearchCreatedEvent>(e => capturedEvent = e)
            .Returns(ValueTask.CompletedTask);

        // Act
        await _handler.HandleAsync(command, CancellationToken.None);

        // Assert
        Assert.NotNull(capturedEvent);
        Assert.Equal(command.CompanyName, capturedEvent!.CompanyName);
        _messageBusMock.Verify(x => x.PublishAsync(It.IsAny<CompanySearchCreatedEvent>()), Times.Once);
    }

    // Helper methods at bottom of class
    private static CreateCompanySearchCommand CreateValidCommand() => new(
        CompanyName: "Acme Pty Ltd",
        Acn: "123456789",
        OrderId: Guid.NewGuid(),
        RequestedBy: "user@lextech.com.au");

    private static AsicPpsrResult CreateSearchResult() => new(
        CompanyName: "Acme Pty Ltd",
        Acn: "123456789",
        Status: "Registered",
        PpsrEntries: []);
}
```

---

## Mock Patterns

### Mock IUnitOfWork with Nested Repositories

```csharp
_unitOfWorkMock = new Mock<IUnitOfWork>();
_orderRepoMock = new Mock<IOrderRepository>();
_titleSearchRepoMock = new Mock<ITitleSearchRepository>();

_unitOfWorkMock.Setup(u => u.Orders).Returns(_orderRepoMock.Object);
_unitOfWorkMock.Setup(u => u.TitleSearches).Returns(_titleSearchRepoMock.Object);
```

### Mock IMessageBus with Callback Capture

Use `Callback` to capture the published event for detailed assertion:

```csharp
OrderCompletedEvent? capturedEvent = null;
_messageBusMock
    .Setup(x => x.PublishAsync(It.IsAny<OrderCompletedEvent>()))
    .Callback<OrderCompletedEvent>(e => capturedEvent = e)
    .Returns(ValueTask.CompletedTask);

// After Act
Assert.NotNull(capturedEvent);
Assert.Equal(expectedOrderId, capturedEvent!.OrderId);
```

### Mock ILogger<T>

Logger mocks are typically created but not verified. Only verify logging if it is a business requirement:

```csharp
_loggerMock = new Mock<ILogger<CreateOrderCommandHandler>>();
```

### Mock IOptions<T>

```csharp
TitleSearchOptions options = new()
{
    MaxConcurrentSearches = 5,
    TimeoutSeconds = 30,
    DefaultJurisdiction = "NSW"
};
Mock<IOptions<TitleSearchOptions>> optionsMock = new();
optionsMock.Setup(o => o.Value).Returns(options);
```

### Mock Repository Returning Specific Entity

```csharp
Order existingOrder = new()
{
    Id = Guid.NewGuid(),
    Status = OrderStatus.InProgress,
    CreatedAt = DateTime.UtcNow
};

_orderRepoMock
    .Setup(r => r.GetByIdAsync(existingOrder.Id, It.IsAny<CancellationToken>()))
    .ReturnsAsync(existingOrder);

// For not-found scenario
_orderRepoMock
    .Setup(r => r.GetByIdAsync(It.IsAny<Guid>(), It.IsAny<CancellationToken>()))
    .ReturnsAsync((Order?)null);
```

---

## Validator Boundary Test Pattern

Test every validation rule with boundary values, null, empty, and whitespace.

```csharp
public class CreateOrderCommandValidatorTests
{
    private readonly CreateOrderCommandValidator _validator = new();

    [Fact]
    public void Validate_WithValidCommand_ReturnsNoErrors()
    {
        // Arrange
        CreateOrderCommand command = new(
            CustomerName: "John Smith",
            Jurisdiction: "NSW",
            PropertyAddress: "123 Main St, Sydney NSW 2000");

        // Act
        ValidationResult result = _validator.Validate(command);

        // Assert
        Assert.True(result.IsValid);
        Assert.Empty(result.Errors);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void Validate_WithInvalidCustomerName_ReturnsError(string? customerName)
    {
        CreateOrderCommand command = new(
            CustomerName: customerName!,
            Jurisdiction: "NSW",
            PropertyAddress: "123 Main St");

        ValidationResult result = _validator.Validate(command);

        Assert.False(result.IsValid);
        Assert.Contains(result.Errors, e => e.PropertyName == "CustomerName");
    }

    [Theory]
    [InlineData("X")]       // Too short
    [InlineData("AB")]      // Too short
    public void Validate_WithJurisdictionTooShort_ReturnsError(string jurisdiction)
    {
        CreateOrderCommand command = new(
            CustomerName: "John Smith",
            Jurisdiction: jurisdiction,
            PropertyAddress: "123 Main St");

        ValidationResult result = _validator.Validate(command);

        Assert.False(result.IsValid);
        Assert.Contains(result.Errors, e => e.PropertyName == "Jurisdiction");
    }

    [Theory]
    [InlineData("NSW")]
    [InlineData("VIC")]
    [InlineData("QLD")]
    public void Validate_WithValidJurisdiction_ReturnsNoErrors(string jurisdiction)
    {
        CreateOrderCommand command = new(
            CustomerName: "John Smith",
            Jurisdiction: jurisdiction,
            PropertyAddress: "123 Main St");

        ValidationResult result = _validator.Validate(command);

        Assert.True(result.IsValid);
    }
}
```

---

## Repository Test with Mock ISqlFileService

Verify that the repository loads the correct SQL file and binds parameters correctly.

```csharp
public class OrderRepositoryTests
{
    private readonly Mock<IDbConnection> _connectionMock;
    private readonly Mock<ISqlFileService> _sqlFileServiceMock;
    private readonly OrderRepository _repository;

    public OrderRepositoryTests()
    {
        _connectionMock = new Mock<IDbConnection>();
        _sqlFileServiceMock = new Mock<ISqlFileService>();
        _repository = new OrderRepository(_connectionMock.Object, _sqlFileServiceMock.Object);
    }

    [Fact]
    public async Task GetByIdAsync_LoadsCorrectSqlFile()
    {
        // Arrange
        Guid orderId = Guid.NewGuid();
        string expectedSql = "SELECT * FROM orders WHERE id = @Id";

        _sqlFileServiceMock
            .Setup(s => s.LoadSqlAsync("Orders/GetById.sql"))
            .ReturnsAsync(expectedSql);

        // Act
        await _repository.GetByIdAsync(orderId, CancellationToken.None);

        // Assert
        _sqlFileServiceMock.Verify(
            s => s.LoadSqlAsync("Orders/GetById.sql"),
            Times.Once);
    }

    [Fact]
    public async Task InsertAsync_BindsParametersCorrectly()
    {
        // Arrange
        Order order = new()
        {
            Id = Guid.NewGuid(),
            CustomerName = "Test Customer",
            Jurisdiction = "NSW",
            Status = OrderStatus.Created
        };

        DynamicParameters? capturedParams = null;

        _sqlFileServiceMock
            .Setup(s => s.LoadSqlAsync("Orders/Insert.sql"))
            .ReturnsAsync("INSERT INTO orders ...");

        // Use callback to capture the DynamicParameters
        _connectionMock
            .Setup(c => c.ExecuteAsync(
                It.IsAny<string>(),
                It.IsAny<DynamicParameters>(),
                It.IsAny<IDbTransaction>(),
                It.IsAny<int?>(),
                It.IsAny<CommandType?>()))
            .Callback<string, object?, IDbTransaction?, int?, CommandType?>(
                (sql, param, txn, timeout, type) => capturedParams = param as DynamicParameters)
            .ReturnsAsync(1);

        // Act
        await _repository.InsertAsync(order, CancellationToken.None);

        // Assert
        Assert.NotNull(capturedParams);
        Assert.Equal(order.Id, capturedParams!.Get<Guid>("Id"));
        Assert.Equal(order.CustomerName, capturedParams.Get<string>("CustomerName"));
    }
}
```

---

## Integration Test with Postgres Test Container

Use `Testcontainers.PostgreSql` for real database integration tests with transaction rollback.

### PostgresContainerFixture

```csharp
public sealed class PostgresContainerFixture : IAsyncLifetime
{
    private readonly PostgreSqlContainer _container = new PostgreSqlBuilder()
        .WithImage("postgres:16-alpine")
        .WithDatabase("testdb")
        .WithUsername("test")
        .WithPassword("test")
        .Build();

    public string ConnectionString => _container.GetConnectionString();

    public async Task InitializeAsync()
    {
        await _container.StartAsync();

        // Run migrations
        await using NpgsqlConnection connection = new(ConnectionString);
        await connection.OpenAsync();

        string migrationSql = await File.ReadAllTextAsync("Migrations/001_initial.sql");
        await using NpgsqlCommand cmd = new(migrationSql, connection);
        await cmd.ExecuteNonQueryAsync();
    }

    public async Task DisposeAsync()
    {
        await _container.DisposeAsync();
    }
}
```

### Integration Test Class

```csharp
public class OrderRepositoryIntegrationTests : IClassFixture<PostgresContainerFixture>, IAsyncLifetime
{
    private readonly PostgresContainerFixture _fixture;
    private NpgsqlConnection _connection = null!;
    private NpgsqlTransaction _transaction = null!;

    public OrderRepositoryIntegrationTests(PostgresContainerFixture fixture)
    {
        _fixture = fixture;
    }

    public async Task InitializeAsync()
    {
        _connection = new NpgsqlConnection(_fixture.ConnectionString);
        await _connection.OpenAsync();
        _transaction = await _connection.BeginTransactionAsync();
    }

    public async Task DisposeAsync()
    {
        // Rollback ensures test isolation - no data persists between tests
        await _transaction.RollbackAsync();
        await _connection.DisposeAsync();
    }

    [Fact]
    public async Task InsertAndGetById_RoundTripsCorrectly()
    {
        // Arrange
        SqlFileService sqlFileService = new();
        OrderRepository repository = new(_connection, sqlFileService, _transaction);

        Order order = new()
        {
            Id = Guid.NewGuid(),
            CustomerName = "Integration Test Customer",
            Jurisdiction = "VIC",
            Status = OrderStatus.Created,
            CreatedAt = DateTime.UtcNow
        };

        // Act
        await repository.InsertAsync(order, CancellationToken.None);
        Order? retrieved = await repository.GetByIdAsync(order.Id, CancellationToken.None);

        // Assert
        Assert.NotNull(retrieved);
        Assert.Equal(order.Id, retrieved!.Id);
        Assert.Equal(order.CustomerName, retrieved.CustomerName);
        Assert.Equal(order.Jurisdiction, retrieved.Jurisdiction);
    }

    [Fact]
    public async Task GetByIdAsync_WithNonExistentId_ReturnsNull()
    {
        // Arrange
        SqlFileService sqlFileService = new();
        OrderRepository repository = new(_connection, sqlFileService, _transaction);

        // Act
        Order? result = await repository.GetByIdAsync(Guid.NewGuid(), CancellationToken.None);

        // Assert
        Assert.Null(result);
    }
}
```

---

## K6 Load Test Scenario Template

K6 scripts live in a `tests/load/` directory. Follow this template for all load test scenarios.

### Basic Load Test

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const searchDuration = new Trend('search_duration', true);

export const options = {
    stages: [
        { duration: '30s', target: 10 },   // Ramp up to 10 VUs
        { duration: '2m',  target: 10 },   // Sustain 10 VUs
        { duration: '1m',  target: 50 },   // Ramp up to 50 VUs
        { duration: '3m',  target: 50 },   // Sustain 50 VUs
        { duration: '30s', target: 0 },    // Ramp down
    ],
    thresholds: {
        http_req_duration: ['p(95)<500', 'p(99)<1000'],  // P95 < 500ms, P99 < 1s
        errors: ['rate<0.01'],                             // Error rate < 1%
        search_duration: ['p(95)<800'],                    // Custom metric threshold
    },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:5000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';

const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${AUTH_TOKEN}`,
};

export default function () {
    // Scenario: Create a title search
    const payload = JSON.stringify({
        jurisdiction: 'NSW',
        propertyAddress: '123 Main St, Sydney NSW 2000',
        searchType: 'Standard',
    });

    const startTime = Date.now();
    const res = http.post(`${BASE_URL}/api/title-searches`, payload, { headers });
    const duration = Date.now() - startTime;

    searchDuration.add(duration);

    const success = check(res, {
        'status is 200 or 201': (r) => r.status === 200 || r.status === 201,
        'response has id': (r) => JSON.parse(r.body).id !== undefined,
        'response time < 1s': (r) => r.timings.duration < 1000,
    });

    errorRate.add(!success);

    sleep(1); // Think time between requests
}

// Lifecycle hooks
export function setup() {
    // Run once before the test - create test data, get tokens, etc.
    const loginRes = http.post(`${BASE_URL}/api/auth/token`, JSON.stringify({
        clientId: __ENV.CLIENT_ID,
        clientSecret: __ENV.CLIENT_SECRET,
    }), { headers: { 'Content-Type': 'application/json' } });

    return { token: JSON.parse(loginRes.body).access_token };
}

export function teardown(data) {
    // Run once after the test - cleanup test data
    console.log('Load test completed');
}
```

### Multi-Scenario Load Test

```javascript
import http from 'k6/http';
import { check, sleep, group } from 'k6';

export const options = {
    scenarios: {
        title_searches: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '1m', target: 20 },
                { duration: '5m', target: 20 },
                { duration: '30s', target: 0 },
            ],
            exec: 'titleSearchScenario',
        },
        order_creation: {
            executor: 'constant-arrival-rate',
            rate: 10,            // 10 requests per timeUnit
            timeUnit: '1s',
            duration: '5m',
            preAllocatedVUs: 20,
            exec: 'orderCreationScenario',
        },
    },
    thresholds: {
        'http_req_duration{scenario:title_searches}': ['p(95)<500'],
        'http_req_duration{scenario:order_creation}': ['p(95)<300'],
    },
};

export function titleSearchScenario() {
    group('Title Search', function () {
        const res = http.get(`${BASE_URL}/api/title-searches?jurisdiction=NSW`);
        check(res, { 'title search 200': (r) => r.status === 200 });
        sleep(0.5);
    });
}

export function orderCreationScenario() {
    group('Order Creation', function () {
        const payload = JSON.stringify({
            customerName: `LoadTest-${Date.now()}`,
            jurisdiction: 'VIC',
        });
        const res = http.post(`${BASE_URL}/api/orders`, payload, {
            headers: { 'Content-Type': 'application/json' },
        });
        check(res, { 'order created 201': (r) => r.status === 201 });
    });
}
```

### Running K6 Tests

```bash
# Local run
k6 run tests/load/title-search.js --env BASE_URL=http://localhost:5000

# With Grafana K6 Cloud output
k6 run tests/load/title-search.js --out cloud

# With specific VU count override
k6 run tests/load/title-search.js --vus 100 --duration 5m
```

---

## Test Naming Conventions

Follow the pattern: `{Method}_{Scenario}_{ExpectedResult}`

```
HandleAsync_WithValidCommand_ReturnsSuccessResponse
HandleAsync_WhenExternalServiceFails_ThrowsHttpRequestException
HandleAsync_WithNullOrderId_ThrowsValidationException
Validate_WithEmptyCustomerName_ReturnsError
GetByIdAsync_WithNonExistentId_ReturnsNull
InsertAsync_WithDuplicateId_ThrowsConflictException
```

---

## Checklist for New Tests

1. Handler test: mock all dependencies, test happy path and failure paths
2. Validator test: test every rule with valid, null, empty, whitespace, and boundary values
3. Repository test: verify SQL file loaded, parameters bound, results mapped
4. Integration test: real database with test container, transaction rollback for isolation
5. K6 test: define stages, thresholds for p95/p99, error rate checks
6. All test methods use Arrange-Act-Assert structure
7. Helper methods (`CreateValidCommand()`, `CreateSearchResult()`) at bottom of class
8. No test should depend on the execution order of other tests
