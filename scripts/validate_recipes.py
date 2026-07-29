#!/usr/bin/env python3
"""
ZABAWHEELS validate_recipes.py — Validate recipes, runtime lock, and structure.

Used by CI workflow to validate:
- All recipe.yaml files
- runtime-lock.json
- source-lock.json
- Repository structure

Usage:
    python scripts/validate_recipes.py
    python scripts/validate_recipes.py --package numpy
    python scripts/validate_recipes.py --runtime-lock
    python scripts/validate_recipes.py --source-lock
    python scripts/validate_recipes.py --structure
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError:
    print("❌ PyYAML and jsonschema are required. Install: pip install pyyaml jsonschema")
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = REPO_ROOT / "packages"
TOOLCHAIN_DIR = REPO_ROOT / "toolchain"
SCHEMA_DIR = REPO_ROOT / "schemas"
INDEX_DIR = REPO_ROOT / "index"


# Required fields in recipe.yaml
REQUIRED_RECIPE_FIELDS = [
    "package",
    "version",
    "upstream_url",
    "upstream_license",
    "source_url",
    "build_system",
    "native",
    "smoke_test",
    "status",
    "target_abis",
    "min_android_api",
]

# Required fields for non-local sources
REQUIRED_SOURCE_FIELDS = [
    "source_sha256",
]

# Valid package statuses
VALID_STATUSES = [
    "planned", "researching", "recipe-ready", "building", "built",
    "inspected", "installable", "imported", "smoke-passed",
    "device-verified", "stable", "broken", "blocked", "deprecated", "revoked",
]


def validate_recipe(recipe_path: Path) -> list:
    """Validate a single recipe.yaml file."""
    errors = []

    if not recipe_path.exists():
        return [f"Recipe file not found: {recipe_path}"]

    with open(recipe_path) as f:
        try:
            recipe = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return [f"Invalid YAML: {e}"]

    if not recipe:
        return ["Empty recipe file"]

    schema_path = SCHEMA_DIR / "recipe.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        for error in sorted(validator.iter_errors(recipe), key=lambda item: list(item.path)):
            location = ".".join(str(part) for part in error.path) or "<root>"
            errors.append(f"Schema violation at {location}: {error.message}")
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"Cannot load recipe schema: {error}")

    # Check required fields
    for field in REQUIRED_RECIPE_FIELDS:
        if field not in recipe:
            errors.append(f"Missing required field: '{field}'")
        elif recipe[field] is None:
            errors.append(f"Field '{field}' is null")

    # Check source_sha256 for non-local packages
    if recipe.get("source_url") and recipe.get("source_url") != "local":
        if not recipe.get("source_sha256"):
            errors.append("Missing 'source_sha256' — required for non-local packages")

    # Check status
    status = recipe.get("status", "")
    if status and status not in VALID_STATUSES:
        errors.append(f"Invalid status '{status}' — must be one of: {VALID_STATUSES}")

    # Check target_abis
    abis = recipe.get("target_abis", [])
    if abis:
        for abi in abis:
            if abi not in ("armeabi-v7a", "arm64-v8a"):
                errors.append(f"Invalid ABI '{abi}' — must be armeabi-v7a or arm64-v8a")

    # Check min_android_api
    min_api = recipe.get("min_android_api")
    if min_api and min_api < 21:
        errors.append(f"min_android_api {min_api} too low — minimum is 21")

    # Check smoke_test
    smoke = recipe.get("smoke_test", "")
    if smoke and "import" not in str(smoke):
        errors.append("smoke_test should include an import statement")

    return errors


def validate_all_recipes() -> bool:
    """Validate all recipe.yaml files in packages directory."""
    print("Validating all package recipes...\n")
    all_valid = True

    if not PACKAGES_DIR.exists():
        print("❌ packages/ directory not found")
        return False

    # Skip template directory
    recipe_files = []
    for package_dir in PACKAGES_DIR.iterdir():
        if package_dir.is_dir() and package_dir.name != "package-template":
            recipe_path = package_dir / "recipe.yaml"
            if recipe_path.exists():
                recipe_files.append(recipe_path)

    if not recipe_files:
        print("  ℹ️  No recipe files found (M0 placeholder state)")
        return True

    for recipe_path in sorted(recipe_files):
        package_name = recipe_path.parent.name
        print(f"  Checking: {package_name}/recipe.yaml")
        errors = validate_recipe(recipe_path)

        if errors:
            all_valid = False
            for e in errors:
                print(f"    ❌ {e}")
        else:
            print(f"    ✓ Valid")

    print()
    if all_valid:
        print("✓ All recipes valid.")
    else:
        print("❌ Some recipes have errors.")

    return all_valid


def validate_runtime_lock() -> bool:
    """Validate runtime-lock.json."""
    print("Validating runtime-lock.json...\n")
    lock_path = TOOLCHAIN_DIR / "runtime-lock.json"

    if not lock_path.exists():
        print("❌ runtime-lock.json not found")
        return False

    with open(lock_path) as f:
        try:
            lock = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON: {e}")
            return False

    # Check required keys
    required_keys = ["schema_version", "runtime_id", "python", "android", "toolchain"]
    for key in required_keys:
        if key not in lock:
            print(f"  ❌ Missing key: '{key}'")
        else:
            print(f"  ✓ Key present: '{key}'")

    # Check for placeholders
    placeholder_count = 0
    for section in ["python", "toolchain"]:
        if section in lock:
            for key, value in lock[section].items():
                if value == "PENDING":
                    placeholder_count += 1
                    print(f"  ⚠️  Placeholder: {section}.{key} = '{value}'")

    if lock.get("runtime_id") == "PENDING_RUNTIME_PROBE":
        placeholder_count += 1
        print(f"  ⚠️  Placeholder: runtime_id = '{lock['runtime_id']}'")

    if lock.get("status") == "M0_PLACEHOLDER":
        print(f"  ⚠️  Status: M0 placeholder — values need real fingerprint before M1 gate")
    else:
        print(f"  Status: {lock.get('status', 'unknown')}")

    print()
    if placeholder_count > 0 and lock.get("status") != "M0_PLACEHOLDER":
        print(f"❌ {placeholder_count} placeholder values found (not allowed after M0)")
        return False
    elif placeholder_count > 0 and lock.get("status") == "M0_PLACEHOLDER":
        print(f"⚠️  {placeholder_count} placeholder values — acceptable in M0, must be replaced before M1")
        return True
    else:
        print("✓ runtime-lock.json valid (no placeholders)")
        return True


def validate_source_lock() -> bool:
    """Validate source-lock.json."""
    print("Validating source-lock.json...\n")
    lock_path = TOOLCHAIN_DIR / "source-lock.json"

    if not lock_path.exists():
        print("❌ source-lock.json not found")
        return False

    with open(lock_path) as f:
        try:
            lock = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON: {e}")
            return False

    # Check packages
    packages = lock.get("packages", {})
    if not packages:
        print("  ℹ️  No packages in source lock yet")

    for name, info in packages.items():
        print(f"  Checking: {name}")
        required_fields = ["version", "source_url", "sha256", "license"]
        for field in required_fields:
            if field not in info:
                print(f"    ❌ Missing field: '{field}'")
            elif info[field] == "PENDING" and field != "sha256":
                print(f"    ⚠️  Pending: {field}")
            else:
                print(f"    ✓ {field}: {info[field]}")

    print()
    return True


def validate_structure() -> bool:
    """Validate repository directory structure."""
    print("Validating repository structure...\n")

    required_dirs = [
        ".github/ISSUE_TEMPLATE",
        ".github/workflows",
        "toolchain",
        "packages",
        "scripts",
        "schemas",
        "index/experimental",
        "index/candidate",
        "index/stable",
        "tests",
        "docs",
    ]

    required_files = [
        "README.md",
        "LICENSE",
        "ZABAWHEELS.md",
        ".gitignore",
        "toolchain/runtime-lock.json",
        "toolchain/source-lock.json",
        "toolchain/README.md",
        "packages/package-template/recipe.yaml",
        "schemas/runtime.schema.json",
        "schemas/recipe.schema.json",
    ]

    all_valid = True

    for dir_path in required_dirs:
        full_path = REPO_ROOT / dir_path
        if full_path.exists():
            print(f"  ✓ {dir_path}/")
        else:
            print(f"  ❌ {dir_path}/ — missing")
            all_valid = False

    for file_path in required_files:
        full_path = REPO_ROOT / file_path
        if full_path.exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ❌ {file_path} — missing")
            all_valid = False

    # Check no binary in Git
    print(f"\n  Checking for tracked binaries...")
    gitignore_path = REPO_ROOT / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path) as f:
            gitignore = f.read()
        if "*.whl" in gitignore:
            print(f"  ✓ *.whl in .gitignore")
        else:
            print(f"  ❌ *.whl not in .gitignore — wheels may be tracked!")
            all_valid = False
    else:
        print(f"  ❌ .gitignore missing")
        all_valid = False

    print()
    if all_valid:
        print("✓ Repository structure valid.")
    else:
        print("❌ Repository structure incomplete.")

    return all_valid


def main():
    parser = argparse.ArgumentParser(description="ZABAWHEELS recipe validator")
    parser.add_argument("--package", default=None,
                        help="Validate specific package recipe")
    parser.add_argument("--runtime-lock", action="store_true",
                        help="Validate runtime-lock.json")
    parser.add_argument("--source-lock", action="store_true",
                        help="Validate source-lock.json")
    parser.add_argument("--structure", action="store_true",
                        help="Validate repository structure")
    parser.add_argument("--all", action="store_true",
                        help="Run all validations")

    args = parser.parse_args()

    results = []

    if args.all or (not args.package and not args.runtime_lock and
                    not args.source_lock and not args.structure):
        # Default: run all validations
        results.append(("Recipes", validate_all_recipes()))
        results.append(("Runtime Lock", validate_runtime_lock()))
        results.append(("Source Lock", validate_source_lock()))
        results.append(("Structure", validate_structure()))

    if args.package:
        recipe_path = PACKAGES_DIR / args.package / "recipe.yaml"
        errors = validate_recipe(recipe_path)
        if errors:
            for e in errors:
                print(f"  ❌ {e}")
            results.append(("Recipe", False))
        else:
            print(f"  ✓ Recipe valid: {args.package}")
            results.append(("Recipe", True))

    if args.runtime_lock:
        results.append(("Runtime Lock", validate_runtime_lock()))

    if args.source_lock:
        results.append(("Source Lock", validate_source_lock()))

    if args.structure:
        results.append(("Structure", validate_structure()))

    # Summary
    print(f"\n{'=' * 40}")
    print("Validation Summary:")
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False
    print(f"{'=' * 40}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
