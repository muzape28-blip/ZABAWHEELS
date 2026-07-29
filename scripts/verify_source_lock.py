#!/usr/bin/env python3
"""Verify deterministic hashes for repository-local package source payloads."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "toolchain" / "source-lock.json"


def local_source_files(package_dir: Path) -> list[Path]:
    """List tracked local-source inputs while avoiding the self-referential recipe."""
    package_dir = package_dir.resolve()
    try:
        relative_package = package_dir.relative_to(ROOT)
    except ValueError as error:
        raise ValueError(f"Local source is outside repository: {package_dir}") from error

    result = subprocess.run(
        ["git", "ls-files", "-z", "--", str(relative_package)],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    files = sorted(
        ROOT / item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item and Path(item.decode("utf-8")).name != "recipe.yaml"
    )
    if not files:
        raise ValueError(f"No tracked source files found for {package_dir}")
    return files


def local_source_hash(package_dir: Path) -> str:
    """Hash every tracked input copied into a repository-local source build."""
    package_dir = package_dir.resolve()
    digest = hashlib.sha256()
    for path in local_source_files(package_dir):
        relative = path.relative_to(package_dir).as_posix().encode("utf-8")
        digest.update(relative + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    data = json.loads(LOCK.read_text("utf-8"))
    failures = []
    for name, package in data.get("packages", {}).items():
        if package.get("source") != "local":
            continue
        actual = local_source_hash(ROOT / package["source_url"])
        if actual != package.get("sha256"):
            failures.append(f"{name}: expected {package.get('sha256')}, got {actual}")
    if failures:
        print("\n".join(failures))
        return 1
    print(f"Verified {len(data.get('packages', {}))} source lock(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
