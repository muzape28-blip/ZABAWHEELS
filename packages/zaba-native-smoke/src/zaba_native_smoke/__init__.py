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


# A feasibility probe must never silently fall back to Python: importing this
# package is itself proof that the compiled extension was loaded.
from zaba_native_smoke._smoke import add as _native_add
from zaba_native_smoke._smoke import native_runtime_info


def add(a: int, b: int) -> int:
    """Add two integers through the compiled extension."""
    return _native_add(a, b)


def runtime_info() -> dict:
    """Return runtime information and explicit native-loading evidence."""
    base = _get_runtime_info_dict()
    base.update(native_runtime_info())
    base["native_loaded"] = True
    return base


__all__ = ["add", "runtime_info", "__version__"]
