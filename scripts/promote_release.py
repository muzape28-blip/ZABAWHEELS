#!/usr/bin/env python3
"""
ZABAWHEELS promote_release.py — Promote a package to a higher release channel.

Handles promotion between channels:
  experimental → candidate : build and static inspection passed
  candidate → stable      : device test and lifecycle test passed
  stable → revoked        : security issue or serious breakage found

Promotion must go through pull request or protected workflow with audit trail.

Usage:
    python scripts/promote_release.py \
        --package numpy --version 1.26.4 \
        --abi armeabi-v7a --channel candidate --dry-run
"""

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = REPO_ROOT / "index"


CHANNEL_ORDER = ["experimental", "candidate", "stable"]


def check_promotion_rules(from_channel: str, to_channel: str) -> bool:
    """Check if promotion is allowed."""
    from_idx = CHANNEL_ORDER.index(from_channel) if from_channel in CHANNEL_ORDER else -1
    to_idx = CHANNEL_ORDER.index(to_channel) if to_channel in CHANNEL_ORDER else -1

    if to_channel == "revoked":
        # Any channel can be revoked
        return True

    if to_idx <= from_idx:
        print(f"  ❌ Cannot promote from '{from_channel}' to '{to_channel}'")
        print(f"     Promotion must go forward: experimental → candidate → stable")
        return False

    return True


def check_candidate_requirements(package: str, version: str, abi: str) -> bool:
    """Check minimum requirements for candidate promotion."""
    print(f"\n  Checking candidate requirements for {package} {version} ({abi}):")
    requirements_met = True

    # Requirement: Build passed
    print(f"    [?] Build passed — requires CI verification")
    # Requirement: ELF inspected
    print(f"    [?] ELF inspected — requires inspection run")
    # Requirement: Metadata valid
    print(f"    [?] Metadata valid — requires wheel inspection")
    # Requirement: SHA-256 available
    print(f"    [?] SHA-256 available — requires build artifact")
    # Requirement: Dependencies noted
    print(f"    [?] Dependencies noted — requires recipe review")

    print(f"\n  ⚠️  Actual verification requires M2+ gate completion.")
    return requirements_met


def check_stable_requirements(package: str, version: str, abi: str) -> bool:
    """Check minimum requirements for stable promotion."""
    print(f"\n  Checking stable requirements for {package} {version} ({abi}):")
    requirements_met = True

    # All candidate requirements + device test
    print(f"    [?] Install succeeded — requires device report")
    print(f"    [?] Import succeeded — requires device report")
    print(f"    [?] Smoke test passed — requires device report")
    print(f"    [?] Interpreter restart — requires device report")
    print(f"    [?] App restart — requires device report")
    print(f"    [?] Uninstall succeeded — requires device report")
    print(f"    [?] No app crash — requires device report")
    print(f"    [?] Device report available — requires submission")

    print(f"\n  ⚠️  Actual verification requires device test report.")
    return requirements_met


def promote_release(
    package: str, version: str, abi: str,
    channel: str, dry_run: bool,
) -> bool:
    """Execute promotion."""
    print(f"\n{'=' * 50}")
    print(f"  ZABAWHEELS Release Promotion")
    print(f"  Package: {package}")
    print(f"  Version: {version}")
    print(f"  ABI: {abi}")
    print(f"  Target channel: {channel}")
    print(f"{'=' * 50}\n")

    # Find current channel
    current_channel = None
    for ch in CHANNEL_ORDER:
        manifest_path = INDEX_DIR / ch / f"{package}-{version}-{abi}.json"
        if manifest_path.exists():
            current_channel = ch
            break

    if current_channel:
        print(f"  Current channel: {current_channel}")
        if not check_promotion_rules(current_channel, channel):
            return False
    else:
        print(f"  ℹ️  No existing manifest found — assuming first promotion")

    # Check requirements
    if channel == "candidate":
        check_candidate_requirements(package, version, abi)
    elif channel == "stable":
        check_stable_requirements(package, version, abi)
    elif channel == "revoked":
        print(f"  ⚠️  Revocation requires documented security issue or breakage.")

    if dry_run:
        print(f"\n  ⚠️  DRY RUN — No actual promotion performed.")
        return True

    print(f"\n  ⚠️  Actual promotion requires CI and device verification.")
    return True


def main():
    parser = argparse.ArgumentParser(description="ZABAWHEELS release promotion")
    parser.add_argument("--package", required=True, help="Package name")
    parser.add_argument("--version", required=True, help="Package version")
    parser.add_argument("--abi", required=True,
                        choices=["armeabi-v7a", "arm64-v8a"],
                        help="Target ABI")
    parser.add_argument("--channel", required=True,
                        choices=["experimental", "candidate", "stable", "revoked"],
                        help="Target channel")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate without actual promotion")
    parser.add_argument("--reason", default=None,
                        help="Reason for revocation (required for revoked channel)")

    args = parser.parse_args()

    if args.channel == "revoked" and not args.reason:
        print("❌ Revocation requires a reason (--reason)")
        sys.exit(1)

    success = promote_release(
        args.package, args.version, args.abi,
        args.channel, args.dry_run
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
