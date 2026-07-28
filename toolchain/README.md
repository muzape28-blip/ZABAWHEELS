# Toolchain Directory

This directory contains the **toolchain lock files** that define the exact build environment for ZABAWHEELS native wheels.

## Files

| File | Purpose |
|---|---|
| `runtime-lock.json` | Pins the exact Python version, ABI, NDK version, p4a commit, and all toolchain components |
| `source-lock.json` | Pins the exact source version and SHA-256 for every tracked package |
| `Dockerfile` | Defines the cross-compilation build environment (CI) |

## Status

⚠️ **M0 — Placeholder state.** All toolchain values are marked as `PENDING` and must be replaced with real values from the APK runtime fingerprint before M1 gate.

## Process

1. **M1**: Export runtime fingerprint from Zabacode APK → fill `runtime-lock.json` with real values
2. **M1**: Pin NDK, p4a, CPython, and all build tool versions
3. **M1**: Freeze `source-lock.json` with exact source hashes
4. After M1: No placeholder values allowed in stable manifests

## Rules

- Every native wheel depends on an exact `runtime_id`
- Runtime ID changes require a new generation (`-r2`, `-r3`, etc.)
- Old wheels must NOT be overwritten with binary from a new contract
- Build image must match pinned toolchain exactly
