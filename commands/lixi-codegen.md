---
name: lixi-codegen
description: Generate C# sealed records or enums from LIXI DAS schema definitions
argument-hint: "[DefinitionName]"
---

# Generate C# Code from LIXI DAS Schema

You are generating C# sealed records or enums from the LIXI DAS 2.2.92 RFC JSON Schema. The generated code must follow Lextech .NET 10 coding standards precisely.

## Step 1: Parse the Definition Name

Extract the definition name from the arguments. If no argument is provided, ask the user:

"Which LIXI definition do you want to generate? (e.g., `Address`, `LoanPurpose`, `PropertyType`). Run `/lextech-dotnet:lixi-lookup` to search for definitions."

The definition name must be an exact match against a key in the schema's `$defs` section (case-sensitive PascalCase).

## Step 2: Load the LIXI Schema

Read the LIXI DAS schema file at:

```
schemas/LIXI-DAS-2_2_92_RFC-Annotated.json
```

Navigate to `$defs.{DefinitionName}` and extract the complete definition.

If the definition is not found:
1. Search for close matches (case-insensitive, partial match).
2. Suggest: "Definition `{name}` not found. Did you mean one of these?" and list the close matches.
3. Suggest running `/lextech-dotnet:lixi-lookup {name}` to search.

## Step 3: Determine the Definition Type

Inspect the definition to determine its type:

- **Enum type**: Has an `enum` array with string values.
- **Object type**: Has `type: "object"` with `properties`.
- **String type**: Has `type: "string"` with optional constraints.
- **Reference type**: Has `$ref` pointing to another definition.
- **Combined type**: Has `allOf`, `oneOf`, or `anyOf` combinators.

## Step 4: Generate C# Enum (for enum definitions)

If the definition contains an `enum` array, generate a C# enum:

```csharp
using System.ComponentModel;

namespace {Service}.Domain.Lixi;

/// <summary>
/// {Description from schema, or "LIXI DAS {DefinitionName} enumeration."}
/// </summary>
/// <remarks>
/// Generated from LIXI DAS 2.2.92 RFC schema definition: {DefinitionName}.
/// </remarks>
public enum {DefinitionName}
{
    /// <summary>
    /// {Description or value name for the first enum value}.
    /// </summary>
    [Description("{OriginalValue1}")]
    {PascalCaseValue1},

    /// <summary>
    /// {Description or value name for the second enum value}.
    /// </summary>
    [Description("{OriginalValue2}")]
    {PascalCaseValue2},

    // ... repeat for all enum values
}
```

### Enum Naming Rules

Convert LIXI enum string values to valid C# enum member names:

| LIXI Value | C# Enum Member |
|-----------|----------------|
| `"Residential"` | `Residential` |
| `"Owner Occupied"` | `OwnerOccupied` |
| `"Non-Resident"` | `NonResident` |
| `"2 Bedroom"` | `TwoBedroom` |
| `"N/A"` | `NotApplicable` |
| `"ACT"` | `Act` or keep `ACT` if it is an abbreviation |
| `"Yes"` / `"No"` | `Yes` / `No` |
| Numeric strings (e.g., `"1"`, `"2"`) | Prefix with descriptive name or `Value1`, `Value2` |

Rules:
- Always preserve the original value in the `[Description("...")]` attribute.
- The `[Description]` attribute is the source of truth for serialization/deserialization.
- Remove spaces, hyphens, slashes from the C# member name; convert to PascalCase.
- If the original value starts with a digit, prefix with a meaningful word or `Value`.
- Add XML `<summary>` doc on every enum member.

## Step 5: Generate C# Sealed Record (for object definitions)

If the definition has `type: "object"` with `properties`, generate a sealed record:

```csharp
namespace {Service}.Domain.Lixi;

/// <summary>
/// {Description from schema, or "LIXI DAS {DefinitionName} type."}
/// </summary>
/// <remarks>
/// Generated from LIXI DAS 2.2.92 RFC schema definition: {DefinitionName}.
/// </remarks>
public sealed record {DefinitionName}
{
    /// <summary>
    /// {Description of property from schema, or property name humanized}.
    /// </summary>
    public {CSharpType} {PropertyName} { get; init; } {DefaultValue};

    // ... repeat for all properties
}
```

### Property Type Mapping Rules

Map JSON Schema types to C# types following these rules:

| JSON Schema | C# Type |
|------------|---------|
| `type: "string"` | `string` |
| `type: "string", format: "date"` | `DateOnly` |
| `type: "string", format: "date-time"` | `DateTimeOffset` |
| `type: "string", format: "uri"` | `Uri` |
| `type: "string", format: "email"` | `string` |
| `type: "string", format: "time"` | `TimeOnly` |
| `type: "string"` with `enum` | Generate inline or reference an enum type |
| `type: "string", pattern: "..."` | `string` (note the pattern in XML docs) |
| `type: "integer"` | `int` |
| `type: "integer", format: "int64"` | `long` |
| `type: "number"` | `decimal` |
| `type: "boolean"` | `bool` |
| `type: "array", items: { $ref }` | `IReadOnlyList<{ReferencedType}>` |
| `type: "array", items: { type }` | `IReadOnlyList<{MappedType}>` |
| `$ref: "#/$defs/{Type}"` | `{Type}` (the referenced definition name) |
| `allOf: [{ $ref }]` | Use the referenced type directly |
| `oneOf: [...]` | Use the most specific common type, or `object` with a doc comment |

### Nullability Rules

- If a property is **not** listed in the `required` array of the definition, make it nullable by appending `?` to the C# type.
- If a property **is** listed in `required`, it is non-nullable.
- For non-nullable `string` properties, provide a default: `= string.Empty;`.
- For non-nullable `IReadOnlyList<T>` properties, provide a default: `= [];`.
- For nullable reference types, no default is needed (defaults to `null`).

### Default Values

| C# Type | Default for Required | Default for Optional |
|---------|---------------------|---------------------|
| `string` | `= string.Empty;` | (nullable, no default) |
| `int` | (no default, 0 is implicit) | (nullable, no default) |
| `decimal` | (no default, 0 is implicit) | (nullable, no default) |
| `bool` | (no default, false is implicit) | (nullable, no default) |
| `DateOnly` | (no default) | (nullable, no default) |
| `DateTimeOffset` | (no default) | (nullable, no default) |
| `IReadOnlyList<T>` | `= [];` | (nullable, no default) |
| `{RecordType}` | (no default) | (nullable, no default) |

## Step 6: Handle Nested and Referenced Types

When a property references another definition via `$ref`:

1. Check if that referenced type already exists in the codebase (search for the C# file).
2. If it exists, use it directly by name.
3. If it does not exist, note it as a dependency and suggest generating it:
   ```
   This type references {ReferencedType} which does not exist yet.
   Run: /lextech-dotnet:lixi-codegen {ReferencedType}
   ```

When a property has an inline `enum` array (not a `$ref` to a named enum):
1. Extract the enum values.
2. Generate a separate enum type named `{ParentDefinitionName}{PropertyName}` (e.g., `AddressAddressType`).
3. Use that enum type for the property.

## Step 7: Generate Companion Enum Helper (if applicable)

If any enum is generated, also generate a JSON converter helper to map between the `[Description]` attribute values and the enum members:

```csharp
/// <summary>
/// JSON serialization extensions for LIXI DAS enums.
/// </summary>
public static class {DefinitionName}Extensions
{
    /// <summary>
    /// Converts the enum value to its LIXI schema string representation.
    /// </summary>
    public static string ToLixiString(this {DefinitionName} value)
    {
        return value switch
        {
            {DefinitionName}.{Member1} => "{OriginalValue1}",
            {DefinitionName}.{Member2} => "{OriginalValue2}",
            _ => throw new ArgumentOutOfRangeException(nameof(value), value, null)
        };
    }

    /// <summary>
    /// Parses a LIXI schema string to the corresponding enum value.
    /// </summary>
    public static {DefinitionName} Parse{DefinitionName}(string value)
    {
        return value switch
        {
            "{OriginalValue1}" => {DefinitionName}.{Member1},
            "{OriginalValue2}" => {DefinitionName}.{Member2},
            _ => throw new ArgumentOutOfRangeException(nameof(value), value, null)
        };
    }
}
```

## Step 8: Output and Placement Suggestion

After generating the code:

1. Display the complete generated C# code.
2. Suggest the file placement:
   - Enums: `{Service}.Domain/Lixi/Enums/{DefinitionName}.cs`
   - Records: `{Service}.Domain/Lixi/{DefinitionName}.cs`
   - Enum extensions: `{Service}.Domain/Lixi/Extensions/{DefinitionName}Extensions.cs`
3. Ask the user if they want to:
   - Write the file to the suggested location.
   - Modify the namespace or location.
   - Generate any referenced types that are missing.
4. List all referenced types that may need to be generated.

## Important Rules

- **JSON only** -- never generate `[XmlElement]`, `[XmlAttribute]`, or any XML serialization attributes.
- **sealed record** for all object types, never `class`.
- **init properties** only, never `set`.
- **XML docs** on the class, every property, and every enum member.
- **No `var`** in any generated code.
- **`[Description]`** attribute on every enum member with the original LIXI string value.
- **IReadOnlyList<T>** for arrays, never `List<T>` or `T[]`.
- **Read the actual schema** -- never fabricate definitions, properties, or enum values.
- **Include the `<remarks>` tag** noting this was generated from the LIXI DAS schema with the version number.
- **Namespace**: `{Service}.Domain.Lixi` for all generated types.
