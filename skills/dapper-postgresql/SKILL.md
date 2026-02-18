---
name: dapper-postgresql
description: "Dapper ORM, PostgreSQL, embedded SQL, Unit of Work, and pgschema migration patterns. Use when creating SQL files, repositories, database operations, or migrations."
---

# Dapper PostgreSQL Data Access

This skill covers all database access patterns for Lextech .NET 10 microservices. We use Dapper with raw SQL files embedded as resources, the Repository pattern, and Unit of Work for transaction management. PostgreSQL is the database engine.

## SQL File Header Template

Every `.sql` file must begin with a comment block documenting its purpose and parameters. Parameters use the `@ParamName` syntax (Dapper convention).

```sql
-- Inserts a new company search order record
-- Parameters:
--   @MatterId: INT - The matter ID from client system
--   @OrderId: VARCHAR(50) - The Dye & Durham Order ID
--   @CompanyIdentifier: VARCHAR(20) - Organisation identifier (ACN/ARBN/ARSN)
--   @OrganisationName: VARCHAR(200) - Organisation name
--   @OrderStatus: INT - Order status enum value
--   @OrderErrorMessage: VARCHAR(1000) - Optional error message
--   @OrderedByUserId: INT - User ID who initiated the search
--   @CreatedAt: TIMESTAMPTZ - Creation timestamp
--   @ModifiedAt: TIMESTAMPTZ - Last modification timestamp

INSERT INTO matter_company_search (matter_id, order_id, company_identifier, organisation_name, order_status, order_error_message, ordered_by_user_id, created_at, modified_at)
VALUES (@MatterId, @OrderId, @CompanyIdentifier, @OrganisationName, @OrderStatus, @OrderErrorMessage, @OrderedByUserId, @CreatedAt, @ModifiedAt)
ON CONFLICT (matter_id, order_id) DO NOTHING;
```

### SQL File Naming Convention

- Files live under `Infrastructure/Persistence/Sql/{Feature}/`.
- Name format: `{TableName}_{Operation}.sql`.
- Examples: `MatterCompanySearch_Insert.sql`, `MatterCompanySearch_GetById.sql`, `MatterTitleSearch_UpdateStatus.sql`.
- Files are embedded resources -- set the Build Action to `EmbeddedResource` in the `.csproj`.

```xml
<ItemGroup>
  <EmbeddedResource Include="Persistence\Sql\**\*.sql" />
</ItemGroup>
```

## ISqlFileService.LoadQuery() Usage

The `ISqlFileService` loads embedded SQL files by name (without the `.sql` extension). Never hardcode SQL strings in repository code.

```csharp
// Load a query by its file name (without .sql extension)
var sql = sqlFileService.LoadQuery("MatterCompanySearch_Insert");

// The service resolves the embedded resource from the assembly
// Throws InvalidOperationException if the file is not found
```

## DynamicParameters Binding

Always use `DynamicParameters` to bind values. Never use anonymous objects for parameterized queries -- `DynamicParameters` gives explicit control over types and direction.

```csharp
var parameters = new DynamicParameters();
parameters.Add("@MatterId", order.MatterId);
parameters.Add("@OrderId", order.OrderId);
parameters.Add("@CompanyIdentifier", order.CompanyIdentifier);
parameters.Add("@OrganisationName", order.OrganisationName);
parameters.Add("@OrderStatus", (int)order.OrderStatus);
parameters.Add("@OrderErrorMessage", order.OrderErrorMessage);
parameters.Add("@OrderedByUserId", order.OrderedByUserId);
parameters.Add("@CreatedAt", order.CreatedAt);
parameters.Add("@ModifiedAt", order.ModifiedAt);
```

### Enum Binding

Always cast enums to `int` when binding. PostgreSQL stores them as integers.

```csharp
parameters.Add("@OrderStatus", (int)order.OrderStatus);
```

### Nullable Parameter Binding

Nullable values are handled naturally by Dapper. Pass `null` directly.

```csharp
parameters.Add("@OrderErrorMessage", order.OrderErrorMessage); // may be null
```

## Repository Implementation

Repositories use primary constructor DI with `IDbConnection` and `ISqlFileService`. They contain no business logic -- only data access.

```csharp
namespace PropertyService.Infrastructure.Persistence.Repositories;

/// <summary>
/// Repository for company search order database operations.
/// </summary>
public class CompanySearchRepository(
    IDbConnection connection,
    ISqlFileService sqlFileService) : ICompanySearchRepository
{
    public async Task<int> CreateAsync(
        CompanySearchOrder order,
        CancellationToken cancellationToken = default)
    {
        var sql = sqlFileService.LoadQuery("MatterCompanySearch_Insert");

        var parameters = new DynamicParameters();
        parameters.Add("@MatterId", order.MatterId);
        parameters.Add("@OrderId", order.OrderId);
        parameters.Add("@CompanyIdentifier", order.CompanyIdentifier);
        parameters.Add("@OrganisationName", order.OrganisationName);
        parameters.Add("@OrderStatus", (int)order.OrderStatus);
        parameters.Add("@OrderErrorMessage", order.OrderErrorMessage);
        parameters.Add("@OrderedByUserId", order.OrderedByUserId);
        parameters.Add("@CreatedAt", order.CreatedAt);
        parameters.Add("@ModifiedAt", order.ModifiedAt);

        return await connection.ExecuteAsync(sql, parameters);
    }

    public async Task<CompanySearchOrder?> GetByMatterAndOrderIdAsync(
        int matterId,
        string orderId,
        CancellationToken cancellationToken = default)
    {
        var sql = sqlFileService.LoadQuery("MatterCompanySearch_GetByMatterAndOrderId");

        var parameters = new DynamicParameters();
        parameters.Add("@MatterId", matterId);
        parameters.Add("@OrderId", orderId);

        return await connection.QuerySingleOrDefaultAsync<CompanySearchOrder>(sql, parameters);
    }

    public async Task<IEnumerable<CompanySearchOrder>> GetByMatterIdAsync(
        int matterId,
        CancellationToken cancellationToken = default)
    {
        var sql = sqlFileService.LoadQuery("MatterCompanySearch_GetByMatterId");

        var parameters = new DynamicParameters();
        parameters.Add("@MatterId", matterId);

        return await connection.QueryAsync<CompanySearchOrder>(sql, parameters);
    }

    public async Task<int> UpdateStatusAsync(
        string orderId,
        OrderStatus status,
        string? errorMessage,
        CancellationToken cancellationToken = default)
    {
        var sql = sqlFileService.LoadQuery("MatterCompanySearch_UpdateStatus");

        var parameters = new DynamicParameters();
        parameters.Add("@OrderId", orderId);
        parameters.Add("@OrderStatus", (int)status);
        parameters.Add("@OrderErrorMessage", errorMessage);
        parameters.Add("@ModifiedAt", DateTimeOffset.UtcNow);

        return await connection.ExecuteAsync(sql, parameters);
    }
}
```

### Repository Interface (Application Layer)

```csharp
namespace PropertyService.Application.CompanySearch.Interfaces;

public interface ICompanySearchRepository
{
    Task<int> CreateAsync(CompanySearchOrder order, CancellationToken cancellationToken = default);
    Task<CompanySearchOrder?> GetByMatterAndOrderIdAsync(int matterId, string orderId, CancellationToken cancellationToken = default);
    Task<IEnumerable<CompanySearchOrder>> GetByMatterIdAsync(int matterId, CancellationToken cancellationToken = default);
    Task<int> UpdateStatusAsync(string orderId, OrderStatus status, string? errorMessage, CancellationToken cancellationToken = default);
}
```

## Unit of Work Lifecycle

The Unit of Work manages a single `IDbConnection` and `IDbTransaction`. Repositories are lazily instantiated and share the same connection.

### Full UnitOfWork Implementation

```csharp
namespace PropertyService.Infrastructure.Persistence;

/// <summary>
/// Manages database transactions and provides access to repositories.
/// </summary>
public class UnitOfWork(
    DapperContext context,
    ISqlFileService sqlFileService,
    ILoggerFactory loggerFactory) : IUnitOfWork
{
    private IDbConnection? _connection;
    private IDbTransaction? _transaction;
    private ITitleSearchRepository? _titleSearchRepository;
    private ICompanySearchRepository? _companySearchRepository;
    private bool _disposed;

    private IDbConnection Connection => _connection ??= context.CreateConnection();

    // Lazy repository instantiation -- all share the same connection
    public ITitleSearchRepository TitleSearchRepository =>
        _titleSearchRepository ??= new TitleSearchRepository(Connection, sqlFileService);

    public ICompanySearchRepository CompanySearchRepository =>
        _companySearchRepository ??= new CompanySearchRepository(Connection, sqlFileService);

    public async Task BeginTransactionAsync(CancellationToken cancellationToken = default)
    {
        if (Connection.State != ConnectionState.Open)
            Connection.Open();

        _transaction = Connection.BeginTransaction();
        await Task.CompletedTask;
    }

    public async Task CommitTransactionAsync(CancellationToken cancellationToken = default)
    {
        try
        {
            _transaction?.Commit();
        }
        catch
        {
            _transaction?.Rollback();
            throw;
        }
        finally
        {
            _transaction?.Dispose();
            _transaction = null;
        }

        await Task.CompletedTask;
    }

    public async Task RollbackTransactionAsync(CancellationToken cancellationToken = default)
    {
        _transaction?.Rollback();
        _transaction?.Dispose();
        _transaction = null;
        await Task.CompletedTask;
    }

    public void Dispose()
    {
        if (_disposed) return;
        _transaction?.Dispose();
        _connection?.Dispose();
        _disposed = true;
    }
}
```

### Transaction Pattern in Handlers

```csharp
await unitOfWork.BeginTransactionAsync(cancellationToken);
try
{
    await unitOfWork.CompanySearchRepository.CreateAsync(order, cancellationToken);
    await unitOfWork.CommitTransactionAsync(cancellationToken);
}
catch
{
    await unitOfWork.RollbackTransactionAsync(cancellationToken);
    throw;
}
```

## Soft Delete Checks

All `SELECT` queries must filter out soft-deleted rows. The convention is a boolean column `is_deleted`.

```sql
-- Retrieves a company search order by matter ID and order ID
-- Parameters:
--   @MatterId: INT - The matter ID
--   @OrderId: VARCHAR(50) - The order ID

SELECT matter_id, order_id, company_identifier, organisation_name,
       order_status, order_error_message, ordered_by_user_id,
       created_at, modified_at
FROM matter_company_search
WHERE matter_id = @MatterId
  AND order_id = @OrderId
  AND is_deleted = false;
```

## ON CONFLICT Upsert Pattern

Use `ON CONFLICT` for idempotent inserts. Choose `DO NOTHING` to silently skip duplicates, or `DO UPDATE` for true upserts.

```sql
-- Idempotent insert: skip if already exists
INSERT INTO matter_company_search (matter_id, order_id, company_identifier)
VALUES (@MatterId, @OrderId, @CompanyIdentifier)
ON CONFLICT (matter_id, order_id) DO NOTHING;

-- True upsert: update on conflict
INSERT INTO matter_title_search (matter_id, property_id, order_status, modified_at)
VALUES (@MatterId, @PropertyId, @OrderStatus, @ModifiedAt)
ON CONFLICT (matter_id, property_id)
DO UPDATE SET
    order_status = EXCLUDED.order_status,
    modified_at = EXCLUDED.modified_at;
```

## Multi-Mapping for Joins

When a query joins multiple tables, use Dapper's multi-mapping to hydrate nested objects.

```csharp
public async Task<IEnumerable<TitleSearchOrder>> GetWithPropertyAsync(
    int matterId,
    CancellationToken cancellationToken = default)
{
    var sql = sqlFileService.LoadQuery("MatterTitleSearch_GetWithProperty");

    var parameters = new DynamicParameters();
    parameters.Add("@MatterId", matterId);

    return await connection.QueryAsync<TitleSearchOrder, PropertyDetails, TitleSearchOrder>(
        sql,
        (order, property) =>
        {
            order.Property = property;
            return order;
        },
        parameters,
        splitOn: "property_id");
}
```

The corresponding SQL uses column ordering with a clear split point:

```sql
-- Retrieves title search orders with property details
-- Parameters:
--   @MatterId: INT - The matter ID
-- Split: property_id

SELECT ts.matter_id, ts.order_id, ts.order_status, ts.created_at,
       p.property_id, p.address, p.title_reference, p.state
FROM matter_title_search ts
INNER JOIN property p ON p.property_id = ts.property_id
WHERE ts.matter_id = @MatterId
  AND ts.is_deleted = false;
```

## Transaction Isolation Levels

For read-heavy queries that need consistency, specify the isolation level.

```csharp
public async Task BeginTransactionAsync(
    IsolationLevel isolationLevel = IsolationLevel.ReadCommitted,
    CancellationToken cancellationToken = default)
{
    if (Connection.State != ConnectionState.Open)
        Connection.Open();

    _transaction = Connection.BeginTransaction(isolationLevel);
    await Task.CompletedTask;
}
```

Use `ReadCommitted` (default) for most operations. Use `Serializable` only when strict ordering is required (e.g., financial transactions).

## pgschema Migration File Format

Database migrations use numbered files with a double-underscore separator.

### Naming Convention

```
V001__create_matter_company_search_table.sql
V002__add_ordered_by_user_id_column.sql
V003__create_matter_title_search_table.sql
```

### Migration File Example

```sql
-- V004__add_is_deleted_to_matter_company_search.sql

ALTER TABLE matter_company_search
ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX idx_matter_company_search_is_deleted
ON matter_company_search (is_deleted)
WHERE is_deleted = false;
```

### Migration Rules

- Migrations are immutable once applied. Never modify a committed migration.
- Always add new columns as `NOT NULL DEFAULT value` or nullable to avoid breaking existing rows.
- Create indexes for columns used in `WHERE` clauses and foreign keys.
- Use partial indexes (`WHERE is_deleted = false`) for soft-delete filtered queries.
- Timestamp columns should use `TIMESTAMPTZ` (not `TIMESTAMP`).
- Use `snake_case` for all PostgreSQL identifiers.

## Embedded Resource SQL File Organization

SQL files are organized by feature under `Infrastructure/Persistence/Sql/`:

```
Infrastructure/
  Persistence/
    Sql/
      CompanySearch/
        MatterCompanySearch_Insert.sql
        MatterCompanySearch_GetByMatterAndOrderId.sql
        MatterCompanySearch_GetByMatterId.sql
        MatterCompanySearch_UpdateStatus.sql
      TitleSearch/
        MatterTitleSearch_Insert.sql
        MatterTitleSearch_GetById.sql
        MatterTitleSearch_GetWithProperty.sql
        MatterTitleSearch_UpdateStatus.sql
```

## Cross-References

- **Feature Workflow**: See `/lextech-dotnet:vertical-slice` for the full 11-step feature development process.
- **Handlers**: See `/lextech-dotnet:wolverine-cqrs` for how handlers interact with the Unit of Work.
- **Testing**: See `/lextech-dotnet:testing-patterns` for repository and integration test patterns.
