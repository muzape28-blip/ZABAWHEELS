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
- **Not a fake terminal** — Nothing is hardcoded or mocked. Python runs in the real embedded CPython runtime, external programs are real child processes with real exit codes, and output streams as it is produced.
- **Not a Unix PTY terminal** — ZMUX is a *virtual* terminal: there is no `/dev/ptmx`, no `openpty()`, and no `/system/bin/sh` login shell. See [Terminal model](#terminal-model) for what that does and does not give you.
- **Not claiming Termux-level root/system access** — ZMUX operates strictly within Android's standard app-private security sandbox.

---

## Terminal model

ZMUX is a **virtual terminal**, not a Unix PTY terminal. This is a deliberate design
choice for a Python-for-Android (p4a) app, and it is worth being precise about, because
earlier versions of this README described a POSIX `openpty()` engine that the code has
never contained.

**How it actually works.** The front-end is xterm.js. Keystrokes travel over a WebSocket to
a Python line-discipline layer (`pty_session.py`) that handles echo, backspace, history, and
Ctrl+C. Completed lines go to `python_shell.py`, which either evaluates them in the embedded
CPython runtime or spawns a real child process by absolute path.

**What that gives you**
- Python that behaves like Python: real `exec`/`eval`, persistent globals, real tracebacks.
- Real child processes with real exit codes, real signals, real pipelines and redirection.
- Live streaming output and working `input()`.
- No dependency on `/dev/ptmx`, which some Android Go / SELinux configurations deny to apps.

**What it does not give you**
- **No full-screen TUI programs.** `vim`, `htop`, `nano`, `less` need a real TTY and will not
  work. This is the main trade-off.
- **No job control.** No `&`, `fg`, `bg`, `Ctrl+Z`.
- **No login shell semantics.** Nothing sources `/etc/profile`; ZMUX reads `~/.zmuxrc` instead.
- Programs that call `isatty()` on a *child* process see a pipe, so some colourise by default
  and others do not.

If you need a full PTY with TUI support, [Termux](https://github.com/termux/termux-app) is the
right tool and we will not pretend otherwise. ZMUX optimises for a different point: a small,
reproducible, Python-first terminal with a verifying package manager.

## Key Features

### Real Terminal Execution Engine
- ✅ **Embedded CPython Execution:** Python source runs in-process in the runtime bundled with the APK; external programs are spawned as real child processes by absolute path.
- ✅ **Real-Time Streaming I/O:** Output reaches the screen as it is produced — a loop that prints every half second renders every half second, and `input()` prompts appear *before* the read blocks.
- ✅ **Bi-directional WebSocket:** Binary streaming between the xterm.js frontend and the Python backend.
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
│   ├── pty_session.py     # Virtual terminal session (line discipline, history, Ctrl+C)
│   ├── streams.py         # Live output streaming to the websocket
│   ├── env.py             # Child-process environment builder
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
1. **No PTY, therefore no TUI programs.** ZMUX is a virtual terminal (see [Terminal model](#terminal-model)). `vim`, `htop`, `less` and other full-screen programs will not work. There is no job control.
2. **Directory Scope:** Built-in `cd` is restricted to app-private storage. Child processes started by absolute path can access whatever the Android OS permits.
3. **Native Package Availability:** Native packages (such as NumPy) require cross-compiled wheels matching the specific Android ABI (`armeabi-v7a` or `arm64-v8a`). `zpip` will display an honest error if a package is not yet built for your runtime.
4. **Executable wrappers are unverified on Android 10+.** `paths.py` generates `#!/system/bin/sh` wrappers in app-private storage. Since targetSdk 29, Android blocks `exec()` on files in the app home directory (a W^X violation); binaries are expected to live in `nativeLibraryDir`. These wrappers may therefore fail to execute on modern devices. They are a convenience only — every ZMUX command also resolves in-process — but the mechanism has not yet been verified on a physical device.

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
