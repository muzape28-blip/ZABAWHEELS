# Roadmap delivery status

Updated: 29 July 2026

This file separates **implemented engineering** from evidence that can only be
produced by a physical Android device. A green CI job is not reported as a
physical-device pass.

| Milestone | Delivered in this repository | External evidence still required |
|---|---|---|
| M0 Foundation | Schemas, security tests, pinned Actions, CI, Pages workflow, binary exclusion | Enable Pages/branch protection in repository settings |
| M1 Runtime contract | ZMUX APK build is pinned to CPython 3.14.2, p4a `5c192d…`, NDK 28c, API 26/34 and both ABIs; `/api/runtime` exports the live fingerprint | Compare exported values from installed APK with the lock before publishing native wheels |
| M2 Native spike | Correct Cython package with no fake Python fallback, source lock, smoke test and inspection tooling | Build/install/import/restart test on the Infinix device |
| M3 Build factory | Reproducible APK workflow, checksums, retained artifact, provenance attestation, source/recipe gates | Native wheel publication remains blocked until M2 device evidence |
| M4 Manifest/index | Versioned runtime and per-ABI JSON index, schemas, channel separation, Pages deployment | Public Pages URL depends on repository setting |
| M5 ZabaPip v2 | HTTPS + SHA-256, universal-wheel policy, safe ZIP extraction, staging, import smoke test, owned-file database, upgrade rollback, verify/uninstall/doctor and allowlisted command dispatcher | Interrupted-process and low-storage tests on Android |
| M6–M7 Package ladder | Native probe and catalog/selection policy are present; unsupported native packages fail honestly instead of using a wrong wheel | Third-party native packages need CI artifacts and device reports before promotion |
| M8 ZMUX | Full Android IDE shell is included under `app/`; `zpip` API supports search/info/install/list/verify/uninstall/doctor; APK/application name is **ZMUX** | Touch/UX acceptance test on device |
| M9 Alpha | Versioned `1.0.0` universal debug APK pipeline, diagnostics, tests and rollback implementation | A signed release and ARMv7 report are release-manager/device actions |
| M10 Scientific preview | Compatibility UI/catalog and explicit build-time status prevent false scientific-package installs | Pillow/NumPy/Matplotlib are not claimed working without native artifacts and sustained device tests |
| M11 ARM64 | CI builds a universal ARMv7 + ARM64 APK; report schema is available | Physical ARM64 report |
| M12 Stable | Locked toolchain, versioned index, source hashes, provenance, revocation model, transactional recovery and contributor docs exist | Stable status is intentionally withheld until ARMv7 and ARM64 evidence exists |

## Definition of the GitHub APK deliverable

A successful **Build ZMUX APK** run publishes an artifact named `zmux` containing:

- `zmux-1.0.0-universal-debug.apk`
- `SHA256SUMS`
- `build-contract.json`
- a GitHub build-provenance attestation on non-PR runs

The APK is a universal fat APK for `armeabi-v7a` and `arm64-v8a`, targets API
34, and supports Android API 26+.
