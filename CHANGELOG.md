# Changelog

All notable changes to the **ZMUX / ZABAWHEELS** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v200.html).

---

## [Unreleased]

### Fixed
- **Transparent Unix Shell Integration for ZMUX Built-in Commands:** typing `zpip`, `help`, `zmux-info`, `clear`, or `pip` inside the real Android PTY shell no longer fails with `/system/bin/sh: <cmd>: inaccessible or not found`. `/system/bin/sh` only executes binaries and scripts found on `$PATH`, so ZMUX now ships native shell entrypoints:
  - Added `app/zmux/cli.py`, a CLI entrypoint (`python -m zmux.cli <cmd> [args...]`) that implements the command handlers: `help` prints the formatted ZMUX terminal help text, `clear` emits `\033[H\033[2J\033[3J`, `zmux-info` prints the formatted runtime fingerprint, `zpip` dispatches through the package manager with cleanly formatted output, and `pip` invokes standard pip when a runnable interpreter exists or prints guidance to use `zpip` otherwise.
  - `app/zmux/paths.py` now defines `BIN_DIR` (`APP_DIR/bin`) and auto-generates executable (`0o755`) `#!/system/bin/sh` wrappers for every command at import time via `ensure_cli_wrappers()`; each wrapper execs `python -m zmux.cli "$0" "$@"` (falling back to `python3`) and `BIN_DIR` is added to `os.environ["PATH"]`.
  - `TerminalSession._build_env()` in `app/zmux/terminal.py` prepends `BIN_DIR` to the `PATH` handed to child PTY processes, so the wrappers resolve transparently in every interactive `/system/bin/sh` session.
  - Moved the terminal-friendly zpip result formatter into `zmux.zpip.format_output()` and extracted `zmux.zpip.format_fingerprint()` for `zmux-info`, so the REST server (`app/zmux/server.py`) and the CLI share one implementation.

---

## [1.0.0] - 2026-07-29

### Fixed — Deep ARMv7a (Infinix Smart 9 HD) Force-Close & Freeze Elimination
- **PTY Process Spawn & Signal Safety on ARMv7 (`armeabi-v7a`):**
  - Replaced Python-level `preexec_fn=os.setsid` with native C-level POSIX `start_new_session=True` across `PTYTerminalSession.start()` and `_start_fallback()`. On 32-bit ARMv7 Android (Bionic libc on devices such as Infinix Smart 9 HD), executing Python functions inside `preexec_fn` after `fork()` in a multithreaded process caused mutex deadlocks and `SIGSEGV` / force-close crashes.
  - Added automatic fallback to standard pipe session when `os.openpty()` raises `PermissionError` (Errno 13) or `OSError`. Many Android Go / ARMv7 SELinux policies restrict untrusted APK access to `/dev/ptmx`; ZMUX now seamlessly transitions to a standard pipe session instead of terminating.
  - Added executable path validation (`os.access(candidate, os.X_OK)`) when detecting shells (`/system/bin/sh`, `/bin/sh`, `/system/xbin/sh`, `"sh"`).
- **Android WebView Port Binding & Socket Reusability (`app/zmux/server.py`):**
  - Enabled `SO_REUSEPORT` alongside `SO_REUSEADDR` for the Android WebView HTTP port 5000 listener (`_bind_http_socket`). When an Android app is restarted or brought back to foreground, previous TCP sockets may linger in `TIME_WAIT`, which previously caused an `OSError: [Errno 98] Address already in use` force close.
  - Added multi-host fallback (`127.0.0.1`, `0.0.0.0`, `localhost`) when binding port 5000 on Android to accommodate OEM loopback network stack variations.
  - Restricted `SO_REUSEPORT` on dynamic free-port allocations (`_bind_ws_socket`) so concurrent test instances or servers never collide on identical port numbers.
- **Dual IPv4/IPv6 WebSocket Server (`app/zmux/ws_server.py` & `app/templates/terminal.html`):**
  - Upgraded `WebSocketServer` to support listening on multiple bound sockets simultaneously (`listeners=[...]`). ZMUX now listens on both IPv4 (`127.0.0.1`) and IPv6 (`::1`) loopback interfaces for both HTTP and WebSocket connections.
  - Enhanced `connectWebSocket()` in the terminal UI with a host cycling strategy (`getWsHost(attempt)`), automatically trying `window.location.hostname`, `"127.0.0.1"`, and `"localhost"` across reconnect attempts to prevent loading screen hangs on devices where `localhost` resolves exclusively to IPv6.
- **Package Manager (`zpip`) Android In-Process Smoke Verification:**
  - Replaced child-process `subprocess.run([sys.executable, ...])` smoke and verification tests with isolated in-process module importing (`_smoke_test_in_process`) when running on Android (`_is_android()`). On Android APKs, Python executes inside a shared library embedded in the Java Activity; invoking `sys.executable` as a standalone binary fails with `PermissionError` / `OSError`.
  - Refined `android_abi()` architecture detection to verify pointer bit width (`struct.calcsize("P") * 8 == 32`), ensuring 32-bit Python userland on ARM builds correctly identifies as `armeabi-v7a` even when executing under a 64-bit kernel (`aarch64`).
- **Path Resolution Hardening (`app/zmux/paths.py`):**
  - Hardened `resolve_app_dir()` to inspect `ANDROID_PRIVATE`, `ANDROID_ARGUMENT`, and `ANDROID_APP_PATH` environment variables and verify directory writability via live write-probe testing (`_is_writable(path)`), preventing unhandled `PermissionError` crashes during startup directory creation.
- **APK Packaging & Requirements (`app/buildozer.spec`):**
  - Added `android.uses_cleartext_traffic = True` to explicitly authorize loopback cleartext HTTP/WS communication across all Android SDK levels.
  - Explicitly listed all required Flask transitive dependencies (`werkzeug`, `jinja2`, `itsdangerous`, `click`, `blinker`, `MarkupSafe`) in Buildozer requirements to guarantee that C-extensions and core runtime dependencies are bundled in the universal ARMv7 + ARM64 APK.
- **Main App Crash Reporting (`app/main.py`):**
  - Upgraded `_write_crash_log()` to write tracebacks to multiple fallback locations (`ANDROID_PRIVATE`, `ANDROID_ARGUMENT`, project directory, `/data/local/tmp`) so crash logs are always accessible on physical mobile devices.

### Changed — Documentation & Presentation
- **Full English Localization:**
  - Translated and standardized `README.md`, `REFACTOR_REPORT.md`, `ROADMAP_STATUS.md`, and `docs/ARCHITECTURE.md` into clean, professional English, accurately reflecting the current status, honest limitations, and tested capabilities of ZMUX.
  - Updated `ZABAWHEELS.md` with an English Executive Summary bridging the repository's historical architecture specification with ZMUX's standalone terminal implementation.

---

## [0.9.0] - 2026-07-29

### Added
- Original ZMUX visual branding (monogram `Z` + prompt `>` + green neon cursor `_`), replacing placeholder/IDE icons across `logo.png`, `icon.png`, and `presplash.png`.
- Real-time interactive Unix PTY and WebSocket terminal engine with scrollback replay buffer and resize support (`pty_session.py`, `ws_server.py`).
- Standalone Android terminal UI (`app/templates/terminal.html`) with mobile-friendly virtual keyboard assistance and command history.
- Curated ZABAWHEELS wheelhouse infrastructure (`index/`, `packages/`, `schemas/`, `scripts/`) with automated validation and reproducible CI build pipelines.
