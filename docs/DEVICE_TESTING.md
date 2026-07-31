# Device Testing

## Status

| Component | ARMv7 | ARM64 |
|-----------|-------|-------|
| APK Install | ⏳ Pending | ⏳ Pending |
| Terminal UI | ⏳ Pending | ⏳ Pending |
| Command Execution | ⏳ Pending | ⏳ Pending |
| Python Runtime | ⏳ Pending | ⏳ Pending |
| zpip Install | ⏳ Pending | ⏳ Pending |
| Native Smoke | ⏳ Pending | ⏳ Pending |

## Test Checklist

### Basic Terminal
- [ ] APK installs and launches
- [ ] Terminal UI renders correctly
- [ ] `echo hello` produces output
- [ ] `python3 --version` works
- [ ] `python3 -c "print(42)"` works
- [ ] `cd` changes directory
- [ ] `pwd` shows correct path
- [ ] `clear` clears screen
- [ ] `help` shows help
- [ ] History navigation works (up/down arrows)
- [ ] Ctrl+C stops running process

### Python Execution
- [ ] Interactive Python REPL works
- [ ] `python3 script.py` runs scripts
- [ ] stdin input works
- [ ] Exit codes are accurate
- [ ] stdout/stderr separated

### Package Manager
- [ ] `zpip list` works
- [ ] `zpip search <name>` works
- [ ] `zpip info <name>` works
- [ ] `zpip install <pure-python-package>` works
- [ ] `zpip uninstall <package>` works
- [ ] `zpip verify <package>` works
- [ ] `zpip doctor` shows runtime info

### Security
- [ ] Path traversal blocked for built-in cd
- [ ] HTTPS-only downloads
- [ ] SHA-256 verified on install
- [ ] Auth token required for API

### Alpine Sandbox (PRoot) — run `gates` in the APK
- [ ] G1 `ptmx`: `/dev/ptmx` openable (PTY possible?)
- [ ] G2 `proot-exec`: `libproot.so` execs from `nativeLibraryDir` (W^X gate)
- [ ] G3 `alpine-boot`: Alpine 3.22.5 boots inside proot
- [ ] G4 `git-clone`: real `git clone` over HTTPS works
- [ ] G5 `apk`: apk-tools runs in the guest
- [ ] `linux-setup` downloads rootfs, verifies SHA-512, extracts atomically
- [ ] `git clone` → `git branch` → `git checkout` normal workflow
- [ ] `linux apk add <pkg>` installs inside the sandbox
- [ ] Ctrl+C interrupts a long `git clone` / `linux` job without freezing
- [ ] 8 sessions each running `git`/`linux` do not corrupt each other

### Performance
- [ ] Terminal responsive on Android Go devices
- [ ] No excessive memory usage
- [ ] No battery drain during idle

## Reporting Results

Use the [Device Test Issue Template](../.github/ISSUE_TEMPLATE/device-test.yml) to report test results.

## Legend

- ✅ Verified — tested on real device
- ⏳ Pending — not yet tested
- ❌ Failed — issue found
- ⚠️ Partial — works with limitations
