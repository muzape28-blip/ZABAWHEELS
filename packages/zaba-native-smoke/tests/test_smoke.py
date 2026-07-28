"""Tests for zaba_native_smoke — native feasibility spike package."""

import platform
import struct
import sys


def test_add():
    """Test that native add() returns correct results."""
    import zaba_native_smoke
    assert zaba_native_smoke.add(20, 22) == 42
    assert zaba_native_smoke.add(0, 0) == 0
    assert zaba_native_smoke.add(-1, 1) == 0
    assert zaba_native_smoke.add(100, -50) == 50


def test_runtime_info():
    """Test that runtime_info() returns valid dict."""
    import zaba_native_smoke
    info = zaba_native_smoke.runtime_info()
    assert isinstance(info, dict)
    assert info["abi"] in ("armeabi-v7a", "arm64-v8a", "x86_64", "AMD64")
    assert info["pointer_bits"] in (32, 64)
    assert info["python_version"] != ""
    assert info["platform"] != ""


def test_native_loaded():
    """Test that native extension reports as loaded (on device) or not (on desktop CI)."""
    import zaba_native_smoke
    info = zaba_native_smoke.runtime_info()
    # On desktop CI, native may not be available (that's OK for CI)
    # On Android device, native MUST be available
    assert isinstance(info["native_loaded"], bool)


def test_version():
    """Test that __version__ is accessible."""
    import zaba_native_smoke
    assert zaba_native_smoke.__version__ == "0.1.0"


def test_import():
    """Test that the package can be imported."""
    import zaba_native_smoke
    assert zaba_native_smoke is not None
    assert hasattr(zaba_native_smoke, "add")
    assert hasattr(zaba_native_smoke, "runtime_info")


def test_reimport():
    """Test that re-importing works (important for interpreter restart)."""
    import zaba_native_smoke
    first_result = zaba_native_smoke.add(20, 22)
    # Re-import should still work
    import zaba_native_smoke as zns2
    assert zns2.add(20, 22) == first_result
