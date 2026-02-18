---
name: lixi-lookup
description: Search LIXI DAS schema definitions, enums, and properties
argument-hint: "[search term]"
---

# Search LIXI DAS Schema

You are searching the LIXI DAS 2.2.92 RFC schema for definitions, enums, and properties that match a user's search term. This schema contains 286 definitions and 235 enums used in Australian lending and property services.

## Step 1: Parse the Search Term

Extract the search term from the arguments. If no argument is provided, ask the user:

"What LIXI definition, property, or enum value are you looking for? (e.g., `Address`, `LoanPurpose`, `PropertyType`)"

Normalize the search term:
- Trim whitespace.
- Prepare for case-insensitive matching.
- Note: LIXI definitions use PascalCase (e.g., `RelatedEntityType`, `AddressType`).

## Step 2: Load the LIXI Schema

Read the LIXI DAS schema file at the path specified in the project conventions:

```
schemas/LIXI-DAS-2_2_92_RFC-Annotated.json
```

This is a JSON Schema file. The key sections are:

- `$defs` -- Contains all 286 type definitions. Each definition is either:
  - An **object** type (with `properties`, `required` arrays)
  - An **enum** type (with `enum` array listing allowed values)
  - A **string** type (with optional `format`, `pattern`, `maxLength`)
  - A **number/integer** type
  - A **reference** type (with `$ref` pointing to another definition)

## Step 3: Search Through Definitions

Search the `$defs` section using these matching strategies (in order of priority):

### 3a. Exact Definition Name Match

Check if any key in `$defs` exactly matches the search term (case-insensitive). This is the highest priority match.

### 3b. Definition Name Contains Search Term

Check if any key in `$defs` contains the search term as a substring (case-insensitive). For example, searching "Address" would match `Address`, `AddressType`, `RelatedAddress`, `StreetAddress`.

### 3c. Property Name Match

For each object-type definition in `$defs`, check if any property name contains the search term (case-insensitive). Include the parent definition name in the results.

### 3d. Enum Value Match

For each enum-type definition in `$defs`, check if any enum value contains the search term (case-insensitive). Include the enum definition name in the results.

### 3e. Description Match

If the definition or property has a `description` field, search that text for the search term.

## Step 4: Format and Display Results

For each match, display the following information based on the definition type:

### Object Type Display

```
## {DefinitionName} (object)

{description if available}

### Properties:
| Property | Type | Required | Description |
|----------|------|----------|-------------|
| {name} | {type or $ref} | {Yes/No} | {description} |
| ... | ... | ... | ... |

### Suggested C# Type:
sealed record {DefinitionName}
```

When displaying property types:
- `$ref: "#/$defs/SomeType"` -- display as `SomeType` (the referenced definition name).
- `type: "string"` with `enum` -- display as `{EnumName} enum`.
- `type: "array"` with `items.$ref` -- display as `IReadOnlyList<{ItemType}>`.
- `type: "string"` with `format: "date"` -- display as `DateOnly`.
- `type: "string"` with `format: "date-time"` -- display as `DateTimeOffset`.
- `type: "integer"` -- display as `int`.
- `type: "number"` -- display as `decimal`.
- `type: "boolean"` -- display as `bool`.

### Enum Type Display

```
## {DefinitionName} (enum)

{description if available}

### Values:
- {Value1}
- {Value2}
- {Value3}
- ... (show all values)

### Suggested C# Type:
public enum {DefinitionName}
{
    [Description("{Value1}")] {PascalCaseValue1},
    [Description("{Value2}")] {PascalCaseValue2},
    ...
}
```

### String Type Display

```
## {DefinitionName} (string)

{description if available}

- Format: {format if specified}
- Pattern: {pattern if specified}
- Max Length: {maxLength if specified}

### Suggested C# Type: string
```

### Reference Type Display

```
## {DefinitionName} (reference)

References: {referenced definition name}

### Suggested C# Type: {ReferencedTypeName}
```

## Step 5: Limit Results

- Show at most **10 results**.
- If more than 10 matches are found, display the first 10 and show:
  ```
  Found {total} matches. Showing first 10. Refine your search term for more specific results.
  ```
- Sort results by relevance:
  1. Exact name matches first.
  2. Name-contains matches second.
  3. Property/enum value matches third.
  4. Description matches last.

## Step 6: Suggest C# Type Mappings

For each result, include a suggested C# type mapping following these rules:

| LIXI JSON Schema Type | C# Type |
|-----------------------|---------|
| `object` | `sealed record` with `init` properties |
| `enum` (string enum) | `enum` with `[Description]` attributes |
| `string` | `string` |
| `string` + `format: "date"` | `DateOnly` |
| `string` + `format: "date-time"` | `DateTimeOffset` |
| `string` + `format: "uri"` | `Uri` |
| `integer` | `int` |
| `number` | `decimal` |
| `boolean` | `bool` |
| `array` of T | `IReadOnlyList<T>` |
| nullable (not in `required`) | append `?` to the C# type |

## Step 7: Offer Next Steps

After displaying results, suggest:

1. **Generate C# code**: "Run `/lextech-dotnet:lixi-codegen {DefinitionName}` to generate the C# sealed record or enum."
2. **Explore related types**: If the definition references other types, suggest searching for those.
3. **Drill deeper**: If the search was broad, suggest more specific search terms based on the results found.

## Important Rules

- **Read the actual schema file** -- do not guess or fabricate LIXI definitions.
- **Case-insensitive matching** for all search operations.
- **Show actual enum values** from the schema, not invented ones.
- **Show actual property names and types** from the schema, not invented ones.
- **JSON only** -- never suggest XML serialization attributes.
- **Maximum 10 results** to keep output manageable.
- **Always include the C# type mapping suggestion** for each result.
- If the schema file cannot be found, tell the user the expected path and ask them to verify.
