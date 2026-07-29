# ZMUX — Standalone Android Terminal for Python

[![Build ZMUX APK](https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/build-zmux-apk.yml/badge.svg)](https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/build-zmux-apk.yml)
[![Validate Repository](https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/validate.yml/badge.svg)](https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/validate.yml)

**ZMUX** is a standalone Android terminal application for Python development that uses the **ZABAWHEELS** curated wheelhouse infrastructure for package management and reproducible builds.

---

## What is ZMUX?

ZMUX is a lightweight terminal emulator for Android devices that allows you to:
- Execute real interactive shell and Python commands on your mobile device.
- Use `zpip`, a secure, hash-verifying package manager, to install Python packages.
- Work safely inside an app-private sandbox with persistent working directory support.
- Access the bundled Python 3 runtime directly from your Android phone or tablet.

### What ZMUX is NOT
- **Not an IDE or code editor** — ZMUX is purely a command-line terminal environment.
- **Not Zabacode with a new name** — All legacy IDE features (code editors, AI assistants, theme marketplaces) were removed during refactoring.
- **Not a simulated terminal** — Commands execute via real subprocesses and pseudo-terminals (PTY) with actual exit codes and streaming I/O.
- **Not claiming Termux-level root/system access** — ZMUX operates strictly within Android's standard app-private security sandbox.

---

## Key Features

### Real Terminal Execution Engine
- ✅ **PTY & Subprocess Support:** Interactive execution with automatic fallback to standard pipes when POSIX pseudo-terminals are restricted by Android SELinux policies.
- ✅ **Real-Time Streaming I/O:** Bi-directional WebSocket communication between the xterm.js frontend and Python backend.
- ✅ **Process Control:** Ctrl+C / Stop support to cancel running processes cleanly.
- ✅ **Signal & Thread Safety:** Hardened for 32-bit ARMv7 Android (`armeabi-v7a`) and 64-bit ARM (`arm64-v8a`) architectures to prevent force closes or Bionic libc pthread deadlocks.
- ✅ **Persistent Working Directory:** Maintains current working directory across commands with path traversal protection.

### Built-in Commands
```bash
help          # Display available commands
clear         # Clear terminal screen
pwd           # Print current working directory
cd <dir>      # Change directory (restricted to app home)
ls, cat, mkdir, touch, cp, mv, rm, echo, env, which, uname
python        # Launch Python REPL
python <file> # Execute a Python script
python -c "..." # Execute inline Python code
pip           # Standard pip package manager (if installed)
zpip          # ZMUX secure package manager
zmux-info     # Display comprehensive runtime fingerprint
exit          # Exit terminal session
```

### Secure Package Manager (`zpip`)
```bash
zpip search <name>             # Search curated ZABAWHEELS package index
zpip info <name>               # View package details and compatibility
zpip install <name>            # Install verified package
zpip install <name> <version>  # Install specific package version
zpip list                      # List installed packages
zpip verify <name>             # Verify installation integrity against manifest
zpip uninstall <name>          # Cleanly remove package and owned files
zpip doctor                    # Diagnose system health and runtime fingerprint
```

### Security & Hardening
- ✅ **Mandatory SHA-256 Verification:** Every package is checksum-verified before installation.
- ✅ **Loopback-Only Server:** HTTP and WebSocket listeners bind strictly to `127.0.0.1` / `::1`.
- ✅ **Authentication Token:** 128-bit random session token protects backend endpoints against unauthorized local access.
- ✅ **Transactional Installations:** Atomic package installation with full rollback on failure.
- ✅ **Path Traversal Protection:** Rejects ZIP entries or commands attempting directory escape.
- ✅ **Encrypted Storage:** At-rest encryption using AES/HMAC-SHA256 for local state.

---

## APK Specifications & Android Compatibility

- **App Title:** ZMUX
- **Package Name:** `zmux`
- **Application ID:** `com.zaba.zmux`
- **Version:** `1.0.0`
- **Minimum Android API:** 26 (Android 8.0)
- **Target Android API:** 34 (Android 14)
- **Supported ABIs:** `armeabi-v7a` (ARMv7 32-bit), `arm64-v8a` (ARM64 64-bit)
- **Permissions Required:** `INTERNET` only (used for loopback WebView connection and curated index downloads)
- **Telemetry & Ads:** Zero ads, zero telemetry, zero background tracking.

### Verified Mobile Capabilities (`armeabi-v7a` & `arm64-v8a`)
ZMUX has been deeply crosschecked and engineered to run reliably across mobile devices, including entry-level **ARMv7 Android Go** devices (such as the *Infinix Smart 9 HD ARMv7*):
1. **No Boot Freezes:** Hardened port binding (`SO_REUSEPORT`) ensures the Android WebView shell connects immediately without waiting on occupied ports.
2. **No Force Closes on ARMv7:** Replaced unsafe after-fork `preexec_fn` calls with POSIX `start_new_session=True`, avoiding Bionic libc signal crashes.
3. **Resilient WebSocket Reconnection:** Automatically cycles through candidate loopback hosts (`127.0.0.1`, `localhost`, `::1`) to handle OEM network stack variations.

---

## Installation

### Download Universal APK
Download the latest universal APK from [GitHub Actions](https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/build-zmux-apk.yml).

Generated build artifacts include:
- `zmux-1.0.0-universal-debug.apk` — Signed universal APK containing `armeabi-v7a` and `arm64-v8a` libraries.
- `SHA256SUMS` — SHA-256 checksums for provenance verification.
- `build-contract.json` — Pinned runtime contract metadata.

### Build from Source
```bash
cd app
pip install buildozer
buildozer android debug
```
For detailed instructions, see [docs/BUILDING.md](docs/BUILDING.md).

---

## Architecture

```
ZMUX Terminal
├── Backend (Python 3 / Flask / Waitress)
│   ├── server.py          # Flask HTTP WebView server
│   ├── ws_server.py       # Pure-Python RFC-6455 WebSocket server
│   ├── terminal.py        # Subprocess execution engine
│   ├── pty_session.py     # POSIX PTY session manager with pipe fallback
│   ├── zpip.py            # Transactional hash-verifying package manager
│   ├── security.py        # Token authentication
│   ├── keystore.py        # Encrypted local storage
│   └── paths.py           # Hardened app-private directory management
│
├── Frontend (HTML / CSS / JavaScript)
│   └── terminal.html      # Mobile-optimized xterm.js terminal UI
│
└── Infrastructure (ZABAWHEELS)
    ├── index/             # Curated package index (stable, candidate, experimental)
    ├── packages/          # Package recipes and manifests
    ├── schemas/           # JSON Schemas for recipes, manifests, and runtimes
    ├── scripts/           # Verification, inspection, and index generation tools
    └── toolchain/         # Pinned runtime and source lockfiles
```

---

## Honest Limitations

To maintain transparency, ZMUX documents its limitations clearly:
1. **Android SELinux Restrictions:** On some Android 14 Go Edition devices, access to `/dev/ptmx` is restricted by SELinux. ZMUX automatically detects this and falls back to a standard pipe-based shell session.
2. **Directory Scope:** Built-in `cd` commands restrict navigation to app-private storage for security. Subprocess commands (`/system/bin/sh`) can access any directories permitted by the Android OS.
3. **Native Package Availability:** Complex native packages (such as NumPy) require cross-compiled wheels matching the specific Android ABI (`armeabi-v7a` or `arm64-v8a`). `zpip` will display an honest error if a package is not yet built for your runtime.

---

## Documentation & Roadmap

- **[CHANGELOG.md](CHANGELOG.md)** — Detailed record of version releases, ARMv7 fixes, and architectural changes.
- **[ROADMAP_STATUS.md](ROADMAP_STATUS.md)** — Comprehensive component status matrix and upcoming milestones.
- **[REFACTOR_REPORT.md](REFACTOR_REPORT.md)** — Complete audit report detailing the transition from Zabacode IDE to ZMUX Terminal.
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — Technical deep-dive into the WebView port contract and anti-freeze invariants.
- **[docs/SECURITY.md](docs/SECURITY.md)** — Threat model and security mechanisms.
- **[ZABAWHEELS.md](ZABAWHEELS.md)** — Curated wheelhouse specification and engineering roadmap.

---

## Local Development & Testing

### Setup Environment
```bash
cd app
pip install -r requirements-dev.txt
pip install -e .
```

### Run Automated Tests
```bash
# Run 95+ unit and regression tests
PYTHONPATH=. pytest -v app/tests/ tests/
```

### Start Local Desktop Server
```bash
cd app
python main.py
# The ZMUX Terminal server will start on http://127.0.0.1:5000
```

---

## Contributing

We welcome contributions to both the ZMUX terminal app and the ZABAWHEELS package infrastructure!
See **[CONTRIBUTING.md](CONTRIBUTING.md)** for package request guidelines, recipe formatting, and pull request procedures.

---

## License

This project is licensed under the terms of the **[LICENSE](LICENSE)**.

---

**ZMUX / ZABAWHEELS** — Honest, transparent, and reproducible Android Python tooling.
