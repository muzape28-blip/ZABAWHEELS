#!/usr/bin/env python3
"""Verify deterministic hashes for repository-local package source payloads."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = ROOT / "toolchain" / "source-lock.json"


def local_source_hash(package_dir: Path) -> str:
    """Hash build inputs only; recipe metadata is excluded to avoid self-reference."""
    files = [package_dir / "pyproject.toml"]
    files.extend(sorted((package_dir / "src").rglob("*")))
    digest = hashlib.sha256()
    for path in files:
        if not path.is_file():
            continue
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
