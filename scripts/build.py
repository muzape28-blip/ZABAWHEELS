#!/usr/bin/env python3
"""
ZABAWHEELS build.py — Cross-compile package into Android wheel.

This script orchestrates the cross-compilation build process.
Currently in M0 placeholder state — actual build requires M1 toolchain freeze.

Usage:
    python scripts/build.py --package numpy --version 1.26.4 --abi armeabi-v7a --channel experimental
    python scripts/build.py --package zaba-native-smoke --version 0.1.0 --abi armeabi-v7a --dry-run
"""

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = REPO_ROOT / "packages"
TOOLCHAIN_DIR = REPO_ROOT / "toolchain"


def load_recipe(package_name: str) -> dict:
    """Load recipe.yaml for a package."""
    import yaml  # noqa: F811 — only needed at runtime

    recipe_path = PACKAGES_DIR / package_name / "recipe.yaml"
    if not recipe_path.exists():
        print(f"❌ Recipe not found: {recipe_path}")
        sys.exit(1)

    with open(recipe_path) as f:
        recipe = yaml.safe_load(f)

    print(f"  ✓ Loaded recipe for {recipe.get('package', package_name)}")
    return recipe


def load_runtime_lock() -> dict:
    """Load runtime-lock.json."""
    lock_path = TOOLCHAIN_DIR / "runtime-lock.json"
    if not lock_path.exists():
        print(f"❌ Runtime lock not found: {lock_path}")
        sys.exit(1)

    with open(lock_path) as f:
        lock = json.load(f)

    return lock


def validate_recipe(recipe: dict, abi: str) -> bool:
    """Validate recipe against basic requirements."""
    errors = []

    if not recipe.get("package"):
        errors.append("Missing 'package' field")
    if not recipe.get("version"):
        errors.append("Missing 'version' field")
    if not recipe.get("source_sha256") and recipe.get("source_url") != "local":
        errors.append("Missing 'source_sha256' — required for non-local packages")
    if not recipe.get("upstream_license"):
        errors.append("Missing 'upstream_license' field")
    if not recipe.get("smoke_test"):
        errors.append("Missing 'smoke_test' field")

    target_abis = recipe.get("target_abis", [])
    if target_abis and abi not in target_abis:
        errors.append(f"ABI '{abi}' not in target_abis: {target_abis}")

    if errors:
        for e in errors:
            print(f"  ❌ {e}")
        return False

    print(f"  ✓ Recipe validation passed")
    return True


def validate_runtime_lock(lock: dict) -> bool:
    """Validate runtime lock has real values (not placeholders)."""
    placeholder_keys = []
    for key, value in lock.get("python", {}).items():
        if value == "PENDING":
            placeholder_keys.append(f"python.{key}")
    for key, value in lock.get("toolchain", {}).items():
        if value == "PENDING" and key != "buildozer_version":
            placeholder_keys.append(f"toolchain.{key}")

    if lock.get("runtime_id") == "PENDING_RUNTIME_PROBE":
        placeholder_keys.append("runtime_id")

    if placeholder_keys and lock.get("status") != "M0_PLACEHOLDER":
        for k in placeholder_keys:
            print(f"  ⚠️  Placeholder value: {k}")
        print("  ⚠️  Runtime lock contains placeholder values. Build requires real values.")
        return False

    if lock.get("status") == "M0_PLACEHOLDER":
        print("  ⚠️  Runtime lock is M0 placeholder. Cannot perform real build.")

    return True


def run_build(package: str, version: str, abi: str, channel: str, dry_run: bool) -> bool:
    """Execute the build process."""
    print(f"\n{'=' * 50}")
    print(f"  ZABAWHEELS Build")
    print(f"  Package: {package}")
    print(f"  Version: {version}")
    print(f"  ABI: {abi}")
    print(f"  Channel: {channel}")
    print(f"{'=' * 50}\n")

    # Step 1: Load recipe
    recipe = load_recipe(package)

    # Step 2: Load runtime lock
    lock = load_runtime_lock()

    # Step 3: Validate recipe
    if not validate_recipe(recipe, abi):
        print("❌ Recipe validation failed.")
        return False

    # Step 4: Validate runtime lock
    validate_runtime_lock(lock)

    # Step 5: Check source
    source_url = recipe.get("source_url")
    source_sha256 = recipe.get("source_sha256")
    if source_url == "local":
        print(f"  ✓ Local source package: {package}")
    elif not source_url or not source_sha256:
        print(f"  ❌ Source URL or SHA-256 missing")
        return False
    else:
        print(f"  ✓ Source: {source_url}")
        print(f"  ✓ SHA-256: {source_sha256}")

    if dry_run:
        print("\n  ⚠️  DRY RUN — No actual build performed.")
        print("  The following steps would be executed:")
        print("    1. Download pinned source")
        print("    2. Verify source SHA-256")
        print("    3. Prepare exact toolchain")
        print("    4. Cross-compile for target ABI")
        print("    5. Build wheel")
        print("    6. Inspect ELF")
        print("    7. Validate metadata")
        print("    8. Generate manifest")
        print("    9. Upload artifact")
        return True

    print("\n  ⚠️  Actual cross-compilation requires M1 gate completion.")
    print("  Toolchain, NDK, and p4a must be pinned with real values.")
    return True


def main():
    parser = argparse.ArgumentParser(description="ZABAWHEELS build script")
    parser.add_argument("--package", required=True, help="Package name")
    parser.add_argument("--version", required=True, help="Package version")
    parser.add_argument("--abi", required=True, choices=["armeabi-v7a", "arm64-v8a"],
                        help="Target ABI")
    parser.add_argument("--channel", default="experimental",
                        choices=["experimental", "candidate", "stable"],
                        help="Release channel")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate recipe and structure without building")
    parser.add_argument("--output", default="dist",
                        help="Output directory for built wheel")

    args = parser.parse_args()

    success = run_build(args.package, args.version, args.abi, args.channel, args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
