---
name: lixi-das-schema
description: "LIXI DAS Schema navigation and C# code generation for Australian lending industry. Use when working with LIXI definitions, generating types, or validating Australian financial data."
---

# LIXI DAS Schema Navigation and Code Generation

This skill covers working with the LIXI DAS (Data and Analytics Services) v2.2.92 RFC schema for Australian lending industry data. It includes schema navigation, C# type generation rules, and Australian data validation patterns.

## Schema Overview

- **Standard**: LIXI DAS v2.2.92 RFC (Lending Industry XML Initiative -- Data and Analytics Services)
- **Format**: JSON Schema (not XML, despite the LIXI name)
- **Definitions**: 286 complex type definitions
- **Enums**: 235 enumeration types
- **Schema file**: `schemas/LIXI-DAS-2_2_92_RFC-Annotated.json`

## Schema File Location

The annotated JSON Schema file is located at:

```
schemas/LIXI-DAS-2_2_92_RFC-Annotated.json
```

This is the single source of truth for all LIXI type definitions. Do not create types from memory or external documentation -- always reference this schema.

## JSON Schema Structure

### Top-Level Layout

The schema follows JSON Schema draft-07 with definitions under `$defs`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$defs": {
    "Package": { ... },
    "Application": { ... },
    "PersonApplicant": { ... },
    "Address": { ... },
    "StateType": {
      "type": "string",
      "enum": ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"]
    }
  }
}
```

### Complex Type Structure

Complex types have `type: "object"` with `properties` and optionally `required`:

```json
{
  "Address": {
    "type": "object",
    "description": "A physical or postal address",
    "properties": {
      "UnitNumber": { "type": "string" },
      "StreetNumber": { "type": "string" },
      "StreetName": { "type": "string", "maxLength": 100 },
      "StreetType": { "$ref": "#/$defs/StreetType" },
      "Suburb": { "type": "string", "maxLength": 50 },
      "State": { "$ref": "#/$defs/StateType" },
      "Postcode": { "type": "string", "pattern": "^[0-9]{4}$" },
      "Country": { "type": "string", "default": "AU" }
    },
    "required": ["StreetName", "Suburb", "State", "Postcode"]
  }
}
```

### Enum Type Structure

Enum types have `type: "string"` with an `enum` array:

```json
{
  "StateType": {
    "type": "string",
    "description": "Australian state or territory",
    "enum": ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"]
  }
}
```

## How to Navigate the Schema

### Search by Definition Name

Look for the exact definition name under `$defs`:

```
Search path: $defs.PersonApplicant
Search path: $defs.Address
Search path: $defs.LoanDetails
```

### Search by Enum Values

To find which enum contains a specific value, search the schema for the value string within `enum` arrays.

### Search by Property Name

To find which definitions contain a specific property, search for the property name within `properties` objects.

### Common LIXI Entities

These are the most frequently used definitions in the schema:

| Entity | Description |
|--------|-------------|
| `Package` | Top-level container for a LIXI message |
| `Application` | A loan application within a package |
| `PersonApplicant` | An individual applicant |
| `CompanyApplicant` | A company/organisation applicant |
| `RealEstateAsset` | A real estate property used as security |
| `LoanDetails` | Loan amount, term, purpose, and repayment details |
| `Address` | Physical or postal address |
| `Insurance` | Insurance policy details (LMI, building, contents) |
| `Employment` | Applicant employment details |
| `Income` | Applicant income details |
| `Expense` | Applicant expense details |
| `Liability` | Applicant liability details |
| `Asset` | Non-real-estate asset details |

## Entity-to-C# Mapping Rules

When generating C# types from LIXI schema definitions, follow these rules exactly.

### Complex Types to Sealed Records

JSON Schema objects map to `sealed record` with `init` properties and XML doc comments.

```csharp
namespace PropertyService.Application.Lixi.Models;

/// <summary>
/// A physical or postal address.
/// LIXI DAS Definition: Address
/// </summary>
public sealed record LixiAddress
{
    /// <summary>
    /// Unit or apartment number.
    /// </summary>
    public string? UnitNumber { get; init; }

    /// <summary>
    /// Street number.
    /// </summary>
    public string? StreetNumber { get; init; }

    /// <summary>
    /// Street name. Required. Max length: 100.
    /// </summary>
    public string StreetName { get; init; } = string.Empty;

    /// <summary>
    /// Street type (e.g., Street, Road, Avenue).
    /// </summary>
    public StreetType? StreetType { get; init; }

    /// <summary>
    /// Suburb or locality name. Required. Max length: 50.
    /// </summary>
    public string Suburb { get; init; } = string.Empty;

    /// <summary>
    /// Australian state or territory. Required.
    /// </summary>
    public StateType State { get; init; }

    /// <summary>
    /// Four-digit Australian postcode. Required.
    /// </summary>
    public string Postcode { get; init; } = string.Empty;

    /// <summary>
    /// Country code. Defaults to "AU".
    /// </summary>
    public string Country { get; init; } = "AU";
}
```

### Enums to C# Enums

JSON Schema enum arrays map to C# `enum` types with XML doc comments.

```csharp
namespace PropertyService.Application.Lixi.Enums;

/// <summary>
/// Australian state or territory.
/// LIXI DAS Enum: StateType
/// </summary>
public enum StateType
{
    /// <summary>New South Wales</summary>
    NSW,

    /// <summary>Victoria</summary>
    VIC,

    /// <summary>Queensland</summary>
    QLD,

    /// <summary>South Australia</summary>
    SA,

    /// <summary>Western Australia</summary>
    WA,

    /// <summary>Tasmania</summary>
    TAS,

    /// <summary>Northern Territory</summary>
    NT,

    /// <summary>Australian Capital Territory</summary>
    ACT
}
```

### Arrays to IReadOnlyList

JSON Schema `array` types map to `IReadOnlyList<T>`.

```csharp
/// <summary>
/// The applicants on this application.
/// </summary>
public IReadOnlyList<PersonApplicant> PersonApplicants { get; init; } = [];

/// <summary>
/// Real estate assets used as security.
/// </summary>
public IReadOnlyList<RealEstateAsset> RealEstateAssets { get; init; } = [];
```

### Nullable Properties

- Properties listed in the schema's `required` array are non-nullable.
- All other properties are nullable using C# nullable reference types (`?`).
- Non-nullable strings default to `string.Empty`.
- Non-nullable collections default to `[]`.

```csharp
// Required property -- non-nullable with default
public string StreetName { get; init; } = string.Empty;

// Optional property -- nullable
public string? UnitNumber { get; init; }

// Required enum -- non-nullable
public StateType State { get; init; }

// Optional enum -- nullable
public StreetType? StreetType { get; init; }
```

### Naming Conventions

- C# type names are prefixed with `Lixi` to avoid collisions: `LixiAddress`, `LixiPersonApplicant`.
- Enum types keep the schema name with `Type` suffix if not already present: `StateType`, `StreetType`.
- Property names match the schema's PascalCase property names exactly.

## JSON-Only Serialization

All LIXI code generation targets JSON only. Do not add XML attributes, XML serialization attributes, or any XML-related code.

```csharp
// CORRECT: JSON serialization attributes only
[JsonPropertyName("streetName")]
public string StreetName { get; init; } = string.Empty;

// WRONG: Do not use XML attributes
// [XmlElement("StreetName")]  -- NEVER DO THIS
```

Use `System.Text.Json` attributes when the JSON property name differs from the C# property name. If they match (after camelCase conversion), no attribute is needed when using `JsonSerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase`.

## Australian Data Validation Patterns

These validation rules are used in FluentValidation validators for Australian financial data.

### ABN (Australian Business Number)

- Exactly 11 digits.
- Must pass the ABN Luhn check algorithm.

```csharp
RuleFor(x => x.Abn)
    .NotEmpty()
    .WithMessage("ABN is required.")
    .Matches(@"^\d{11}$")
    .WithMessage("ABN must be exactly 11 digits.")
    .Must(BeAValidAbn)
    .WithMessage("ABN is not valid (failed checksum).");

private static bool BeAValidAbn(string? abn)
{
    if (string.IsNullOrWhiteSpace(abn) || abn.Length != 11) return false;

    int[] weights = [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19];
    int sum = 0;

    for (int i = 0; i < 11; i++)
    {
        int digit = abn[i] - '0';
        if (i == 0) digit -= 1; // Subtract 1 from first digit
        sum += digit * weights[i];
    }

    return sum % 89 == 0;
}
```

### ACN (Australian Company Number)

- Exactly 9 digits.

```csharp
RuleFor(x => x.Acn)
    .NotEmpty()
    .WithMessage("ACN is required.")
    .Matches(@"^\d{9}$")
    .WithMessage("ACN must be exactly 9 digits.");
```

### BSB (Bank-State-Branch)

- 6 digits, formatted as `XXX-XXX`.

```csharp
RuleFor(x => x.Bsb)
    .NotEmpty()
    .WithMessage("BSB is required.")
    .Matches(@"^\d{3}-\d{3}$")
    .WithMessage("BSB must be in the format XXX-XXX (e.g., 062-000).");
```

### Postcode

- Exactly 4 digits.

```csharp
RuleFor(x => x.Postcode)
    .NotEmpty()
    .WithMessage("Postcode is required.")
    .Matches(@"^\d{4}$")
    .WithMessage("Postcode must be exactly 4 digits.");
```

### Australian Phone Number

```csharp
RuleFor(x => x.PhoneNumber)
    .Matches(@"^(\+61|0)[2-478]\d{8}$")
    .When(x => !string.IsNullOrEmpty(x.PhoneNumber))
    .WithMessage("Phone number must be a valid Australian number (e.g., 0412345678 or +61412345678).");
```

### State Validation

```csharp
private static readonly HashSet<string> ValidStates =
    ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"];

RuleFor(x => x.State)
    .NotEmpty()
    .WithMessage("State is required.")
    .Must(state => ValidStates.Contains(state))
    .WithMessage("State must be a valid Australian state or territory (NSW, VIC, QLD, SA, WA, TAS, NT, ACT).");
```

## Complete Example: PersonApplicant Generation

Given the schema definition for `PersonApplicant`, the generated C# would be:

```csharp
namespace PropertyService.Application.Lixi.Models;

/// <summary>
/// An individual person applicant on a loan application.
/// LIXI DAS Definition: PersonApplicant
/// </summary>
public sealed record LixiPersonApplicant
{
    /// <summary>
    /// Title (e.g., Mr, Mrs, Ms, Dr).
    /// </summary>
    public string? Title { get; init; }

    /// <summary>
    /// First/given name. Required.
    /// </summary>
    public string FirstName { get; init; } = string.Empty;

    /// <summary>
    /// Middle name(s).
    /// </summary>
    public string? MiddleName { get; init; }

    /// <summary>
    /// Surname/family name. Required.
    /// </summary>
    public string Surname { get; init; } = string.Empty;

    /// <summary>
    /// Date of birth. Required.
    /// </summary>
    public DateOnly DateOfBirth { get; init; }

    /// <summary>
    /// Gender.
    /// </summary>
    public GenderType? Gender { get; init; }

    /// <summary>
    /// Australian tax file number.
    /// </summary>
    public string? TaxFileNumber { get; init; }

    /// <summary>
    /// Email address.
    /// </summary>
    public string? Email { get; init; }

    /// <summary>
    /// Mobile phone number.
    /// </summary>
    public string? MobilePhone { get; init; }

    /// <summary>
    /// Residential addresses.
    /// </summary>
    public IReadOnlyList<LixiAddress> Addresses { get; init; } = [];

    /// <summary>
    /// Employment records.
    /// </summary>
    public IReadOnlyList<LixiEmployment> Employments { get; init; } = [];

    /// <summary>
    /// Income records.
    /// </summary>
    public IReadOnlyList<LixiIncome> Incomes { get; init; } = [];
}
```

## Reference Commands

Use these plugin commands for schema operations:

- `/lextech-dotnet:lixi-lookup` -- Search the LIXI DAS schema for definitions, enums, or properties by name.
- `/lextech-dotnet:lixi-codegen` -- Generate C# sealed records and enums from a LIXI DAS schema definition.

## Cross-References

- **Feature Workflow**: See `/lextech-dotnet:vertical-slice` for how generated LIXI types fit into the vertical slice structure.
- **Validation**: Use the Australian data validation patterns above in FluentValidation validators (see vertical-slice skill).
- **Data Access**: See `/lextech-dotnet:dapper-postgresql` when persisting LIXI data to PostgreSQL.
