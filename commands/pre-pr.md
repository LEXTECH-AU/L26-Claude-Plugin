---
name: pre-pr
description: Run pre-PR quality checklist including build, tests, architecture, and standards compliance
---

# Pre-PR Quality Checklist

You are running a comprehensive quality checklist for a Lextech .NET 10 Clean Architecture microservice before a pull request is submitted. Execute every check below and produce a markdown report.

## Overview

Run all checks against the current solution and produce a summary report at the end. Each check results in one of:
- **PASS** -- The check passed with no issues.
- **WARN** -- The check found non-blocking issues that should be reviewed.
- **FAIL** -- The check found blocking issues that must be fixed before PR submission.

## Check 1: Build

Run the .NET build and check for errors and warnings.

**Execute:**
```bash
dotnet build --no-restore 2>&1
```

If `--no-restore` fails (packages not restored), fall back to:
```bash
dotnet build 2>&1
```

**Evaluate:**
- **PASS**: Build succeeds with 0 errors and 0 warnings.
- **WARN**: Build succeeds but has warnings. List all warnings with file and line number.
- **FAIL**: Build fails. List all errors with file and line number.

## Check 2: Tests

Run all tests in the solution and verify they pass.

**Execute:**
```bash
dotnet test --no-build --verbosity normal 2>&1
```

If `--no-build` fails, fall back to:
```bash
dotnet test --verbosity normal 2>&1
```

**Evaluate:**
- **PASS**: All tests pass, 0 failed, 0 skipped.
- **WARN**: All tests pass but some are skipped. List skipped test names.
- **FAIL**: Any test fails. List failed test names with failure messages.

## Check 3: Architecture Layer Violations

Scan `using` statements across all C# files to detect layer dependency violations.

**Rules to check:**

### 3a. Domain Layer Purity
Search files in `*.Domain` projects for forbidden using statements:
- `using Microsoft.AspNetCore` -- Domain must not reference ASP.NET.
- `using Microsoft.EntityFrameworkCore` -- Domain must not reference EF Core.
- `using Dapper` -- Domain must not reference Dapper.
- `using System.Text.Json` -- Domain should not reference JSON serialization (WARN, not FAIL).
- `using Newtonsoft` -- Domain must not reference Newtonsoft.
- `using {Service}.Infrastructure` -- Domain must not reference Infrastructure.

### 3b. Application Layer Boundaries
Search files in `*.Application` projects for forbidden using statements:
- `using {Service}.Infrastructure` -- Application must not reference Infrastructure.
- `using Microsoft.EntityFrameworkCore` -- Application must not reference EF Core.
- `using Dapper` -- Application must not reference Dapper.
- `using Npgsql` -- Application must not reference Npgsql directly.

### 3c. API Layer Restrictions
Search files in `*.Api` projects for forbidden patterns:
- Direct repository usage: `new {anything}Repository(` -- API must not instantiate repositories.
- `using {Service}.Infrastructure.Persistence.Repositories` -- API must not reference repository implementations.

**Evaluate:**
- **PASS**: No layer violations found.
- **FAIL**: List each violation with file path, line number, and the offending using statement.

## Check 4: SQL File Standards

Scan all `.sql` files in the solution for compliance with SQL standards.

**Rules to check:**

### 4a. Header Comments
Every `.sql` file must start with a comment block (line starting with `--`). Check that the first non-empty line starts with `--`.

### 4b. Parameterized Queries
Search for string concatenation patterns that indicate non-parameterized queries:
- `' + '` or `' || '` followed by variable-looking names.
- `${` inside SQL files (template literals).
- `string.Format` or `String.Format` patterns in nearby C# files that construct SQL.

### 4c. Parameter Documentation
Check that SQL files with parameters (`@` symbols) have a parameter documentation block in the header comments.

### 4d. Soft Delete Compliance
For SELECT queries: verify they include `is_deleted = false` in the WHERE clause.
For UPDATE queries: verify they include `is_deleted = false` in the WHERE clause.

### 4e. ORDER BY for Multi-Row SELECTs
For SELECT queries that do not have `LIMIT 1` or query by primary key: verify they include an `ORDER BY` clause.

**Evaluate:**
- **PASS**: All SQL files comply with all rules.
- **WARN**: Minor issues found (missing parameter docs, missing ORDER BY). List each with file path.
- **FAIL**: Critical issues found (no header, string concatenation, missing soft delete check). List each with file path and line.

## Check 5: Coding Standards

Scan all C# files for coding standard violations.

### 5a. No `var` Usage
Search all `.cs` files for the pattern `var ` (the keyword `var` followed by a space). This is forbidden per team standards.

Exclude:
- Files in `obj/` and `bin/` directories.
- Files in `Migrations/` directories (auto-generated).
- Test files that use third-party test helpers (still flag but as WARN).

**Search pattern:** Look for lines containing `var ` that are not inside comments or strings.

### 5b. XML Documentation on Public Members
Search for public classes, methods, properties, and records that are missing XML doc comments. A public member must be preceded by a `/// <summary>` comment.

Check for:
- `public class ` not preceded by `/// <summary>`
- `public sealed class ` not preceded by `/// <summary>`
- `public sealed record ` not preceded by `/// <summary>`
- `public static class ` not preceded by `/// <summary>`
- `public async Task` methods not preceded by `/// <summary>`
- `public {type} {Name} { get;` properties not preceded by `/// <summary>`

Exclude: `Program.cs`, `*.Designer.cs`, `obj/`, `bin/`.

### 5c. CancellationToken on Async Methods
Search for `async Task` methods in non-test files that do not have a `CancellationToken` parameter.

**Evaluate:**
- **PASS**: No violations found.
- **WARN**: Minor issues (missing XML docs on a few members). List each with file path and line.
- **FAIL**: `var` usage found, or many missing XML docs. List each with file path, line, and the offending code.

## Check 6: Serilog Patterns

Search for string interpolation inside Serilog log calls, which is a common mistake that defeats structured logging.

**Patterns to detect:**

Search for lines matching these patterns:
- `Log.Information($"` or `Log.Warning($"` or `Log.Error($"` or `Log.Debug($"` or `Log.Fatal($"`
- `logger.LogInformation($"` or `logger.LogWarning($"` or `logger.LogError($"` etc.
- `.Log{Level}($"` with a `$"` interpolated string.
- `_logger.Log{anything}($"`

The correct pattern uses structured logging placeholders:
```csharp
// WRONG:
logger.LogInformation($"Processing order {orderId}");

// CORRECT:
logger.LogInformation("Processing order {OrderId}", orderId);
```

**Evaluate:**
- **PASS**: No string interpolation in log calls.
- **FAIL**: Interpolated strings in log calls found. List each with file path, line number, and the offending line.

## Check 7: Security

Scan for common security issues.

### 7a. Hardcoded Connection Strings
Search for patterns that look like hardcoded connection strings:
- `"Host=` or `"Server=` or `"Data Source=` in `.cs` files.
- `"Password=` or `"Pwd=` in `.cs` files.
- `"ConnectionString"` assigned to a literal string (not from configuration).

Exclude: `appsettings.Development.json` localhost entries (WARN only), test fixtures.

### 7b. Missing Authorization
Search for endpoint registrations (`MapGet`, `MapPost`, `MapPut`, `MapDelete`, `MapPatch`) that do not chain `.RequireAuthorization()`.

Pattern: Find `app.Map{Method}(` calls and verify that the fluent chain includes `RequireAuthorization()` before the semicolon.

### 7c. Sensitive Data in Logs
Search for log calls that might log sensitive data:
- Parameters named `password`, `token`, `secret`, `key`, `credential`, `connectionString` in log message templates.

### 7d. Missing Input Validation
For each command handler, verify that a corresponding validator class exists. Search for `{CommandName}Validator.cs` matching each `{CommandName}Handler.cs`.

**Evaluate:**
- **PASS**: No security issues found.
- **WARN**: Minor issues (missing auth on health check endpoints is acceptable).
- **FAIL**: Hardcoded credentials, missing authorization on business endpoints, sensitive data in logs. List each with file path and details.

## Check 8: OpenAPI Contract Compliance

Validate that the API layer conforms to the OpenAPI contract.

**Pre-requisite:** Locate the OpenAPI spec file. Search for `openapi.yaml` or `openapi.json` in the solution. If no spec file exists, this check is FAIL with the message "No OpenAPI spec file found."

### 8a. Spec File Validity
Verify the spec file is valid YAML/JSON and follows OpenAPI 3.0+ structure. Look for the `openapi:` version field and `paths:` section.

**Execute:** Check that the file parses as valid YAML and contains required top-level fields (`openapi`, `info`, `paths`).

### 8b. OperationId Coverage
For each endpoint class (files matching `*Endpoint*.cs` in the API project):
- Extract the `.WithName("X")` value (this is the operationId).
- Verify a matching `operationId: X` exists in the spec's `paths` section.
- FAIL if an endpoint has no `.WithName()` or its operationId is not in the spec.

### 8c. Response Schema Coverage
For each endpoint:
- Extract all `.Produces<T>(statusCode)` declarations.
- Verify the spec has a matching response entry for each status code under the correct operation.
- WARN if the spec has response codes not covered by `.Produces<T>()`.

### 8d. Orphaned Operations
Scan the spec for operations that have no matching endpoint class:
- For each `operationId` in the spec, search for a `.WithName("{operationId}")` in the codebase.
- WARN if the spec has operations with no matching endpoint (may indicate dead spec entries or unimplemented features).

### 8e. Breaking Changes
If the spec file is tracked in git, compare the current version against the last committed version:
- Search for removed paths, removed operations, removed required request fields, or changed response schemas.
- WARN if potential breaking changes are detected.
- Note: This is a best-effort check. Recommend running `oasdiff` for comprehensive breaking change detection.

**Evaluate:**
- **PASS**: Spec exists, all endpoints have matching operations, response schemas align.
- **WARN**: Minor mismatches (extra spec operations, missing .WithSummary()).
- **FAIL**: No spec file, endpoints without operationIds in spec, or missing response coverage.

## Final Report

After running all checks, produce a markdown summary report:

```markdown
# Pre-PR Quality Report

**Date:** {today's date}
**Solution:** {solution name}

## Summary

| # | Check | Result | Issues |
|---|-------|--------|--------|
| 1 | Build | {PASS/WARN/FAIL} | {count} |
| 2 | Tests | {PASS/WARN/FAIL} | {count} |
| 3 | Architecture Layers | {PASS/WARN/FAIL} | {count} |
| 4 | SQL Standards | {PASS/WARN/FAIL} | {count} |
| 5 | Coding Standards | {PASS/WARN/FAIL} | {count} |
| 6 | Serilog Patterns | {PASS/WARN/FAIL} | {count} |
| 7 | Security | {PASS/WARN/FAIL} | {count} |
| 8 | OpenAPI Contract | {PASS/WARN/FAIL} | {count} |

**Overall: {PASS/WARN/FAIL}**

## Details

### 1. Build
{Details of any warnings or errors}

### 2. Tests
{Details of any failures or skips}

### 3. Architecture Layer Violations
{Details of any violations}

### 4. SQL File Standards
{Details of any issues}

### 5. Coding Standards
{Details of any violations}

### 6. Serilog Patterns
{Details of any violations}

### 7. Security
{Details of any issues}

### 8. OpenAPI Contract Compliance
{Details of any issues}

## Recommendations
{Bulleted list of specific actions to fix FAIL and WARN items}
```

## Overall Result Logic

- **Overall PASS**: All checks are PASS.
- **Overall WARN**: No checks are FAIL, but one or more are WARN.
- **Overall FAIL**: Any check is FAIL.

If the overall result is FAIL, end with:
```
This PR is NOT ready for submission. Fix the FAIL items above and run /lextech-dotnet:pre-pr again.
```

If the overall result is PASS or WARN, end with:
```
This PR is ready for submission. Review any WARN items before creating the PR.
```

## Important Rules

- **Run actual commands** (`dotnet build`, `dotnet test`) -- do not skip them.
- **Search actual files** -- do not guess or assume compliance.
- **Report exact file paths and line numbers** for every issue found.
- **Do not auto-fix issues** -- only report them. The developer decides how to fix.
- **Exclude generated files** in `obj/`, `bin/`, and `*.Designer.cs` from coding standard checks.
- **Be thorough** -- scan every `.cs` and `.sql` file in the solution.
- **Order results by severity** -- FAIL items first, then WARN, then PASS.
