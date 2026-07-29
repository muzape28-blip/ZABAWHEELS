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
