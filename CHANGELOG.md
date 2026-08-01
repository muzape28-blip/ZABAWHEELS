# Changelog

All notable changes to the **ZMUX / ZABAWHEELS** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v200.html).

---

## [Unreleased]

### Fixed — `cd` home via symlink, soft-keyboard overlap, ragged wrapping, scroll stutter (2026-08-01)
- **Bare `cd` no longer reports "outside home directory".** Android exposes
  app storage as `/data/user/0/...`, a symlink to `/data/data/...`; `cd`
  compared the raw HOME_DIR against its own `.resolve()` and failed, locking
  the user out of `~` (while `cd <subdir>` worked because `_path()` resolves).
  Both sides are resolved before the sandbox check now.
- **Soft keyboard no longer covers the banner/input.** The frontend now
  tracks the Visual Viewport: when the IME opens/closes the layout is
  re-sized to the visible area and the terminal refits, so the prompt always
  sits above the keyboard and the top bar stays visible.
- **Line wrapping is exact; `help` / `cat README.md` render like a normal
  terminal.** `fitTerminal()` clamps the xterm screen to 100% width, re-fits
  once the bundled fonts finish loading (the first fit used fallback metrics
  and produced ragged right edges), and forces a refresh after `clear` so
  the prompt never renders shifted off the left edge.
- **Scrolling is smoother and more aggressive.** `scrollToBottom` is
  coalesced to one call per animation frame (was: once per output chunk,
  causing reflow stutter on low-end phones), momentum touch scrolling is
  enabled on the xterm viewport, and scrollback is raised to 6000 lines so
  long tracebacks stay reachable.
- Tests: 367 Python + 44 UI-harness checks pass.

### Fixed — `git clone` progress now streams; no more infinite hang on stray pipes (2026-08-01)
- **On-device win: `gates` is 5/5 PASS.** With the length-preserving talloc
  rewrite, `linux apk add git openssh-client` installs 19 packages and
  `gates` G1–G5 all pass on the Infinix-class ARMv7 device (`Proot NEEDED:
  libtalloc.so, libdl.so, libc.so`).
- **`git clone` looked permanently stuck** even though `gates` G4 (shallow
  clone) passed: git writes *all* progress ("Cloning into…", "Enumerating
  objects…") to **stderr**, and ZMUX's subprocess executor only streamed
  stdout — a slow full clone on ARMv7+proot showed a frozen screen until
  completion. The executor now streams stderr live like stdout (same
  newline/encoding handling), so long-running tools are visibly alive.
- **No more infinite hang on stray pipe holders.** `_read_stdout_streaming`
  waited on the *pipe* (readline EOF) instead of the *process*; a finished
  `git clone` whose remote helper grandchild inherited stdout kept the pipe
  open forever → `reader.join(None)` never returned. It now polls the
  process to exit, gives the drain thread a moment to flush, then returns —
  a lingering child can never wedge the session. Reproduced the deadlock
  via stack dump (handle.close() blocked against the reading pump) and
  fixed by abandoning the daemon pump instead of force-closing the handle.
- The Ctrl+C signal hint is streamed too (it is appended after the live
  drain, and stderr is now marked streamed).
- Tests: 365 passed, 25 skipped. Docs updated.

### Fixed — the real proot bug: talloc NEEDED rewrite corrupted the ELF (2026-08-01)
- **Root cause of the on-device `empty/missing DT_HASH/DT_GNU_HASH`
  failure.** The in-place rewrite of `libtalloc.so.2` → `libtalloc.so` in
  `scripts/build_proot_android.py` used a 13-byte replacement
  (`b"libtalloc.so\x00"`) for a 14-byte needle — "libtalloc.so" is 12
  characters, not 13 — so the file shrank by one byte and **every section
  header, program header and string after it shifted**, producing a
  misaligned `.dynamic` (garbage `unused DT entry` warnings) and
  `empty/missing DT_HASH/DT_GNU_HASH` at exec time. Reproduced locally by
  building talloc + proot from the pinned sources: `readelf` confirmed the
  1-byte size change and the resulting "extends past end of file" error.
- **Fix:** the replacement is now `b"libtalloc.so\x00\x00"` (14 bytes,
  length-preserving). Verified locally: size unchanged, `NEEDED:
  [libtalloc.so]`, `GNU_HASH` intact, `readelf` clean.
- **Hard invariants added:** the build script asserts needle/replacement
  length equality and fails the build if patching ever changes the file
  size; `verify_needed()` now also requires the final `libproot.so` to
  parse and to bind exactly `libtalloc.so`.
- **`zmux-info`/`gates` now report an unreadable/corrupted `libproot.so`
  explicitly** ("Proot status: ... corrupted build — reinstall"), so a
  broken binary is never silently ignored on the phone.
- Tests: 360 passed, 25 skipped (length-invariant, size-preserving patch,
  corrupted-ELF detection via `elfscan`).
### Fixed — stale-APK root cause: on-device proof of the shipped binary (2026-08-01)
- **"Fixed APK still failing" traced to a stale APK.** The device's
  `gates` output said `[PASS] ptx`, but this repo has always named that gate
  `ptmx` (`git log -S 'ptx'` is empty) — the installed APK was not built from
  this repository's code at all.
- **Buildozer/p4a packaging verified (theory check):** buildozer 1.6.0
  `build_package()` copies `android.add_libs_*` into `dist/libs/<abi>`
  (jniLibs) at *every* build via an overwriting `copyfile`, so the .so files
  do land in the right structure; the failure was the DT_NEEDED name
  (`libtalloc.so.2`) vs the shipped filename.
- **`gates` G2 and `zmux-info` now read the shipped `libproot.so`
  `DT_NEEDED` on the phone itself** (new `app/zmux/elfscan.py` — pure-Python
  ELF32/64 LE/BE parser). A stale binary is reported as
  `STALE BINARY` / `[STALE — reinstall]` instead of an unexplained
  `libtalloc.so.2 not found`.
- **Runtime self-heal is bidirectional:** `libtalloc.so.2`-only or
  `libtalloc.so`-only APKs both get the missing alias mirrored at runtime.
- **`toolchain/runtime-lock.json` records the proot contract**
  (`talloc_soname: libtalloc.so.2`, `packaged_needed: libtalloc.so`).
- **Workflow hardening (cache key + "Verify APK contents" step + build
  marker) prepared as `docs/WORKFLOW_VERIFY_STEPS.md`** — pending the GitHub
  App's `workflows` permission to push; the on-device checks above work
  without it.

### Fixed — first on-device failures: proot libtalloc, storage Java bridge, nano (2026-07-31)
- **`linux apk add …` no longer dies with `CANNOT LINK EXECUTABLE …: library
  "libtalloc.so.2" not found`.** Root cause: talloc's SONAME is
  `libtalloc.so.2`, Android's linker matches `DT_NEEDED` against exact
  filenames, and the APK shipped the file as `libtalloc.so`.
  `scripts/build_proot_android.py` now rewrites the NEEDED/SONAME strings
  inside `libproot.so`/`libtalloc.so` to plain `libtalloc.so` (same byte
  length, ELF offsets stay valid) and fails the build if any `DT_NEEDED`
  cannot be satisfied by the packaged files (`verify_needed()`).
  `linuxenv.proot_env()` additionally self-heals already-shipped APKs by
  mirroring `libtalloc.so` → `libtalloc.so.2` into a writable runtime dir
  prepended to `LD_LIBRARY_PATH`.
- **`zmux-setup-storage` no longer throws `ClassNotFoundException:
  org.kivy.android.PythonActivity`.** Root cause: p4a's `android.permissions`
  runs `autoclass()` on the command-executor worker thread, where JNI
  `FindClass` falls back to the system class loader (no app Java frames on
  the stack) — the exact failure documented in p4a #2533 for the webview
  bootstrap. New `zmux/javabridge.py` resolves the activity class once on
  the Python main thread at startup (pyjnius caches it), and
  `storage.request_permissions()` calls `mActivity.requestPermissions([…])`
  directly through that primed bridge instead of the p4a module.
- **`nano` no longer leaks a `NameError`.** PyPI's `nano` is a Django
  library, not GNU nano (which also cannot render without a PTY, which ZMUX
  does not provide). `zpip install nano` now prints a loud WARNING about the
  collision, and the shell answers known TUI names (`nano`, `vim`, `htop`,
  `less`, …) with an honest "needs a real TTY" message plus alternatives.
- Analysis + citations: `docs/DEVICE_FAILURE_ANALYSIS.md`.

### Fixed — Python 3.14 rootfs extraction + terminal UX (2026-07-31)
- **`linux-setup` works on Python 3.14 (on-device p4a runtime).** 3.14 made
  `TarFile.extractall()` default to `filter="data"`, which refuses absolute
  symlink targets (`./usr/bin/yes is a link to an absolute path`) — a
  busybox-style minirootfs has ~306 of them, so installation died on the
  phone while desktop CI (older default) passed. `_safe_extract()` now
  passes `filter="fully_trusted"` explicitly — honest, because member names
  are already validated (no absolute names, no `..`, size cap) and the
  tarball is SHA-512-pinned to Alpine's official digest — with a
  `TypeError` fallback for runtimes lacking the kwarg.
  `app/tests/test_linuxenv_extract.py` runs the real pipeline (file://
  mirror → sha512 → tarfile → disk), simulates the 3.14 filter surface,
  and proves `install()` idempotency without touching the network.
- **Tabs: hold-to-close replaces the tiny `×`.** The per-tab close button
  sat millimetres from the switch target and ate mis-taps on phones. Tabs
  are now bigger (≥44 px wide, roomier padding) and holding one for ~1.5 s
  closes its session: the tab flashes red with a filling progress bar on
  hold start, sliding the finger >12 px cancels, releasing early cancels,
  a plain tap still switches, the post-close click is suppressed, and
  `navigator.vibrate(40)` confirms when available. Closing the last tab
  still respawns a fresh session (backend contract, unchanged).
- **Scroll-follow no longer freezes.** `userScrolledUp` used to latch on
  ANY upward `scrollTop` movement — including programmatic ones — so a
  `\x1b[2J` clear or a resize reflow silently disabled follow forever. Now
  only genuine user gestures (wheel-up, touch-drag toward history, PageUp)
  mark "reading"; reaching the bottom always re-arms follow; and every
  output payload containing `\x1b[2J` (`clear`, session switch) resets the
  latch and snaps to live output. Bounded scroll-up / free scroll-down,
  and the terminal never yanks the viewport while the user reads.
- **Keyword bar can be hidden.** New `KEYS` toggle in the topbar next to
  the `> ZMUX` title shows/hides the virtual-key rows (ESC/CTRL/Tab/^C…).
  Default stays visible; the choice persists in `localStorage`
  (`zmux.keysBar.visible`) and the terminal refits immediately so the row
  count uses the freed space.
- **UI behavior is executed, not eyeballed.** `app/tests/ui_harness.js`
  (Node) runs the shipped `terminal.html` script verbatim against a
  deterministic DOM/xterm/WebSocket surface, replaying synthetic touch,
  wheel, and key sequences — 44 assertions, driven from pytest by
  `app/tests/test_ui_behavior.py` (skipped only where Node is absent).

### Added — Alpine Linux sandbox (PRoot) for real `git` and shell commands
- **`linux-setup` / `git` / `linux` / `alpine` commands** (`zmux/linuxenv.py`).
  ZMUX can now run a real Alpine 3.22.5 userland via PRoot: `git clone`,
  `git branch`, `git checkout`, `git push` use the real git binary with
  normal syntax, and `linux <cmd>` runs any shell command (`apk add ...`,
  `sh`, `python3`) inside the sandbox. See `docs/PROOT_ALPINE.md`.
- **W^X-safe packaging.** PRoot (`libproot.so` + loaders) and talloc are
  cross-compiled by `scripts/build_proot_android.py` and shipped in
  `nativeLibraryDir` via `android.add_libs_*` — the only app location
  Android allows `exec()` on (p4a already sets `useLegacyPackaging=true`).
  Same approach as Kai 9000 (targetSdk 37) and UserLAnd.
- **`gates`** — a strict, unmocked on-device probe: `/dev/ptmx` (G1),
  nativeLibraryDir exec (G2), Alpine boot (G3), real git clone (G4),
  apk-tools (G5). Exits non-zero unless every gate passes.
- **Pinned rootfs with hash verification.** Alpine `3.22.5` (docker-alpine
  v3.22 branch; the version Kai pins because apk-tools 3 breaks proot) is
  downloaded from the official CDN and rejected on any SHA-512 mismatch.
- **`new` tab now actually switches page.** Creating a session clears the
  old screen before the new banner renders, instead of stacking prompts
  ("there are just more prompts now").

### Added — terminal UI polish (xterm.js)
- **Aggressive scroll**: output follows the cursor unless the user scrolled
  up to read; a tap while scrolled up jumps back to the live output.
  Scrollback raised to 2000 rows.
- **Virtual key rows wrap** instead of overflowing unscrollably on narrow
  screens — every key is always reachable.
- **Prompt tidiness**: the prompt never gets pasted onto a command's
  unterminated output tail (`print(1, end="")` then prompt starts a new line).
- Active tab is scrolled into view when the tab strip overflows.

### Fixed — `true && cmd` now fails loudly, Python strings stay safe
- `true && touch x` used to fall through to the Python evaluator (because
  `true`/`false` are keyword-guarded) and produce a confusing
  `SyntaxError`. It now returns exit 2 with the standard shell-operator
  message — while `print("a && b")`, `x = "a && b"` and `true & x`
  (bitwise on a variable) keep working as Python.
- **Command audit tests** (`test_commands_audit.py`) freeze the
  "everything that is called must answer" contract: every exposed command
  returns a result with an exit code, builtins all have handlers, the pty
  layer knows every command, and `cli.COMMANDS` matches the `BIN_DIR`
  wrapper list (which now also includes `linux-setup`, `linux`, `gates`).
- `linux-setup` and `gates` now stream progress live through the terminal's
  output sink (module-level `progress_sink`, same pattern as zpip) instead
  of blocking silently until they finish.

### Fixed — more silent-failure class bugs (2026-07-31)
- **`ls` flags are now implemented or rejected — never swallowed.** `ls -R`
  and `ls -t` previously exited 0 with plain output (the same silent-failure
  class as the operator guards) and `ls --color` was accepted and ignored.
  `ls` now supports `-a -l -R -t -r` (any cluster, `--` terminator, GNU-style
  headers for multiple operands and recursive output) and rejects unknown
  flags loudly with `ls: invalid option -- 'X'` and exit 1.
- **Scrollback raised from 32 KiB to 1 MiB per session.** Long outputs (a
  full `ls -R` of a large tree) were truncated mid-listing. 8 sessions ×
  1 MiB bounds the worst case to 8 MiB of RAM, still affordable on Android Go.
- **CI YAML/JSON validation no longer crashes on non-UTF-8 blobs.** A stray
  file with a `.yml`/`.json` suffix (cp1252 `0x82` bytes, an interrupted
  index download) used to kill the whole job with a raw `UnicodeDecodeError`.
  Files are now decoded leniently with the offending offset reported; a
  genuinely broken config still fails, but as a parse error that names the
  file instead of a cryptic crash.

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
