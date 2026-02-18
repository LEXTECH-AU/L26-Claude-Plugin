#!/usr/bin/env python3
"""
PostToolUse hook: Coding standards enforcement for C# files.

Checks for:
  - var usage (WARN)
  - Missing XML docs on public methods/classes (WARN)
  - Missing CancellationToken on async methods (WARN)
  - Commands/Queries not using sealed record (WARN)

Exit 0 = allow (warnings on stderr). This hook never blocks.
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


def check_var_usage(content: str) -> list[str]:
    """Detect 'var ' usage outside of comments and strings."""
    warnings = []
    for i, line in enumerate(content.splitlines(), start=1):
        stripped = line.lstrip()
        # Skip single-line comments and XML doc comments
        if stripped.startswith("//") or stripped.startswith("///") or stripped.startswith("/*") or stripped.startswith("*"):
            continue
        # Skip lines that are entirely inside a string (rough heuristic)
        if stripped.startswith('"') or stripped.startswith("'"):
            continue
        # Match 'var ' followed by an identifier character (letter or underscore)
        if re.search(r'\bvar\s+[a-zA-Z_]', line):
            warnings.append(
                f"  Line {i}: Use explicit type instead of 'var'. "
                f"Lextech standard forbids var usage."
            )
    return warnings


def check_xml_docs(content: str) -> list[str]:
    """Detect public methods and classes missing XML documentation."""
    warnings = []
    lines = content.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Check for public class, record, struct, interface, enum declarations
        if re.match(r'^public\s+(sealed\s+)?(partial\s+)?(static\s+)?(class|record|struct|interface|enum)\s+', stripped):
            # Look backwards for XML doc comment
            has_doc = False
            for j in range(i - 1, max(i - 5, -1), -1):
                prev = lines[j].strip()
                if prev.startswith("/// <summary>") or prev.startswith("/// <inheritdoc"):
                    has_doc = True
                    break
                if prev.startswith("///"):
                    continue
                if prev == "" or prev.startswith("["):
                    continue
                break
            if not has_doc:
                warnings.append(
                    f"  Line {i + 1}: Public type declaration missing XML documentation. "
                    f"Add /// <summary> above the declaration."
                )

        # Check for public method declarations
        if re.match(r'^public\s+(sealed\s+)?(static\s+)?(override\s+)?(virtual\s+)?(async\s+)?[\w<>\[\]?,\s]+\s+\w+\s*\(', stripped):
            # Exclude property-like patterns and constructors
            if '{' in stripped and 'get;' in stripped:
                continue
            has_doc = False
            for j in range(i - 1, max(i - 5, -1), -1):
                prev = lines[j].strip()
                if prev.startswith("/// <summary>") or prev.startswith("/// <inheritdoc"):
                    has_doc = True
                    break
                if prev.startswith("///"):
                    continue
                if prev == "" or prev.startswith("["):
                    continue
                break
            if not has_doc:
                warnings.append(
                    f"  Line {i + 1}: Public method missing XML documentation. "
                    f"Add /// <summary> above the method."
                )
    return warnings


def check_cancellation_token(content: str) -> list[str]:
    """Detect async methods missing CancellationToken parameter."""
    warnings = []
    for i, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        # Match async method declarations
        match = re.match(r'^(public|private|protected|internal)\s+.*\basync\s+\w+.*\s+(\w+)\s*\(([^)]*)\)', stripped)
        if match:
            method_name = match.group(2)
            params = match.group(3)
            if "CancellationToken" not in params:
                warnings.append(
                    f"  Line {i}: Async method '{method_name}' is missing a "
                    f"CancellationToken parameter."
                )
    return warnings


def check_sealed_record(content: str) -> list[str]:
    """Detect Command/Query types not declared as sealed record."""
    warnings = []
    for i, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        # Match types whose name ends with Command or Query
        match = re.match(
            r'^public\s+(sealed\s+)?(partial\s+)?(class|record|struct)\s+(\w+)',
            stripped,
        )
        if match:
            is_sealed = match.group(1) is not None
            kind = match.group(3)
            type_name = match.group(4)
            if type_name.endswith("Command") or type_name.endswith("Query"):
                if kind != "record" or not is_sealed:
                    expected = "sealed record"
                    actual = f"{'sealed ' if is_sealed else ''}{kind}"
                    warnings.append(
                        f"  Line {i}: '{type_name}' should be declared as "
                        f"'{expected}' but is '{actual}'."
                    )
    return warnings


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    file_path, content = extract_file_and_content(payload)

    # Only check C# files
    if not file_path.endswith(".cs"):
        sys.exit(0)

    if not content:
        sys.exit(0)

    all_warnings: list[str] = []
    all_warnings.extend(check_var_usage(content))
    all_warnings.extend(check_xml_docs(content))
    all_warnings.extend(check_cancellation_token(content))
    all_warnings.extend(check_sealed_record(content))

    if all_warnings:
        print(
            f"[lextech-dotnet] Coding standards warnings for {file_path}:",
            file=sys.stderr,
        )
        for warning in all_warnings:
            print(warning, file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
