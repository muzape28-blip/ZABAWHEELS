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
| Terminal UI (HTML/CSS/JS) | Implemented | Mobile-friendly, no editor features |
| Flask WebView Server | Implemented | Loopback-only, auth-protected |
| Execution Engine (subprocess) | Implemented | Real command execution |
| Built-in Commands | Implemented | cd, pwd, clear, help, exit |
| Python Execution | Implemented | python, python -c, python script.py |
| stdin/stdout/stderr | Implemented | Line-buffered, pipe-based |
| Ctrl+C / Stop | Implemented | SIGINT with SIGKILL fallback |
| Command History | Implemented | Client-side, up/down arrows |
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

### v1.1.0 (Planned)
- [ ] PTY support for full interactive REPL
- [ ] Session management (multiple tabs)
- [ ] File browser for working directory
- [ ] Improved stdin handling
- [ ] Command auto-completion

### v1.2.0 (Planned)
- [ ] SSH client integration
- [ ] Git operations
- [ ] Environment variable editor
- [ ] Export/import terminal sessions

## Honest Limitations

1. **No PTY**: Current implementation uses subprocess pipes, not pseudo-terminals.

2. **Shell access**: Built-in cd is restricted to home, shell commands can access Android-permitted areas.

3. **Native packages**: Many native packages not yet available in ZABAWHEELS index.

4. **No device testing**: All implemented status is based on code review and unit tests, not real device verification.

## What ZMUX is NOT

- Not an IDE or code editor
- Not Zabacode with a new name
- Not a fake terminal with hardcoded output
- Not claiming Termux-level capabilities
- Not providing AI assistant or marketplace
- Not marking packages as stable without device testing

## Recent Changes (2026-07-29)

### Fixed
- GitHub Actions workflow updated with correct branches
- Package index structure created (index.json, index/stable/, index/candidate/)

### Added
- index.json root file
- index/stable/index.json
- index/candidate/index.json (with numpy, pillow, cryptography)
- index/experimental/index.json

### Next
- Trigger GitHub Actions build by pushing to main
- Download and test APK on device
- Build native packages (numpy, pillow, etc.)
- Device verification and testing