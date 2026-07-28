# Compatibility Contract

> **Status:** Pre-Alpha (M0) — runtime fingerprint pending

## Runtime ID

Every Zabacode runtime generation has a unique identifier:

```text
zabacode-py<python>-api<minapi>-p4a<revision>-r<generation>
```

Example: `zabacode-py312-api26-p4aXXX-r1`

⚠️ The actual values are **PENDING** until M1 runtime fingerprint is completed.

## Runtime Manifest

The full runtime contract is defined in `toolchain/runtime-lock.json`:

```json
{
  "runtime_id": "zabacode-pyXXX-api26-p4aXXX-r1",
  "python": {
    "implementation": "CPython",
    "version": "...",
    "soabi": "...",
    "ext_suffix": "..."
  },
  "android": {
    "min_api": 26,
    "target_api": 34,
    "abis": ["armeabi-v7a", "arm64-v8a"]
  },
  "toolchain": {
    "p4a_commit": "...",
    "ndk_version": "...",
    "ndk_api": 26,
    "clang_version": "..."
  }
}
```

**No placeholder values allowed in stable manifests.**

## Runtime Fingerprint (Required)

Before M1, the following must be collected from the Zabacode APK:

```python
import os, platform, struct, sys, sysconfig

report = {
    "python_version": sys.version,
    "implementation": platform.python_implementation(),
    "machine": platform.machine(),
    "pointer_bits": struct.calcsize("P") * 8,
    "platform": sysconfig.get_platform(),
    "soabi": sysconfig.get_config_var("SOABI"),
    "ext_suffix": sysconfig.get_config_var("EXT_SUFFIX"),
    "executable": sys.executable,
    "android_api": os.environ.get("ANDROID_API"),
}
```

Additional required data:
- Device ABI list
- Android release and API level
- App version
- Page size
- Location of `user_packages`
- Accepted extension suffixes
- Runtime library path
- Filesystem and dynamic loading capability

## Generation Changes

A new runtime generation (r2, r3, etc.) is required when:

1. CPython minor version upgrade
2. SOABI or extension suffix changes
3. p4a commit that affects ABI
4. Major NDK version change
5. Minimum NDK/API level change
6. Native library structure change
7. Dynamic loading mechanism change
8. Build flag changes affecting ABI or CPU requirements

**Old wheels must NOT be overwritten with binary from new contract.**

## ABI Compatibility

### armeabi-v7a (ARMv7, 32-bit)

- Primary device: Infinix Smart 9 HD (Android 14 Go)
- Not a primary target of PEP 738
- Build path: Zabacode/p4a-specific
- Status: device-verified (after M2 gate)

### arm64-v8a (ARM64, 64-bit)

- Built via CI (no physical device yet)
- Status: build-only / unverified
- Can be promoted to verified only after receiving valid device test report
- PEP 738 focuses on arm64_v8a as official Android target

## Version Decision Process

Do NOT assume Python version. Follow this order:

1. Inspect current APK runtime version
2. Check ARMv7 build stability
3. Check package recipe availability
4. Choose ONE minor Python version
5. Pin version and toolchain
6. Rebuild APK
7. Verify fingerprint unchanged
8. Start producing native wheels
