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
                zf.writestr("test/__init__.py", "duplicate")  # Duplicate
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
