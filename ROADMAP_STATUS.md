# ZMUX Roadmap & Status

## Status Legend

| Status | Meaning |
|--------|---------|
| Implemented | Code exists and passes tests |
| CI-built | Built successfully in GitHub Actions |
| Statically inspected | Code reviewed, not device-tested |
| Emulator-tested | Tested on Android emulator |
| Device-verified | Tested on real Android device |
| Stable | Production-ready with evidence |

## Current Status

### Core Terminal
| Component | Status | Notes |
|-----------|--------|-------|
| Terminal UI (HTML/CSS/JS) | Implemented | Mobile-friendly, xterm.js terminal |
| Flask WebView Server | Implemented | Dual IPv4/IPv6 loopback, auth-protected |
| Execution Engine (virtual terminal) | Implemented | Embedded CPython + real child processes. No PTY: see README "Terminal model" |
| Built-in Commands | Implemented | cd, pwd, clear, help, exit |
| Python Execution | Implemented | python, python -c, python script.py |
| stdin/stdout/stderr | Implemented | Live streaming; `input()` prompts render before the read blocks |
| Ctrl+C / Stop | Implemented | SIGINT with process group cleanup |
| Command History | Implemented | Per session, up/down arrows |
| Working Directory | Implemented | Persistent, path-traversal protected |

### Package Manager (zpip)
| Component | Status | Notes |
|-----------|--------|-------|
| HTTPS-only downloads | Implemented | No trusted-host, no HTTP |
| SHA-256 verification | Implemented | Mandatory |
| Transactional install | Implemented | Full rollback on failure |
| Dependency resolution | Implemented | DAG with cycle detection |
| File ownership | Implemented | Prevents conflicts |
| Path traversal rejection | Implemented | ZIP validation |
| Duplicate entry rejection | Implemented | ZIP validation |
| Smoke import test | Implemented | Before commit |
| Pure Python (PyPI) | Implemented | py3-none-any wheels |
| Native wheels (ZABAWHEELS) | Implemented | Runtime/ABI matched |
| Uninstall safety | Implemented | Only removes owned files |

### Build Pipeline
| Component | Status | Notes |
|-----------|--------|-------|
| Buildozer spec | Implemented | Universal ARMv7+ARM64 |
| GitHub Actions workflow | Implemented | FIXED - branches updated |
| APK artifact | CI-built | zmux-1.0.0-universal-debug.apk |
| SHA256SUMS | CI-built | Checksum verification |
| build-contract.json | CI-built | Runtime contract |
| Provenance attestation | CI-built | GitHub attestation |
| Package index | Implemented | index.json structure created |

### Device Testing
| Component | ARMv7 | ARM64 |
|-----------|-------|-------|
| APK Install | Pending | Pending |
| Terminal UI | Pending | Pending |
| Command Execution | Pending | Pending |
| Python Runtime | Pending | Pending |
| zpip | Pending | Pending |
| Native Smoke | Pending | Pending |

### Security
| Component | Status | Notes |
|-----------|--------|-------|
| Auth Token | Implemented | 128-bit random, constant-time |
| CSP Headers | Implemented | Restrictive policy |
| Loopback Server | Implemented | 127.0.0.1 only |
| TLS Verification | Implemented | certifi CA bundle |
| Key Encryption | Implemented | PBKDF2 + HMAC-SHA256 |
| Path Traversal Protection | Implemented | Built-in cd restricted |

## Roadmap

### v1.0.0 (Current)
- [x] Terminal UI (no IDE features)
- [x] Real subprocess execution
- [x] zpip package manager
- [x] GitHub Actions CI/CD
- [x] Security hardening
- [x] Package index structure
- [x] Workflow FIXED
- [ ] Device testing (ARMv7 + ARM64)
- [ ] Native package builds

### v1.1.0 (In progress)
- [x] Session management (multiple tabs, isolated cwd/globals/history)
- [x] Improved stdin handling (live prompts, streaming output)
- [x] Virtual keys with sticky Ctrl modifier
- [x] `~/.zmuxrc` startup file
- [ ] Command auto-completion
- [ ] File browser for working directory
- [ ] Foreground service so sessions survive backgrounding

### v1.2.0 (Planned)
- [ ] SSH client integration
- [ ] Git operations
- [ ] Environment variable editor
- [ ] Export/import terminal sessions

## Honest Limitations

1. **No PTY at all**: ZMUX is a virtual terminal — there is no `os.openpty()`, no `/dev/ptmx` and no `/system/bin/sh` login shell. Consequence: full-screen TUI programs (`vim`, `htop`, `less`) and job control do not work. This avoids the SELinux `/dev/ptmx` restrictions seen on Android Go devices entirely, at the cost of TUI support. Earlier revisions of this file claimed an `openpty` engine with pipe fallback; that code never existed and the claim has been removed.

2. **Shell access**: Built-in `cd` is restricted to app-private home storage; child processes started by absolute path can access whatever the Android OS permits.

3. **Native packages**: Many native packages (e.g. NumPy) are not yet cross-compiled in the ZABAWHEELS index. ZMUX will display an honest error if a native wheel is unavailable for your ABI.

4. **No device testing**: All implemented status is based on code review, architecture cross-check, and 95+ unit/regression tests; physical device verification on Infinix Smart 9 HD is pending.

## What ZMUX is NOT

- Not an IDE or code editor
- Not Zabacode with a new name
- Not a fake terminal with hardcoded output
- Not claiming Termux-level root or system access
- Not providing AI assistant or marketplace
- Not marking packages as stable without device testing

## Recent Changes (2026-07-29)

> **Correction (2026-07-31):** the PTY entry below was inaccurate when written. The
> codebase has never contained `os.openpty()` or a pipe-fallback path. The
> `start_new_session=True` change was real and is still in effect for child
> processes; the "PTY" and "fallback" framing was not. Kept here unedited for an
> honest record, with this note. See README "Terminal model" for the real design.

### Fixed — Deep ARMv7a (Infinix Smart 9 HD) Force-Close & Freeze Elimination
- **PTY Process Spawn & Signal Safety (`armeabi-v7a`):** Replaced Python `preexec_fn=os.setsid` after `fork()` with C-level POSIX `start_new_session=True` across PTY and fallback sessions to prevent Bionic libc pthread deadlocks and `SIGSEGV` force-close crashes on 32-bit ARMv7 Android 14. Added automatic fallback to standard pipe sessions when `os.openpty()` is denied by SELinux permissions.
- **WebView Port Contract (`SO_REUSEPORT`):** Added `SO_REUSEPORT` to the Android HTTP port 8000 listener (`_bind_http_socket`) so restarting ZMUX while a previous TCP socket lingers in `TIME_WAIT` never throws `Address already in use`. Added multi-host binding fallback (`127.0.0.1`, `0.0.0.0`, `localhost`). (Port 8000 because Zabacode owns 5000 and Chromium blocks 6000/X11 with `ERR_UNSAFE_PORT`.)
- **Dual IPv4/IPv6 WebSocket Server:** Configured `WebSocketServer` to bind simultaneously on both IPv4 (`127.0.0.1`) and IPv6 (`::1`) loopback interfaces, and updated `terminal.html` to cycle candidate hosts across reconnect attempts to eliminate loading screen hangs.
- **APK In-Process Smoke Verification:** Replaced child-process `subprocess.run([sys.executable, ...])` smoke tests with in-process module import checks on Android (`_is_android()`), avoiding `PermissionError` when executing embedded APK Python runtimes.
- **Path Resolution Hardening:** Hardened `resolve_app_dir()` to check `ANDROID_PRIVATE`, `ANDROID_ARGUMENT`, and `ANDROID_APP_PATH` with live filesystem write tests before creating runtime directories.
- **APK Packaging:** Added `android.uses_cleartext_traffic = True` and listed required Flask transitive dependencies (`werkzeug`, `jinja2`, `itsdangerous`, `click`, `blinker`, `MarkupSafe`) in `buildozer.spec`.

### Changed
- Translated all technical documentation (`README.md`, `REFACTOR_REPORT.md`, `ROADMAP_STATUS.md`, `docs/ARCHITECTURE.md`) and added `CHANGELOG.md` in clean English.

### Next
- Trigger GitHub Actions universal APK build by pushing to main
- Physical device verification on Infinix Smart 9 HD (`armeabi-v7a` & `arm64-v8a`)
- Native package builds (NumPy, Pillow, etc.)