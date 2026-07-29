# ZMUX Architecture

## Overview

ZMUX adalah terminal Android yang berjalan sebagai WebView app di atas Python backend (Flask + Waitress). Arsitektur ini dipilih karena:

1. **Python-for-Android** menyediakan Python runtime di Android
2. **WebView bootstrap** memungkinkan UI HTML/CSS/JS tanpa Kivy
3. **Flask** menyediakan REST API untuk terminal operations
4. **Subprocess** untuk eksekusi command real

## Component Diagram

```
┌─────────────────────────────────────────┐
│              Android Device              │
│                                          │
│  ┌──────────────────────────────────┐   │
│  │         WebView (UI)              │   │
│  │  ┌──────────────────────────┐    │   │
│  │  │   terminal.html          │    │   │
│  │  │   - Terminal output      │    │   │
│  │  │   - Command input        │    │   │
│  │  │   - History navigation   │    │   │
│  │  │   - Status indicator     │    │   │
│  │  └──────────┬───────────────┘    │   │
│  └─────────────┼────────────────────┘   │
│                │ HTTP (loopback)          │
│  ┌─────────────▼────────────────────┐   │
│  │     Flask Server (127.0.0.1)      │   │
│  │                                    │   │
│  │  ┌──────────┐  ┌───────────────┐ │   │
│  │  │  /api/   │  │   Security    │ │   │
│  │  │  exec    │  │   (Auth)      │ │   │
│  │  │  input   │  │               │ │   │
│  │  │  stop    │  └───────────────┘ │   │
│  │  │  status  │                     │   │
│  │  └─────┬────┘                     │   │
│  └────────┼──────────────────────────┘   │
│           │                               │
│  ┌────────▼──────────────────────────┐   │
│  │       Terminal Engine              │   │
│  │  ┌──────────────────────────────┐ │   │
│  │  │  subprocess.Popen            │ │   │
│  │  │  - stdout/stderr streaming   │ │   │
│  │  │  - stdin handling            │ │   │
│  │  │  - exit code tracking        │ │   │
│  │  │  - CWD persistence           │ │   │
│  │  └──────────────────────────────┘ │   │
│  │                                    │   │
│  │  ┌──────────────────────────────┐ │   │
│  │  │  Built-in Commands           │ │   │
│  │  │  - cd, pwd, clear, help      │ │   │
│  │  │  - Path traversal protection │ │   │
│  │  └──────────────────────────────┘ │   │
│  └────────────────────────────────────┘   │
│                                            │
│  ┌────────────────────────────────────┐   │
│  │        zpip Package Manager        │   │
│  │  - HTTPS-only downloads            │   │
│  │  - SHA-256 verification            │   │
│  │  - Transactional install           │   │
│  │  - Dependency resolution           │   │
│  │  - Cycle detection                 │   │
│  └────────────────────────────────────┘   │
│                                            │
│  ┌────────────────────────────────────┐   │
│  │        App-Private Storage         │   │
│  │  home/ projects/ cache/ staging/   │   │
│  │  user_packages/ installed/ logs/   │   │
│  └────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

## Data Flow

### Command Execution
1. User types command in WebView input
2. JavaScript sends POST to `/api/exec` with auth token
3. Flask validates token, dispatches to terminal engine
4. Built-in commands handled internally; others spawn subprocess
5. stdout/stderr captured via pipe reader threads
6. Result returned as JSON with exit code
7. JavaScript renders output in terminal area

### Package Installation (zpip)
1. `zpip install <name>` → dispatches to zpip module
2. Resolve manifest from ZABAWHEELS index or PyPI
3. Download wheel over HTTPS with SHA-256 verification
4. Validate ZIP structure (no traversal, no duplicates)
5. Extract to staging directory
6. Smoke-import test
7. Atomic commit to user_packages/
8. Record in installed database
9. On failure: full rollback

## Boot & Port Contract (p4a webview bootstrap)

The pinned p4a webview bootstrap starts `main.py` in a background thread, then
`WebViewLoader.testConnection()` polls **`localhost:5000`** (the value of
`p4a.port` in `buildozer.spec`) *forever* until a TCP connect succeeds, and only
then loads `http://127.0.0.1:5000/` into the WebView. Consequences, enforced in
`zmux.server.run_server()`:

- **On Android the HTTP server must bind exactly port 5000.** Moving to another
  port when 5000 is busy leaves the WebView waiting forever (the stuck loading
  screen). Instead, binding is retried for 30 s (a zombie process from a
  previous launch may hold the port briefly) and fails loudly into
  `zmux_crash.log` afterwards.
- **Listeners are bound before serving** and handed to Waitress
  (`serve(..., sockets=[...])`) and to the WebSocket server
  (`start(listener=...)`), eliminating probe-then-bind races.
- **A best-effort second listener on `::1`** is added because the bootstrap
  pings the hostname `localhost`, which may resolve to IPv6 on some devices.
- The terminal UI talks to the PTY over a WebSocket whose port is injected into
  the page (`WS_PORT`) together with the auth token; the CSP `connect-src`
  allows exactly that port.

## Freeze-avoidance invariants

- `WebSocketServer.broadcast()` never calls `_unregister_client()` while
  holding `clients_lock` (that re-entry deadlocked the PTY reader thread
  permanently after any unclean WebView disconnect, e.g. rotation/reload).
  Sends run outside the lock; failed clients are removed afterwards.
- Client sockets get `SO_SNDTIMEO` (best-effort) so a suspended WebView that
  stops draining its TCP buffer cannot block `sendall()` forever.
- PTY shells are spawned with `setsid`; `killpg()` is only used when the child
  actually owns a process group, otherwise it would kill the app itself.
- The frontend retries WebSocket connections a bounded number of times, then
  shows a tappable retry state instead of an infinite silent spinner.

## Security Boundaries

- **WebView ↔ Server**: Loopback only (127.0.0.1), auth token validated
- **Server ↔ Subprocess**: App-private CWD, environment control
- **Built-in cd**: Restricts to HOME_DIR
- **Shell commands**: Can access OS-permitted areas (documented)
- **Package installs**: HTTPS-only, hash-verified, path-safe

## Threat Model

See [SECURITY.md](SECURITY.md) for detailed threat model.
