#!/usr/bin/env python3
"""
PostToolUse hook: Clean Architecture layer dependency enforcement.

Detects the layer of a C# file by path and checks using statements for
violations of the dependency direction rule:

  Domain (pure) -> Application -> Infrastructure -> API

Checks:
  - Domain: BLOCK if using Infrastructure, ASP.NET, Dapper, System.Data,
    Newtonsoft, or JSON serialization namespaces.
  - Application: BLOCK if using Infrastructure namespace.
  - API: WARN if using repository implementation namespaces.

Exit 0 = allow (warnings on stderr).
Exit 2 = block and undo the write.
"""

import json
import re
import sys


# Layer detection patterns (matched against file path segments)
LAYER_PATTERNS = {
    "Domain": [".Domain/", ".Domain\\", "/Domain/", "\\Domain\\"],
    "Application": [".Application/", ".Application\\", "/Application/", "\\Application\\"],
    "Infrastructure": [".Infrastructure/", ".Infrastructure\\", "/Infrastructure/", "\\Infrastructure\\"],
    "Api": [".Api/", ".Api\\", ".API/", ".API\\", "/Api/", "\\Api\\", "/API/", "\\API\\"],
}

# Forbidden using namespaces per layer
DOMAIN_FORBIDDEN = [
    "Infrastructure",
    "Microsoft.AspNetCore",
    "Microsoft.EntityFrameworkCore",
    "Dapper",
    "System.Data",
    "Newtonsoft.Json",
    "System.Text.Json",
]

APPLICATION_FORBIDDEN = [
    "Infrastructure",
]

API_WARN_PATTERNS = [
    "Repository",
    "Repositories",
    "Persistence",
]


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


def detect_layer(file_path: str) -> str | None:
    """Determine which architecture layer a file belongs to by its path."""
    for layer, patterns in LAYER_PATTERNS.items():
        for pattern in patterns:
            if pattern in file_path:
                return layer
    return None


def extract_usings(content: str) -> list[tuple[int, str]]:
    """Extract all using directives with their line numbers."""
    usings = []
    for i, line in enumerate(content.splitlines(), start=1):
        stripped = line.strip()
        match = re.match(r'^using\s+([\w.]+)\s*;', stripped)
        if match:
            usings.append((i, match.group(1)))
        # Also match using with alias: using Alias = Namespace;
        match_alias = re.match(r'^using\s+\w+\s*=\s*([\w.]+)\s*;', stripped)
        if match_alias:
            usings.append((i, match_alias.group(1)))
    return usings


def check_domain_layer(usings: list[tuple[int, str]], file_path: str) -> list[tuple[str, str]]:
    """Check Domain layer for forbidden dependencies."""
    violations = []
    for line_num, namespace in usings:
        for forbidden in DOMAIN_FORBIDDEN:
            if forbidden in namespace:
                violations.append((
                    "BLOCK",
                    f"  Line {line_num}: Domain layer cannot reference '{namespace}'. "
                    f"Domain must be pure -- no infrastructure, ORM, ASP.NET, "
                    f"or serialization dependencies.",
                ))
    return violations


def check_application_layer(usings: list[tuple[int, str]], file_path: str) -> list[tuple[str, str]]:
    """Check Application layer for forbidden dependencies."""
    violations = []
    for line_num, namespace in usings:
        for forbidden in APPLICATION_FORBIDDEN:
            # Match Infrastructure as a namespace segment, not as a substring
            # of other words. Check if it appears as a standalone segment.
            segments = namespace.split(".")
            if forbidden in segments:
                violations.append((
                    "BLOCK",
                    f"  Line {line_num}: Application layer cannot reference "
                    f"'{namespace}'. Application must not depend on "
                    f"Infrastructure. Use interfaces defined in Application.",
                ))
    return violations


def check_api_layer(usings: list[tuple[int, str]], file_path: str) -> list[tuple[str, str]]:
    """Check API layer for discouraged dependencies."""
    violations = []
    for line_num, namespace in usings:
        for pattern in API_WARN_PATTERNS:
            if pattern in namespace:
                violations.append((
                    "WARN",
                    f"  Line {line_num}: API layer references '{namespace}'. "
                    f"Endpoints should dispatch via IMessageBus, not call "
                    f"repositories directly.",
                ))
    return violations


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

    layer = detect_layer(file_path)
    if layer is None:
        sys.exit(0)

    usings = extract_usings(content)
    if not usings:
        sys.exit(0)

    violations: list[tuple[str, str]] = []

    if layer == "Domain":
        violations = check_domain_layer(usings, file_path)
    elif layer == "Application":
        violations = check_application_layer(usings, file_path)
    elif layer == "Api":
        violations = check_api_layer(usings, file_path)
    # Infrastructure layer: no outbound checks needed (it can reference Domain)

    if not violations:
        sys.exit(0)

    has_blockers = any(level == "BLOCK" for level, _ in violations)

    if has_blockers:
        print(
            f"[lextech-dotnet] BLOCKED: Layer dependency violation in "
            f"{file_path} ({layer} layer):",
            file=sys.stderr,
        )
    else:
        print(
            f"[lextech-dotnet] Layer dependency warnings for "
            f"{file_path} ({layer} layer):",
            file=sys.stderr,
        )

    for level, message in violations:
        print(f"  [{level}] {message}", file=sys.stderr)

    if has_blockers:
        print(
            f"  Dependency direction: Domain (pure) -> Application -> "
            f"Infrastructure -> API. Inner layers must not reference outer layers.",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
