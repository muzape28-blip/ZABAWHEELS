"""
ZMUX zpip — Transactional, hash-verifying package manager.

The installer accepts curated ZABAWHEELS manifests first and can optionally use
PyPI *universal* wheels. Native wheels are never guessed: their runtime id and
Android ABI must match the running application.
"""
from __future__ import annotations

import csv
import hashlib
import importlib
import io
import json
import os
import platform
import re
import shlex
import shutil
import struct
import subprocess
import sys
import sysconfig
import tempfile
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from packaging.requirements import InvalidRequirement, Requirement
    from packaging.version import InvalidVersion, Version
except ImportError:
    # Minimal fallback when packaging is not available
    class InvalidRequirement(Exception):
        pass
    class InvalidVersion(Exception):
        pass
    class Requirement:
        def __init__(self, s):
            parts = re.split(r"[><=!~\s]", s, maxsplit=1)
            self.name = parts[0]
            self.specifier = None
    class Version:
        def __init__(self, s):
            self.parts = tuple(int(x) for x in str(s).split(".") if x.isdigit())

from zmux.net import get_ssl_context
from zmux.paths import (
    APP_DIR,
    CACHE_DIR,
    USER_PACKAGES_DIR,
    INSTALLED_DIR,
    DOWNLOADS_DIR,
    STAGING_DIR,
)

APP_VERSION = "1.0.0"
INDEX_URL = os.environ.get(
    "ZMUX_WHEEL_INDEX",
    "https://muzape28-blip.github.io/ZABAWHEELS/index/v1",
).rstrip("/")
MAX_WHEEL_BYTES = 100 * 1024 * 1024
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")

DB_FILE = INSTALLED_DIR / "packages.json"


def canonicalize(name: str) -> str:
    if not isinstance(name, str) or not _NAME.fullmatch(name.strip()):
        raise ValueError("Invalid package name")
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def _is_android() -> bool:
    return any(k in os.environ for k in ("ANDROID_PRIVATE", "ANDROID_ARGUMENT", "ANDROID_APP_PATH"))


def android_abi() -> str:
    machine = platform.machine().lower()
    is_32bit = struct.calcsize("P") * 8 == 32
    if is_32bit and machine in {"aarch64", "arm64", "arm64-v8a", "armv7l", "armv8l", "armeabi-v7a", "arm"}:
        return "armeabi-v7a"
    if machine in {"armv7l", "armv8l", "armeabi-v7a"}:
        return "armeabi-v7a"
    if machine in {"aarch64", "arm64", "arm64-v8a"}:
        return "arm64-v8a"
    return machine


def runtime_fingerprint() -> dict:
    """Build the runtime fingerprint.
    
    Values that can only be known at runtime are marked with 'observed'.
    Build-contract values come from toolchain/runtime-lock.json.
    """
    version = platform.python_version()
    short = "".join(version.split(".")[:2])
    p4a = "5c192d7b7308"
    ndk = "28c"
    
    fp = {
        "schema_version": 1,
        "app_version": APP_VERSION,
        "runtime_id": f"zmux-py{short}-api26-p4a{p4a}-r1",
        "python": {
            "implementation": platform.python_implementation(),
            "version": version,
            "soabi": sysconfig.get_config_var("SOABI") or "",
            "ext_suffix": sysconfig.get_config_var("EXT_SUFFIX") or "",
            "pointer_bits": struct.calcsize("P") * 8,
        },
        "android": {
            "abi": android_abi(),
            "api": int(os.environ.get("ANDROID_API", "0") or 0),
            "release": platform.release(),
        },
        "build_contract": {
            "p4a_commit": p4a,
            "ndk": ndk,
        },
        "paths": {
            "cwd": str(Path.cwd()),
            "user_packages": str(USER_PACKAGES_DIR),
            "home": str(Path.home()),
        },
        "storage": {
            "free_bytes": shutil.disk_usage(str(APP_DIR)).free,
        },
        "installed": list(_load_db().keys()),
    }
    return fp


def _load_db() -> dict:
    try:
        data = json.loads(DB_FILE.read_text("utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_db(data: dict) -> None:
    INSTALLED_DIR.mkdir(parents=True, exist_ok=True)
    temp = DB_FILE.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, DB_FILE)


def _request_json(url: str) -> dict:
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS package metadata is accepted")
    req = urllib.request.Request(url, headers={"User-Agent": f"ZMUX/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=25, context=get_ssl_context()) as response:
        if int(response.headers.get("Content-Length", "0") or 0) > 5 * 1024 * 1024:
            raise ValueError("Package metadata is too large")
        value = json.loads(response.read(5 * 1024 * 1024 + 1))
    if not isinstance(value, dict):
        raise ValueError("Package metadata must be a JSON object")
    return value


def _download(url: str, expected_hash: str, destination: Path) -> tuple:
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS wheel downloads are accepted")
    if not _SHA256.fullmatch(expected_hash):
        raise ValueError("A valid SHA-256 is required")
    request = urllib.request.Request(url, headers={"User-Agent": f"ZMUX/{APP_VERSION}"})
    digest, total = hashlib.sha256(), 0
    with urllib.request.urlopen(request, timeout=90, context=get_ssl_context()) as response:
        announced = int(response.headers.get("Content-Length", "0") or 0)
        if announced > MAX_WHEEL_BYTES:
            raise ValueError("Wheel exceeds the 100 MiB safety limit")
        with destination.open("wb") as output:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_WHEEL_BYTES:
                    raise ValueError("Wheel exceeds the 100 MiB safety limit")
                digest.update(chunk)
                output.write(chunk)
    actual = digest.hexdigest()
    if actual != expected_hash:
        destination.unlink(missing_ok=True)
        raise ValueError(f"SHA-256 mismatch: expected {expected_hash}, got {actual}")
    return total, actual


def _safe_members(wheel: Path) -> list:
    seen = set()
    members = []
    total = 0
    with zipfile.ZipFile(wheel) as archive:
        for member in archive.infolist():
            path = PurePosixPath(member.filename)
            if path.is_absolute() or ".." in path.parts or "" in path.parts:
                raise ValueError(f"Unsafe archive path: {member.filename}")
            if member.filename in seen:
                raise ValueError(f"Duplicate archive member: {member.filename}")
            if member.is_dir():
                continue
            seen.add(member.filename)
            total += member.file_size
            if member.file_size > MAX_WHEEL_BYTES or total > MAX_WHEEL_BYTES * 3:
                raise ValueError("Uncompressed wheel content exceeds safety limit")
            members.append(member)
    if not any(item.filename.endswith(".dist-info/WHEEL") for item in members):
        raise ValueError("Wheel metadata is missing")
    if not any(item.filename.endswith(".dist-info/RECORD") for item in members):
        raise ValueError("Wheel RECORD is missing")
    return members


def _extract(wheel: Path, staging: Path) -> list:
    members = _safe_members(wheel)
    staging_root = staging.resolve()
    with zipfile.ZipFile(wheel) as archive:
        for member in members:
            destination = (staging / member.filename).resolve()
            if destination != staging_root and staging_root not in destination.parents:
                raise ValueError("Wheel attempted to escape staging")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)
    return [item.filename for item in members]


def _manifest_from_curated(name: str, channel: str):
    fp = runtime_fingerprint()
    abi = fp["android"]["abi"]
    runtime_id = fp["runtime_id"]
    try:
        index = _request_json(f"{INDEX_URL}/runtimes/{runtime_id}/{abi}.json")
    except Exception:
        return None
    package = (index.get("packages") or {}).get(name)
    if not isinstance(package, dict) or package.get("channel") != channel:
        return None
    if package.get("runtime_id") != runtime_id or package.get("abi") != abi:
        raise ValueError("Curated wheel does not match this runtime and ABI")
    return package


def _manifest_from_pypi(name: str, version: str = None) -> dict:
    endpoint = f"https://pypi.org/pypi/{urllib.parse.quote(name)}"
    if version:
        endpoint += f"/{urllib.parse.quote(version)}"
    metadata = _request_json(endpoint + "/json")
    selected = None
    for item in metadata.get("urls", []):
        filename = str(item.get("filename", ""))
        if filename.endswith("-py3-none-any.whl"):
            selected = item
            break
    if not selected:
        raise ValueError(
            f"{name} has no universal Python wheel; a runtime-locked ZABAWHEELS build is required"
        )
    digest = (selected.get("digests") or {}).get("sha256", "")
    return {
        "name": name,
        "version": str((metadata.get("info") or {}).get("version", version or "")),
        "runtime_id": "py3-none-any",
        "abi": "any",
        "channel": "pypi",
        "artifact": {
            "filename": selected["filename"],
            "url": selected["url"],
            "size": int(selected.get("size", 0)),
            "sha256": digest,
        },
        "dependencies": list((metadata.get("info") or {}).get("requires_dist") or []),
        "native": {"has_extensions": False, "needed_libraries": []},
        "source": {"url": endpoint, "sha256": "", "license": (metadata.get("info") or {}).get("license", "")},
    }


def resolve(name: str, version: str = None, channel: str = "stable") -> dict:
    normalized = canonicalize(name)
    curated = _manifest_from_curated(normalized, channel)
    if curated:
        return curated
    return _manifest_from_pypi(normalized, version)


def _import_name(name: str) -> str:
    aliases = {
        "beautifulsoup4": "bs4", "pillow": "PIL", "python-dotenv": "dotenv",
        "pyyaml": "yaml", "pyjwt": "jwt",
    }
    return aliases.get(name, name.replace("-", "_"))


def _smoke_test_in_process(staging: Path, module: str) -> None:
    old_path = list(sys.path)
    old_modules = set(sys.modules.keys())
    try:
        if str(staging) not in sys.path:
            sys.path.insert(0, str(staging))
        if str(USER_PACKAGES_DIR) not in sys.path:
            sys.path.insert(1, str(USER_PACKAGES_DIR))
        importlib.invalidate_caches()
        importlib.import_module(module)
    finally:
        sys.path[:] = old_path
        for mod in list(sys.modules.keys()):
            if mod not in old_modules:
                sys.modules.pop(mod, None)


def _smoke_test(staging: Path, package: str) -> None:
    module = _import_name(package)
    if _is_android():
        _smoke_test_in_process(staging, module)
        return
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(staging), str(USER_PACKAGES_DIR), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import importlib; importlib.import_module({module!r})"],
            env=env, capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise ValueError(f"Smoke import failed: {(result.stderr or result.stdout).strip()}")
    except (OSError, PermissionError, FileNotFoundError):
        _smoke_test_in_process(staging, module)


def _manifest_requirements(manifest: dict) -> list:
    requirements = []
    for dep in manifest.get("dependencies") or []:
        try:
            requirement = Requirement(dep)
        except InvalidRequirement:
            continue
        if requirement.marker and not requirement.marker.evaluate():
            continue
        requirements.append(requirement)
    return requirements


def _satisfies(record: Any, requirement) -> bool:
    if not isinstance(record, dict):
        return False
    try:
        return not requirement.specifier or Version(str(record.get("version", ""))) in requirement.specifier
    except InvalidVersion:
        return False


def install(
    name: str,
    version: str = None,
    channel: str = "stable",
    _stack: tuple = (),
) -> dict:
    try:
        package = canonicalize(name)
    except (TypeError, ValueError) as error:
        return {"ok": False, "package": "", "error": str(error), "rolled_back": False}
    if package in _stack:
        chain = " -> ".join((*_stack, package))
        return {"ok": False, "package": package, "error": f"Dependency cycle: {chain}", "rolled_back": True}
    transaction = uuid.uuid4().hex
    staging = STAGING_DIR / transaction
    backup = STAGING_DIR / f"{transaction}.backup"
    wheel = DOWNLOADS_DIR / f"{transaction}.whl"
    committed = []
    previous = []
    new_dependencies = []
    try:
        manifest = resolve(package, version, channel)
        db_before = _load_db()
        for requirement in _manifest_requirements(manifest):
            dependency = canonicalize(requirement.name)
            existing = db_before.get(dependency)
            if _satisfies(existing, requirement):
                continue
            if existing:
                raise ValueError(
                    f"Dependency conflict: installed {dependency} {existing.get('version')} "
                    f"does not satisfy {requirement.specifier}; upgrade it explicitly"
                )
            exact = None
            try:
                specs = list(requirement.specifier)
                if len(specs) == 1 and specs[0].operator == "==" and "*" not in specs[0].version:
                    exact = specs[0].version
            except:
                pass
            dependency_result = install(dependency, exact, channel, (*_stack, package))
            if not dependency_result.get("ok"):
                raise ValueError(
                    f"Dependency {dependency} failed: {dependency_result.get('error', 'unknown error')}"
                )
            new_dependencies.append(dependency)
            installed = _load_db().get(dependency)
            if not _satisfies(installed, requirement):
                raise ValueError(
                    f"Resolved {dependency} {installed.get('version') if installed else ''} "
                    f"does not satisfy {requirement.specifier}"
                )
        artifact = manifest.get("artifact") or {}
        wheel.parent.mkdir(parents=True, exist_ok=True)
        size, digest = _download(str(artifact.get("url", "")), str(artifact.get("sha256", "")), wheel)
        staging.mkdir(parents=True)
        files = _extract(wheel, staging)
        _smoke_test(staging, package)

        db = _load_db()
        old = db.get(package) if isinstance(db.get(package), dict) else {}
        previous = list(old.get("files", []))
        owners = {
            relative: owner
            for owner, record in db.items()
            if owner != package and isinstance(record, dict)
            for relative in record.get("files", [])
        }
        collisions = sorted(set(files) & set(owners))
        if collisions:
            first = collisions[0]
            raise ValueError(f"File ownership conflict: {first} belongs to {owners[first]}")
        backup.mkdir(parents=True)
        for relative in files:
            source = staging / relative
            target = USER_PACKAGES_DIR / relative
            if target.exists() and target.is_file():
                saved = backup / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
            committed.append(relative)
        for obsolete in set(previous) - set(files):
            target = USER_PACKAGES_DIR / obsolete
            if target.is_file():
                target.unlink()
        db[package] = {
            "version": manifest.get("version", ""),
            "runtime_id": manifest.get("runtime_id", ""),
            "abi": manifest.get("abi", ""),
            "channel": manifest.get("channel", channel),
            "files": sorted(files),
            "sha256": digest,
            "size": size,
            "transaction": transaction,
        }
        _save_db(db)
        importlib.invalidate_caches()
        return {
            "ok": True,
            "package": package,
            "version": manifest.get("version"),
            "files": len(files),
            "sha256": digest,
            "dependencies_installed": new_dependencies,
        }
    except Exception as error:
        for relative in reversed(committed):
            target, saved = USER_PACKAGES_DIR / relative, backup / relative
            if saved.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(saved, target)
            elif target.exists():
                target.unlink()
        for dependency in reversed(new_dependencies):
            uninstall(dependency)
        return {"ok": False, "package": package, "error": str(error), "rolled_back": True}
    finally:
        wheel.unlink(missing_ok=True)
        shutil.rmtree(staging, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)


def uninstall(name: str) -> dict:
    package = canonicalize(name)
    db = _load_db()
    record = db.get(package)
    if not isinstance(record, dict):
        return {"ok": False, "error": f"{package} is not managed by zpip"}
    removed = 0
    for relative in record.get("files", []):
        target = (USER_PACKAGES_DIR / relative).resolve()
        base = USER_PACKAGES_DIR.resolve()
        if base in target.parents and target.is_file():
            target.unlink()
            removed += 1
    for path in sorted(USER_PACKAGES_DIR.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir():
            try:
                path.rmdir()
            except OSError:
                pass
    del db[package]
    _save_db(db)
    importlib.invalidate_caches()
    return {"ok": True, "package": package, "removed": removed}


def verify(name: str) -> dict:
    package = canonicalize(name)
    record = _load_db().get(package)
    if not isinstance(record, dict):
        return {"ok": False, "error": f"{package} is not managed by zpip"}
    missing = [item for item in record.get("files", []) if not (USER_PACKAGES_DIR / item).is_file()]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(USER_PACKAGES_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        if _is_android():
            old_path = list(sys.path)
            try:
                if str(USER_PACKAGES_DIR) not in sys.path:
                    sys.path.insert(0, str(USER_PACKAGES_DIR))
                importlib.invalidate_caches()
                importlib.import_module(_import_name(package))
                import_ok = True
                error = ""
            finally:
                sys.path[:] = old_path
        else:
            result = subprocess.run(
                [sys.executable, "-c", f"import importlib; importlib.import_module({_import_name(package)!r})"],
                env=env, capture_output=True, text=True, timeout=30,
            )
            import_ok = result.returncode == 0
            error = "" if import_ok else (result.stderr or result.stdout).strip()
    except (OSError, PermissionError, FileNotFoundError):
        old_path = list(sys.path)
        try:
            if str(USER_PACKAGES_DIR) not in sys.path:
                sys.path.insert(0, str(USER_PACKAGES_DIR))
            importlib.invalidate_caches()
            importlib.import_module(_import_name(package))
            import_ok = True
            error = ""
        except Exception as exc:
            import_ok, error = False, str(exc)
        finally:
            sys.path[:] = old_path
    except Exception as exc:
        import_ok, error = False, str(exc)
    return {"ok": not missing and import_ok, "package": package, "missing": missing, "import_ok": import_ok, "error": error}


def list_installed() -> dict:
    return {"ok": True, "packages": _load_db()}


def doctor() -> dict:
    checks = {name: verify(name) for name in _load_db()}
    fingerprint = runtime_fingerprint()
    free = shutil.disk_usage(str(APP_DIR)).free
    return {
        "ok": all(item.get("ok") for item in checks.values()),
        "runtime": fingerprint,
        "free_bytes": free,
        "index": INDEX_URL,
        "packages": checks,
    }


def info(name: str) -> dict:
    package = canonicalize(name)
    installed = _load_db().get(package)
    try:
        available = resolve(package)
        return {"ok": True, "name": package, "installed": installed, "available": available}
    except Exception as error:
        return {"ok": bool(installed), "name": package, "installed": installed, "error": str(error)}


def search(query: str) -> dict:
    needle = canonicalize(query)
    known = set(_load_db()) | {
        "requests", "rich", "click", "sympy", "beautifulsoup4", "tinydb",
        "numpy", "pillow", "matplotlib", "pandas", "xxhash", "ujson", "regex",
    }
    return {"ok": True, "query": needle, "results": sorted(x for x in known if needle in x)}


def format_output(command, result):
    """Turn a structured zpip result into terminal-friendly text.

    Shared by the REST server (zmux.server) and the CLI (zmux.cli) so a zpip
    invocation renders identically no matter which transport carried it.

    Returns a ``(text, exit_code)`` tuple.
    """
    parts = command.strip().split()
    action = parts[1] if len(parts) > 1 else ""

    if action == "verify":
        pkg = result.get("package", parts[2] if len(parts) > 2 else "")
        if result.get("ok"):
            return f"{pkg} is installed and verified", 0
        missing = result.get("missing", [])
        if missing:
            return f"{pkg} verification failed: missing files: {', '.join(missing)}", 1
        error = result.get("error", "unknown error")
        return f"{pkg} verification failed: {error}", 1

    if action == "doctor" and "runtime" in result:
        rt = result.get("runtime", {})
        free = result.get("free_bytes", 0)
        pkgs = result.get("packages", {})
        idx = result.get("index", "unknown")
        lines = [
            "ZMUX Package Manager",
            f"Runtime: {rt.get('runtime_id', 'unknown')}",
            f"Python: {rt.get('python', {}).get('version', 'unknown')}",
            f"ABI: {rt.get('android', {}).get('abi', 'unknown')}",
            f"User packages: {rt.get('paths', {}).get('user_packages', 'unknown')}",
            f"Free storage: {free:,} bytes",
            f"Index: {idx}",
        ]
        if pkgs:
            lines.extend(("", "Installed packages:"))
            for name, status in pkgs.items():
                lines.append(f"  {name}: {'OK' if status.get('ok') else 'FAILED'}")
        return "\n".join(lines), 0 if result.get("ok") else 1

    if not result.get("ok"):
        return f"Error: {result.get('error', 'unknown error')}", 1

    if action == "install":
        pkg = result.get("package", "")
        ver = result.get("version", "")
        deps = result.get("dependencies_installed", [])
        msg = f"Successfully installed {pkg}{f'-{ver}' if ver else ''}"
        if deps:
            msg += f"\nAlso installed: {', '.join(deps)}"
        return msg, 0
    if action == "list":
        pkgs = result.get("packages", {})
        if pkgs:
            return "\n".join(
                f"{name} {record.get('version', '')}" for name, record in pkgs.items()
            ), 0
        return "No packages installed", 0
    if action == "search":
        results = result.get("results", [])
        return "\n".join(results) if results else "No packages found", 0
    if action == "info":
        pkg = result.get("name", "")
        installed = result.get("installed")
        available = result.get("available")
        lines = [f"Package: {pkg}"]
        if installed:
            lines.append(f"Installed: {installed.get('version', 'unknown')}")
        if available:
            lines.append(f"Available: {available.get('version', 'unknown')}")
        return "\n".join(lines), 0
    if action == "uninstall":
        return f"Successfully uninstalled {result.get('package', '')}", 0
    return "Command executed successfully", 0


def format_fingerprint(fp: dict) -> str:
    """Render the runtime fingerprint for the ``zmux-info`` command.

    Shared by the REST server (zmux.server) and the CLI (zmux.cli).
    """
    lines = [
        "ZMUX Runtime Fingerprint",
        "=" * 40,
        f"App version:        {fp['app_version']}",
        f"Python version:     {fp['python']['version']}",
        f"Implementation:     {fp['python']['implementation']}",
        f"SOABI:              {fp['python']['soabi']}",
        f"EXT_SUFFIX:         {fp['python']['ext_suffix']}",
        f"Pointer bits:       {fp['python']['pointer_bits']}",
        f"ABI:                {fp['android']['abi']}",
        f"Android API:        {fp['android']['api']}",
        f"Runtime ID:         {fp['runtime_id']}",
        f"p4a commit:         {fp['build_contract']['p4a_commit']}",
        f"NDK:                {fp['build_contract']['ndk']}",
        f"CWD:                {fp['paths']['cwd']}",
        f"User packages:      {fp['paths']['user_packages']}",
        f"Free storage:       {fp['storage']['free_bytes']:,} bytes",
    ]
    installed = fp["installed"]
    if installed:
        lines.append(f"Installed packages: {', '.join(installed)}")
    else:
        lines.append("Installed packages: (none)")
    return "\n".join(lines)


def dispatch(command: str) -> dict:
    """Dispatch one honest zpip command without invoking a shell."""
    try:
        args = shlex.split(command)
    except ValueError as error:
        return {"ok": False, "error": str(error)}
    if args and args[0] == "zpip":
        args.pop(0)
    if not args:
        return {"ok": False, "error": "usage: zpip search|info|install|list|verify|uninstall|doctor"}
    action, values = args[0], args[1:]
    try:
        if action == "list" and not values:
            return list_installed()
        if action == "doctor" and not values:
            return doctor()
        if action in {"search", "info", "verify", "uninstall"} and len(values) == 1:
            return globals()[action](values[0])
        if action == "install" and len(values) in {1, 2}:
            return install(values[0], values[1] if len(values) == 2 else None)
    except (ValueError, OSError) as error:
        return {"ok": False, "error": str(error)}
    return {"ok": False, "error": f"invalid arguments for zpip {action}"}
