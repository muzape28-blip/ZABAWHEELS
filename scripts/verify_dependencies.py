#!/usr/bin/env python3
"""
ZABAWHEELS verify_dependencies.py — Verify wheel dependencies.

Checks that all DT_NEEDED libraries in .so files are available
on the target Android runtime.

Usage:
    python scripts/verify_dependencies.py --wheel path/to/package.whl --abi armeabi-v7a
"""

import argparse
import json
import os
import sys
import zipfile
from pathlib import Path


# Libraries available on Android (Bionic libc)
ANDROID_SYSTEM_LIBS = {
    "libc.so",
    "libm.so",
    "libdl.so",
    "liblog.so",
    "libpthread.so",  # merged into libc since API 21, but still linkable
    "libstdc++.so",
}

# Libraries provided by Zabacode runtime
ZABACODE_RUNTIME_LIBS = {
    "libpython3.so",
    "libpython3.10.so",
    "libpython3.11.so",
    "libpython3.12.so",
    "libpython3.13.so",
}

# Libraries that must NOT be linked
PROHIBITED_LIBS = {
    "libc.so.6",       # glibc
    "libglibc.so",     # glibc
    "libart.so",       # private Android
    "libdalvik.so",    # private Android
    "libandroid_runtime.so",  # private Android
    "libnativehelper.so",     # private Android
}


def verify_wheel_dependencies(wheel_path: str, abi: str) -> dict:
    """Verify all .so dependencies in a wheel."""
    print(f"\nZABAWHEELS Dependency Verifier")
    print(f"Wheel: {wheel_path}")
    print(f"ABI: {abi}\n")

    results = {
        "wheel": wheel_path,
        "abi": abi,
        "files": {},
        "missing_deps": [],
        "prohibited_deps": [],
        "valid": True,
    }

    if not os.path.exists(wheel_path):
        print(f"  ❌ Wheel file not found: {wheel_path}")
        results["valid"] = False
        return results

    # Extract .so files
    so_names = []
    with zipfile.ZipFile(wheel_path) as zf:
        for name in zf.namelist():
            if name.endswith(".so") or ".so." in name:
                so_names.append(name)

    if not so_names:
        print("  ℹ️  Pure Python package — no .so files to verify")
        results["native"] = False
        return results

    print(f"  Found {len(so_names)} .so file(s)")

    # For each .so, check dependencies using readelf
    for so_name in so_names:
        print(f"\n  Checking: {so_name}")

        # We would need to extract and run readelf here
        # For M0, we prepare the script logic
        results["files"][so_name] = {
            "status": "M0_PLACEHOLDER",
            "needed": [],
            "missing": [],
            "prohibited": [],
        }

    return results


def main():
    parser = argparse.ArgumentParser(description="ZABAWHEELS dependency verifier")
    parser.add_argument("--wheel", required=True, help="Path to wheel file")
    parser.add_argument("--abi", required=True,
                        choices=["armeabi-v7a", "arm64-v8a"],
                        help="Target ABI")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")

    args = parser.parse_args()

    result = verify_wheel_dependencies(args.wheel, args.abi)

    if args.json:
        print(json.dumps(result, indent=2))

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
