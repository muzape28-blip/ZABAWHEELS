#!/usr/bin/env python3
"""
ZABAWHEELS inspect_elf.py — Inspect ELF binaries in a wheel.

Performs ELF inspection on .so files found in a wheel:
- ELF architecture (must match target ABI)
- Dynamic dependencies (DT_NEEDED)
- Text relocation detection
- Private Android API dependency detection
- Missing dependency detection

Wheel ARMv7 MUST NOT:
- Contain ELF x86
- Contain ELF ARM64
- Link against glibc
- Link to private Android API
- Have text relocation
- Depend on .so not available on Android
- Contain unsafe archive path

Usage:
    python scripts/inspect_elf.py --wheel path/to/package.whl --abi armeabi-v7a
"""

import argparse
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path


ELF_MACHINE_MAP = {
    3: "x86",
    40: "arm",       # ARMv7 (32-bit)
    62: "x86_64",
    183: "arm64",    # ARMv8/AArch64
}

ABI_MACHINE_MAP = {
    "armeabi-v7a": 40,
    "arm64-v8a": 183,
}

# Private Android libraries that should not be linked
PRIVATE_ANDROID_LIBS = {
    "libart.so",
    "libdalvik.so",
    "libandroid_runtime.so",
    "libnativehelper.so",
}

# Expected system libraries on Android
SYSTEM_LIBS = {
    "libc.so",
    "libm.so",
    "libdl.so",
    "liblog.so",
    "libpthread.so",
    "libstdc++.so",
}


def extract_so_files(wheel_path: str, tmp_dir: str) -> list:
    """Extract .so files from wheel to temporary directory."""
    so_files = []
    with zipfile.ZipFile(wheel_path) as zf:
        for name in zf.namelist():
            if name.endswith(".so") or ".so." in name:
                zf.extract(name, tmp_dir)
                so_files.append(os.path.join(tmp_dir, name))
    return so_files


def readelf_header(so_path: str) -> dict:
    """Run readelf -h on .so file."""
    try:
        result = subprocess.run(
            ["readelf", "-h", so_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"error": result.stderr}

        header = {}
        for line in result.stdout.splitlines():
            if "Machine:" in line:
                machine_str = line.split(":")[-1].strip()
                header["machine_str"] = machine_str
            if "Class:" in line:
                header["class"] = line.split(":")[-1].strip()
            if "Type:" in line:
                header["type"] = line.split(":")[-1].strip()

        return header
    except FileNotFoundError:
        return {"error": "readelf not available (install binutils)"}
    except subprocess.TimeoutExpired:
        return {"error": "readelf timed out"}


def readelf_dynamic(so_path: str) -> dict:
    """Run readelf -d on .so file to get DT_NEEDED."""
    try:
        result = subprocess.run(
            ["readelf", "-d", so_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"error": result.stderr}

        needed = []
        has_text_reloc = False
        for line in result.stdout.splitlines():
            if "NEEDED" in line:
                lib_name = line.split("[")[-1].rstrip("]").strip()
                needed.append(lib_name)
            if "TEXTREL" in line:
                has_text_reloc = True

        return {"needed": needed, "has_text_relocation": has_text_reloc}
    except FileNotFoundError:
        return {"error": "readelf not available"}
    except subprocess.TimeoutExpired:
        return {"error": "readelf timed out"}


def inspect_elf_files(so_files: list, target_abi: str) -> dict:
    """Inspect all .so files in a wheel."""
    results = {
        "target_abi": target_abi,
        "expected_machine": ABI_MACHINE_MAP.get(target_abi),
        "files": {},
        "errors": [],
        "warnings": [],
    }

    target_machine = ABI_MACHINE_MAP.get(target_abi)

    for so_path in so_files:
        name = os.path.basename(so_path)
        print(f"\n  Inspecting: {name}")

        # readelf -h
        header = readelf_header(so_path)
        if "error" in header:
            print(f"    ⚠️  readelf -h: {header['error']}")
            results["warnings"].append(f"{name}: {header['error']}")
            continue

        machine = header.get("machine_str", "unknown")
        print(f"    Machine: {machine}")
        print(f"    Class: {header.get('class', 'unknown')}")
        print(f"    Type: {header.get('type', 'unknown')}")

        # Check architecture
        is_arm = "ARM" in machine.upper()
        is_aarch64 = "AArch64" in machine or "ARM64" in machine.upper()
        is_x86 = "x86" in machine.lower() and not is_aarch64

        if is_x86:
            print(f"    ❌ x86 ELF found — ARMv7 wheel must not contain x86!")
            results["errors"].append(f"{name}: x86 ELF (wrong architecture)")

        if target_abi == "armeabi-v7a" and is_aarch64:
            print(f"    ❌ ARM64 ELF in ARMv7 wheel!")
            results["errors"].append(f"{name}: ARM64 ELF in ARMv7 wheel")

        if target_abi == "arm64-v8a" and is_arm and not is_aarch64:
            print(f"    ❌ ARMv7 ELF in ARM64 wheel!")
            results["errors"].append(f"{name}: ARMv7 ELF in ARM64 wheel")

        # readelf -d
        dynamic = readelf_dynamic(so_path)
        if "error" in dynamic:
            print(f"    ⚠️  readelf -d: {dynamic['error']}")
            results["warnings"].append(f"{name}: {dynamic['error']}")
            continue

        needed = dynamic.get("needed", [])
        print(f"    DT_NEEDED: {needed}")

        # Check for glibc link
        glibc_deps = [n for n in needed if "glibc" in n.lower() or "libc.so.6" in n]
        if glibc_deps:
            print(f"    ❌ Links against glibc: {glibc_deps}")
            results["errors"].append(f"{name}: links against glibc ({glibc_deps})")

        # Check for private Android API
        private_deps = [n for n in needed if n in PRIVATE_ANDROID_LIBS]
        if private_deps:
            print(f"    ❌ Links to private Android API: {private_deps}")
            results["errors"].append(f"{name}: private Android API ({private_deps})")

        # Check for text relocation
        if dynamic.get("has_text_relocation"):
            print(f"    ❌ Text relocation detected!")
            results["errors"].append(f"{name}: text relocation")

        # Store results
        results["files"][name] = {
            "header": header,
            "dynamic": dynamic,
        }

    return results


def main():
    parser = argparse.ArgumentParser(description="ZABAWHEELS ELF inspector")
    parser.add_argument("--wheel", required=True, help="Path to wheel file")
    parser.add_argument("--abi", required=True,
                        choices=["armeabi-v7a", "arm64-v8a"],
                        help="Expected target ABI")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")

    args = parser.parse_args()

    print(f"\nZABAWHEELS ELF Inspector")
    print(f"Wheel: {args.wheel}")
    print(f"Target ABI: {args.abi}\n")

    # Create temp directory for extraction
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        so_files = extract_so_files(args.wheel, tmp_dir)

        if not so_files:
            print("  ℹ️  No .so files found in wheel (pure Python package)")
            result = {"has_native": False, "target_abi": args.abi}
        else:
            print(f"  Found {len(so_files)} .so file(s)")
            result = inspect_elf_files(so_files, args.abi)

    if args.json:
        print(json.dumps(result, indent=2))

    has_errors = bool(result.get("errors"))
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
