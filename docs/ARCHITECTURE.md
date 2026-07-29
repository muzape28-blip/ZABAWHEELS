# ZMUX Architecture

## Overview

ZMUX is a standalone Android terminal application that runs as a WebView frontend powered by an embedded Python backend (Flask + Waitress + RFC-6455 WebSocket Server). This architecture was chosen because:

1. **Python-for-Android (p4a)** provides a fully featured Python 3 runtime on Android devices.
2. **WebView Bootstrap** allows a responsive, mobile-friendly HTML/CSS/JavaScript terminal UI without heavy native frameworks.
3. **Flask & Pure-Python WebSockets** provide REST API endpoints and real-time bi-directional PTY streaming.
4. **POSIX Pseudo-Terminals (PTY) & Subprocesses** provide authentic command execution with automatic pipe fallback.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       Android Device                        │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                     WebView (UI)                      │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │   terminal.html (xterm.js)                      │  │  │
│  │  │   - Real-time terminal output rendering         │  │  │
│  │  │   - Interactive keyboard input & mobile bar     │  │  │
│  │  │   - Command history & status indicators         │  │  │
│  │  └──────────┬─────────────────────────────┬────────┘  │  │
│  └─────────────┼─────────────────────────────┼───────────┘  │
│                │ HTTP (127.0.0.1 / ::1)      │ WebSocket    │
│  ┌─────────────▼─────────────────────────────▼───────────┐  │
│  │           Python Backend (127.0.0.1 & ::1)            │  │
│  │                                                       │  │
│  │  ┌─────────────────────────┐  ┌─────────────────────┐ │  │
│  │  │     Flask HTTP API      │  │  RFC-6455 WebSocket │ │  │
│  │  │     (/api/exec, stop)   │  │  Server (PTY Stream)│ │  │
│  │  └────────────┬────────────┘  └──────────┬──────────┘ │  │
│  └───────────────┼──────────────────────────┼────────────┘  │
│                  │                          │               │
│  ┌───────────────▼──────────────────────────▼────────────┐  │
│  │                   Terminal Execution Engine           │  │
│  │  ┌──────────────────────────────────────────────────┐ │  │
│  │  │  PTYTerminalSession & subprocess.Popen           │ │  │
│  │  │  - POSIX openpty with standard pipe fallback     │ │  │
│  │  │  - Real-time stdout/stderr binary streaming      │ │  │
│  │  │  - CWD persistence & path traversal protection   │ │  │
│  │  │  - Signal safety (start_new_session=True)        │ │  │
│  │  └──────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                 zpip Package Manager                  │  │
│  │  - HTTPS-only downloads & SHA-256 hash verification   │  │
│  │  - Transactional installations with atomic rollback   │  │
│  │  - In-process Android smoke import verification       │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                 App-Private Storage                   │  │
│  │  home/ projects/ cache/ staging/                      │  │
│  │  user_packages/ installed/ logs/                      │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### Command Execution & PTY Streaming
1. User enters commands via the mobile virtual keyboard or external keyboard in WebView.
2. Interactive keyboard input streams directly over the authenticated WebSocket connection to `PTYTerminalSession`.
3. Non-interactive REST commands POST to `/api/exec` with the 128-bit authentication token.
4. Built-in commands (`cd`, `pwd`, `clear`, `help`) execute internally; external commands spawn via `subprocess.Popen`.
5. Binary terminal output streams asynchronously to all registered WebSocket clients.
6. When an interactive session terminates, exit codes and state transitions are reported to the UI.

### Package Installation (`zpip`)
1. `zpip install <name>` dispatches to the secure `zpip` package manager.
2. Resolves manifest from the curated ZABAWHEELS index or universal PyPI wheels.
3. Downloads package archives over HTTPS with mandatory SHA-256 checksum verification.
4. Validates ZIP archive integrity (rejects path traversal entries and duplicate entries).
5. Extracts files into a temporary staging directory.
6. Runs an in-process smoke import check (`_smoke_test_in_process`) on Android to verify runtime compatibility.
7. Atomically commits files to `user_packages/` and records metadata in the installed package database.
8. On any failure: performs a full rollback without corrupting existing installations.

## Boot & Port Contract (p4a WebView Bootstrap)

The pinned Python-for-Android WebView bootstrap starts `main.py` in a background thread, while `WebViewLoader.testConnection()` polls **`localhost:5000`** (the value of `p4a.port` in `buildozer.spec`) continuously until a TCP connection succeeds before loading `http://127.0.0.1:5000/`. To guarantee reliable boot across Android devices:

- **Strict Android Port 5000 Ownership (`SO_REUSEPORT`):** On Android, the HTTP server must bind exactly port 5000. Setting both `SO_REUSEADDR` and `SO_REUSEPORT` ensures that restarting ZMUX while a previous socket is lingering in `TIME_WAIT` never throws `Address already in use`.
- **Multi-Host Fallback:** If binding `127.0.0.1:5000` fails due to OEM network stack variations, ZMUX automatically retries binding on `0.0.0.0` and `localhost`.
- **Pre-Bound Listener Injection:** Sockets are bound before starting Waitress (`serve(..., sockets=[...])`) and the WebSocket server (`start(listeners=[...])`), eliminating probe-then-bind race conditions.
- **Dual IPv4/IPv6 Loopback Listeners:** Both the HTTP server and WebSocket server listen simultaneously on IPv4 (`127.0.0.1`) and IPv6 (`::1`) loopback addresses, preventing connection hangs when `localhost` resolves to IPv6.

## Freeze & Force-Close Prevention Invariants

- **Bionic libc Signal Safety (ARMv7a / `armeabi-v7a`):** Subprocesses are spawned using POSIX C-level `start_new_session=True` instead of Python `preexec_fn=os.setsid`. In multithreaded Android ARMv7 builds, calling Python functions inside `preexec_fn` after `fork()` causes mutex deadlocks and `SIGSEGV` force closes in Bionic libc.
- **PTY SELinux Fallback:** On Android Go / OEM ROMs where `/dev/ptmx` is restricted by SELinux, `PTYTerminalSession` catches `PermissionError` (Errno 13) and transitions seamlessly to a standard pipe-based shell session.
- **Lock-Free Broadcasts:** `WebSocketServer.broadcast()` sends data outside `clients_lock`. Previously, sending inside the lock caused a deadlock when `_unregister_client()` was invoked on a disconnected client.
- **Send Timeouts (`SO_SNDTIMEO`):** Client sockets use `SO_SNDTIMEO` so a backgrounded WebView cannot block `sendall()` indefinitely.
- **Host Cycling Reconnection:** The terminal UI cycles through loopback candidate hosts (`window.location.hostname`, `127.0.0.1`, `localhost`) across reconnect attempts, preventing silent loading screen hangs.

## Security Boundaries

- **WebView ↔ Server:** Loopback only (`127.0.0.1` / `::1`), protected by a 128-bit random authentication token.
- **Server ↔ Subprocess:** App-private current working directory with clean environment variables.
- **Built-in `cd`:** Strictly restricted to app-private storage (`HOME_DIR`).
- **Package Installations:** HTTPS-only, mandatory SHA-256 validation, path-traversal protected.

## Threat Model

See [SECURITY.md](SECURITY.md) for detailed threat modeling and security mitigations.
