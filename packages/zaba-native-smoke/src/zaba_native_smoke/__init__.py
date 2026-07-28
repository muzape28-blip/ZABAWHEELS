"""
zaba_native_smoke — Minimal native extension package for Android feasibility testing.

Purpose: prove that native extension loading works on Zabacode/Android.
This package provides the simplest possible C extension via Cython.

API:
    import zaba_native_smoke
    zaba_native_smoke.add(a, b)     # Returns a + b (native C arithmetic)
    zaba_native_smoke.runtime_info()  # Returns dict with runtime information

Smoke test:
    assert zaba_native_smoke.add(20, 22) == 42
    assert zaba_native_smoke.runtime_info()["abi"] in ("armeabi-v7a", "arm64-v8a")
"""

import platform
import struct
import sys

__version__ = "0.1.0"
__author__ = "muzape28"


def _get_runtime_info_dict():
    """Collect runtime information about the Python environment."""
    return {
        "python_version": sys.version,
        "implementation": platform.python_implementation(),
        "platform": sys.platform,
        "machine": platform.machine(),
        "abi": platform.machine(),  # Will reflect armeabi-v7a or arm64-v8a on Android
        "pointer_bits": struct.calcsize("P") * 8,
    }


# Try to import the native extension
try:
    from zaba_native_smoke._smoke import add, native_runtime_info
    _native_available = True
except ImportError:
    _native_available = False


def add(a: int, b: int) -> int:
    """Add two integers. Uses native C implementation if available."""
    if _native_available:
        return add(a, b)  # type: ignore[no-redef]
    # Fallback for pure Python testing
    return a + b


def runtime_info() -> dict:
    """Return runtime information dict. Uses native info if available."""
    base = _get_runtime_info_dict()
    if _native_available:
        native_info = native_runtime_info()  # type: ignore[no-redef]
        base.update(native_info)
        base["native_loaded"] = True
    else:
        base["native_loaded"] = False
    return base


__all__ = ["add", "runtime_info", "__version__"]
