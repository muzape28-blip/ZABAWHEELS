"""Tests for ZMUX zpip package manager."""
import os
import sys
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

APP_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(APP_DIR))


class TestZpipCanonicalize:
    """Test package name canonicalization."""

    def test_valid_names(self):
        from zmux.zpip import canonicalize
        assert canonicalize("requests") == "requests"
        assert canonicalize("Requests") == "requests"
        assert canonicalize("my_package") == "my-package"
        assert canonicalize("my.package") == "my-package"

    def test_invalid_names(self):
        from zmux.zpip import canonicalize
        with pytest.raises(ValueError):
            canonicalize("")
        with pytest.raises(ValueError):
            canonicalize("   ")
        with pytest.raises(ValueError):
            canonicalize(123)


class TestZpipDispatch:
    """Test zpip command dispatch."""

    def test_empty_command(self):
        from zmux.zpip import dispatch
        result = dispatch("zpip")
        assert not result["ok"]
        assert "usage" in result["error"]

    def test_invalid_action(self):
        from zmux.zpip import dispatch
        result = dispatch("zpip invalid_action")
        assert not result["ok"]

    def test_list_command(self):
        from zmux.zpip import dispatch
        result = dispatch("zpip list")
        assert result["ok"]
        assert "packages" in result

    def test_search_command(self):
        from zmux.zpip import dispatch
        result = dispatch("zpip search requests")
        assert result["ok"]
        assert "results" in result

    def test_doctor_command(self):
        from zmux.zpip import dispatch
        result = dispatch("zpip doctor")
        assert "runtime" in result

    def test_install_invalid_name(self):
        from zmux.zpip import dispatch
        result = dispatch("zpip install ")
        assert not result["ok"]


class TestZpipWheelSecurity:
    """Test wheel security validation."""

    def test_sha256_mismatch(self):
        """Test that SHA-256 mismatch is detected."""
        from zmux.zpip import _download
        # This would require a mock server, so we test the validation logic
        with pytest.raises(ValueError, match="SHA-256"):
            # Invalid hash format
            _download("https://example.com/test.whl", "not_a_valid_hash", Path("/tmp/test.whl"))

    def test_http_rejected(self):
        """Test that HTTP (non-HTTPS) is rejected."""
        from zmux.zpip import _download
        with pytest.raises(ValueError, match="HTTPS"):
            _download("http://example.com/test.whl", "a" * 64, Path("/tmp/test.whl"))

    def test_path_traversal_rejected(self):
        """Test that path traversal in wheel is rejected."""
        from zmux.zpip import _safe_members
        
        # Create a malicious wheel
        with tempfile.NamedTemporaryFile(suffix=".whl", delete=False) as f:
            with zipfile.ZipFile(f.name, "w") as zf:
                zf.writestr("test/__init__.py", "")
                zf.writestr("test-1.0.dist-info/WHEEL", "Wheel-Version: 1.0")
                zf.writestr("test-1.0.dist-info/RECORD", "")
                zf.writestr("../etc/passwd", "malicious")  # Path traversal
            
            try:
                with pytest.raises(ValueError, match="Unsafe"):
                    _safe_members(Path(f.name))
            finally:
                os.unlink(f.name)

    def test_duplicate_entries_rejected(self):
        """Test that duplicate ZIP entries are rejected."""
        from zmux.zpip import _safe_members
        
        with tempfile.NamedTemporaryFile(suffix=".whl", delete=False) as f:
            with zipfile.ZipFile(f.name, "w") as zf:
                zf.writestr("test/__init__.py", "first")
                with pytest.warns(UserWarning, match="Duplicate name"):
                    zf.writestr("test/__init__.py", "duplicate")
                zf.writestr("test-1.0.dist-info/WHEEL", "Wheel-Version: 1.0")
                zf.writestr("test-1.0.dist-info/RECORD", "")
            
            try:
                with pytest.raises(ValueError, match="Duplicate"):
                    _safe_members(Path(f.name))
            finally:
                os.unlink(f.name)


class TestRuntimeFingerprint:
    """Test runtime fingerprint."""

    def test_fingerprint_shape(self):
        from zmux.zpip import runtime_fingerprint
        fp = runtime_fingerprint()
        
        assert "schema_version" in fp
        assert "app_version" in fp
        assert "runtime_id" in fp
        assert "python" in fp
        assert "android" in fp
        assert "build_contract" in fp
        assert "paths" in fp
        assert "storage" in fp
        assert "installed" in fp

    def test_python_fields(self):
        from zmux.zpip import runtime_fingerprint
        fp = runtime_fingerprint()
        
        assert "version" in fp["python"]
        assert "implementation" in fp["python"]
        assert "soabi" in fp["python"]
        assert "ext_suffix" in fp["python"]
        assert "pointer_bits" in fp["python"]

    def test_android_fields(self):
        from zmux.zpip import runtime_fingerprint
        fp = runtime_fingerprint()
        
        assert "abi" in fp["android"]
        assert "api" in fp["android"]
        assert fp["android"]["abi"] in ["armeabi-v7a", "arm64-v8a", "x86_64", "x86"]


class TestZpipDatabase:
    """Test installed packages database."""

    def test_load_empty_db(self):
        from zmux.zpip import _load_db
        db = _load_db()
        assert isinstance(db, dict)

    def test_uninstall_not_installed(self):
        from zmux.zpip import uninstall
        result = uninstall("nonexistent_package_xyz")
        assert not result["ok"]
        assert "not managed" in result["error"]

    def test_verify_not_installed(self):
        from zmux.zpip import verify
        result = verify("nonexistent_package_xyz")
        assert not result["ok"]
        assert "not managed" in result["error"]


class TestDependencyCycle:
    """Test dependency cycle detection."""

    def test_cycle_detection(self):
        """Test that dependency cycles are detected."""
        from zmux.zpip import install
        # Simulate a cycle by passing the package in the stack
        result = install("test-package", _stack=("test-package",))
        assert not result["ok"]
        assert "cycle" in result["error"].lower()


class TestNativeLibrariesInstalledReadOnly:
    """Android 14+ safer dynamic code loading requires dlopen()'d files to be
    read-only. Installed .so files must therefore be frozen (0o444) at commit
    time — while upgrades and uninstalls must still work on the frozen files."""

    @staticmethod
    def _write_demo_wheel(destination: Path):
        with zipfile.ZipFile(destination, "w") as zf:
            zf.writestr("demo/__init__.py", "VALUE = 1\n")
            zf.writestr("demo/native.so", b"\x7fELF-demo")
            zf.writestr("demo-1.0.dist-info/WHEEL", "Wheel-Version: 1.0")
            zf.writestr("demo-1.0.dist-info/RECORD", "")

    @staticmethod
    def _prepare(tmp_path: Path, monkeypatch):
        import stat as stat_module  # noqa: F401  (kept local to fixture users)
        from zmux import zpip

        user_packages_dir = tmp_path / "user_packages"
        user_packages_dir.mkdir()
        monkeypatch.setattr(zpip, "USER_PACKAGES_DIR", user_packages_dir)
        monkeypatch.setattr(zpip, "STAGING_DIR", tmp_path / "staging")
        monkeypatch.setattr(zpip, "DOWNLOADS_DIR", tmp_path / "downloads")
        monkeypatch.setattr(zpip, "INSTALLED_DIR", tmp_path / "installed")
        monkeypatch.setattr(zpip, "DB_FILE", tmp_path / "installed" / "packages.json")

        manifest = {
            "name": "demo",
            "version": "1.0",
            "runtime_id": "py3-none-any",
            "abi": "any",
            "channel": "pypi",
            "artifact": {
                "filename": "demo-1.0-py3-none-any.whl",
                "url": "https://example.invalid/demo-1.0-py3-none-any.whl",
                "size": 0,
                "sha256": "a" * 64,
            },
            "dependencies": [],
        }
        monkeypatch.setattr(zpip, "resolve", lambda name, version=None, channel="stable": manifest)

        def fake_download(url, expected_hash, destination):
            TestNativeLibrariesInstalledReadOnly._write_demo_wheel(Path(destination))
            return (123, "a" * 64)

        monkeypatch.setattr(zpip, "_download", fake_download)
        return zpip, user_packages_dir

    def test_so_files_frozen_py_files_writable(self, tmp_path, monkeypatch):
        import stat
        zpip, user_packages_dir = self._prepare(tmp_path, monkeypatch)

        result = zpip.install("demo")
        assert result["ok"], result.get("error")

        so_mode = stat.S_IMODE((user_packages_dir / "demo" / "native.so").stat().st_mode)
        assert so_mode == 0o444, f"expected 0o444, got {oct(so_mode)}"

        py_mode = stat.S_IMODE((user_packages_dir / "demo" / "__init__.py").stat().st_mode)
        assert py_mode & 0o200, "pure-python files must keep normal (writable) permissions"

    def test_reinstall_over_read_only_and_uninstall(self, tmp_path, monkeypatch):
        zpip, user_packages_dir = self._prepare(tmp_path, monkeypatch)

        assert zpip.install("demo")["ok"]
        # Re-install must replace the frozen .so without aborting the commit.
        second = zpip.install("demo")
        assert second["ok"], second.get("error")

        # Uninstall must still be able to remove read-only files.
        removed = zpip.uninstall("demo")
        assert removed["ok"], removed.get("error")
        assert not (user_packages_dir / "demo" / "native.so").exists()
