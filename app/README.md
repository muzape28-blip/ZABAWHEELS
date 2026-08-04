# ZMUX Terminal App

Android terminal application for Python development.

## Structure

```
app/
├── main.py              # Entry point
├── buildozer.spec       # APK build configuration
├── zmux/                # Core package
│   ├── __init__.py
│   ├── server.py        # Flask WebView server
│   ├── terminal.py      # Execution engine
│   ├── zpip.py          # Package manager
│   ├── security.py      # Auth token
│   ├── net.py           # TLS/SSL context
│   ├── keystore.py      # Encrypted storage
│   └── paths.py         # Directory management
├── templates/
│   └── terminal.html    # Terminal UI
├── assets/
│   ├── icon.png
│   ├── logo.png
│   └── presplash.png
└── tests/
    ├── conftest.py
    ├── test_terminal.py
    ├── test_zpip.py
    └── test_security.py
```

## Development

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
python main.py  # Start terminal server
```

## Build APK

```bash
pip install buildozer
buildozer android debug
```

## REST compatibility note

The WebView terminal uses the authenticated WebSocket and Alpine PTY session path. REST terminal-session endpoints such as `/api/exec`, `/api/status`, `/api/prompt`, `/api/input`, and `/api/stop` are compatibility-only and expose legacy metadata in their JSON responses.

For legacy `/api/exec` callers, prefer explicit language selection:

```json
{"command": "echo hello", "language": "command"}
{"command": "print(21 + 21)", "language": "python"}
{"command": "echo old flow", "language": "legacy-auto"}
```

See `../docs/REST_COMPATIBILITY.md` and `../docs/REST_EXEC_LANGUAGE_MIGRATION.md` before changing these endpoints.

## Package workflow note

Do not add new user-facing features to the legacy `zpip` package ecosystem.
The supported package workflow is now inside Alpine:

```sh
apk add <package>
python3 -m venv ~/.venv
. ~/.venv/bin/activate
python3 -m pip install <name>
```
