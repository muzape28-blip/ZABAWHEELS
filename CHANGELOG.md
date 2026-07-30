# Changelog

All notable changes to the **ZMUX / ZABAWHEELS** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v200.html).

---

## [Unreleased]

### Security
- **Removed `0.0.0.0` (wildcard-interface) bind fallback for both the HTTP and WebSocket listeners** (`app/zmux/server.py`). `/` serves the WebView `AUTH_TOKEN` unauthenticated (the page's JavaScript needs it), so any device on the same LAN could previously have fetched the token and driven `/api/exec` whenever the fallback triggered. Listeners are now strictly loopback (`127.0.0.1` / `localhost` / `::1`), restoring the documented security boundary.
- **Native wheel libraries are installed read-only** (`app/zmux/zpip.py`): `.so` files committed to `user_packages/` are now `chmod 0o444`. Android 14+ "safer dynamic code loading" requires dynamically loaded files to be read-only (warning on targetSdk 34, hard `UnsatisfiedLinkError: Attempt to load writable file` enforced on newer targets). Same fix Termux applied to `termux-am`.
- **`rm` flag parsing is now strict** (`app/zmux/python_shell.py`): unknown options raise `invalid option` instead of being fuzzy-matched. Previously any `-` argument merely *containing* the letters `r`/`f` enabled recursive/force — `rm -random-flag dir/` would have recursively deleted a directory.

### Changed
- **The WebSocket port now lives in `app.config["WS_PORT"]`** instead of a mutable module-level global in `app/zmux/server.py`, so the CSP header and `terminal.html` always render the real port and tests can set it explicitly without `run_server()`.

### Removed
- **Dead code in `app/zmux/terminal.py`** (~180 lines): `_handle_builtin()` and its five `_builtin_*` handlers, `_read_stream()`, `_drain_output()`, `_collect_output()`, and the unused output queue/stream threads — all unreachable since `execute()` delegates exclusively to `PythonShell`. The module docstring and the `send_input()`/`stop()` stubs now honestly describe what they do today (no long-lived streaming process exists, so both report "No process running").

### Fixed
- **`which` no longer resolves each name twice** per lookup (`app/zmux/python_shell.py`).
- **Removed the duplicated pipeline/redirection operator check** in `PythonShell.execute()` — lines containing `|`, `>`, `<` were tested twice on the same code path.
- **`zpip install` no longer swallows `KeyboardInterrupt`/`SystemExit`** while probing dependency pins (bare `except:` → `except Exception:`).

### Added — Interactive Terminal (PR 2: terminal identity)
- **Shell/REPL mode split.** The terminal no longer looks like a bare `>>>`
  interpreter for everything. Default is a real shell persona (`zmux:~$`,
  cwd-aware prompt); typing `python`/`python3` enters a *pure* Python REPL
  (`>>>`) where shell builtins are not intercepted (`ls` is a NameError,
  like the real CPython REPL); `exit()`/`quit()` or Ctrl+D returns to the
  shell. Compound blocks keep `...` continuation and a blank line closes an
  open block — standard REPL semantics.
- **Kill switch (real Ctrl+C).** Runaway commands can finally be stopped:
  - Pure-Python runaways (`while True: pass`) are interrupted by async
    `KeyboardInterrupt` injection into the dedicated execution thread.
  - Subprocess pipelines run `start_new_session=True` in their own process
    group; Ctrl+C forwards SIGINT to the group (escalating SIGKILL after
    1.5 s) without ever signalling the app itself (a shared process group
    would have nuked the hosting process — caught in testing).
  - An interrupt **epoch counter** wipes out the classic busy-flag race
    window, and a spawn-race check covers Ctrl+C landing between worker
    start and `Popen` returning. Both were reproduced as flaky-test
    failures and are now deterministic (5/5 clean suite runs).
  - Processes killed by a signal render an explicit `[process terminated
    by signal N]` hint (Termux-style), with a phantom-process-killer note
    for SIGKILL on Android 12+.
  - KeyboardInterrupt/SystemExit render like the real REPL (one-line
    notice + exit 130, quiet code propagation) instead of traceback spam.
- **Working stdin.** While a command runs, typed lines queue as stdin, so
  `input()` now works in both modes; leftover lines when the command
  finishes become type-ahead commands (real-terminal semantics). Stdin
  reads unblock cleanly on Ctrl+C via the queue-backed provider polling
  the interrupt flag. (`contextlib.redirect_stdin` doesn't exist before
  Python 3.12, so the swap is done manually — caught on-device-class 3.11.)
- **Command history.** Up/Down arrows (`ESC [ A/B`, plus SS3 dialect)
  recall submitted lines (cap 500); escape sequences no longer leak `[A`
  into the line buffer (previous bug).

### Added — DX polish (PR 3)
- **Rich-rendered tracebacks when `rich` is installed** (pure-python
  universal wheel, `zpip install rich`): syntax-highlighted exceptions in
  `_exec_python`, transparent plain-traceback fallback otherwise. Width
  follows the front-end resize events.
- **First-boot example scripts** (`~/examples/`: `hello.py`,
  `files_demo.py`, `zpip_demo.py`), seeded once behind a marker so user
  edits are never overwritten; seeding failure never blocks startup.

### Added — Real package search (PR 4)
- **`zpip search` now answers from real sources instead of a hardcoded list
  of 13 package names** (`app/zmux/zpip.py`). Results merge, per query:
  - the **curated ZABAWHEELS catalog** for the running runtime/ABI
    (`<index>/runtimes/<runtime_id>/<abi>.json`), fetched with an 8 s budget
    and cached on disk (`cache/catalogs/`, 1 h freshness) — the source
    status is always disclosed as `live` / `cache` / `stale` / `unavailable`;
  - the **installed database** (always available, fully offline);
  - an **exact-name PyPI probe** for single-token queries that are valid
    package names and not an exact curated hit — PyPI has no search API any
    more, so an exact probe is the only honest thing zpip can offer there,
    and its result is labeled `[pypi]` (uncurated).
- **Multi-word queries** (`zpip search http client`) match every token (AND)
  against name (separator-insensitive: `http_toolbox` ↔ `http-toolbox`) and
  summary. Ranking: exact name match first, then name matches, then
  summary-only matches; ties resolve curated > pypi > installed so the
  richest metadata wins. Entries also flag packages that are already
  installed (`[curated,installed]`).
- **`ZMUX_OFFLINE=1`**: search never touches the network — it answers from
  the installed database plus the on-disk catalog cache and says so. A
  missing/empty index yields an honest empty result instead of the old
  pretend-list, and unreachable sources are printed as notes under the
  results instead of failing the command.

### Fixed (kept from earlier unreleased work)
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
