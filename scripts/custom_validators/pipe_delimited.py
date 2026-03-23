#!/usr/bin/env python3
"""Validator for pipe-delimited files.

Checks that the file is valid UTF-8, non-empty, and has consistent column
counts when split on the pipe character '|'.
"""

import sys
from pathlib import Path


def validate(file_path: Path) -> bool:
    """Validate a pipe-delimited file."""
    if not file_path.exists():
        print(f"FAIL: File does not exist: {file_path}")
        return False

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"FAIL: File is not valid UTF-8 (possibly binary): {file_path}")
        return False

    lines = [line for line in content.strip().splitlines() if line.strip()]
    if not lines:
        print(f"FAIL: File is empty: {file_path}")
        return False

    col_count = None
    for i, line in enumerate(lines, start=1):
        cols = len(line.split("|"))
        if col_count is None:
            col_count = cols
        elif cols != col_count:
            print(
                f"FAIL: {file_path} has inconsistent column count "
                f"(row {i}: expected {col_count}, got {cols})"
            )
            return False

    print(f"PASS: {file_path} is valid pipe-delimited ({len(lines)} rows, {col_count} columns)")
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
