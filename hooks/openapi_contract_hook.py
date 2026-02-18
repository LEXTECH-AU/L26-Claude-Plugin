#!/usr/bin/env python3
"""
PostToolUse hook: OpenAPI contract-first enforcement for endpoint files.

Checks for:
  - Missing .WithName() (WARN)
  - Missing .Produces<T>() or .Produces() (WARN)
  - Missing .WithTags() (WARN)
  - Missing .WithSummary() or .WithDescription() (WARN)
  - Missing .RequireAuthorization() (WARN)
  - Command/Query used directly as endpoint parameter type (WARN)

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


def is_endpoint_file(file_path: str) -> bool:
    """Check if the file matches *Endpoint*.cs pattern."""
    import os
    basename = os.path.basename(file_path)
    return "Endpoint" in basename and basename.endswith(".cs")


def check_with_name(content: str) -> list[str]:
    """Check for .WithName() usage."""
    warnings = []
    if ".WithName(" not in content:
        warnings.append(
            "  Endpoint missing .WithName() - required for OpenAPI operationId mapping"
        )
    return warnings


def check_produces(content: str) -> list[str]:
    """Check for .Produces<T>() or .Produces() usage."""
    warnings = []
    if ".Produces<" not in content and ".Produces(" not in content:
        warnings.append(
            "  Endpoint missing .Produces<T>() declarations for response types"
        )
    return warnings


def check_with_tags(content: str) -> list[str]:
    """Check for .WithTags() usage."""
    warnings = []
    if ".WithTags(" not in content:
        warnings.append(
            "  Endpoint missing .WithTags() - required for OpenAPI tag grouping"
        )
    return warnings


def check_summary_or_description(content: str) -> list[str]:
    """Check for .WithSummary() or .WithDescription() usage."""
    warnings = []
    if ".WithSummary(" not in content and ".WithDescription(" not in content:
        warnings.append(
            "  Endpoint missing .WithSummary() or .WithDescription() for OpenAPI documentation"
        )
    return warnings


def check_require_authorization(content: str) -> list[str]:
    """Check for .RequireAuthorization() usage."""
    warnings = []
    if ".RequireAuthorization(" not in content:
        warnings.append(
            "  Endpoint missing .RequireAuthorization() - all endpoints must have explicit authorization"
        )
    return warnings


def check_direct_command_query_parameter(content: str) -> list[str]:
    """Check if a Command or Query type is used directly as an endpoint parameter."""
    warnings = []
    # Match patterns like (SomeCommand command) or (SomeQuery query) in lambda/method parameters
    pattern = r'\(\s*\w*(Command|Query)\s+\w+\s*[,)]'
    if re.search(pattern, content):
        warnings.append(
            "  Consider using a generated DTO from the OpenAPI contract instead of "
            "the command/query directly"
        )
    return warnings


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    file_path, content = extract_file_and_content(payload)

    # Only check endpoint files
    if not is_endpoint_file(file_path):
        sys.exit(0)

    if not content:
        sys.exit(0)

    all_warnings: list[str] = []
    all_warnings.extend(check_with_name(content))
    all_warnings.extend(check_produces(content))
    all_warnings.extend(check_with_tags(content))
    all_warnings.extend(check_summary_or_description(content))
    all_warnings.extend(check_require_authorization(content))
    all_warnings.extend(check_direct_command_query_parameter(content))

    if all_warnings:
        print(
            f"[lextech-dotnet] OpenAPI contract warnings for {file_path}:",
            file=sys.stderr,
        )
        for warning in all_warnings:
            print(warning, file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
