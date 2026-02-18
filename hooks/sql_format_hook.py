#!/usr/bin/env python3
"""
PostToolUse hook: SQL file format and injection prevention.

Checks for:
  - Missing header comment (WARN)
  - Missing parameter documentation (WARN)
  - String concatenation patterns indicating SQL injection risk (BLOCK - exit 2)
  - Non-parameterized values in WHERE clauses (BLOCK - exit 2)

Exit 0 = allow (warnings on stderr).
Exit 2 = block and undo the write.
"""

import json
import re
import sys


def extract_file_and_content(payload: dict) -> tuple[str, str]:
    """Extract the file path and new content from the hook payload."""
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})

    file_path = tool_input.get("file_path", "")

    if tool_name == "Write":
        content = tool_input.get("content", "")
    elif tool_name == "Edit":
        content = tool_input.get("new_string", "")
    elif tool_name == "MultiEdit":
        edits = tool_input.get("edits", [])
        content = "\n".join(e.get("new_string", "") for e in edits)
    else:
        content = ""

    return file_path, content


def check_header_comment(content: str) -> list[str]:
    """Check that the SQL file starts with a header comment block."""
    warnings = []
    stripped = content.lstrip()
    if not stripped.startswith("--") and not stripped.startswith("/*"):
        warnings.append(
            "  SQL file is missing a header comment block. "
            "Add a comment describing the query's purpose, parameters, and author."
        )
    return warnings


def check_parameter_documentation(content: str) -> list[str]:
    """Check that SQL parameters (@Param) are documented in comments."""
    warnings = []
    # Find all @-prefixed parameters used in the SQL body
    params = set(re.findall(r'@(\w+)', content))
    # Exclude common built-in parameters and functions
    builtin = {"ROWCOUNT", "ERROR", "IDENTITY", "SCOPE_IDENTITY", "TRANCOUNT"}
    params = params - builtin

    if not params:
        return warnings

    # Look for parameter documentation in comments at the top of the file
    comment_section = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or stripped.startswith("/*") or stripped.startswith("*") or stripped.startswith("*/"):
            comment_section.append(stripped)
        elif stripped == "":
            continue
        else:
            break

    comment_text = "\n".join(comment_section).lower()
    undocumented = []
    for param in params:
        if param.lower() not in comment_text:
            undocumented.append(f"@{param}")

    if undocumented:
        warnings.append(
            f"  Undocumented SQL parameters: {', '.join(sorted(undocumented))}. "
            f"Add parameter descriptions to the header comment."
        )

    return warnings


def check_string_concatenation(content: str) -> list[str]:
    """Detect string concatenation patterns that indicate SQL injection risk."""
    blockers = []
    for i, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        # Skip comment lines
        if stripped.startswith("--") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # Pattern: + @ (concatenating a variable)
        if re.search(r'\+\s*@', stripped) or re.search(r"'\s*\+", stripped):
            blockers.append(
                f"  Line {i}: String concatenation detected. "
                f"Use parameterized queries with @-prefixed parameters only."
            )

        # Pattern: CONCAT( function
        if re.search(r'\bCONCAT\s*\(', stripped, re.IGNORECASE):
            blockers.append(
                f"  Line {i}: CONCAT() function detected in SQL. "
                f"Use parameterized queries instead of building strings."
            )

        # Pattern: string.Format (C# embedding in SQL template)
        if "string.Format" in stripped or "String.Format" in stripped:
            blockers.append(
                f"  Line {i}: string.Format detected. "
                f"Use parameterized queries with @-prefixed parameters."
            )

    return blockers


def check_non_parameterized_where(content: str) -> list[str]:
    """Detect hardcoded literal values in WHERE clauses instead of parameters."""
    blockers = []
    in_where = False
    for i, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip().upper()
        # Skip comments
        if stripped.startswith("--") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        if "WHERE" in stripped:
            in_where = True

        if in_where:
            # End of WHERE clause heuristic
            if any(kw in stripped for kw in ["ORDER BY", "GROUP BY", "HAVING", "LIMIT", "OFFSET", "UNION", "INSERT", "UPDATE", "DELETE"]):
                in_where = False
                continue

            original = line.strip()
            # Detect: = 'literal' or = "literal" (not parameters)
            # Match equality with string literals that are not part of comments
            if re.search(r"=\s*'[^'@][^']*'", original):
                blockers.append(
                    f"  Line {i}: Hardcoded string literal in WHERE clause. "
                    f"Use a @-prefixed parameter instead."
                )

            # Detect: = <number> without a parameter (but allow = 0, = 1 for booleans like is_deleted = false)
            numeric_match = re.search(r'=\s*(\d+)', original)
            if numeric_match:
                value = int(numeric_match.group(1))
                # Allow 0 and 1 as common boolean/flag values, block others
                if value > 1:
                    blockers.append(
                        f"  Line {i}: Hardcoded numeric literal ({value}) in WHERE clause. "
                        f"Use a @-prefixed parameter instead."
                    )

    return blockers


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    file_path, content = extract_file_and_content(payload)

    # Only check .sql files under Infrastructure/
    if not file_path.endswith(".sql"):
        sys.exit(0)

    if "Infrastructure" not in file_path and "infrastructure" not in file_path:
        sys.exit(0)

    if not content:
        sys.exit(0)

    warnings: list[str] = []
    blockers: list[str] = []

    warnings.extend(check_header_comment(content))
    warnings.extend(check_parameter_documentation(content))
    blockers.extend(check_string_concatenation(content))
    blockers.extend(check_non_parameterized_where(content))

    if warnings:
        print(
            f"[lextech-dotnet] SQL format warnings for {file_path}:",
            file=sys.stderr,
        )
        for w in warnings:
            print(w, file=sys.stderr)

    if blockers:
        print(
            f"[lextech-dotnet] BLOCKED: SQL injection risk in {file_path}:",
            file=sys.stderr,
        )
        for b in blockers:
            print(b, file=sys.stderr)
        print(
            "  Use parameterized queries with @-prefixed parameters. "
            "Never concatenate user input into SQL strings.",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
