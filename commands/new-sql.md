---
name: new-sql
description: Create an embedded SQL file with proper header, parameter docs, and parameterized queries
argument-hint: "[EntityName] [insert|update|select|delete]"
---

# Create an Embedded SQL File

You are creating a parameterized SQL file for a Lextech .NET 10 microservice using Dapper and PostgreSQL. Follow every instruction below precisely.

## Step 1: Parse Arguments

Parse the arguments provided by the user. Expect two positional arguments:

1. **EntityName** -- The domain entity this SQL operates on (e.g., `MatterCompanySearch`, `TitleSearchOrder`). PascalCase.
2. **OperationType** -- One of: `insert`, `update`, `select`, `delete`, `select-list`, `upsert`.

If either argument is missing, ask the user interactively. Also ask:

- What table name to target (suggest snake_case conversion of EntityName, e.g., `matter_company_search`).
- For `select`: What columns to filter on? What to return?
- For `select-list`: What columns to filter on? What ordering? Any pagination?
- For `insert`/`upsert`: What columns to insert? What conflict target for ON CONFLICT?
- For `update`: What columns to update? What is the WHERE clause key?
- For `delete`: Confirm soft delete (set `is_deleted = true`) vs hard delete.

## Step 2: Load the Dapper-PostgreSQL Skill

Read the `dapper-postgresql` skill to load the SQL file conventions, header format, and parameterized query patterns. Apply all conventions from that skill.

## Step 3: Detect the Infrastructure Project

Search the solution for the Infrastructure project (pattern: `*.Infrastructure`). Locate the SQL folder at:

```
{Service}.Infrastructure/Persistence/Sql/{FeatureName}/
```

If the feature folder does not exist, create it. Determine the correct feature folder from the entity name or ask the user.

## Step 4: Determine the File Name

Follow the naming convention:

```
{EntityName}_{Operation}.sql
```

Examples:
- `MatterCompanySearch_Insert.sql`
- `MatterCompanySearch_GetById.sql`
- `MatterCompanySearch_GetByMatterId.sql`
- `MatterCompanySearch_Update.sql`
- `MatterCompanySearch_SoftDelete.sql`
- `MatterCompanySearch_Upsert.sql`

## Step 5: Generate the SQL File

### Header Block (Required for ALL SQL files)

Every SQL file must start with a header comment block:

```sql
-- =============================================================================
-- File:        {EntityName}_{Operation}.sql
-- Description: {One-line description of what this query does}
-- Table:       {schema}.{table_name}
-- Author:      Lextech Team
-- Created:     {today's date in YYYY-MM-DD format}
-- =============================================================================
-- Parameters:
--   @ParamName    (type)     - Description of this parameter
--   @ParamName2   (type)     - Description of this parameter
-- =============================================================================
```

### INSERT Template

```sql
INSERT INTO {schema}.{table_name} (
    {column1},
    {column2},
    {column3},
    created_at,
    modified_at,
    is_deleted
)
VALUES (
    @{Column1},
    @{Column2},
    @{Column3},
    @CreatedAt,
    @ModifiedAt,
    false
)
RETURNING *;
```

Rules for INSERT:
- Always include `created_at`, `modified_at`, `is_deleted` columns.
- Always use `RETURNING *` or `RETURNING {specific columns}` to return the inserted row.
- Use `@PascalCase` parameter names that match the C# property names.

### UPSERT Template (INSERT with ON CONFLICT)

```sql
INSERT INTO {schema}.{table_name} (
    {column1},
    {column2},
    created_at,
    modified_at,
    is_deleted
)
VALUES (
    @{Column1},
    @{Column2},
    @CreatedAt,
    @ModifiedAt,
    false
)
ON CONFLICT ({conflict_columns})
DO UPDATE SET
    {column2} = EXCLUDED.{column2},
    modified_at = EXCLUDED.modified_at
RETURNING *;
```

Rules for UPSERT:
- ON CONFLICT must target a unique constraint or unique index columns.
- DO UPDATE SET should only update mutable columns (never created_at, never the conflict key).
- Use `EXCLUDED.{column}` to reference the values from the attempted insert.

### SELECT (Single Row) Template

```sql
SELECT
    {column1},
    {column2},
    {column3},
    created_at,
    modified_at
FROM {schema}.{table_name}
WHERE {key_column} = @{KeyColumn}
    AND is_deleted = false;
```

Rules for SELECT:
- Always include `AND is_deleted = false` for soft-delete filtering.
- Use explicit column list, never `SELECT *` in production queries.
- Alias columns to PascalCase if the C# property name differs from snake_case column name:
  `created_at AS "CreatedAt"`.

### SELECT (Multiple Rows) Template

```sql
SELECT
    {column1},
    {column2},
    {column3},
    created_at,
    modified_at
FROM {schema}.{table_name}
WHERE {filter_column} = @{FilterColumn}
    AND is_deleted = false
ORDER BY {order_column} {ASC|DESC};
```

Rules for SELECT-LIST:
- Always include `ORDER BY` -- never return unordered result sets.
- Always include `AND is_deleted = false`.
- If pagination is needed, add `LIMIT @PageSize OFFSET @Offset` and document those parameters.

### UPDATE Template

```sql
UPDATE {schema}.{table_name}
SET
    {column1} = @{Column1},
    {column2} = @{Column2},
    modified_at = @ModifiedAt
WHERE {key_column} = @{KeyColumn}
    AND is_deleted = false
RETURNING *;
```

Rules for UPDATE:
- Always update `modified_at`.
- Never update `created_at` or primary key columns.
- Include `AND is_deleted = false` in the WHERE clause.
- Use `RETURNING *` to confirm the update applied.

### DELETE (Soft Delete) Template

```sql
UPDATE {schema}.{table_name}
SET
    is_deleted = true,
    modified_at = @ModifiedAt
WHERE {key_column} = @{KeyColumn}
    AND is_deleted = false
RETURNING *;
```

Rules for DELETE:
- Default to soft delete unless the user explicitly requests hard delete.
- Soft delete sets `is_deleted = true` and updates `modified_at`.
- Hard delete uses `DELETE FROM` and should be rare and explicitly justified.

## Step 6: Ensure Embedded Resource

After creating the SQL file, check the Infrastructure `.csproj` file for an `<EmbeddedResource>` glob that covers SQL files. If there is no matching glob, add one:

```xml
<ItemGroup>
    <EmbeddedResource Include="Persistence\Sql\**\*.sql" />
</ItemGroup>
```

If a glob already covers the new file, inform the user that it is already handled.

## Step 7: Output and Next Steps

After creating the file:

1. Display the full file path of the created SQL file.
2. Display the full SQL content for review.
3. Show the corresponding DynamicParameters C# snippet that the repository will use:

```csharp
DynamicParameters parameters = new();
parameters.Add("@{Column1}", entity.{Column1});
parameters.Add("@{Column2}", entity.{Column2});
parameters.Add("@CreatedAt", entity.CreatedAt);
parameters.Add("@ModifiedAt", entity.ModifiedAt);
```

4. Remind the user:
   - Verify the table and column names match the actual database schema.
   - If this is a new table, create a migration first: `/lextech-dotnet:new-migration`
   - Create or update the repository to use this SQL file.
   - Run integration tests to verify the query works against the database.

## Important Rules

- **Never use string concatenation** in SQL -- always parameterized queries.
- **Never use `SELECT *`** in production queries (allowed in RETURNING clauses).
- **Always include `is_deleted = false`** in SELECT and UPDATE WHERE clauses.
- **Always include `ORDER BY`** for queries returning multiple rows.
- **Always include the header comment block** with parameter documentation.
- **Parameter names must use `@PascalCase`** to match C# property naming conventions.
- **SQL keywords in UPPERCASE**, identifiers in snake_case.
- **One SQL operation per file** -- do not combine multiple statements unless they are part of a CTE or transaction block.
