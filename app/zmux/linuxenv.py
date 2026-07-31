"""ZMUX Alpine Linux environment — a proot-based userspace Linux sandbox.

Why this exists
---------------
ZMUX is a Python-first virtual terminal: no PTY, no shell language, no TUI
programs, and Android's W^X policy blocks ``execve()`` on anything in the app
home directory. The one place Android *does* allow execution is the APK's
``nativeLibraryDir`` (the read-only ``lib/<abi>/`` extraction). PRoot runs
there: it is a tiny userland binary that emulates ``chroot`` + ``execve`` via
``ptrace`` and ``mmap(PROT_EXEC)`` — which the W^X policy explicitly permits
(``dlopen()``-style loading is not blocked). Bundling ``libproot.so`` in the
APK therefore gives ZMUX a real Alpine Linux userland: real ``git``, ``apk``,
``sh``, without root and without touching the host system.

Provenance (all pinned, all verifiable):
- Alpine minirootfs ``3.22.5`` is downloaded from the official Alpine CDN and
  verified against the official ``sha512`` published in the
  ``alpinelinux/docker-alpine`` ``v3.22`` branch (docker-alpine ships the
  minirootfs plus ``ca-certificates``, so TLS works out of the box).
- PRoot ``4dba3af`` (termux/proot) and talloc ``2.4.2`` are cross-compiled by
  ``scripts/build_proot_android.py`` (NDK) and shipped as ``libproot.so`` /
  ``libtalloc.so`` / ``libproot-loader*.so`` in the APK.
- Alpine 3.23+ is deliberately NOT used: apk-tools 3 calls ``execveat()``,
  which proot cannot translate (Kai 9000 pins 3.22.5 for the same reason).

Licensing note: PRoot is GPL-2.0+ (STMicroelectronics), talloc is LGPL-3.0.
ZMUX is AGPL-3.0; exec'ing a separate GPL binary is distribution-compatible,
and the proot/talloc sources are rebuilt by our own CI from pinned commits.

Public surface used by the terminal:
    status()                       human-readable one-line state
    install(progress=None)         download + verify + extract + bootstrap
    build_command_line(argv, cwd)  proot command line for the pipeline executor
    proot_env()                    extra child env (loader, libs, guest PATH)
    run_gates(print=...)           strict on-device probe (the "gates")
"""
from __future__ import annotations

import contextlib
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

from zmux.net import get_ssl_context
from zmux.paths import APP_DIR, CACHE_DIR, HOME_DIR

#: App version marker for the User-Agent (mirrors zmux.zpip.APP_VERSION).
APP_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Pinned Alpine release (see module docstring for why not 3.23+)
# ---------------------------------------------------------------------------
ALPINE_VERSION = "3.22.5"
ALPINE_BRANCH = "v3.22"
ALPINE_MIRROR = os.environ.get(
    "ZMUX_ALPINE_MIRROR", "https://dl-cdn.alpinelinux.org/alpine"
).rstrip("/")

# Official SHA-512 digests from alpinelinux/docker-alpine branch v3.22
# (checksums.sha512). The download is rejected on any mismatch.
ALPINE_SHA512 = {
    "aarch64": "40ee819e0bab9b92c44a1edd176a3ae1b5020078a50f158d66011ba7be3325653526"
               "dadb4bcb896f7c6544c7cbbfd6904f0287f93ae447b3754e59d7e5679b2e",
    "armv7": "7c27652b0d5c9cd028cc3c6bae05bee48d2be564ac41b4afc8cad221c167b33af8e46c"
             "da822ad0555eff01127dfe4f384f8267709466f6a748131a12664188e2",
    "x86_64": "daf0cedbcbe47f1108bea745a0722e42f0ec0f0c08dd1e8b255234a48f2e5d45d0c96"
              "b437bcf60be2ee7ced261870a736e4831bc55924f73b23756283ecfb29b",
}

#: Guest PATH handed to processes inside the sandbox. The child env is built
#: by zmux.env for Android binaries; inside proot it must be Alpine's PATH or
#: `git`/`apk`/`sh` will not resolve.
GUEST_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
GUEST_HOME = "/root"

#: Host path bound to /root inside the sandbox: the user's ZMUX home.
#: Everything the terminal can `cd` into lives under HOME_DIR, so the whole
#: user workspace is reachable as ~/ inside Alpine.
HOME_BIND = "/root"

MAX_ROOTFS_BYTES = 256 * 1024 * 1024

#: Optional callback receiving progress text (already carriage-returned)
#: while the rootfs downloads. Set by the terminal so `linux-setup` streams
#: instead of blocking silently; left None for CLI callers, who get their
#: own progress lambda.
progress_sink = None

#: Overridable so tests (and power users) can point at an existing rootfs.
_ROOTFS_DIR = Path(os.environ.get("ZMUX_ROOTFS_DIR", APP_DIR / "linux" / "rootfs"))
_STAGING_DIR = APP_DIR / "linux" / ".staging"


# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------
def _is_android() -> bool:
    return any(k in os.environ for k in ("ANDROID_PRIVATE", "ANDROID_ARGUMENT", "ANDROID_APP_PATH"))


def alpine_arch() -> str:
    """Map the running platform to an Alpine minirootfs arch."""
    if _is_android():
        machine = os.uname().machine.lower()
        bits = 32 if sys.maxsize <= 2**32 else 64
        if machine in ("aarch64", "arm64", "arm64-v8a"):
            return "aarch64"
        if machine in ("armv7l", "armv8l", "armeabi-v7a", "arm"):
            return "armv7"
        if machine in ("x86_64", "amd64"):
            return "x86_64"
        return machine
    machine = os.uname().machine.lower()
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    if machine in ("aarch64", "arm64"):
        return "aarch64"
    if machine in ("armv7l", "armv8l"):
        return "armv7"
    return machine


def rootfs_dir() -> Path:
    return _ROOTFS_DIR


def is_installed() -> bool:
    return (rootfs_dir() / "bin" / "busybox").is_file() and (
        rootfs_dir() / "etc" / "alpine-release"
    ).is_file()


def installed_version() -> str:
    try:
        return (rootfs_dir() / "etc" / "alpine-release").read_text("utf-8").strip()
    except OSError:
        return ""


def status() -> str:
    if not is_installed():
        return "Alpine Linux environment: NOT INSTALLED (run `linux-setup`)"
    proot = proot_binary()
    proot_state = "ok" if proot else "missing libproot.so in nativeLibraryDir"
    return (f"Alpine {installed_version()} ({alpine_arch()}) @ {rootfs_dir()}\n"
            f"proot: {proot_state}")


# ---------------------------------------------------------------------------
# PRoot binary + child environment
# ---------------------------------------------------------------------------
def native_library_dir() -> str | None:
    """Android's nativeLibraryDir (where exec is allowed), or None on desktop.

    Uses pyjnius (bundled via buildozer requirements) to read
    ``getApplicationInfo().nativeLibraryDir`` — the same value Kai 9000 reads
    from Kotlin. Falls back to scanning /proc/self/maps for an extracted
    libpython mapping if pyjnius is unavailable.
    """
    if not _is_android():
        return None
    try:
        from jnius import autoclass  # type: ignore
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        value = activity.getApplicationInfo().nativeLibraryDir
        if value:
            return str(value)
    except Exception:
        pass
    try:
        with open("/proc/self/maps", "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if "libpython" in line and "/lib/" in line:
                    path = line.split()[-1]
                    return str(Path(path).parent)
    except OSError:
        pass
    return None


def proot_binary() -> str | None:
    """Absolute path to an executable proot binary, or None."""
    if _is_android():
        lib_dir = native_library_dir()
        if lib_dir:
            candidate = os.path.join(lib_dir, "libproot.so")
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return None
    env_bin = os.environ.get("ZMUX_PROOT_BIN", "")
    if env_bin and os.path.isfile(env_bin) and os.access(env_bin, os.X_OK):
        return env_bin
    return shutil.which("proot")


def proot_env() -> dict:
    """Extra environment variables every proot child needs."""
    extra: dict = {
        "PATH": GUEST_PATH,
        "HOME": GUEST_HOME,
    }
    if _is_android():
        lib_dir = native_library_dir() or ""
        if lib_dir:
            extra["LD_LIBRARY_PATH"] = lib_dir
            extra["PROOT_LOADER"] = os.path.join(lib_dir, "libproot-loader.so")
            extra["PROOT_TMP_DIR"] = str(CACHE_DIR)
    else:
        # Host build of proot links a dynamic libtalloc; the builder writes
        # it next to the binary, so make the loader find it.
        binary = proot_binary()
        if binary:
            neighbor = os.path.dirname(os.path.realpath(binary))
            extra["LD_LIBRARY_PATH"] = neighbor
    return extra


def guest_cwd(host_cwd: Path) -> str:
    """Map a host path (always under HOME_DIR) to its guest path."""
    try:
        rel = Path(host_cwd).resolve().relative_to(HOME_DIR.resolve())
    except ValueError:
        return "/"
    if str(rel) == ".":
        return GUEST_HOME
    return f"{GUEST_HOME}/{rel.as_posix()}"


def _bind_flags() -> list:
    """proot bind flags shared by every invocation."""
    flags = ["-b", "/dev", "-b", "/proc", "-b", "/sys"]
    flags += ["-b", f"{HOME_DIR}:{HOME_BIND}"]
    resolv = Path("/etc/resolv.conf")
    if resolv.is_file():
        flags += ["-b", f"{resolv}:/etc/resolv.conf"]
    return flags


def build_command_line(guest_argv: list, host_cwd: Path,
                       extra_binds: list | None = None) -> str:
    """Return the full proot command line for the pipeline executor.

    ``python_shell`` feeds this string to its subprocess executor, so the
    result gets live streaming, Ctrl+C (killpg), timeouts and exit codes for
    free. ``extra_binds`` are ``src:dst`` pairs appended to the standard
    binds (used by the integration tests to bind a host git binary into a
    rootfs that has not had git installed yet).
    """
    proot = proot_binary()
    if not proot:
        raise RuntimeError(
            "proot is not available in this runtime (libproot.so missing)"
        )
    argv = [proot, "-0", "-r", str(rootfs_dir()), * _bind_flags()]
    for bind in extra_binds or ():
        argv += ["-b", bind]
    argv += ["-w", guest_cwd(host_cwd), *guest_argv]
    return shlex.join(argv)


# ---------------------------------------------------------------------------
# Installation (download -> sha512 verify -> safe extract -> bootstrap)
# ---------------------------------------------------------------------------
def _download_url() -> str:
    arch = alpine_arch()
    expected = ALPINE_SHA512.get(arch)
    if not expected:
        raise RuntimeError(f"No pinned Alpine rootfs for architecture {arch!r}")
    return (f"{ALPINE_MIRROR}/{ALPINE_BRANCH}/releases/{arch}/"
            f"alpine-minirootfs-{ALPINE_VERSION}-{arch}.tar.gz"), expected


def install(progress=None) -> dict:
    """Download, verify and install the Alpine rootfs. Idempotent."""
    if is_installed():
        return {"ok": True, "already": True, "version": installed_version(),
                "path": str(rootfs_dir())}
    url, expected = _download_url()
    arch = alpine_arch()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tarball = CACHE_DIR / f"alpine-minirootfs-{ALPINE_VERSION}-{arch}.tar.gz"

    def _report(text: str) -> None:
        if progress is not None:
            progress(text.replace("\n", "\r\n"))
        elif progress_sink is not None:
            progress_sink(text.replace("\n", "\r\n"))

    _report(f"Downloading Alpine {ALPINE_VERSION} ({arch})…\n")
    digest, total = _hashlib_sha512(), 0
    started = time.monotonic()
    last = 0.0
    request = urllib.request.Request(
        url, headers={"User-Agent": f"ZMUX/{APP_VERSION}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120, context=get_ssl_context()) as response:
            announced = int(response.headers.get("Content-Length", "0") or 0)
            if announced > MAX_ROOTFS_BYTES:
                raise RuntimeError("rootfs tarball exceeds safety limit")
            with tarball.open("wb") as output:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_ROOTFS_BYTES:
                        raise RuntimeError("rootfs tarball exceeds safety limit")
                    digest.update(chunk)
                    output.write(chunk)
                    if progress is not None and time.monotonic() - last >= 0.15:
                        _report(f"  {total / 1048576:5.1f} MiB "
                                f"({total / max(time.monotonic() - started, 1e-6) / 1024:5.1f} KiB/s)\r")
                        last = time.monotonic()
    except Exception as error:
        tarball.unlink(missing_ok=True)
        raise RuntimeError(f"download failed: {error}") from error

    actual = digest.hexdigest()
    if actual != expected:
        tarball.unlink(missing_ok=True)
        raise RuntimeError(
            f"SHA-512 mismatch for Alpine rootfs:\n  expected {expected}\n  actual   {actual}"
        )
    _report("  checksum verified ✓\n")

    _ROOTFS_DIR.parent.mkdir(parents=True, exist_ok=True)
    staging = _STAGING_DIR
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    try:
        _safe_extract(tarball, staging)
        _bootstrap(staging)
        # Atomic swap: never leave a half-installed rootfs at the live path.
        if rootfs_dir().exists():
            shutil.rmtree(rootfs_dir(), ignore_errors=True)
        os.replace(staging, rootfs_dir())
    finally:
        tarball.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)
    return {"ok": True, "already": False, "version": installed_version(),
            "path": str(rootfs_dir())}


def _hashlib_sha512():
    import hashlib
    return hashlib.sha512()


def _safe_extract(tarball: Path, target: Path) -> None:
    """Extract the minirootfs with path-traversal protection."""
    with tarfile.open(tarball, "r:gz") as archive:
        members = []
        total = 0
        for member in archive.getmembers():
            name = member.name
            if name.startswith("/") or ".." in Path(name).parts:
                raise RuntimeError(f"unsafe archive member: {name!r}")
            if member.isfile():
                total += member.size
                if total > MAX_ROOTFS_BYTES:
                    raise RuntimeError("uncompressed rootfs exceeds safety limit")
            members.append(member)
        # Python 3.14 changed the extractall() default filter to "data",
        # which refuses absolute symlink targets — and a busybox-style
        # minirootfs is full of them (usr/bin/yes -> /bin/busybox, ~306
        # links), so `linux-setup` died on-device with "is a link to an
        # absolute path" while desktop CI (3.11, default None) passed.
        # "fully_trusted" is the honest filter here: member *names* are
        # already validated above (no absolute names, no "..", size cap)
        # and the archive itself is SHA-512-pinned to Alpine's official
        # digest, i.e. fully trusted content by construction.
        try:
            archive.extractall(target, members=members, filter="fully_trusted")
        except TypeError:
            # Python < 3.12 (and early patch levels) has no filter kwarg.
            archive.extractall(target, members=members)


def _bootstrap(root: Path) -> None:
    """First-run files every Alpine guest needs to be useful."""
    apk = root / "etc" / "apk"
    apk.mkdir(parents=True, exist_ok=True)
    (apk / "repositories").write_text(
        f"{ALPINE_MIRROR}/{ALPINE_BRANCH}/main\n"
        f"{ALPINE_MIRROR}/{ALPINE_BRANCH}/community\n",
        encoding="utf-8",
    )
    # DNS: prefer the host's resolv.conf; fall back to public resolvers.
    host_resolv = Path("/etc/resolv.conf")
    if host_resolv.is_file():
        try:
            content = host_resolv.read_text("utf-8", errors="replace")
            if content.strip():
                (root / "etc" / "resolv.conf").write_text(content, encoding="utf-8")
        except OSError:
            pass
    resolv = root / "etc" / "resolv.conf"
    if not resolv.is_file():
        resolv.write_text("nameserver 8.8.8.8\nnameserver 1.1.1.1\n", encoding="utf-8")
    # Mark the version so `installed_version()` works even mid-upgrade.
    (root / "etc" / "alpine-release").write_text(
        f"{ALPINE_VERSION}\n", encoding="utf-8"
    ) if not (root / "etc" / "alpine-release").is_file() else None


def uninstall() -> dict:
    """Remove the installed rootfs (keeps cache)."""
    if rootfs_dir().exists():
        shutil.rmtree(rootfs_dir(), ignore_errors=True)
    return {"ok": True, "path": str(rootfs_dir())}


# ---------------------------------------------------------------------------
# Strict on-device probe ("zmux gates") — the acceptance test for this feature
# ---------------------------------------------------------------------------
def run_gates(report=None) -> dict:
    """Run every gate the real device must pass. Nothing here is mocked.

    Returns {name: {"ok": bool, "detail": str}}. ``report`` receives
    ``[PASS]/[FAIL]/[INFO]`` lines as they complete so the terminal streams
    progress. When no reporter is given, progress goes through
    :data:`progress_sink` if the terminal installed one, else ``print``.
    """
    if report is None:
        report = progress_sink if progress_sink is not None else print
    results: dict = {}

    def gate(name, ok, detail):
        results[name] = {"ok": bool(ok), "detail": str(detail)}
        report(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        return bool(ok)

    # G1 — /dev/ptmx: can ZMUX ever be a real PTY terminal?
    try:
        fd = os.open("/dev/ptmx", os.O_RDWR | os.O_NOCTTY)
        os.close(fd)
        gate("ptmx", True, "/dev/ptmx openable — PTY possible")
    except OSError as error:
        gate("ptmx", False, f"/dev/ptmx denied: {error}")

    # G2 — exec from nativeLibraryDir (the W^X gate).
    proot = proot_binary()
    if proot:
        try:
            env = dict(os.environ)
            env.update(proot_env())
            result = subprocess.run([proot, "--version"], capture_output=True,
                                    text=True, timeout=30, env=env)
            detail = (result.stdout or result.stderr).strip().splitlines()
            first = detail[0] if detail else "(no output)"
            gate("proot-exec", result.returncode == 0,
                 f"exec {proot} OK — {first}")
        except Exception as error:
            gate("proot-exec", False, f"exec {proot} failed: {error}")
    else:
        gate("proot-exec", False, "libproot.so not found/executable")

    # G3 — Alpine rootfs boots inside proot.
    if proot and is_installed():
        try:
            line = build_command_line(["/bin/sh", "-c",
                                       "echo zmux-alpine-ok; cat /etc/alpine-release"],
                                      HOME_DIR)
            env = dict(os.environ)
            env.update(proot_env())
            result = subprocess.run(line, shell=True, capture_output=True,
                                    text=True, timeout=60, env=env)
            ok = result.returncode == 0 and "zmux-alpine-ok" in (result.stdout or "")
            gate("alpine-boot", ok,
                 f"Alpine {installed_version()} boots in proot "
                 f"(exit={result.returncode}, out={result.stdout.strip()!r})")
        except Exception as error:
            gate("alpine-boot", False, f"boot failed: {error}")
    else:
        gate("alpine-boot", False,
             "rootfs not installed or proot missing (run `linux-setup` first)")

    # G4 — real `git clone` over HTTPS inside the sandbox. The target lives
    # under HOME_DIR (bound to /root inside the guest) so both the guest git
    # and the host check see the same directory.
    if proot and is_installed():
        target = HOME_DIR / ".zmux-gates-clone"
        shutil.rmtree(target, ignore_errors=True)
        try:
            guest_target = guest_cwd(target)
            line = build_command_line(["/usr/bin/git", "clone", "--depth", "1",
                                       "https://github.com/muzape28-blip/ZABAWHEELS",
                                       guest_target], HOME_DIR)
            env = dict(os.environ)
            env.update(proot_env())
            result = subprocess.run(line, shell=True, capture_output=True,
                                    text=True, timeout=300, env=env)
            files = sum(1 for _ in target.rglob("*")) if target.is_dir() else 0
            stderr_tail = (result.stderr or "").strip().splitlines()[-2:]
            detail = f"git clone over HTTPS: exit={result.returncode}, files={files}"
            if not (result.returncode == 0 and files > 0) and stderr_tail:
                detail += " — " + " / ".join(stderr_tail)
            gate("git-clone", result.returncode == 0 and files > 0, detail)
        except Exception as error:
            gate("git-clone", False, f"clone failed: {error}")
        finally:
            shutil.rmtree(target, ignore_errors=True)
    else:
        gate("git-clone", False, "skipped: proot/rootfs unavailable")

    # G5 — apk tooling present inside the guest (binary level; network update
    # is environment-dependent and reported as INFO, not a gate failure).
    if proot and is_installed():
        try:
            line = build_command_line(["/sbin/apk", "--version"], HOME_DIR)
            env = dict(os.environ)
            env.update(proot_env())
            result = subprocess.run(line, shell=True, capture_output=True,
                                    text=True, timeout=60, env=env)
            gate("apk", result.returncode == 0,
                 (result.stdout or result.stderr).strip())
        except Exception as error:
            gate("apk", False, f"apk check failed: {error}")
    else:
        gate("apk", False, "skipped: proot/rootfs unavailable")

    report("")
    passed = sum(1 for r in results.values() if r["ok"])
    report(f"[INFO] gates passed: {passed}/{len(results)}")
    return results
