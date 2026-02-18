#!/usr/bin/env python3
"""
PostToolUse hook: Serilog structured logging enforcement.

Checks C# files containing logger calls for:
  - String interpolation in log calls: _logger.Log..($"...) or Log..($"...) (WARN)
  - PII parameter names in log calls: password, token, secret, creditcard, ssn (WARN)

Exit 0 = allow (warnings on stderr). This hook never blocks.
"""

import json
import re
import sys


# PII-sensitive parameter names (case-insensitive matching)
PII_PATTERNS = [
    "password",
    "passwd",
    "token",
    "secret",
    "creditcard",
    "credit_card",
    "creditcardnumber",
    "ssn",
    "socialsecurity",
    "social_security",
    "taxfilenumber",
    "tfn",
    "bankaccount",
    "bank_account",
    "apikey",
    "api_key",
    "privatekey",
    "private_key",
]

# Compiled pattern for logger method calls
LOGGER_CALL_PATTERN = re.compile(
    r'(?:_?[Ll]og(?:ger)?)\s*\.\s*'
    r'(?:Log(?:Information|Warning|Error|Critical|Debug|Trace|Fatal)?'
    r'|Information|Warning|Error|Critical|Debug|Trace|Fatal'
    r'|Verbose|Write)\s*\(',
    re.IGNORECASE,
)

# Pattern for string interpolation: ($" or ($@" or ($""" etc.
INTERPOLATION_PATTERN = re.compile(
    r'\(\s*\$"'
    r'|\(\s*\$@"'
    r'|\,\s*\$"'
    r'|\,\s*\$@"',
)


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


def has_logger_usage(content: str) -> bool:
    """Quick check: does this content contain any logger calls?"""
    lower = content.lower()
    return "log" in lower and (
        "_logger." in lower
        or "logger." in lower
        or "log." in lower
        or "Log." in content
    )


def check_string_interpolation(content: str) -> list[str]:
    """Detect string interpolation ($\") in Serilog log calls."""
    warnings = []
    lines = content.splitlines()

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("//") or stripped.startswith("///") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # Check if this line has a logger call
        if not LOGGER_CALL_PATTERN.search(line):
            continue

        # Check if interpolation is used in the same line
        if INTERPOLATION_PATTERN.search(line):
            warnings.append(
                f"  Line {i}: String interpolation ($\") detected in log call. "
                f"Use Serilog message templates with {{PropertyName}} placeholders "
                f"instead. Example: _logger.LogInformation(\"Processing order {{OrderId}}\", orderId)"
            )
            continue

        # Check if the message template is on the next line (multi-line calls)
        if i < len(lines):
            next_line = lines[i]  # i is 1-indexed, so lines[i] is the next line
            if INTERPOLATION_PATTERN.search(next_line):
                warnings.append(
                    f"  Line {i + 1}: String interpolation ($\") detected in "
                    f"multi-line log call. Use Serilog message templates with "
                    f"{{PropertyName}} placeholders instead."
                )

    return warnings


def check_pii_parameters(content: str) -> list[str]:
    """Detect PII-sensitive parameter names in Serilog log calls."""
    warnings = []
    lines = content.splitlines()
    in_log_call = False
    brace_depth = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("//") or stripped.startswith("///") or stripped.startswith("/*") or stripped.startswith("*"):
            continue

        # Track whether we are inside a log call (handles multi-line calls)
        if LOGGER_CALL_PATTERN.search(line):
            in_log_call = True
            brace_depth = 0

        if in_log_call:
            brace_depth += line.count("(") - line.count(")")
            if brace_depth <= 0:
                in_log_call = False

            # Check for PII in message template placeholders: {Password}, {Token}, etc.
            template_params = re.findall(r'\{(\w+)\}', line)
            for param in template_params:
                param_lower = param.lower()
                for pii in PII_PATTERNS:
                    if pii in param_lower:
                        warnings.append(
                            f"  Line {i}: PII-sensitive placeholder "
                            f"{{{param}}} found in log call. "
                            f"Never log sensitive data. Redact or remove "
                            f"this parameter."
                        )
                        break

            # Check for PII in named arguments passed to the log call
            named_args = re.findall(r'\b(\w+)\s*:', line)
            for arg in named_args:
                arg_lower = arg.lower()
                for pii in PII_PATTERNS:
                    if pii in arg_lower:
                        warnings.append(
                            f"  Line {i}: PII-sensitive named argument "
                            f"'{arg}' found in log call. "
                            f"Never log sensitive data."
                        )
                        break

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

    # Quick bail-out if no logger usage detected
    if not has_logger_usage(content):
        sys.exit(0)

    all_warnings: list[str] = []
    all_warnings.extend(check_string_interpolation(content))
    all_warnings.extend(check_pii_parameters(content))

    if all_warnings:
        print(
            f"[lextech-dotnet] Serilog logging warnings for {file_path}:",
            file=sys.stderr,
        )
        for warning in all_warnings:
            print(warning, file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
