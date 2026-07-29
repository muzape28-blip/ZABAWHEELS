#!/usr/bin/env python3
"""
ZABAWHEELS generate_index.py — Generate the package index for ZabaPip.

Builds the JSON index structure that ZabaPip uses to find compatible packages.
The index is organized by runtime ID and ABI, following the URL structure:

    index/v1/
    ├── runtimes.json
    └── runtimes/
        └── zabacode-pyXXX-api26-p4aXXX-r1/
            ├── packages.json
            ├── armeabi-v7a.json
            └── arm64-v8a.json

Usage:
    python scripts/generate_index.py --output index/
    python scripts/generate_index.py --channel stable
"""

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = REPO_ROOT / "index"
TOOLCHAIN_DIR = REPO_ROOT / "toolchain"


def load_runtime_lock() -> dict:
    """Load runtime-lock.json."""
    lock_path = TOOLCHAIN_DIR / "runtime-lock.json"
    if not lock_path.exists():
        print("❌ runtime-lock.json not found")
        sys.exit(1)

    with open(lock_path) as f:
        return json.load(f)


def collect_manifests(channel: str) -> list:
    """Collect all manifest JSON files for a channel."""
    channel_dir = INDEX_DIR / channel
    manifests = []

    if channel_dir.exists():
        for json_file in sorted(channel_dir.glob("*.json")):
            if json_file.name in {"index.json", "packages.json"}:
                continue
            with open(json_file) as f:
                try:
                    manifest = json.load(f)
                except json.JSONDecodeError:
                    print(f"  ⚠️  Invalid JSON: {json_file}")
                    continue
            required = {"name", "version", "runtime_id", "abi", "artifact"}
            if not required.issubset(manifest):
                print(f"  ⚠️  Ignoring non-manifest JSON: {json_file}")
                continue
            manifests.append(manifest)

    return manifests


def generate_routines_json(runtime_lock: dict) -> dict:
    """Generate runtimes.json — list of available runtime IDs."""
    return {
        "schema_version": 1,
        "runtimes": [
            {
                "runtime_id": runtime_lock.get("runtime_id", "PENDING"),
                "python_version": runtime_lock.get("python", {}).get("version", "PENDING"),
                "abis": runtime_lock.get("android", {}).get("abis", []),
                "min_api": runtime_lock.get("android", {}).get("min_api", 26),
                "status": runtime_lock.get("status", "unknown"),
            }
        ],
    }


def generate_packages_json(manifests: list, runtime_id: str) -> dict:
    """Generate packages.json for a runtime."""
    packages = {}
    for m in manifests:
        name = m.get("name", "unknown")
        packages[name] = {
            "name": name,
            "version": m.get("version", "unknown"),
            "channel": m.get("channel", "experimental"),
            "native": m.get("native", {}).get("has_extensions", False),
            "status": m.get("verification", {}).get("build_passed", False)
                       and "smoke-passed" or "planned",
        }
    return {"schema_version": 1, "runtime_id": runtime_id, "packages": packages}


def generate_abi_json(manifests: list, runtime_id: str, abi: str) -> dict:
    """Generate ABI-specific index for a runtime."""
    abi_manifests = [m for m in manifests if m.get("abi") == abi]
    packages = {}
    for m in abi_manifests:
        name = m.get("name", "unknown")
        packages[name] = m
    return {"schema_version": 1, "runtime_id": runtime_id, "abi": abi, "packages": packages}


def generate_index(output_dir: str, channel: str) -> bool:
    """Generate the full index without overwriting data from other channels."""
    print("\nZABAWHEELS Index Generator")
    print(f"Output: {output_dir}")
    print(f"Channel: {channel}\n")

    # Load runtime lock
    runtime_lock = load_runtime_lock()
    runtime_id = runtime_lock.get("runtime_id", "PENDING_RUNTIME_PROBE")

    # The public v1 index is shared by every release channel. When all channels
    # are requested, collect them first and write the index exactly once.
    channels = (
        ["experimental", "candidate", "stable"]
        if channel == "all"
        else [channel]
    )
    manifests = [
        manifest
        for current_channel in channels
        for manifest in collect_manifests(current_channel)
    ]
    print(
        f"  Found {len(manifests)} manifests across "
        f"{', '.join(repr(item) for item in channels)}"
    )

    # Create output structure
    output_path = Path(output_dir)
    v1_dir = output_path / "v1"
    runtimes_dir = v1_dir / "runtimes" / runtime_id
    v1_dir.mkdir(parents=True, exist_ok=True)
    runtimes_dir.mkdir(parents=True, exist_ok=True)

    # Generate runtimes.json
    runtimes_json = generate_routines_json(runtime_lock)
    runtimes_path = v1_dir / "runtimes.json"
    with open(runtimes_path, "w") as f:
        json.dump(runtimes_json, f, indent=2)
    print(f"  ✓ runtimes.json → {runtimes_path}")

    # Generate packages.json
    packages_json = generate_packages_json(manifests, runtime_id)
    packages_path = runtimes_dir / "packages.json"
    with open(packages_path, "w") as f:
        json.dump(packages_json, f, indent=2)
    print(f"  ✓ packages.json → {packages_path}")

    # Generate ABI-specific indices
    for abi in ["armeabi-v7a", "arm64-v8a"]:
        abi_json = generate_abi_json(manifests, runtime_id, abi)
        abi_path = runtimes_dir / f"{abi}.json"
        with open(abi_path, "w") as f:
            json.dump(abi_json, f, indent=2)
        print(f"  ✓ {abi}.json → {abi_path}")

    print(f"\n  ✓ Index generation complete.")
    return True


def main():
    parser = argparse.ArgumentParser(description="ZABAWHEELS index generator")
    parser.add_argument("--output", default=str(INDEX_DIR),
                        help="Output directory for index")
    parser.add_argument("--channel", default="all",
                        choices=["all", "experimental", "candidate", "stable"],
                        help="Channel to generate index for")

    args = parser.parse_args()

    success = generate_index(args.output, args.channel)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
