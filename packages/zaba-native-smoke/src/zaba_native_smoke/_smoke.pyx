# =============================================================================
# zaba_native_smoke._smoke — Cython native extension
# =============================================================================
# Minimal C extension to prove .so loading works on Android ARMv7/ARM64.
# This provides two functions:
#   - add(a, b): simple integer addition (proves C arithmetic works)
#   - native_runtime_info(): dict with native-level runtime info

import platform
import struct
import sys


def add(int a, int b) -> int:
    """Add two integers using native C arithmetic.
    
    This proves that:
    1. The .so was loaded successfully
    2. C integer operations work
    3. Python-C boundary works
    
    >>> add(20, 22)
    42
    >>> add(0, 0)
    0
    >>> add(-1, 1)
    0
    """
    return a + b


def native_runtime_info() -> dict:
    """Return runtime information collected at native level.
    
    This proves that:
    1. Platform detection works
    2. Memory layout is correct
    3. ABI detection works
    
    >>> info = native_runtime_info()
    >>> info["abi"] in ("armeabi-v7a", "arm64-v8a")
    True
    >>> info["pointer_bits"] in (32, 64)
    True
    """
    return {
        "abi": platform.machine(),
        "pointer_bits": struct.calcsize("P") * 8,
        "platform": sys.platform,
        "python_version": sys.version,
        "native_extension_loaded": True,
    }
