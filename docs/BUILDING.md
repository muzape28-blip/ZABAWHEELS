# Building Packages

> **Status:** Pre-Alpha (M0) — actual cross-compilation not yet enabled

## Overview

ZABAWHEELS builds native Python wheels for Android using GitHub Actions CI. The build process is designed to be reproducible, auditable, and secure.

## Current State (M0)

Cross-compilation is **not yet enabled**. The current infrastructure provides:
- ✅ Build scripts (placeholder/dry-run mode)
- ✅ Wheel inspection scripts
- ✅ ELF inspection scripts
- ✅ Manifest generation scripts
- ✅ Index generation scripts
- ✅ CI workflow definitions (pinned SHA)

Missing (requires M1):
- ⬜ Pinned NDK and toolchain
- ⬜ Runtime fingerprint from APK
- ⬜ python-for-Android build environment
- ⬜ Actual cross-compilation capability

## Build Process (Future)

```text
validate recipe
    ↓
download pinned source
    ↓
verify source SHA-256
    ↓
prepare exact toolchain (Docker image matching runtime-lock.json)
    ↓
cross-compile for target ABI
    ↓
build wheel
    ↓
inspect ELF (architecture, DT_NEEDED, text relocation)
    ↓
validate wheel metadata
    ↓
generate manifest
    ↓
upload workflow artifact
```

## Triggering a Build

```sh
# Via GitHub Actions workflow_dispatch
gh workflow run build-package.yml \
  -f package=zaba-native-smoke \
  -f version=0.1.0 \
  -f abi=armeabi-v7a \
  -f channel=experimental

# Or locally (dry-run only)
python scripts/build.py \
  --package zaba-native-smoke \
  --version 0.1.0 \
  --abi armeabi-v7a \
  --channel experimental \
  --dry-run
```

## Build Security Rules

- ✅ GitHub Actions pinned with commit SHA
- ✅ Pull requests from forks CANNOT publish releases
- ✅ Publishing only from protected workflows
- ✅ Package recipes must be in allowlist
- ✅ No raw shell command as workflow input
- ✅ Source must have version and SHA-256
- ✅ No PAT in application or workflow
- ✅ Cache keys include p4a, Python, NDK, ABI, and package version
- ✅ Build logs and manifests saved as artifacts

## Package Allowlist

```text
zaba-native-smoke
xxhash
ujson
regex
```

New packages must be added to the allowlist via pull request.

## Reproducibility

Goal: Two builds from the same source and toolchain produce functionally identical artifacts.

If hash differs due to timestamps or metadata, the cause must be known and documented.
