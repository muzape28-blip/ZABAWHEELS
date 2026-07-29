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
