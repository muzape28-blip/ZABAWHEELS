# Device Testing

> **Status:** Pre-Alpha (M0) — no device tests conducted yet

## Primary Test Device

| Property | Value |
|---|---|
| Model | Infinix Smart 9 HD |
| ABI | armeabi-v7a |
| Android | 14 Go |
| Role | Primary ARMv7 runtime validation |

## Testing Protocol (M2 Gate)

The device test protocol for zaba-native-smoke (and all future packages):

### Installation Test

1. Install APK debug Zabacode
2. Export runtime report
3. Download smoke wheel from candidate release
4. Verify SHA-256
5. Install to staging directory
6. Atomic commit to `user_packages`
7. Run import test

### Functionality Test

8. Call `zaba_native_smoke.add(20, 22)` → must return 42
9. Call `zaba_native_smoke.runtime_info()` → must show correct ABI

### Persistence Test

10. Restart interpreter → import again → must work
11. Restart app → import again → must work

### Cleanup Test

12. Uninstall package → import must fail cleanly
13. Reinstall → package must work again

### Submit Report

14. Export device test report (JSON format per device-report.schema.json)
15. Upload report to GitHub issue or pull request

## M2 Decision

### Result A — Native loading works

Continue with runtime wheel repository model. Expand to real third-party packages.

### Result B — Native loading fails

Do NOT create fake workaround. Use alternative strategy:
- Runtime install only for pure Python
- Native packages bundled when APK is built
- Optional native package pack or APK flavor
- ZabaPip marks native packages as `requires-rebuild`

## ARM64 Testing

ARM64 wheels are built via CI but labeled `build-only` until device-tested.

To verify ARM64:
- Build ARM64 wheel through CI
- Find ARM64 device testers
- Tester submits device report manually
- No automatic telemetry collected
- No personal data stored
- Status upgraded from `build-only` to `device-verified` only after valid report

## Device Report Format

```json
{
  "package": "numpy",
  "version": "x.y.z",
  "runtime_id": "...",
  "device": {
    "model": "...",
    "abi": "arm64-v8a",
    "android": "..."
  },
  "tests": {
    "install": "pass",
    "import": "pass",
    "smoke": "pass",
    "restart": "pass",
    "uninstall": "pass"
  }
}
```

Use the Device Test Report issue template to submit results.
