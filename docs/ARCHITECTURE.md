# ZABAWHEELS Architecture

> **Status:** Pre-Alpha (M0)

## Overview

ZABAWHEELS is a **curated Android wheelhouse** for Zabacode. It provides the infrastructure for cross-compiling, validating, publishing, and indexing Python native wheels that work on Android ARMv7/ARM64.

The system follows a strict pipeline:

```text
Source package → Recipe → Cross-compile → Inspect → Manifest → Index → ZabaPip → Android runtime
```

## Two-Repository Architecture

### ZABAWHEELS (this repository)

Responsible for:
- Build recipes and patches
- Cross-compilation pipeline (GitHub Actions CI)
- Wheel validation and ELF inspection
- Package manifest generation
- Package index (GitHub Pages)
- Device test record collection
- Release artifact publishing (GitHub Releases)

### ZABACODE (consumer repository)

Responsible for:
- Runtime fingerprint export
- ZabaPip — transactional package installer
- Dependency resolution
- Package download, SHA-256 verification, installation
- Import smoke test, uninstall, rollback
- ZMUX command integration

## Key Principles

### Truth-first

Every package status has clear meaning. "Build successful" ≠ "working on Android". Status progression:

```text
planned → researching → recipe-ready → building → built → inspected
→ installable → imported → smoke-passed → device-verified → stable
```

Failure paths: `broken`, `blocked`, `deprecated`, `revoked`.

### Runtime-locked

Each native wheel is compatible with exactly one runtime contract:

```text
Python version + ABI + SOABI + p4a commit + NDK version + min API + dependencies
= one compatibility contract (runtime_id)
```

### ARMv7-first, not ARMv7-only

ARMv7 is the primary device verification target. ARM64 wheels are built via CI but labeled `build-only / unverified` until device-tested.

### CI builds, phone validates

| Component | Role |
|---|---|
| GitHub Actions | Cross-compile, lint, inspect, publish |
| Infinix Smart 9 HD | ARMv7 runtime validation |
| ZABAWHEELS | Recipes, manifests, index, provenance |
| ZABACODE | Installer, resolver, runtime diagnostics |

## Repository Structure

```text
ZABAWHEELS/
├── .github/           # Issue templates & CI workflows (pinned SHA)
├── toolchain/         # Runtime lock, source lock, build Dockerfile
├── packages/          # Package recipes, source, tests
├── scripts/           # Build, inspect, manifest, index scripts
├── schemas/           # JSON schema validation
├── index/             # Package index per release channel
├── tests/             # Repository validation tests
└── docs/              # Documentation
```

## Runtime ID Format

```text
zabacode-py<python>-api<minapi>-p4a<revision>-r<generation>
```

Example: `zabacode-py312-api26-p4aXXX-r1`

A new generation is required when:
- CPython minor version changes
- SOABI or extension suffix changes
- p4a ABI changes
- NDK major version changes
- Build flags affecting ABI change

## Compatibility Contract

Every wheel artifact must specify:
- `runtime_id` — exact runtime it targets
- `abi` — armeabi-v7a or arm64-v8a
- `android_min_api` — minimum Android API
- `python_tag` — CPython version tag
- `sha256` — artifact hash for verification

ZabaPip must reject:
- Wrong ABI wheel
- Wrong runtime wheel
- Hash mismatch
- Corrupted download
