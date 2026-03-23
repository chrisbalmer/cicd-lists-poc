#!/usr/bin/env python3
"""Validate XSOAR/XSIAM list files based on metadata.yaml in each list directory.

Lists live under Packs/<PackName>/Lists/<ListName>/ and contain:
  - <ListName>.json        (demisto-sdk metadata, managed by XSOAR/XSIAM)
  - <ListName>_data.<ext>  (raw list content)
  - metadata.yaml          (our CI/CD validation config)

metadata.yaml fields (optional file):
  name:      Display name for validation output (optional, falls back to .json name)
  type:      Validation type — json, csv, plain_text (optional, falls back to .json type)
  validator: Name of a custom validator script in scripts/custom_validators/ (optional)
             Overrides type-based validation when set.

If no metadata.yaml exists, validation falls back to the type from <ListName>.json.
"""

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

import yaml


def discover_lists(root: Path) -> list[Path]:
    """Find all list directories under Packs/*/Lists/*/."""
    lists = []
    packs_dir = root / "Packs"
    if not packs_dir.exists():
        return lists
    for pack_dir in sorted(packs_dir.iterdir()):
        lists_dir = pack_dir / "Lists"
        if not lists_dir.is_dir():
            continue
        for list_dir in sorted(lists_dir.iterdir()):
            if not list_dir.is_dir():
                continue
            has_sdk_json = (list_dir / f"{list_dir.name}.json").exists()
            if has_sdk_json:
                lists.append(list_dir)
    return lists


def load_sdk_metadata(list_dir: Path) -> dict:
    """Load the demisto-sdk <ListName>.json file."""
    sdk_path = list_dir / f"{list_dir.name}.json"
    if not sdk_path.exists():
        return {}
    with open(sdk_path) as f:
        return json.load(f)


def load_metadata(list_dir: Path) -> dict:
    """Load validation config by merging metadata.yaml over <ListName>.json defaults."""
    sdk_meta = load_sdk_metadata(list_dir)

    metadata_path = list_dir / "metadata.yaml"
    if metadata_path.exists():
        with open(metadata_path) as f:
            custom_meta = yaml.safe_load(f) or {}
    else:
        custom_meta = {}

    # Build merged config: metadata.yaml wins, sdk json is fallback
    return {
        "name": custom_meta.get("name", sdk_meta.get("name", list_dir.name)),
        "type": custom_meta.get("type", sdk_meta.get("type", "")),
        "validator": custom_meta.get("validator"),
    }


def find_data_file(list_dir: Path) -> Path:
    """Find the data file in a list directory (<ListName>_data.<ext>)."""
    list_name = list_dir.name
    for f in list_dir.iterdir():
        if f.is_file() and f.name.startswith(f"{list_name}_data"):
            return f
    raise FileNotFoundError(f"No data file matching '{list_name}_data.*' found in {list_dir}")


def validate_json(data_path: Path) -> bool:
    """Validate that the file contains valid JSON."""
    try:
        with open(data_path) as f:
            json.load(f)
        print(f"  PASS: {data_path} is valid JSON")
        return True
    except json.JSONDecodeError as e:
        print(f"  FAIL: {data_path} is not valid JSON: {e}")
        return False


def validate_csv(data_path: Path) -> bool:
    """Validate that the file contains valid CSV with consistent columns."""
    try:
        with open(data_path, newline="") as f:
            content = f.read()
        reader = csv.reader(io.StringIO(content))
        row_count = 0
        col_count = None
        for row in reader:
            row_count += 1
            if col_count is None:
                col_count = len(row)
            elif len(row) != col_count:
                print(
                    f"  FAIL: {data_path} has inconsistent column count "
                    f"(row {row_count}: expected {col_count}, got {len(row)})"
                )
                return False
        if row_count == 0:
            print(f"  FAIL: {data_path} is empty")
            return False
        print(f"  PASS: {data_path} is valid CSV ({row_count} rows, {col_count} columns)")
        return True
    except csv.Error as e:
        print(f"  FAIL: {data_path} is not valid CSV: {e}")
        return False


def validate_plain_text(data_path: Path) -> bool:
    """Validate that the file is readable UTF-8 text and not empty."""
    try:
        content = data_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        print(f"  FAIL: {data_path} is not valid UTF-8 (possibly binary)")
        return False

    if not content.strip():
        print(f"  FAIL: {data_path} is empty")
        return False

    if "\x00" in content:
        print(f"  FAIL: {data_path} contains null bytes (possibly binary)")
        return False

    print(f"  PASS: {data_path} is valid plain text")
    return True


def validate_custom(data_path: Path, validator_name: str) -> bool:
    """Run a named custom validator script from scripts/custom_validators/."""
    validators_dir = Path(__file__).parent / "custom_validators"
    script = validators_dir / f"{validator_name}.py"
    if not script.exists():
        print(f"  FAIL: Custom validator '{validator_name}' not found at {script}")
        return False

    result = subprocess.run(
        [sys.executable, str(script), str(data_path)],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        for line in result.stdout.strip().splitlines():
            print(f"  {line}")
    if result.returncode != 0:
        if result.stderr:
            for line in result.stderr.strip().splitlines():
                print(f"  ERROR: {line}")
        print(f"  FAIL: Custom validation '{validator_name}' failed for {data_path}")
        return False
    print(f"  PASS: Custom validation '{validator_name}' passed for {data_path}")
    return True


VALIDATORS = {
    "json": validate_json,
    "csv": validate_csv,
    "plain_text": validate_plain_text,
    "plaintext": validate_plain_text,
}


def validate_list(list_dir: Path) -> bool:
    """Validate a single list directory using metadata.yaml or <ListName>.json."""
    metadata = load_metadata(list_dir)

    list_name = metadata["name"]
    list_type = metadata["type"].lower()
    validator = metadata.get("validator")

    if not list_type:
        print(f"FAIL: No type found for {list_dir} (checked metadata.yaml and {list_dir.name}.json)")
        return False

    print(f"Validating list: {list_name} (type: {list_type})")

    try:
        data_path = find_data_file(list_dir)
    except FileNotFoundError as e:
        print(f"  FAIL: {e}")
        return False

    if validator:
        return validate_custom(data_path, validator)

    if list_type in VALIDATORS:
        return VALIDATORS[list_type](data_path)

    print(f"  FAIL: Unknown list type '{list_type}' for {list_dir}")
    return False


def resolve_list_dirs(paths: list[str], root: Path) -> list[Path]:
    """Resolve changed file paths to their list directories.

    Accepts paths like 'Packs/ListManagement/Lists/Aisummary/Aisummary_data.txt'
    and returns unique list directories like 'Packs/ListManagement/Lists/Aisummary'.
    Also accepts list directories directly.
    """
    list_dirs = set()
    for p in paths:
        path = root / p if not Path(p).is_absolute() else Path(p)
        candidate = path if path.is_dir() else path.parent
        while candidate != root and candidate != candidate.parent:
            has_metadata = (candidate / "metadata.yaml").exists()
            has_sdk_json = (candidate / f"{candidate.name}.json").exists()
            if has_metadata or has_sdk_json:
                list_dirs.add(candidate)
                break
            candidate = candidate.parent
    return sorted(list_dirs)


def main():
    root = Path.cwd()

    if len(sys.argv) > 1:
        list_dirs = resolve_list_dirs(sys.argv[1:], root)
    else:
        list_dirs = discover_lists(root)

    if not list_dirs:
        print("No lists found to validate.")
        sys.exit(0)

    all_passed = True
    for list_dir in list_dirs:
        if not validate_list(list_dir):
            all_passed = False

    if all_passed:
        print("\nAll validations passed!")
        sys.exit(0)
    else:
        print("\nSome validations failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
