# ZMUX — Standalone Android Terminal for Python

[![Build ZMUX APK](https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/build-zmux-apk.yml/badge.svg)](https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/build-zmux-apk.yml)
[![Validate Repository](https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/validate.yml/badge.svg)](https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/validate.yml)

**ZMUX** is a standalone Android terminal for Python development. It pairs a
real embedded CPython runtime with the **ZABAWHEELS** curated wheelhouse
infrastructure (hash-verifying packages, reproducible builds) and an
opt-in **Alpine Linux sandbox** — real `git`, `apk`, `sh` — running through
PRoot, no root required.

> **Status (2026-08-01):** verified on a real ARMv7 device — `gates` **5/5 PASS**
> on-device, `git clone` over HTTPS works, `apk add` installs real Alpine
> packages, terminal UX is smooth (soft-keyboard aware, exact line wrapping,
> fast scrolling). Everything in this README is executed, not claimed.

---

## What is ZMUX?

ZMUX is a lightweight terminal emulator for Android that lets you:

- Type **Python directly** — expressions, statements, scripts — in a real
  embedded CPython runtime (not a fake shell).
- Run **real system commands** (`ls`, `cat`, `git`, `apk`, …) as genuine child
  processes with real exit codes, streaming output.
- Install Python packages with **`zpip`**, a transactional, SHA-256-verifying
  package manager backed by the curated ZABAWHEELS index.
- Enter a **real Alpine Linux userland** (`linux-setup` + proot) for anything
  that needs a normal Unix environment — `git clone`, `apk add`, shell scripts.
- Work inside an **app-private sandbox** — nothing touches your device's
  system, no root, no `/system` writes.

### What ZMUX is NOT

- **Not an IDE or code editor** — it is a command-line terminal.
- **Not Zabacode with a new name** — the old IDE features (editors, AI
  assistants, theme marketplaces) were deliberately removed; ZMUX was rebuilt
  from scratch as an honest, standalone terminal (see
  [REFACTOR_REPORT.md](REFACTOR_REPORT.md)).
- **Not a fake terminal** — nothing is hardcoded or mocked. `git` is real git,
  `apk` is real apk, Python is real CPython, errors are real tracebacks.
- **Not a Unix PTY terminal** — there is no `/dev/ptmx`/`openpty()` session.
  See [Terminal model](#terminal-model) for the honest trade-offs.
- **Not Termux** — ZMUX is Python-first, lives inside Android's app sandbox,
  and does not claim root/system access. Termux remains the right tool for a
  full Unix PTY shell.

---

## Terminal model

ZMUX is a **virtual terminal**, and it says so plainly. The front-end is
xterm.js; keystrokes travel over a WebSocket to a Python line-discipline layer
(`pty_session.py`) that handles echo, backspace, history and Ctrl+C. Completed
lines go to `python_shell.py`, which either evaluates them in the embedded
CPython runtime or spawns a real child process by absolute path.

**What that gives you**

- Python that behaves like Python: real `exec`/`eval`, persistent globals,
  real tracebacks (Rich-rendered and wrapped to your screen width).
- Real child processes: real exit codes, real signals, pipelines `|`,
  redirection `>`/`>>`, live streaming output and working `input()`.
- **Streaming progress** — `git clone`, `apk add`, `curl` show their stderr
  progress live (stderr is streamed like stdout), so a long operation never
  looks frozen.
- **Robust against hangs** — the executor waits on the *process*, not the
  pipe, so a finished command whose grandchild held the pipe open can never
  wedge your session.
- No dependency on `/dev/ptmx`, which some Android Go / SELinux setups deny.

**What it does not give you**

- **No full-screen TUI programs.** `vim`, `htop`, `nano`, `less` need a real
  TTY and will not work interactively. ZMUX tells you this honestly when you
  type them.
- **No job control.** No `&`, `fg`, `bg`, `Ctrl+Z`.
- **No login-shell semantics.** Nothing sources `/etc/profile`; ZMUX reads
  `~/.zmuxrc`.
- `isatty()` on child processes sees a pipe, so some tools colour by default
  and others do not.

If you need a full PTY with TUI support, [Termux](https://github.com/termux/termux-app)
is the right tool — we will not pretend otherwise. ZMUX optimises for a
different point: a small, reproducible, Python-first terminal with a
verifying package manager.

---

## Key Features

### Real Terminal Execution Engine

- ✅ **Embedded CPython:** Python runs in-process in the runtime bundled with
  the APK; external programs are real child processes by absolute path.
- ✅ **Real-Time Streaming I/O:** stdout *and* stderr reach the screen as they
  are produced — `input()` prompts appear before the read blocks, git/apk
  progress is visible while it runs.
- ✅ **Bi-directional WebSocket:** binary streaming between xterm.js and Python.
- ✅ **Multiple Sessions:** up to 8 tabs, each with its own cwd, Python globals
  and history; background sessions keep running.
- ✅ **Virtual Keys:** two-row key bar with a sticky Ctrl latch
  (`Ctrl+C`, `Ctrl+R`, `Ctrl+L` typeable) and hold-to-repeat arrows.
- ✅ **Process Control:** Ctrl+C / Stop cancels running processes cleanly
  (process-group signalling, no Bionic libc crashes on ARMv7).
- ✅ **Persistent Working Directory:** `cd` persists across commands with
  sandbox path-traversal protection — including bare `cd` (go home), even when
  Android exposes the app home through the `/data/user/0` ↔ `/data/data`
  symlink.
- ✅ **Mobile UX:** soft-keyboard aware (the banner stays visible and the
  prompt sits above the IME), exact line wrapping to the visible width,
  coalesced frame-synced scrolling, 6000-line scrollback.

### Alpine Linux Sandbox (PRoot) — real git, apk, sh

- ✅ `linux-setup` downloads the **Alpine 3.22.5** minirootfs (~4 MiB),
  SHA-512 verified against the official Alpine digest, extracted atomically.
- ✅ `git <args>` runs **real git** (Alpine's build) with normal syntax:
  clone, branch, checkout, push.
- ✅ `linux <cmd>` / `alpine <cmd>` runs any shell command inside the sandbox:
  `linux apk add git openssh-client` installs real Alpine packages.
- ✅ W^X-safe: proot execs from `nativeLibraryDir` (the one app location
  Android allows) — no root, no SELinux changes, no system writes.
- ✅ **On-device diagnostics:** `zmux-info` prints the real `DT_NEEDED` of the
  shipped `libproot.so` and `gates` reads the binary on the phone itself, so
  a stale or corrupted build is reported explicitly instead of as a cryptic
  linker error.

### Built-in Commands

```bash
help            # Display available commands
clear           # Clear terminal screen
pwd             # Print working directory
cd <dir>        # Change directory (restricted to app home; bare `cd` = home)
ls, cat, mkdir, touch, cp, mv, rm, echo, env, which, uname
python          # Launch Python REPL (typing Python directly also works)
python <file>   # Execute a Python script
python -c "..." # Execute inline Python code
pip             # Standard pip package manager (if available)
zpip            # ZMUX secure package manager
zmux-info       # Runtime fingerprint + on-device binary verification

# Alpine Linux sandbox (PRoot) — real git and shell commands
linux-setup     # Install Alpine 3.22.5 (SHA-512 verified) — enables git/linux
git <args>      # REAL git: clone, branch, checkout, push
linux <cmd>     # Any shell command inside Alpine: linux apk add git
alpine <cmd>    # Alias of linux
gates           # Strict on-device acceptance probe (G1–G5)
```

### Secure Package Manager (`zpip`)

```bash
zpip search <name>             # Search curated index + PyPI (exact probe)
zpip info <name>               # Package details and compatibility
zpip install <name>            # Install verified package (SHA-256 checked)
zpip install <name> <version>  # Install a specific version
zpip list                      # Installed packages (dependencies marked)
zpip verify <name>             # Verify installation integrity against manifest
zpip uninstall <name>          # Cleanly remove a package and its files
zpip doctor                    # Diagnose system health and runtime fingerprint
```

`zpip` is transactional: a failed install rolls back atomically, file
ownership conflicts are rejected, and native wheels must match your exact
Android ABI. Name collisions with famous CLI tools (e.g. PyPI's `nano` is a
Django library, not GNU nano) produce a loud warning instead of silent
"success".

### Security & Hardening

- ✅ **Mandatory SHA-256 verification** for every package; SHA-512 for the
  Alpine rootfs.
- ✅ **Loopback-only server** (HTTP + WebSocket bind strictly to `127.0.0.1`/`::1`)
  with a 128-bit session token.
- ✅ **Transactional installs** with full rollback; path-traversal protection
  on archives and commands.
- ✅ **Encrypted local storage** (AES/HMAC-SHA256) via Android Keystore.
- ✅ **Zero ads, zero telemetry, zero background tracking.** `INTERNET` is the
  only permission; storage access is opt-in (`zmux-setup-storage`).

---

## Verified on device (2026-08-01)

First real-device pass on an entry-level **ARMv7** phone (Infinix Smart 9 HD
class, Android 14):

| Check | Result |
|---|---|
| `gates` G1–G5 (ptmx, proot-exec, alpine-boot, git-clone, apk) | ✅ **5/5 PASS** |
| `linux apk add git openssh-client` | ✅ 19 real Alpine packages installed |
| `git clone https://github.com/…` | ✅ full repo cloned over HTTPS |
| `zmux-info` → `Proot NEEDED` | ✅ `libtalloc.so, libdl.so, libc.so` (patched binary verified on-device) |
| Terminal UX (keyboard, wrapping, scrolling, `cd`) | ✅ smooth and correct |

The full failure→fix journey (talloc SONAME, DT_HASH corruption, Java
classloader on worker threads, stale-APK detection, clone "hang", `cd` home,
keyboard overlap) is documented in
[docs/DEVICE_FAILURE_ANALYSIS.md](docs/DEVICE_FAILURE_ANALYSIS.md).

---

## APK Specifications & Android Compatibility

- **App Title:** ZMUX · **Package:** `com.zaba.zmux` · **Version:** `1.0.0`
- **Min API 26** (Android 8.0) · **Target API 34** (Android 14)
- **ABIs:** `armeabi-v7a` (32-bit), `arm64-v8a` (64-bit)
- **Permission:** `INTERNET` only (loopback WebView + package index).

---

## Installation

### Download the Universal APK

Grab the latest artifact from
[GitHub Actions](https://github.com/muzape28-blip/ZABAWHEELS/actions/workflows/build-zmux-apk.yml)
(latest successful **Build ZMUX APK** run → *Artifacts* → `zmux`). The zip
contains:

- `zmux-1.0.0-universal-debug.apk` — signed universal APK (both ABIs)
- `SHA256SUMS` — checksums for provenance
- `build-contract.json` — pinned runtime contract

> On Android, uninstall the previous ZMUX before installing a new build —
> the app data dir can otherwise carry a stale build's binaries.

### Build from Source

```bash
cd app
pip install buildozer==1.6.0
buildozer android debug
```

The APK build runs `scripts/build_proot_android.py` (cross-compiles PRoot +
talloc with the NDK), patches/verifies the ELF `DT_NEEDED` on the artifacts,
and refuses to package a broken binary. See [docs/BUILDING.md](docs/BUILDING.md).

---

## Architecture

```
ZMUX Terminal
├── Backend (Python 3 / Flask / Waitress)
│   ├── server.py          # Flask HTTP WebView server
│   ├── ws_server.py       # Pure-Python RFC-6455 WebSocket server
│   ├── python_shell.py    # Embedded CPython executor + subprocess pipelines
│   ├── pty_session.py     # Virtual terminal session (line discipline, tabs)
│   ├── sessions.py        # Multiple sessions, tab routing, scrollback replay
│   ├── streams.py         # Live stdout/stderr streaming to the websocket
│   ├── linuxenv.py        # Alpine PRoot sandbox (setup, command line, gates)
│   ├── elfscan.py         # Pure-Python ELF DT_NEEDED/SONAME reader (on-device)
│   ├── javabridge.py      # Java bridge primed on the main thread (worker-safe)
│   ├── storage.py         # Opt-in shared-storage access (zmux-setup-storage)
│   ├── zpip.py            # Transactional hash-verifying package manager
│   ├── security.py        # Token authentication
│   ├── keystore.py        # Encrypted local storage
│   └── paths.py           # App-private directory management + CLI wrappers
│
├── Frontend (HTML / CSS / JavaScript)
│   └── terminal.html      # Mobile-optimized xterm.js terminal UI
│
└── Infrastructure (ZABAWHEELS)
    ├── index/             # Curated package index (stable, candidate, experimental)
    ├── packages/          # Package recipes and manifests
    ├── schemas/           # JSON Schemas for recipes, manifests, and runtimes
    ├── scripts/           # Verification, inspection, index, and build tools
    └── toolchain/         # Pinned runtime and source lockfiles
```

---

## Honest Limitations

1. **No PTY, therefore no TUI programs.** `vim`, `htop`, `less` and other
   full-screen programs will not work; there is no job control. ZMUX says so
   instead of pretending.
2. **Directory scope.** Built-in `cd` is restricted to app-private storage.
   Child processes can access whatever Android permits.
3. **Native wheels.** Packages with native extensions (NumPy etc.) need
   cross-compiled wheels matching your ABI; `zpip` reports honestly when a
   package is not yet available for your runtime.
4. **ARMv7 performance.** PRoot adds ptrace overhead; heavy compiles are slow
   on low-end devices — fine for `git`/`apk`/`sh`, painful for builds.

---

## Documentation

- **[CHANGELOG.md](CHANGELOG.md)** — version history and every fix.
- **[docs/DEVICE_FAILURE_ANALYSIS.md](docs/DEVICE_FAILURE_ANALYSIS.md)** —
  the on-device failure→fix journey with primary-source citations.
- **[docs/PROOT_ALPINE.md](docs/PROOT_ALPINE.md)** — the Alpine PRoot sandbox
  design and packaging.
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — WebView port contract,
  streaming, and anti-freeze invariants.
- **[docs/SECURITY.md](docs/SECURITY.md)** — threat model and mechanisms.
- **[docs/DEVICE_TESTING.md](docs/DEVICE_TESTING.md)** — device test matrix.
- **[REFACTOR_REPORT.md](REFACTOR_REPORT.md)** — Zabacode → ZMUX transition.
- **[ZABAWHEELS.md](ZABAWHEELS.md)** — the curated wheelhouse spec.

---

## Local Development & Testing

```bash
cd app
pip install -r requirements-dev.txt
pip install -e .

# Backend + infra tests
PYTHONPATH=. pytest -q app/tests tests/          # 367 passing, 25 skipped

# Frontend behavioral tests (Node)
node app/tests/ui_harness.js app/templates/terminal.html   # 44/44

# Run the terminal on desktop (browser at http://127.0.0.1:5000)
python main.py
```

---

## Contributing

We welcome contributions to the ZMUX app and the ZABAWHEELS package
infrastructure. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for package request
guidelines, recipe formatting, and PR procedures.

---

## License

Licensed under the terms of the **[LICENSE](LICENSE)**.

---

**ZMUX / ZABAWHEELS** — Honest, transparent, and reproducible Android Python
tooling.
