---
name: new-migration
description: Create a numbered pgschema database migration file
argument-hint: "[description]"
---

# Create a pgschema Database Migration

You are creating a new numbered pgschema database migration file for a Lextech .NET 10 microservice using PostgreSQL. Follow every instruction below precisely.

## Step 1: Parse Arguments

Parse the description argument provided by the user. This should be a brief, descriptive name for the migration:

- Examples: `add_company_search_table`, `add_status_column_to_orders`, `create_title_search_indexes`
- If no argument is provided, ask the user: "What does this migration do? (e.g., `add_company_search_table`)"
- Convert spaces to underscores and ensure the description is lowercase with underscores (snake_case).
- Strip any leading/trailing whitespace or special characters.

## Step 2: Find the Migrations Folder

Search the solution for the migrations folder. Look for these patterns in order:

1. A folder named `Migrations` or `migrations` inside the Infrastructure project.
2. A folder containing files matching the pattern `V{NNN}__*.sql` (pgschema naming convention).
3. A `db/migrations` or `database/migrations` folder at the solution root.

If no migrations folder is found, ask the user for the correct location. If the folder structure does not exist, create it inside the Infrastructure project at `Persistence/Migrations/`.

## Step 3: Detect the Next Version Number

Scan all existing migration files in the folder and determine the next version number:

1. List all files matching the pattern `V{number}__*.sql`.
2. Extract the numeric portion from each filename.
3. Find the highest number.
4. Increment by 1 for the new migration.
5. Pad to 3 digits (e.g., `001`, `002`, `015`, `100`).

If no existing migrations are found, start at `V001`.

## Step 4: Construct the File Name

Build the migration file name following the pgschema convention exactly:

```
V{NNN}__{description_in_snake_case}.sql
```

Note: There are exactly **two underscores** between the version number and the description. This is the pgschema convention and must not be changed.

Examples:
- `V001__create_matter_company_search_table.sql`
- `V002__add_order_status_index.sql`
- `V003__add_abn_column_to_company_search.sql`
- `V014__create_title_search_results_table.sql`

## Step 5: Generate the Migration File

Create the migration file with the following structure:

```sql
-- =============================================================================
-- Migration: V{NNN}__{description}
-- Description: {Human-readable description of what this migration does}
-- Author:      Lextech Team
-- Date:        {today's date in YYYY-MM-DD format}
-- =============================================================================

-- UP: Apply migration
-- ---------------------------------------------------------------------------

-- {The actual SQL DDL/DML statements go here}
```

### Common Migration Templates

Based on the description, generate the appropriate SQL. Ask the user for details if needed.

#### Create Table

```sql
CREATE TABLE IF NOT EXISTS {schema}.{table_name} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Business columns
    {column_name} {DATA_TYPE} {NOT NULL} {DEFAULT},

    -- Audit columns
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT false
);

-- Indexes
CREATE INDEX IF NOT EXISTS ix_{table_name}_{column_name}
    ON {schema}.{table_name} ({column_name})
    WHERE is_deleted = false;

-- Comments
COMMENT ON TABLE {schema}.{table_name} IS '{Description of the table}';
COMMENT ON COLUMN {schema}.{table_name}.{column_name} IS '{Description of the column}';
```

#### Add Column

```sql
ALTER TABLE {schema}.{table_name}
    ADD COLUMN IF NOT EXISTS {column_name} {DATA_TYPE} {NOT NULL} {DEFAULT};

COMMENT ON COLUMN {schema}.{table_name}.{column_name} IS '{Description}';
```

#### Create Index

```sql
CREATE INDEX IF NOT EXISTS ix_{table_name}_{column_name}
    ON {schema}.{table_name} ({column_name})
    WHERE is_deleted = false;
```

#### Create Unique Constraint

```sql
ALTER TABLE {schema}.{table_name}
    ADD CONSTRAINT uq_{table_name}_{column_name}
    UNIQUE ({column_name})
    WHERE is_deleted = false;
```

#### Add Foreign Key

```sql
ALTER TABLE {schema}.{table_name}
    ADD CONSTRAINT fk_{table_name}_{referenced_table}
    FOREIGN KEY ({column_name})
    REFERENCES {schema}.{referenced_table} (id);
```

## Step 6: Ask for Table and Column Details

If the migration involves creating or altering tables, gather the following details from the user if not already clear:

1. **Schema name** (default: `public`, but ask if the service uses a custom schema).
2. **Table name** (snake_case, plural by convention).
3. **Column definitions**: name, data type, nullable, default value.
4. **Indexes needed**: Which columns need indexes? Partial indexes with `WHERE is_deleted = false`?
5. **Foreign keys**: Any references to other tables?
6. **Unique constraints**: Any unique combinations?

### PostgreSQL Type Mapping Reference

Provide this reference when asking about column types:

| C# Type | PostgreSQL Type |
|---------|----------------|
| `Guid` | `UUID` |
| `int` | `INTEGER` |
| `long` | `BIGINT` |
| `decimal` | `NUMERIC(18,6)` |
| `string` | `TEXT` or `VARCHAR(n)` |
| `bool` | `BOOLEAN` |
| `DateTime` | `TIMESTAMP` |
| `DateTimeOffset` | `TIMESTAMPTZ` |
| `DateOnly` | `DATE` |
| `TimeOnly` | `TIME` |
| `byte[]` | `BYTEA` |
| `string` (JSON) | `JSONB` |
| enum | `TEXT` (store as string) |

## Step 7: Validate the Migration

Before finalizing, verify:

1. All `CREATE TABLE` statements use `IF NOT EXISTS`.
2. All `CREATE INDEX` statements use `IF NOT EXISTS`.
3. All `ADD COLUMN` statements use `IF NOT EXISTS`.
4. The migration is idempotent where possible (can be run multiple times safely).
5. No destructive operations without explicit user confirmation (DROP TABLE, DROP COLUMN).
6. Table and column comments are included for documentation.
7. Audit columns (`created_at`, `modified_at`, `is_deleted`) are present on new tables.
8. Partial indexes include `WHERE is_deleted = false` for soft-delete tables.

## Step 8: Output and Next Steps

After creating the migration file:

1. Display the full file path.
2. Display the complete SQL content for review.
3. Show the current migration sequence (list the last 5 migrations and the new one).
4. Remind the user:
   - Review the SQL carefully before applying.
   - Test the migration against a development database.
   - If this creates a new table, create the corresponding SQL query files: `/lextech-dotnet:new-sql`
   - If this adds columns, update existing SQL files and repository methods.
   - Coordinate with the team if this migration could conflict with others in progress.
   - Migrations are applied in version order and cannot be reordered after deployment.

## Important Rules

- **pgschema convention**: `V{NNN}__{description}.sql` with exactly two underscores.
- **Idempotent**: Use `IF NOT EXISTS` and `IF EXISTS` wherever possible.
- **No destructive operations** without explicit user confirmation.
- **Always include audit columns** on new tables: `created_at`, `modified_at`, `is_deleted`.
- **Partial indexes** with `WHERE is_deleted = false` for soft-delete tables.
- **Table and column comments** for schema documentation.
- **Snake_case** for all PostgreSQL identifiers.
- **TIMESTAMPTZ** for all timestamp columns (timezone-aware).
- **UUID primary keys** with `DEFAULT gen_random_uuid()`.
- **Sequential version numbers** -- never skip or reuse a number.
