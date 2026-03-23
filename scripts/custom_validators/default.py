#!/usr/bin/env python3
"""Default custom validator for XSOAR/XSIAM lists.

Performs basic checks: file is readable and non-empty.
Custom validators are referenced by name via the 'validator' field in metadata.yaml.
"""

import sys
from pathlib import Path


def validate(file_path: Path) -> bool:
    """Run default validation checks on the file."""
    if not file_path.exists():
        print(f"FAIL: File does not exist: {file_path}")
        return False

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"FAIL: File is not valid UTF-8 (possibly binary): {file_path}")
        return False

    if not content.strip():
        print(f"FAIL: File is empty: {file_path}")
        return False

    # Check for null bytes (binary content in a text list)
    if "\x00" in content:
        print(f"FAIL: File contains null bytes (possibly binary): {file_path}")
        return False

    print(f"PASS: Basic validation passed for {file_path}")
    return True


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <file_path>")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not validate(file_path):
        sys.exit(1)


if __name__ == "__main__":
    main()
