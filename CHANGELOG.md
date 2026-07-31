# Changelog

All notable changes to the **ZMUX / ZABAWHEELS** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v200.html).

---

## [Unreleased]

### Fixed — silent-failure class bugs (see docs/POST_FIX_REPORT.md)
- **`cd` now moves in-process Python too.** It previously updated only a
  variable: subprocesses received `cwd=` but `open()` in user code resolved
  against the process directory, so a file written in Python was invisible to
  `ls` and `cat`. `_chdir_context()` wraps in-process execution with
  `os.chdir()` and restores it afterwards.
- **Unsupported shell operators fail loudly.** `&&`, `||`, `;`, `&`, `2>&1`,
  backticks and `$(...)` were passed to the child as ordinary arguments:
  `/bin/true && touch x` reported **exit 0 and never created x**, and `2>&1`
  created a file literally named `&1`. They now return exit 2 with an
  explanation. The check runs on tokenised input, so quoted text
  (`echo 'a && b'`) and Python source (`x = 1; y = 2`) are unaffected.
- **Module names are read from the artifact, not guessed.** `_import_name()`
  derived the import name via a dash-to-underscore substitution, which is
  wrong for `markdown-it-py` (imports `markdown_it`) and `python-dateutil`
  (imports `dateutil`) — so `zpip install rich` failed on a dependency.
  `_discover_modules()` reads `dist-info/top_level.txt`, falling back to the
  extracted tree, and records the result so `zpip verify` re-imports the same
  name.
- **Mistyped commands report `command not found`** (exit 127) instead of a
  Python `SyntaxError`/`NameError`. The classifier only matches bare command
  words and flag-style arguments, so `undefined_var + 1` and `x = = 5` still
  raise genuine Python errors.
- **Installed packages are importable in the REPL.** `USER_PACKAGES_DIR` was
  exported to child processes via `PYTHONPATH` but never added to the running
  interpreter's `sys.path`: `zpip install X` reported success and the very
  next `import X` raised `ModuleNotFoundError`.

### Added — `zmux-setup-storage`
- Opt-in shared-storage access, modelled on `termux-setup-storage`. Links the
  Android shared directories into `~/storage`.
- **This costs the "INTERNET only" permission claim.** The storage permissions
  are declared with `maxSdkVersion=28` (from Android 10 they grant nothing
  under scoped storage) and are **never requested** until the user runs the
  command, so ZMUX stays fully sandboxed by default.
- Reports honestly when scoped storage blocks a directory instead of failing
  silently.

### Documentation — Correction of an inaccurate claim
- **ZMUX has no PTY, and the documentation said it did.** `README.md`,
  `ROADMAP_STATUS.md` and `REFACTOR_REPORT.md` described "POSIX PTY sessions
  (`os.openpty`) with automatic fallback to standard pipes when SELinux denies
  `/dev/ptmx`". No such code has ever existed — there is no `openpty`, no
  `/dev/ptmx`, no `termios` and no fallback path anywhere in `app/zmux/`. The
  module docstring in `pty_session.py` was accurate; the user-facing docs were
  not. Added a **Terminal model** section to the README stating what ZMUX is (a
  virtual terminal over the embedded CPython runtime) and what that costs:
  **no full-screen TUI programs (`vim`, `htop`, `less`), no job control, no
  login shell**. The incorrect historical changelog entry in `ROADMAP_STATUS.md`
  is annotated rather than rewritten, so the record of the error survives.
- **Documented that the `BIN_DIR` shell wrappers are unverified on Android 10+.**
  Since targetSdk 29, Android blocks `exec()` on files in the app home directory
  (a W^X violation); executables are expected to live in `nativeLibraryDir`.
  The `#!/system/bin/sh` wrappers `paths.py` generates may therefore fail to run
  on modern devices. Every ZMUX command also resolves in-process, so this is a
  convenience path — but the claim is now honest about being untested.

### Added — Multiple terminal sessions
- **Up to 8 sessions with tabs** (`app/zmux/sessions.py`). Each owns its own
  `PythonShell`, and therefore its own working directory, Python globals,
  command history and running command. Only the active session writes to the
  websocket; background sessions keep executing and keep recording their own
  scrollback, so a long job continues while you work elsewhere. Switching clears
  the screen and replays the target session's scrollback instead of interleaving
  output. Closing the active tab activates its right-hand neighbour; closing the
  last one opens a fresh session so the user is never left with a dead terminal.
  Resize applies to every session, not just the visible one.
- **Session protocol over the existing websocket**: `session.new`,
  `session.switch`, `session.close`, `session.list`, plus a `{"type":"sessions"}`
  state frame pushed on connect and after every change. The backend owns all
  state; the front-end renders a tab strip and sends intents. Sessions busy in
  the background show a dot.

### Added — Live output streaming
- **Command output now reaches the terminal while the command runs**
  (`app/zmux/streams.py`). Output was previously captured into `io.StringIO` and
  emitted only after `execute()` returned, so a progressive command looked frozen
  and then dumped everything at once. `StreamingWriter` pushes complete lines as
  they are written and flushes partial lines past 256 characters, so prompts,
  `print(..., end="")` output and `\r`-repainting progress bars all render.
  Measured: three prints separated by 0.5 s now arrive at t=0.0/0.5/1.0 s.
- **`input()` prompts are visible again.** `input("Your name? ")` wrote its
  prompt into the captured buffer and then blocked, so users were asked a
  question they could not see and the terminal appeared hung — the interactive
  stdin support added in the previous release was effectively unusable. The
  stdin provider now flushes pending output before blocking.
- **Subprocess stdout streams too.** `communicate()` replaced with a `readline`
  pump on a helper thread, so `ping`/`logcat`-style commands appear live rather
  than arriving in one block on exit. Timeout semantics are preserved via a join
  deadline.
- REST callers are unaffected: the result dict still carries the complete text.
  A new `streamed` key names which streams already reached the screen so the
  renderer never double-prints, and non-streaming paths (built-in commands,
  `zpip`) still render normally.

### Added — Virtual keys, startup file, crash visibility
- **Two-row virtual key bar with a sticky Ctrl modifier** (`terminal.html`). The
  toolbar was 13 hardcoded `onclick` buttons with no modifier support at all, so
  `Ctrl+C`, `Ctrl+R`, `Ctrl+L` and `Ctrl+Z` were untypeable. Keys are now
  generated from a `KEY_ROWS` array (the data-driven shape Termux uses for its
  JSON extra-keys config, so a user-supplied layout can be added later without
  touching markup). Tap CTRL to latch, tap a key to apply; the latch also covers
  soft-keyboard input, so `Ctrl+<letter>` works however the letter is typed.
  Arrows and backspace auto-repeat when held (400 ms delay, 55 ms interval).
- **`~/.zmuxrc`** runs line by line before the first prompt. ZMUX has no login
  shell, so this is the only hook for imports, variables and aliases. A broken
  rc file reports the error and startup continues.
- **Worker-thread crashes are now recorded** (`app/zmux/crash.py`):
  `threading.excepthook` and `sys.unraisablehook` persist tracebacks to
  `logs/zmux_crash.log` with size-bounded rotation. The command worker's blanket
  `except Exception` kept the terminal alive but discarded the traceback
  entirely; it now records before resuming.

### Added — Package manager UX (`zpip`)
- **Download progress bar** — name, MiB, KiB/s, 20-character bar and percent,
  repainted in place at most every 100 ms. A wheel download is the longest
  blocking operation `zpip` performs and it previously reported nothing, so
  `zpip install` looked like a hang. Rendered only when a progress sink is
  installed, so REST and CLI output stay free of escape codes.
- **Explicit vs dependency tracking.** The install database records whether a
  package was requested by name or pulled in as a dependency. `zpip list` marks
  dependencies; re-installing one by name promotes it, and the flag is never
  silently lost. Records predating the flag default to explicit. This is the
  prerequisite for a future `zpip autoremove`.
- **`zpip search` marks packages that are already installed.**

### Fixed
- **`import math` executed ImageMagick's `import` binary** instead of importing
  the module (`app/zmux/python_shell.py`). `_is_external_command()` consulted
  `PATH` for every first word, and ImageMagick ships an `import` screenshot
  tool, so the most common statement in Python failed with `unable to open X
  server` on any system where it is installed. Python statement keywords are now
  guarded against external-command resolution.
- **The child-process environment was built and then thrown away.**
  `TerminalSession._build_env()` assigned `self._env` and nothing ever read it;
  the only `subprocess.Popen` in the codebase passed no `env=` at all, so
  children inherited the raw app environment without `TERM`, `LANG`, the
  ZMUX `PATH` or `PYTHONPATH`. Consolidated into `app/zmux/env.py`, now actually
  passed to children, with `COLORTERM`, `TMPDIR` and `PWD` added and the Android
  zygote passthrough variables documented.
- **`_find_executable()` never searched `BIN_DIR`**, so the `zpip`, `help`,
  `zmux-info`, `clear` and `pip` wrappers generated by `paths.py` were
  unresolvable from the pipeline executor. It now resolves against the same
  `PATH` handed to child processes.

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
