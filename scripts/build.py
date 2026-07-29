#!/usr/bin/env python3
"""
ZABAWHEELS build.py — Cross-compile package into Android wheel.

This script orchestrates the cross-compilation build process.
The runtime contract is locked to toolchain/runtime-lock.json.
Cross-compile env vars are derived from p4a's Arch.get_env() output
but are set manually — no p4a import is required at build time.

Usage:
    python scripts/build.py --package zaba-native-smoke --version 0.1.0 --abi armeabi-v7a --channel experimental
    python scripts/build.py --package zaba-native-smoke --version 0.1.0 --abi armeabi-v7a --dry-run
"""

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = REPO_ROOT / "packages"
TOOLCHAIN_DIR = REPO_ROOT / "toolchain"
SCRIPTS_DIR = REPO_ROOT / "scripts"
PACKAGE_NAME = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")

try:
    from scripts.verify_source_lock import local_source_files, local_source_hash
except ModuleNotFoundError:
    from verify_source_lock import local_source_files, local_source_hash

# ---------------------------------------------------------------------------
# Recipe & runtime-lock loaders
# ---------------------------------------------------------------------------

def package_directory(package_name: str) -> Path:
    """Resolve an allowlisted package directory without permitting traversal."""
    if not PACKAGE_NAME.fullmatch(package_name):
        print(f"❌ Invalid package name: {package_name!r}")
        sys.exit(1)
    package_dir = (PACKAGES_DIR / package_name).resolve()
    if PACKAGES_DIR.resolve() not in package_dir.parents:
        print(f"❌ Package path escapes packages directory: {package_name!r}")
        sys.exit(1)
    return package_dir


def load_recipe(package_name: str) -> dict:
    """Load recipe.yaml for a package."""
    import yaml  # noqa: F811

    recipe_path = package_directory(package_name) / "recipe.yaml"
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


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

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
        return False

    return True


# ---------------------------------------------------------------------------
# NDK / Python distribution discovery
# ---------------------------------------------------------------------------

def find_ndk() -> Path:
    """Find the Android NDK installation directory."""
    # 1. ANDROID_NDK_HOME env var
    env_home = os.environ.get("ANDROID_NDK_HOME")
    if env_home:
        p = Path(env_home)
        if p.is_dir():
            return p

    # 2. Inside Android SDK
    sdk_root = os.environ.get("ANDROID_SDK_ROOT", os.environ.get("ANDROID_HOME", ""))
    if sdk_root:
        ndk_dir = Path(sdk_root) / "ndk"
        if ndk_dir.is_dir():
            versions = sorted(ndk_dir.iterdir(), reverse=True)
            for v in versions:
                if v.is_dir():
                    return v

    # 3. Buildozer default
    home = Path.home()
    bozer_ndk = home / ".buildozer" / "android" / "platform" / "android-ndk"
    if bozer_ndk.is_dir():
        versions = sorted(bozer_ndk.iterdir(), reverse=True)
        for v in versions:
            if v.is_dir():
                return v

    print("❌ Android NDK not found. Set ANDROID_NDK_HOME or run buildozer first.")
    sys.exit(1)


def find_python_dist(abi: str) -> Path:
    """Find the cross-compiled Python distribution from buildozer output.

    Searches for the 'android-build' directory that contains include/ and lib/
    for the target ABI.
    """
    home = Path.home()
    search_roots = [
        home / ".buildozer" / "android" / "platform",
        REPO_ROOT / "app" / ".buildozer" / "android" / "platform",
    ]

    # Also check ANDROID_BUILD_DIR if set
    custom = os.environ.get("ANDROID_BUILD_DIR")
    if custom:
        search_roots.append(Path(custom))

    for root in search_roots:
        if not root.is_dir():
            continue
        # Pattern: build-{abi}/build/other_builds/python3/{abi}__ndk_target_*/python3/android-build
        pattern = f"**/other_builds/python3/{abi}*/python3/android-build"
        matches = sorted(root.glob(pattern), reverse=True)
        if matches:
            return matches[0]

    print(f"❌ Python distribution for {abi} not found.")
    print("   Run buildozer first to build the Python distribution,")
    print("   or set ANDROID_BUILD_DIR to the build output directory.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Cross-compile environment builder
# ---------------------------------------------------------------------------

# Target triplet → ABI mapping
ABI_CONFIG = {
    "armeabi-v7a": {
        "target": "armv7a-linux-androideabi{ndk_api}",
        "command_prefix": "arm-linux-androideabi",
        "arch_cflags": [
            "-march=armv7-a",
            "-mfloat-abi=softfp",
            "-mfpu=vfp",
            "-mthumb",
            "-fPIC",
        ],
        "platform_tag": "android_{ndk_api}_arm",
    },
    "arm64-v8a": {
        "target": "aarch64-linux-android{ndk_api}",
        "command_prefix": "aarch64-linux-android",
        "arch_cflags": [
            "-march=armv8-a",
            "-fPIC",
        ],
        "platform_tag": "android_{ndk_api}_arm64_v8a",
    },
}


def build_cross_compile_env(
    abi: str,
    ndk: Path,
    python_dist: Path,
    lock: dict,
) -> dict:
    """Build the cross-compile environment for the target ABI.

    Derived from p4a's Arch.get_env() and CythonRecipe.get_recipe_env(),
    but set manually without importing p4a.
    """
    if abi not in ABI_CONFIG:
        print(f"❌ Unsupported ABI: {abi}")
        sys.exit(1)

    cfg = ABI_CONFIG[abi]
    ndk_api = lock.get("android", {}).get("min_api", 26)
    python_version = lock.get("python", {}).get("version", "3.14.2")
    python_short = "".join(python_version.split(".")[:2])  # e.g. "314"

    # NDK paths
    llvm_bin = ndk / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64" / "bin"
    sysroot = ndk / "toolchains" / "llvm" / "prebuilt" / "linux-x86_64" / "sysroot"
    sysroot_include = sysroot / "usr" / "include"

    # Target triple
    target = cfg["target"].format(ndk_api=ndk_api)

    # Python paths
    python_includes = python_dist / "include" / f"python{python_version}"
    python_lib_dir = python_dist / "lib"

    # NDK arch-specific lib dir
    command_prefix = cfg["command_prefix"]
    ndk_lib_dir = sysroot / "usr" / "lib" / command_prefix / str(ndk_api)

    # Verify key paths exist
    if not llvm_bin.is_dir():
        print(f"❌ NDK LLVM bin dir not found: {llvm_bin}")
        sys.exit(1)
    if not python_includes.is_dir():
        print(f"❌ Python includes not found: {python_includes}")
        print(f"   python_dist = {python_dist}")
        sys.exit(1)

    # Compiler paths
    cc = str(llvm_bin / f"{target}-clang")
    cxx = str(llvm_bin / f"{target}-clang++")

    # Common flags (from p4a Arch.get_env)
    common_cflags = [f"-target {target}", "-fomit-frame-pointer"]
    arch_cflags = cfg["arch_cflags"]
    all_cflags = " ".join(common_cflags + arch_cflags)

    # CPPFLAGS (from p4a Arch.get_env)
    cppflags = " ".join([
        "-DANDROID",
        f"-I{sysroot_include}",
        f"-I{python_includes}",
    ])

    # LDFLAGS (from p4a Arch.get_env + CythonRecipe.get_recipe_env)
    ldflags = " ".join([
        f"-L{python_lib_dir}",
        f"-L{ndk_lib_dir}",
        f"-lpython{python_short}",
        "-lm",
    ])

    # LDSHARED (from p4a Arch.get_env)
    ldshared = " ".join([
        cc,
        "-pthread",
        "-shared",
        "-Wl,-O1",
        "-Wl,-Bsymbolic-functions",
    ])

    env = {
        "CC": cc,
        "CXX": cxx,
        "AR": str(llvm_bin / "llvm-ar"),
        "RANLIB": str(llvm_bin / "llvm-ranlib"),
        "STRIP": f"{llvm_bin / 'llvm-strip'} --strip-unneeded",
        "READELF": str(llvm_bin / "llvm-readelf"),
        "CFLAGS": all_cflags,
        "CXXFLAGS": all_cflags,
        "CPPFLAGS": cppflags,
        "LDFLAGS": ldflags,
        "LDSHARED": ldshared,
        "LDLIBS": "-lm",
        # Tell setuptools we're cross-compiling for Android
        "_PYTHON_HOST_PLATFORM": f"{command_prefix}",
        # Prevent Python from finding host packages
        "PYTHONPATH": "",
        # Reproducible builds
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
    }

    # Add SOURCE_DATE_EPOCH if available
    if "SOURCE_DATE_EPOCH" in os.environ:
        env["SOURCE_DATE_EPOCH"] = os.environ["SOURCE_DATE_EPOCH"]
        env["PYTHONHASHSEED"] = "0"

    return env


# ---------------------------------------------------------------------------
# Build execution
# ---------------------------------------------------------------------------

def prepare_source(package: str, recipe: dict, build_dir: Path) -> Path:
    """Prepare source code in the build directory."""
    source_url = recipe.get("source_url")

    if source_url == "local":
        # Copy from packages/{package}/
        pkg_dir = PACKAGES_DIR / package
        if not pkg_dir.is_dir():
            print(f"❌ Local source directory not found: {pkg_dir}")
            sys.exit(1)

        dest = build_dir / package
        if dest.is_dir():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        for source in local_source_files(pkg_dir):
            relative = source.relative_to(pkg_dir)
            target = dest / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        print(f"  ✓ Verified local source copied to: {dest}")
        return dest

    # TODO: Download external source + verify SHA-256
    print(f"❌ External source download not yet implemented")
    sys.exit(1)


def run_cmd(cmd: list, env: dict = None, cwd: str = None, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        cmd,
        env=run_env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def build_wheel(
    source_dir: Path,
    abi: str,
    env: dict,
    lock: dict,
    output_dir: Path,
) -> Path:
    """Build the wheel using pip wheel with cross-compile env."""
    python_version = lock.get("python", {}).get("version", "3.14.2")
    python_short = "".join(python_version.split(".")[:2])
    ndk_api = lock.get("android", {}).get("min_api", 26)
    cfg = ABI_CONFIG[abi]
    platform_tag = cfg["platform_tag"].format(ndk_api=ndk_api)

    # Create a dist-extra-config for platform tag override
    config_dir = source_dir / "_zmux_build"
    config_dir.mkdir(exist_ok=True)
    config_file = config_dir / "build-opts.cfg"
    config_file.write_text(f"[bdist_wheel]\nplat_name={platform_tag}\n")

    # Extend env with our build config
    build_env = dict(env)
    build_env["DIST_EXTRA_CONFIG"] = str(config_file)

    # Build using pip wheel --no-build-isolation
    # This uses the host Python's build system but with our cross-compile env
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Building wheel for {abi}...")
    print(f"    CC      = {build_env.get('CC', 'not set')}")
    print(f"    CFLAGS  = {build_env.get('CFLAGS', 'not set')}")
    print(f"    LDFLAGS = {build_env.get('LDFLAGS', 'not set')}")
    print(f"    LDSHARED= {build_env.get('LDSHARED', 'not set')}")
    print(f"    plat    = {platform_tag}")

    result = run_cmd(
        [
            sys.executable, "-m", "pip", "wheel",
            str(source_dir),
            "--wheel-dir", str(output_dir),
            "--no-build-isolation",
            "--no-deps",
            "--no-clean",
        ],
        env=build_env,
        cwd=str(source_dir),
        timeout=600,
    )

    if result.returncode != 0:
        print(f"  ❌ pip wheel failed:")
        print(f"     stdout: {result.stdout[-2000:] if result.stdout else '(empty)'}")
        print(f"     stderr: {result.stderr[-2000:] if result.stderr else '(empty)'}")
        return None

    # Find the built wheel
    wheels = sorted(output_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not wheels:
        print(f"  ❌ No wheel file produced in {output_dir}")
        return None

    wheel_path = wheels[0]
    print(f"  ✓ Built wheel: {wheel_path.name}")

    # Fix platform tag if needed (like p4a's install_wheel does)
    try:
        from wheel.cli.tags import tags as wheel_tags
        fixed_name = wheel_tags(str(wheel_path), platform_tags=platform_tag, remove=True)
        fixed_path = output_dir / fixed_name
        if fixed_path != wheel_path:
            print(f"  ✓ Fixed platform tag: {wheel_path.name} → {fixed_name}")
        return fixed_path
    except ImportError:
        print(f"  ⚠️  'wheel' package not installed — skipping platform tag fix")
        return wheel_path
    except Exception as e:
        print(f"  ⚠️  Platform tag fix failed: {e}")
        return wheel_path


def inspect_artifact(wheel_path: Path, abi: str) -> bool:
    """Run inspect_elf and inspect_wheel on the built wheel."""
    all_ok = True

    # inspect_wheel
    result = run_cmd(
        [sys.executable, str(SCRIPTS_DIR / "inspect_wheel.py"),
         "--wheel", str(wheel_path), "--security"],
        timeout=30,
    )
    if result.returncode != 0:
        print(f"  ⚠️  inspect_wheel issues detected")
        all_ok = False
    else:
        print(f"  ✓ inspect_wheel passed")

    # inspect_elf
    result = run_cmd(
        [sys.executable, str(SCRIPTS_DIR / "inspect_elf.py"),
         "--wheel", str(wheel_path), "--abi", abi],
        timeout=30,
    )
    if result.returncode != 0:
        print(f"  ⚠️  inspect_elf issues detected")
        all_ok = False
    else:
        print(f"  ✓ inspect_elf passed")

    return all_ok


def compute_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# ---------------------------------------------------------------------------
# Main build orchestration
# ---------------------------------------------------------------------------

def run_build(package: str, version: str, abi: str, channel: str, dry_run: bool) -> bool:
    """Execute the build process."""
    print(f"\n{'=' * 60}")
    print(f"  ZABAWHEELS Cross-Compile Build")
    print(f"  Package: {package}")
    print(f"  Version: {version}")
    print(f"  ABI:     {abi}")
    print(f"  Channel: {channel}")
    print(f"{'=' * 60}\n")

    # Step 1: Load recipe
    recipe = load_recipe(package)
    if recipe.get("package") != package:
        print(
            f"❌ Recipe package {recipe.get('package')!r} does not match "
            f"requested package {package!r}."
        )
        return False
    if str(recipe.get("version")) != version:
        print(
            f"❌ Recipe version {recipe.get('version')!r} does not match "
            f"requested version {version!r}."
        )
        return False

    # Step 2: Load runtime lock
    lock = load_runtime_lock()

    # Step 3: Validate recipe
    if not validate_recipe(recipe, abi):
        print("❌ Recipe validation failed.")
        return False

    # Step 4: Validate runtime lock
    if not validate_runtime_lock(lock):
        print("❌ Runtime lock has placeholders. Cannot perform real build.")
        return False

    # Step 5: Check source
    source_url = recipe.get("source_url")
    source_sha256 = recipe.get("source_sha256")
    if source_url == "local":
        actual_source_hash = local_source_hash(package_directory(package))
        if actual_source_hash != source_sha256:
            print(
                "  ❌ Local source hash mismatch: "
                f"expected {source_sha256}, got {actual_source_hash}"
            )
            return False
        print(f"  ✓ Local source package verified: {package}")
    elif not source_url or not source_sha256:
        print(f"  ❌ Source URL or SHA-256 missing")
        return False
    else:
        print(f"  ✓ Source: {source_url}")
        print(f"  ✓ SHA-256: {source_sha256}")

    if dry_run:
        print("\n  ⚠️  DRY RUN — No actual build performed.")
        print("  The following steps would be executed:")
        print("    1. Find NDK and Python distribution")
        print("    2. Build cross-compile environment")
        print("    3. Prepare source in build directory")
        print("    4. Build wheel via pip wheel")
        print("    5. Fix platform tag")
        print("    6. Inspect ELF and wheel")
        print("    7. Generate manifest")
        print("    8. Output artifact")
        return True

    # Step 6: Find NDK
    print(f"\n  Looking for NDK...")
    ndk = find_ndk()
    print(f"  ✓ NDK found: {ndk}")

    # Step 7: Find Python distribution
    print(f"  Looking for Python distribution ({abi})...")
    python_dist = find_python_dist(abi)
    print(f"  ✓ Python dist found: {python_dist}")

    # Step 8: Build cross-compile environment
    print(f"  Building cross-compile environment...")
    env = build_cross_compile_env(abi, ndk, python_dist, lock)
    print(f"  ✓ Cross-compile env ready ({len(env)} vars)")

    # Step 9: Prepare source
    build_dir = REPO_ROOT / "build" / f"{package}-{version}-{abi}"
    print(f"\n  Preparing source in: {build_dir}")
    source_dir = prepare_source(package, recipe, build_dir)

    # Step 10: Build wheel
    output_dir = build_dir / "dist"
    print(f"\n  Building wheel...")
    wheel_path = build_wheel(source_dir, abi, env, lock, output_dir)
    if wheel_path is None:
        print("❌ Wheel build failed.")
        return False

    # Step 11: Inspect artifact
    print(f"\n  Inspecting artifact...")
    inspect_ok = inspect_artifact(wheel_path, abi)
    if not inspect_ok:
        print("  ❌ Artifact inspection failed; refusing to publish the wheel.")
        return False

    # Step 12: Compute SHA-256
    sha256 = compute_sha256(wheel_path)
    size = wheel_path.stat().st_size
    print(f"  ✓ SHA-256: {sha256}")
    print(f"  ✓ Size: {size:,} bytes")

    # Step 13: Generate manifest
    print(f"\n  Generating manifest...")
    manifest_result = run_cmd(
        [
            sys.executable, str(SCRIPTS_DIR / "generate_manifest.py"),
            "--package", package,
            "--version", version,
            "--runtime-id", lock.get("runtime_id", "unknown"),
            "--abi", abi,
            "--channel", channel,
            "--wheel", str(wheel_path),
            "--build-passed",
            "--elf-inspected",
            "--output", str(build_dir / "manifest.json"),
        ],
        timeout=30,
    )
    if manifest_result.returncode == 0:
        print(f"  ✓ Manifest generated")
    else:
        print(f"  ⚠️  Manifest generation failed: {manifest_result.stderr[:200]}")

    # Step 14: Copy artifact to output
    final_output = REPO_ROOT / "dist"
    final_output.mkdir(parents=True, exist_ok=True)
    final_wheel = final_output / wheel_path.name
    shutil.copy2(wheel_path, final_wheel)
    print(f"\n  ✓ Final artifact: {final_wheel}")
    print(f"  ✓ SHA-256: {sha256}")
    print(f"  ✓ Size: {size:,} bytes")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  BUILD SUMMARY")
    print(f"  Package:  {package} {version}")
    print(f"  ABI:      {abi}")
    print(f"  Channel:  {channel}")
    print(f"  Artifact: {final_wheel.name}")
    print(f"  SHA-256:  {sha256}")
    print(f"  Inspect:  {'PASS' if inspect_ok else 'ISSUES'}")
    print(f"{'=' * 60}")

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
