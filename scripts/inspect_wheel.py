#!/usr/bin/env python3
"""
ZABAWHEELS inspect_wheel.py — Validate wheel metadata and structure.

Performs static inspection on a wheel file:
- Validate ZIP structure
- Validate WHEEL metadata
- Validate METADATA
- Validate RECORD
- Path traversal detection
- Duplicate file detection
- Unexpected executable detection
- Check file sizes

Usage:
    python scripts/inspect_wheel.py --wheel path/to/package.whl
    python scripts/inspect_wheel.py --wheel path/to/package.whl --security
"""

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path


def validate_wheel_filename(filename: str) -> dict:
    """Validate wheel filename follows PEP 427 naming convention."""
    # Pattern: {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
    pattern = r"^(?P<distribution>[A-Za-z0-9]+([_.-][A-Za-z0-9]+)*)"
    pattern += r"-(?P<version>[A-Za-z0-9]+([_.-][A-Za-z0-9]+)*)"
    pattern += r"(-(?P<build>[A-Za-z0-9]+([_.-][A-Za-z0-9]+)*))?"
    pattern += r"-(?P<python>[A-Za-z0-9]+([_.-][A-Za-z0-9]+)*)"
    pattern += r"-(?P<abi>[A-Za-z0-9]+([_.-][A-Za-z0-9]+)*)"
    pattern += r"-(?P<platform>[A-Za-z0-9]+([_.-][A-Za-z0-9]+)*)"
    pattern += r"\.whl$"

    match = re.match(pattern, filename)
    if not match:
        return {"valid": False, "error": f"Filename does not follow PEP 427: {filename}"}

    return {
        "valid": True,
        "distribution": match.group("distribution"),
        "version": match.group("version"),
        "python_tag": match.group("python"),
        "abi_tag": match.group("abi"),
        "platform_tag": match.group("platform"),
    }


def check_path_traversal(wheel_path: str) -> list:
    """Detect path traversal in wheel archive."""
    traversal_issues = []
    with zipfile.ZipFile(wheel_path) as zf:
        for name in zf.namelist():
            if name.startswith("/") or ".." in name:
                traversal_issues.append(name)
    return traversal_issues


def check_duplicate_files(wheel_path: str) -> list:
    """Detect duplicate files in wheel."""
    duplicates = []
    seen = set()
    with zipfile.ZipFile(wheel_path) as zf:
        for name in zf.namelist():
            if name in seen:
                duplicates.append(name)
            seen.add(name)
    return duplicates


def check_security(wheel_path: str) -> dict:
    """Run security checks on wheel."""
    results = {"path_traversal": [], "duplicate_files": [], "unexpected_executables": []}

    traversal = check_path_traversal(wheel_path)
    if traversal:
        results["path_traversal"] = traversal
        print(f"  ❌ Path traversal detected: {traversal}")
    else:
        print(f"  ✓ No path traversal detected")

    duplicates = check_duplicate_files(wheel_path)
    if duplicates:
        results["duplicate_files"] = duplicates
        print(f"  ❌ Duplicate files: {duplicates}")
    else:
        print(f"  ✓ No duplicate files")

    # Check for unexpected executables
    with zipfile.ZipFile(wheel_path) as zf:
        for info in zf.infolist():
            if info.filename.endswith(".exe") or info.filename.endswith(".dll"):
                results["unexpected_executables"].append(info.filename)

    if results["unexpected_executables"]:
        print(f"  ❌ Unexpected executables: {results['unexpected_executables']}")
    else:
        print(f"  ✓ No unexpected executables")

    return results


def inspect_wheel(wheel_path: str, security: bool = False) -> dict:
    """Perform full wheel inspection."""
    print(f"\nInspecting wheel: {wheel_path}\n")

    if not os.path.exists(wheel_path):
        print(f"  ❌ Wheel file not found: {wheel_path}")
        return {"valid": False, "error": "file not found"}

    # Step 1: Validate filename
    filename = os.path.basename(wheel_path)
    filename_info = validate_wheel_filename(filename)
    if filename_info["valid"]:
        print(f"  ✓ Filename valid: {filename}")
        print(f"    Distribution: {filename_info['distribution']}")
        print(f"    Version: {filename_info['version']}")
        print(f"    Python tag: {filename_info['python_tag']}")
        print(f"    ABI tag: {filename_info['abi_tag']}")
        print(f"    Platform tag: {filename_info['platform_tag']}")
    else:
        print(f"  ❌ Filename invalid: {filename_info['error']}")

    # Step 2: Validate ZIP structure
    try:
        with zipfile.ZipFile(wheel_path) as zf:
            names = zf.namelist()
            print(f"  ✓ ZIP structure valid ({len(names)} files)")

            # Check for WHEEL metadata
            wheel_meta = [n for n in names if n.endswith("/WHEEL")]
            if wheel_meta:
                print(f"  ✓ WHEEL metadata found: {wheel_meta}")
            else:
                print(f"  ❌ WHEEL metadata missing")

            # Check for METADATA
            pkg_meta = [n for n in names if n.endswith("/METADATA")]
            if pkg_meta:
                print(f"  ✓ METADATA found: {pkg_meta}")
            else:
                print(f"  ❌ METADATA missing")

            # Check for RECORD
            record = [n for n in names if n.endswith("/RECORD")]
            if record:
                print(f"  ✓ RECORD found: {record}")
            else:
                print(f"  ⚠️  RECORD missing")
    except zipfile.BadZipFile:
        print(f"  ❌ Invalid ZIP file")
        return {"valid": False, "error": "bad zip"}

    # Step 3: Compute SHA-256
    sha256 = hashlib.sha256()
    with open(wheel_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    print(f"  ✓ SHA-256: {sha256.hexdigest()}")

    # Step 4: File size
    size = os.path.getsize(wheel_path)
    print(f"  ✓ Size: {size} bytes ({size / 1024:.1f} KB)")

    # Step 5: Security checks (if requested)
    security_results = {}
    if security:
        print(f"\n  Security checks:")
        security_results = check_security(wheel_path)

    return {
        "valid": True,
        "filename_info": filename_info,
        "sha256": sha256.hexdigest(),
        "size": size,
        "security": security_results,
    }


def main():
    parser = argparse.ArgumentParser(description="ZABAWHEELS wheel inspector")
    parser.add_argument("--wheel", required=True, help="Path to wheel file")
    parser.add_argument("--security", action="store_true",
                        help="Run additional security checks")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")

    args = parser.parse_args()

    result = inspect_wheel(args.wheel, args.security)

    if args.json:
        print(json.dumps(result, indent=2))

    sys.exit(0 if result.get("valid") else 1)


if __name__ == "__main__":
    main()
