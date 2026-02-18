---
name: new-test
description: Generate test scaffolds for handlers, validators, or repositories
argument-hint: "[TargetClassName] [handler|validator|repository|integration]"
---

# Generate Test Scaffolds

You are generating test scaffolds for a Lextech .NET 10 Clean Architecture microservice using xUnit and Moq. Follow every instruction below precisely.

## Step 1: Parse Arguments

Parse the arguments provided by the user. Expect two positional arguments:

1. **TargetClassName** -- The fully qualified or short name of the class to test (e.g., `CreateCompanySearchCommandHandler`, `CreateCompanySearchValidator`, `CompanySearchRepository`).
2. **TestType** -- One of: `handler`, `validator`, `repository`, `integration`.

If either argument is missing, ask the user interactively. Confirm both values before proceeding.

## Step 2: Load the Testing Patterns Skill

Read the `testing-patterns` skill to load the test conventions, fixture patterns, and assertion styles. Apply all conventions from that skill.

## Step 3: Locate the Target Class

Search the solution for the target class file:

1. Use glob patterns to find `{TargetClassName}.cs` across all projects.
2. Read the file to understand:
   - Constructor parameters (these become mock dependencies).
   - Public methods (these become test targets).
   - The command/query/entity types used (these need test data builders).
   - The namespace (to determine the correct test project namespace).
3. If the class cannot be found, ask the user for the file path.

## Step 4: Detect the Test Project

Find the test project(s) in the solution:

- Unit tests: `{Service}.Application.Tests` or `{Service}.Tests.Unit`
- Integration tests: `{Service}.Infrastructure.Tests` or `{Service}.Tests.Integration`

If multiple test projects exist, select the appropriate one based on TestType. If no test project exists, warn the user and suggest creating one.

## Step 5: Determine the Test File Path

Follow the convention:

```
{TestProject}/{FeatureName}/{TestType}/{TargetClassName}Tests.cs
```

Mirror the source folder structure in the test project. For example:
- Source: `PropertyService.Application/CompanySearch/Commands/CreateCompanySearch/CreateCompanySearchCommandHandler.cs`
- Test: `PropertyService.Application.Tests/CompanySearch/Commands/CreateCompanySearch/CreateCompanySearchCommandHandlerTests.cs`

## Step 6: Generate Handler Tests

Only generate this section if TestType is `handler`.

Read the target handler class and identify all constructor dependencies. Generate the following test class:

```csharp
namespace {Service}.Application.Tests.{FeatureName}.Commands.{CommandName};

/// <summary>
/// Unit tests for <see cref="{HandlerClassName}"/>.
/// </summary>
public sealed class {HandlerClassName}Tests
{
    private readonly Mock<IUnitOfWork> _unitOfWorkMock;
    private readonly Mock<IMessageBus> _messageBusMock;
    private readonly Mock<ILogger<{HandlerClassName}>> _loggerMock;
    private readonly Mock<I{Entity}Repository> _repositoryMock;
    private readonly {HandlerClassName} _sut;

    public {HandlerClassName}Tests()
    {
        _unitOfWorkMock = new Mock<IUnitOfWork>();
        _messageBusMock = new Mock<IMessageBus>();
        _loggerMock = new Mock<ILogger<{HandlerClassName}>>();
        _repositoryMock = new Mock<I{Entity}Repository>();

        _unitOfWorkMock
            .Setup(u => u.{Entity}Repository)
            .Returns(_repositoryMock.Object);

        _sut = new {HandlerClassName}(
            _unitOfWorkMock.Object,
            _messageBusMock.Object,
            _loggerMock.Object);
    }

    // -- Test Data Builder --

    private static {CommandType} CreateValidCommand()
    {
        return new {CommandType}
        {
            // Populate with valid test data for every property
        };
    }

    // -- Happy Path --

    [Fact]
    public async Task HandleAsync_WithValidCommand_ShouldReturnExpectedResult()
    {
        // Arrange
        {CommandType} command = CreateValidCommand();
        // Setup repository mocks to return expected data

        // Act
        {ResponseType} result = await _sut.HandleAsync(command, CancellationToken.None);

        // Assert
        Assert.NotNull(result);
        // Assert specific property values
    }

    [Fact]
    public async Task HandleAsync_WithValidCommand_ShouldCallSaveChanges()
    {
        // Arrange
        {CommandType} command = CreateValidCommand();

        // Act
        await _sut.HandleAsync(command, CancellationToken.None);

        // Assert
        _unitOfWorkMock.Verify(u => u.CommitTransactionAsync(It.IsAny<CancellationToken>()), Times.Once);
    }

    [Fact]
    public async Task HandleAsync_WithValidCommand_ShouldCallRepository()
    {
        // Arrange
        {CommandType} command = CreateValidCommand();

        // Act
        await _sut.HandleAsync(command, CancellationToken.None);

        // Assert
        _repositoryMock.Verify(
            r => r.CreateAsync(It.IsAny<{EntityType}>(), It.IsAny<CancellationToken>()),
            Times.Once);
    }

    // -- Error Paths --

    [Fact]
    public async Task HandleAsync_WhenRepositoryThrows_ShouldRollbackAndRethrow()
    {
        // Arrange
        {CommandType} command = CreateValidCommand();
        _repositoryMock
            .Setup(r => r.CreateAsync(It.IsAny<{EntityType}>(), It.IsAny<CancellationToken>()))
            .ThrowsAsync(new InvalidOperationException("Database error"));

        // Act & Assert
        await Assert.ThrowsAsync<InvalidOperationException>(
            () => _sut.HandleAsync(command, CancellationToken.None));

        _unitOfWorkMock.Verify(
            u => u.RollbackTransactionAsync(It.IsAny<CancellationToken>()), Times.Once);
    }

    // -- Cancellation --

    [Fact]
    public async Task HandleAsync_WhenCancelled_ShouldThrowOperationCancelled()
    {
        // Arrange
        {CommandType} command = CreateValidCommand();
        CancellationTokenSource cts = new();
        cts.Cancel();

        // Act & Assert
        await Assert.ThrowsAsync<OperationCanceledException>(
            () => _sut.HandleAsync(command, cts.Token));
    }
}
```

### Handler Test Rules

- One `CreateValid{Command}()` helper that returns a fully populated, valid command.
- At minimum generate: happy path test, SaveChanges/CommitTransaction verification, repository call verification, error rollback test, cancellation test.
- For query handlers: test null return (not found) scenario, test successful return.
- Mock setup goes in the constructor, not duplicated in each test.
- Use `_sut` (system under test) for the handler instance.
- Use `CancellationToken.None` in tests unless testing cancellation.

## Step 7: Generate Validator Tests

Only generate this section if TestType is `validator`.

Read the target validator class and identify all validation rules. Generate boundary tests for each rule:

```csharp
namespace {Service}.Application.Tests.{FeatureName}.Commands.{CommandName};

/// <summary>
/// Unit tests for <see cref="{ValidatorClassName}"/>.
/// </summary>
public sealed class {ValidatorClassName}Tests
{
    private readonly {ValidatorClassName} _sut;

    public {ValidatorClassName}Tests()
    {
        _sut = new {ValidatorClassName}();
    }

    private static {CommandType} CreateValidCommand()
    {
        return new {CommandType}
        {
            // Populate with valid test data for every property
        };
    }

    // -- Valid Input --

    [Fact]
    public void Validate_WithValidCommand_ShouldHaveNoErrors()
    {
        // Arrange
        {CommandType} command = CreateValidCommand();

        // Act
        FluentValidation.Results.ValidationResult result = _sut.Validate(command);

        // Assert
        Assert.True(result.IsValid);
    }

    // -- Property: {PropertyName} --

    [Fact]
    public void Validate_When{PropertyName}IsEmpty_ShouldHaveError()
    {
        // Arrange
        {CommandType} command = CreateValidCommand() with { {PropertyName} = string.Empty };

        // Act
        FluentValidation.Results.ValidationResult result = _sut.Validate(command);

        // Assert
        Assert.False(result.IsValid);
        Assert.Contains(result.Errors, e => e.PropertyName == "{PropertyName}");
    }

    [Fact]
    public void Validate_When{PropertyName}ExceedsMaxLength_ShouldHaveError()
    {
        // Arrange
        {CommandType} command = CreateValidCommand() with
        {
            {PropertyName} = new string('A', {MaxLength + 1})
        };

        // Act
        FluentValidation.Results.ValidationResult result = _sut.Validate(command);

        // Assert
        Assert.False(result.IsValid);
        Assert.Contains(result.Errors, e => e.PropertyName == "{PropertyName}");
    }

    [Fact]
    public void Validate_When{PropertyName}IsAtMaxLength_ShouldHaveNoError()
    {
        // Arrange
        {CommandType} command = CreateValidCommand() with
        {
            {PropertyName} = new string('A', {MaxLength})
        };

        // Act
        FluentValidation.Results.ValidationResult result = _sut.Validate(command);

        // Assert
        Assert.True(result.IsValid);
    }

    // Repeat the above pattern for EVERY property with validation rules.
    // For numeric properties, test: zero, negative, boundary values.
    // For enum/pattern properties, test: valid values, invalid values.
    // For nullable properties, test: null is accepted when optional.
}
```

### Validator Test Rules

- Generate tests for **every** validation rule in the validator.
- For string properties with NotEmpty: test empty string and null.
- For string properties with MaximumLength: test at max (pass), at max+1 (fail).
- For numeric properties with GreaterThan(0): test 0 (fail), 1 (pass), -1 (fail).
- For Must() rules with patterns: test each valid value and at least one invalid value.
- For conditional rules (.When()): test the condition true and false paths.
- Use `with { }` syntax on sealed records to modify individual properties.

## Step 8: Generate Repository Tests

Only generate this section if TestType is `repository`.

Read the target repository class and its SQL files. Generate tests that verify SQL loading and parameter binding:

```csharp
namespace {Service}.Infrastructure.Tests.Persistence.Repositories;

/// <summary>
/// Unit tests for <see cref="{RepositoryClassName}"/>.
/// </summary>
public sealed class {RepositoryClassName}Tests
{
    private readonly Mock<IDbConnection> _connectionMock;
    private readonly Mock<ISqlFileService> _sqlFileServiceMock;
    private readonly {RepositoryClassName} _sut;

    public {RepositoryClassName}Tests()
    {
        _connectionMock = new Mock<IDbConnection>();
        _sqlFileServiceMock = new Mock<ISqlFileService>();

        _sut = new {RepositoryClassName}(
            _connectionMock.Object,
            _sqlFileServiceMock.Object);
    }

    // -- SQL File Loading --

    [Fact]
    public async Task CreateAsync_ShouldLoadCorrectSqlFile()
    {
        // Arrange
        _sqlFileServiceMock
            .Setup(s => s.GetSql("{EntityName}/Insert"))
            .Returns("INSERT INTO ...");

        {EntityType} entity = CreateValidEntity();

        // Act
        // Note: This will fail at Dapper execution, but we verify SQL loading
        try
        {
            await _sut.CreateAsync(entity, CancellationToken.None);
        }
        catch (Exception)
        {
            // Expected -- we are testing SQL file loading, not execution
        }

        // Assert
        _sqlFileServiceMock.Verify(s => s.GetSql("{EntityName}/Insert"), Times.Once);
    }

    // Repeat for each repository method: GetByIdAsync, UpdateAsync, DeleteAsync, etc.
    // Verify the correct SQL file key is loaded for each operation.

    private static {EntityType} CreateValidEntity()
    {
        return new {EntityType}
        {
            // Populate with valid test data
        };
    }
}
```

## Step 9: Generate Integration Tests

Only generate this section if TestType is `integration`.

Generate a test class that runs against a real PostgreSQL database using Testcontainers:

```csharp
namespace {Service}.Infrastructure.Tests.Persistence.Repositories;

/// <summary>
/// Integration tests for <see cref="{RepositoryClassName}"/> against PostgreSQL.
/// </summary>
public sealed class {RepositoryClassName}IntegrationTests : IAsyncLifetime
{
    private readonly PostgreSqlContainer _postgres = new PostgreSqlBuilder()
        .WithImage("postgres:16-alpine")
        .Build();

    private NpgsqlConnection _connection = null!;
    private {RepositoryClassName} _sut = null!;

    public async Task InitializeAsync()
    {
        await _postgres.StartAsync();

        _connection = new NpgsqlConnection(_postgres.GetConnectionString());
        await _connection.OpenAsync();

        // Run migrations or create schema
        string schemaSql = @"
            CREATE TABLE IF NOT EXISTS {schema}.{table_name} (
                -- Define columns matching the production schema
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                -- ... additional columns ...
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                modified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                is_deleted BOOLEAN NOT NULL DEFAULT false
            );";
        await _connection.ExecuteAsync(schemaSql);

        ISqlFileService sqlFileService = new EmbeddedSqlFileService(
            typeof({RepositoryClassName}).Assembly);

        _sut = new {RepositoryClassName}(_connection, sqlFileService);
    }

    public async Task DisposeAsync()
    {
        await _connection.DisposeAsync();
        await _postgres.DisposeAsync();
    }

    [Fact]
    public async Task CreateAsync_ShouldInsertAndReturnEntity()
    {
        // Arrange
        {EntityType} entity = CreateValidEntity();

        // Act
        {EntityType} result = await _sut.CreateAsync(entity, CancellationToken.None);

        // Assert
        Assert.NotNull(result);
        Assert.NotEqual(Guid.Empty, result.Id);
    }

    [Fact]
    public async Task GetByIdAsync_WhenExists_ShouldReturnEntity()
    {
        // Arrange
        {EntityType} created = await _sut.CreateAsync(CreateValidEntity(), CancellationToken.None);

        // Act
        {EntityType}? result = await _sut.GetByIdAsync(created.Id, CancellationToken.None);

        // Assert
        Assert.NotNull(result);
        Assert.Equal(created.Id, result!.Id);
    }

    [Fact]
    public async Task GetByIdAsync_WhenNotExists_ShouldReturnNull()
    {
        // Act
        {EntityType}? result = await _sut.GetByIdAsync(Guid.NewGuid(), CancellationToken.None);

        // Assert
        Assert.Null(result);
    }

    [Fact]
    public async Task GetByIdAsync_WhenSoftDeleted_ShouldReturnNull()
    {
        // Arrange
        {EntityType} created = await _sut.CreateAsync(CreateValidEntity(), CancellationToken.None);
        await _sut.DeleteAsync(created.Id, CancellationToken.None);

        // Act
        {EntityType}? result = await _sut.GetByIdAsync(created.Id, CancellationToken.None);

        // Assert
        Assert.Null(result);
    }

    private static {EntityType} CreateValidEntity()
    {
        return new {EntityType}
        {
            // Populate with valid test data
            CreatedAt = DateTimeOffset.UtcNow,
            ModifiedAt = DateTimeOffset.UtcNow
        };
    }
}
```

### Integration Test Rules

- Use Testcontainers with `postgres:16-alpine` image.
- Implement `IAsyncLifetime` for container lifecycle management.
- Create the schema in `InitializeAsync` matching the production schema.
- Test CRUD operations: create, read, read-not-found, update, soft-delete.
- Test that soft-deleted records are not returned by SELECT queries.
- Each test should be independent -- do not rely on test execution order.
- Clean up data between tests if needed, or use unique identifiers.

## Step 10: Final Output

After generating the test file:

1. Display the full file path of the created test file.
2. Display the complete test class for review.
3. Suggest running the tests:
   ```
   dotnet test --filter "FullyQualifiedName~{TargetClassName}Tests"
   ```
4. List any TODO items where test data or assertions need manual refinement.
5. Remind the user: **All tests must pass before proceeding to the next feature step.**

## Important Rules

- **AAA pattern** (Arrange-Act-Assert) with comment separators in every test.
- **No `var`** -- always use explicit types.
- **One assertion concept per test** -- multiple Assert calls are fine if they verify the same concept.
- **Test method naming**: `{Method}_When{Condition}_Should{ExpectedBehavior}` or `{Method}_With{Input}_Should{ExpectedBehavior}`.
- **No test interdependence** -- each test must be runnable in isolation.
- **Use `CancellationToken.None`** in tests unless specifically testing cancellation behavior.
- **Mock only direct dependencies** -- do not mock types owned by the SUT.
- **sealed class** on all test classes.
