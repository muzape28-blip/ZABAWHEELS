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

## Security Boundaries

- **WebView ↔ Server**: Loopback only (127.0.0.1), auth token validated
- **Server ↔ Subprocess**: App-private CWD, environment control
- **Built-in cd**: Restricts to HOME_DIR
- **Shell commands**: Can access OS-permitted areas (documented)
- **Package installs**: HTTPS-only, hash-verified, path-safe

## Threat Model

See [SECURITY.md](SECURITY.md) for detailed threat model.
