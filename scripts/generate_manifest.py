#!/usr/bin/env python3
"""
ZABAWHEELS generate_manifest.py — Generate package manifest JSON.

Creates the manifest JSON file for a wheel artifact, containing:
- Package identity
- Runtime compatibility
- Artifact details (filename, URL, size, SHA-256)
- Dependencies
- Native extension info
- Source provenance
- Verification status

Usage:
    python scripts/generate_manifest.py \
        --package numpy --version 1.26.4 \
        --runtime-id zabacode-py312-api26-p4aXXX-r1 \
        --abi armeabi-v7a --channel candidate
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schemas"


def load_recipe(package_name: str) -> dict:
    """Load recipe.yaml for a package."""
    import yaml

    recipe_path = REPO_ROOT / "packages" / package_name / "recipe.yaml"
    if not recipe_path.exists():
        print(f"❌ Recipe not found: {recipe_path}")
        sys.exit(1)

    with open(recipe_path) as f:
        return yaml.safe_load(f)


def validate_manifest(manifest: dict) -> bool:
    """Validate manifest against schema."""
    schema_path = SCHEMA_DIR / "package-manifest.schema.json"
    if schema_path.exists():
        try:
            import jsonschema

            with open(schema_path) as f:
                schema = json.load(f)
            jsonschema.validate(manifest, schema)
            print("  ✓ Manifest schema validation passed")
            return True
        except ImportError:
            print("  ⚠️  jsonschema not installed — skipping schema validation")
            return True
        except jsonschema.ValidationError as e:
            print(f"  ❌ Schema validation failed: {e.message}")
            return False
    else:
        print("  ⚠️  Schema file not found — skipping validation")
        return True


def generate_manifest(
    package: str,
    version: str,
    runtime_id: str,
    abi: str,
    channel: str,
    wheel_path: str = None,
) -> dict:
    """Generate package manifest."""
    recipe = load_recipe(package)

    manifest = {
        "schema_version": 1,
        "name": package,
        "version": version,
        "runtime_id": runtime_id,
        "python_tag": recipe.get("python_tag", f"cp{recipe.get('python_version', '3XX')}"),
        "abi": abi,
        "android_min_api": recipe.get("min_android_api", 26),
        "channel": channel,
        "artifact": {
            "filename": "",
            "url": "",
            "size": 0,
            "sha256": "",
        },
        "dependencies": recipe.get("runtime_dependencies", []),
        "native": {
            "has_extensions": recipe.get("native", False),
            "needed_libraries": recipe.get("required_shared_libs", []),
        },
        "source": {
            "url": recipe.get("source_url", ""),
            "sha256": recipe.get("source_sha256", ""),
            "license": recipe.get("upstream_license", ""),
        },
        "verification": {
            "build_passed": False,
            "elf_inspected": False,
            "device_tested": False,
            "tested_devices": [],
        },
    }

    # If wheel path provided, compute artifact details
    if wheel_path and os.path.exists(wheel_path):
        manifest["artifact"]["filename"] = os.path.basename(wheel_path)
        manifest["artifact"]["size"] = os.path.getsize(wheel_path)

        sha256 = hashlib.sha256()
        with open(wheel_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        manifest["artifact"]["sha256"] = sha256.hexdigest()

        print(f"  ✓ Artifact: {manifest['artifact']['filename']}")
        print(f"  ✓ SHA-256: {manifest['artifact']['sha256']}")
        print(f"  ✓ Size: {manifest['artifact']['size']} bytes")

    return manifest


def main():
    parser = argparse.ArgumentParser(description="ZABAWHEELS manifest generator")
    parser.add_argument("--package", required=True, help="Package name")
    parser.add_argument("--version", required=True, help="Package version")
    parser.add_argument("--runtime-id", required=True, help="Runtime ID")
    parser.add_argument("--abi", required=True,
                        choices=["armeabi-v7a", "arm64-v8a"],
                        help="Target ABI")
    parser.add_argument("--channel", default="experimental",
                        choices=["experimental", "candidate", "stable"],
                        help="Release channel")
    parser.add_argument("--wheel", default=None, help="Path to wheel file")
    parser.add_argument("--output", default=None, help="Output path for manifest JSON")

    args = parser.parse_args()

    print(f"\nZABAWHEELS Manifest Generator")
    print(f"Package: {args.package}")
    print(f"Version: {args.version}")
    print(f"Runtime: {args.runtime_id}")
    print(f"ABI: {args.abi}")
    print(f"Channel: {args.channel}\n")

    manifest = generate_manifest(
        args.package, args.version, args.runtime_id, args.abi,
        args.channel, args.wheel
    )

    if not validate_manifest(manifest):
        print("❌ Manifest validation failed.")
        sys.exit(1)

    # Output
    output_path = args.output
    if not output_path:
        output_path = str(REPO_ROOT / "index" / args.channel / f"{args.package}-{args.version}-{args.abi}.json")

    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n  ✓ Manifest saved to: {output_path}")


if __name__ == "__main__":
    main()
