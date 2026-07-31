#!/usr/bin/env python3
"""Cross-compile PRoot + talloc for Android (armeabi-v7a / arm64-v8a).

Adapted from Kai 9000's ``build-proot.sh`` (https://github.com/SimonSchubert/Kai,
Apache-2.0) with the logic kept identical so the same artefacts are produced:

    libproot.so            the PRoot binary, renamed lib*.so so Android
                           extracts it into nativeLibraryDir (W^X-safe exec)
    libproot-loader.so     PRoot's loader ELF (PROOT_LOADER at runtime)
    libproot-loader32.so   the 32-bit loader (arm64-v8a builds only)
    libtalloc.so           talloc, PRoot's allocator dependency

Sources are pinned and re-downloaded on every build (never vendored):
    PRoot   termux/proot @ 4dba3afbf3a63af89b4d9c1a59bf2bda10f4d10f
            (the exact commit Kai pins)
    talloc  deepin-community/talloc @ 2.4.2-1deepin1 (full upstream source
            mirror of talloc 2.4.2, Samba waf build)

Usage:
    python scripts/build_proot_android.py \
        --ndk ~/.buildozer/android/platform/android-ndk-r28c \
        --out app/libs \
        --abis armeabi-v7a,arm64-v8a

Licensing: PRoot is GPL-2.0+ (STMicroelectronics), talloc is LGPL-3.0,
talloc's waf build is Samba's (GPL-3.0 with the runtime exception); this
script only orchestrates their source builds.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

PROOT_COMMIT = "4dba3afbf3a63af89b4d9c1a59bf2bda10f4d10f"
TALLOC_TAG = "2.4.2-1deepin1"
MIN_API = 26
ABI_TRIPLES = {
    "armeabi-v7a": "armv7a-linux-androideabi",
    "arm64-v8a": "aarch64-linux-android",
}
LOADER32_ABI = {"arm64-v8a": "armeabi-v7a", "armeabi-v7a": None}

CROSS_ANSWERS = """Checking uname sysname type: "Linux"
Checking uname machine type: "dontcare"
Checking uname release type: "dontcare"
Checking uname version type: "dontcare"
Checking simple C program: OK
building library support: OK
Checking for large file support: OK
Checking for -D_FILE_OFFSET_BITS=64: OK
Checking for WORDS_BIGENDIAN: OK
Checking for C99 vsnprintf: OK
Checking for HAVE_SECURE_MKSTEMP: OK
rpath library support: OK
-Wl,--version-script support: FAIL
Checking correct behavior of strtoll: OK
Checking correct behavior of strptime: OK
Checking for HAVE_IFACE_GETIFADDRS: OK
Checking for HAVE_IFACE_IFCONF: OK
Checking for HAVE_IFACE_IFREQ: OK
Checking getconf LFS_CFLAGS: OK
Checking for large file support without additional flags: OK
Checking for working strptime: OK
Checking for HAVE_SHARED_MMAP: OK
Checking for HAVE_MREMAP: OK
Checking for HAVE_INCOHERENT_MMAP: OK
Checking getconf large file support flags work: OK
"""


def run(cmd: list, cwd: Path | None = None, env: dict | None = None) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=True)


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"[download] {url}", flush=True)
    with urllib.request.urlopen(url, timeout=120) as response, dest.open("wb") as out:
        shutil.copyfileobj(response, out)
    return dest


def extract(archive: Path, dest: Path) -> Path:
    import tarfile
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(dest)
    members = list(dest.iterdir())
    if len(members) == 1 and members[0].is_dir():
        return members[0]
    return dest


def find_ndk(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    for key in ("ANDROID_NDK_HOME", "ANDROID_NDK_ROOT", "ANDROID_HOME"):
        value = os.environ.get(key)
        if value:
            candidate = Path(value)
            if (candidate / "toolchains" / "llvm").is_dir():
                return candidate
    for base in (Path.home() / ".buildozer" / "android" / "platform",
                 Path.home() / "Android" / "Sdk", Path.home() / "Android" / "sdk"):
        if base.is_dir():
            for candidate in sorted(base.glob("android-ndk-*"), reverse=True):
                if (candidate / "toolchains" / "llvm").is_dir():
                    return candidate
    raise SystemExit("NDK not found: pass --ndk or set ANDROID_NDK_HOME")


def toolchain(ndk: Path) -> Path:
    for tag in (f"{sys.platform}-x86_64", "linux-x86_64", "darwin-x86_64"):
        candidate = ndk / "toolchains" / "llvm" / "prebuilt" / tag / "bin"
        if candidate.is_dir():
            return candidate
    raise SystemExit(f"no llvm prebuilt toolchain under {ndk}")


def build_talloc(src: Path, tc: Path, abi: str, sysroot: Path, jobs: int) -> None:
    triple = ABI_TRIPLES[abi]
    cc = tc / f"{triple}{MIN_API}-clang"
    prefix = sysroot
    if (prefix / "lib" / "libtalloc.so").is_file():
        print(f"[talloc/{abi}] already built, skipping")
        return
    build = src / f"build-talloc-{abi}"
    if build.exists():
        shutil.rmtree(build)
    shutil.copytree(src, build)
    answers = build / "cross-answers.txt"
    answers.write_text(CROSS_ANSWERS, encoding="utf-8")
    env = dict(os.environ)
    env.update({
        "CC": str(cc),
        "AR": str(tc / "llvm-ar"),
        "RANLIB": str(tc / "llvm-ranlib"),
        "STRIP": str(tc / "llvm-strip"),
    })
    run(["./configure", "--prefix", str(prefix), "--disable-rpath",
         "--disable-python", "--cross-compile", "--cross-answers=cross-answers.txt"],
        cwd=build, env=env)
    run(["make", "-j", str(jobs)], cwd=build, env=env)
    run(["make", "install"], cwd=build, env=env)


def build_proot(src: Path, tc: Path, abi: str, sysroot: Path, jobs: int) -> tuple:
    triple = ABI_TRIPLES[abi]
    cc = tc / f"{triple}{MIN_API}-clang"
    build = src / f"build-proot-{abi}"
    if build.exists():
        shutil.rmtree(build)
    shutil.copytree(src, build)
    # Remove HAS_LOADER_32BIT from arch.h — the 32-bit loader is built
    # separately with the 32-bit toolchain (NDK clang has no -m32).
    arch_h = build / "src" / "arch.h"
    text = arch_h.read_text(encoding="utf-8")
    arch_h.write_text(
        "\n".join(line for line in text.splitlines()
                  if "HAS_LOADER_32BIT" not in line) + "\n",
        encoding="utf-8",
    )
    tmp_bin = build / "bin"
    tmp_bin.mkdir(parents=True, exist_ok=True)
    if not (tmp_bin / "readelf").exists():
        (tmp_bin / "readelf").symlink_to(tc / "llvm-readelf")
    loader_dir = build / "loader-out"
    env = dict(os.environ)
    env.update({
        "CC": str(cc),
        "LD": str(cc),
        "STRIP": str(tc / "llvm-strip"),
        "OBJCOPY": str(tc / "llvm-objcopy"),
        "OBJDUMP": str(tc / "llvm-objdump"),
        "CFLAGS": (f"-DARG_MAX=131072 -I{sysroot}/include "
                   "-Wno-error=implicit-function-declaration -Wno-error=int-conversion"),
        "LDFLAGS": f"-L{sysroot}/lib",
        "PATH": f"{tmp_bin}:{os.environ.get('PATH', '')}",
    })
    run(["make", "-C", "src", f"PROOT_UNBUNDLE_LOADER={loader_dir.relative_to(build)}",
         "-j", str(jobs)], cwd=build, env=env)
    out = build / "out"
    out.mkdir(parents=True, exist_ok=True)
    # PROOT_UNBUNDLE_LOADER emits the loader as a separate file; keep the
    # runtime loader from src/loader/loader (the one the app references via
    # PROOT_LOADER). Mirrors Kai exactly.
    for name, src_file in (
        ("libproot.so", build / "src" / "proot"),
        ("libproot-loader.so", build / "src" / "loader" / "loader"),
    ):
        if not src_file.is_file():
            raise SystemExit(f"build did not produce {src_file}")
        shutil.copy2(src_file, out / name)
    shutil.copy2(sysroot / "lib" / "libtalloc.so", out / "libtalloc.so")
    for name in ("libproot.so", "libproot-loader.so", "libtalloc.so"):
        run([str(tc / "llvm-strip"), str(out / name)])
    return build, out, loader_dir


def build_loader32(proot_build: Path, tc: Path, abi: str, out: Path) -> None:
    abi32 = LOADER32_ABI[abi]
    if not abi32:
        return
    triple32 = ABI_TRIPLES[abi32]
    cc32 = tc / f"{triple32}{MIN_API}-clang"
    src_dir = proot_build / "src"
    # LOADER_ADDRESS for the 32-bit arch, read via the C preprocessor.
    probe = subprocess.run(
        [str(cc32), "-dM", "-E", "-x", "c", str(src_dir / "arch.h")],
        capture_output=True, text=True, check=True,
    )
    addr = None
    for line in probe.stdout.splitlines():
        if "LOADER_ADDRESS" in line:
            addr = line.split()[-1]
            break
    if not addr:
        print(f"[loader32/{abi}] WARNING: no LOADER_ADDRESS, skipping")
        return
    print(f"[loader32/{abi}] LOADER_ADDRESS={addr}", flush=True)
    obj = proot_build / f"loader32-{abi}.o"
    asm = proot_build / f"assembly32-{abi}.o"
    run([str(cc32), f"-DLOADER_ADDRESS={addr}", f"-I{src_dir}",
         "-Wall", "-Wextra", "-O2", "-fPIC", "-ffreestanding",
         "-c", str(src_dir / "loader" / "loader.c"), "-o", str(obj)])
    run([str(cc32), f"-I{src_dir}", "-c",
         str(src_dir / "loader" / "assembly.S"), "-o", str(asm)])
    run([str(cc32), "-static", "-nostdlib", "-Wl,-N", f"-Wl,-Ttext={addr}",
         "-o", str(out / "libproot-loader32.so"), str(obj), str(asm)])
    run([str(tc / "llvm-strip"), str(out / "libproot-loader32.so")])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndk", default=None, help="Android NDK root")
    parser.add_argument("--out", default="app/libs", help="output dir")
    parser.add_argument("--abis", default="armeabi-v7a,arm64-v8a")
    parser.add_argument("--work", default=None, help="source/work dir (default: temp)")
    parser.add_argument("--jobs", type=int, default=0)
    args = parser.parse_args()

    ndk = find_ndk(args.ndk)
    tc = toolchain(ndk)
    abis = [a for a in args.abis.split(",") if a]
    jobs = args.jobs or (os.cpu_count() or 4)
    out_root = Path(args.out)
    print(f"NDK: {ndk}\ntoolchain: {tc}\nABIs: {abis}\nout: {out_root}")

    work = Path(args.work) if args.work else Path(tempfile.mkdtemp(prefix="zmux-proot-"))
    work.mkdir(parents=True, exist_ok=True)
    try:
        proot_src = extract(
            download(f"https://codeload.github.com/termux/proot/tar.gz/{PROOT_COMMIT}",
                     work / "proot.tar.gz"),
            work / "proot-src",
        )
        talloc_src = extract(
            download(f"https://codeload.github.com/deepin-community/talloc/tar.gz/refs/tags/{TALLOC_TAG}",
                     work / "talloc.tar.gz"),
            work / "talloc-src",
        )
        for abi in abis:
            sysroot = work / f"sysroot-{abi}"
            print(f"\n=== [{abi}] talloc ===", flush=True)
            build_talloc(talloc_src, tc, abi, sysroot, jobs)
            print(f"=== [{abi}] proot ===", flush=True)
            build, out, _loader_dir = build_proot(proot_src, tc, abi, sysroot, jobs)
            build_loader32(build, tc, abi, out)
            # Reproducible binaries: drop the .comment section that embeds
            # the NDK clang version string (Kai does the same for F-Droid).
            for lib in out.glob("*.so"):
                run([str(tc / "llvm-objcopy"), "--remove-section", ".comment", str(lib)])
            target = out_root / abi
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(out, target)
            print(f"[{abi}] -> {target}:", flush=True)
            for lib in sorted(target.iterdir()):
                print(f"    {lib.name}  {lib.stat().st_size:,} bytes", flush=True)
        print("\nAll builds complete.")
        return 0
    finally:
        if not args.work:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
