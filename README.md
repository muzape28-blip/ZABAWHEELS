# ZMUX — Android Terminal for Python

**ZMUX** adalah terminal Python Android mandiri yang menggunakan ZABAWHEELS sebagai package/wheel infrastructure.

## Apa itu ZMUX?

ZMUX adalah terminal emulator untuk Android yang memungkinkan Anda:
- Menjalankan command shell dan Python secara real
- Menggunakan `zpip` untuk install package Python
- Bekerja dalam lingkungan app-private yang aman
- Mengakses Python interpreter langsung dari device Android

**ZMUX BUKAN:**
- IDE atau code editor
- Zabacode dengan nama berbeda
- Simulasi terminal dengan output palsu
- Editor dengan AI assistant atau marketplace

## Fitur

### Terminal Nyata
- ✅ Eksekusi command real via subprocess
- ✅ stdout/stderr streaming
- ✅ stdin interaktif
- ✅ Exit code nyata
- ✅ Ctrl+C/Stop untuk cancel proses
- ✅ Timeout opsional
- ✅ Working directory persisten

### Command Built-in
```bash
help          # Bantuan
clear         # Clear screen
pwd           # Print working directory
cd <dir>      # Change directory
ls, cat, mkdir, touch, cp, mv, rm, echo, env, which, uname
python        # Python interpreter
python <file> # Run Python script
python -c "..." # Execute Python code
pip           # Python package manager (jika tersedia)
zpip          # ZMUX package manager
zmux-info     # Runtime fingerprint
exit          # Exit terminal
```

### zpip Package Manager
```bash
zpip search <name>      # Search packages
zpip info <name>        # Package info
zpip install <name>     # Install package
zpip install <name> <version>  # Install specific version
zpip list               # List installed
zpip verify <name>      # Verify installation
zpip uninstall <name>   # Uninstall package
zpip doctor             # System health check
```

### Keamanan
- ✅ HTTPS verification aktif
- ✅ SHA-256 wajib untuk wheel
- ✅ Path traversal protection
- ✅ Duplicate ZIP entry rejection
- ✅ Transactional install dengan rollback
- ✅ File ownership tracking
- ✅ Auth token untuk WebView security

## Spesifikasi APK

- **App title:** ZMUX
- **Package name:** zmux
- **Application ID:** com.zaba.zmux
- **Version:** 1.0.0
- **Min Android API:** 26
- **Target Android API:** 34
- **ABI:** armeabi-v7a, arm64-v8a
- **Orientation:** portrait
- **Ads:** zero
- **Telemetry:** zero
- **Permissions:** INTERNET only

## Instalasi

### Download APK
Download APK terbaru dari [GitHub Actions](../../actions/workflows/build-zmux-apk.yml).

Artifact yang dihasilkan:
- `zmux-1.0.0-universal-debug.apk`
- `SHA256SUMS`
- `build-contract.json`

### Build dari Source
```bash
cd app
pip install buildozer
buildozer android debug
```

Lihat [docs/BUILDING.md](docs/BUILDING.md) untuk detail.

## Arsitektur

```
ZMUX Terminal
├── Backend (Python/Flask)
│   ├── server.py          # Flask WebView server
│   ├── terminal.py        # Execution engine (subprocess)
│   ├── zpip.py           # Package manager
│   ├── security.py       # Auth token
│   └── paths.py          # App-private directories
│
├── Frontend (HTML/CSS/JS)
│   └── terminal.html     # Terminal UI
│
└── Infrastructure (ZABAWHEELS)
    ├── index/            # Package index
    ├── packages/         # Wheel recipes
    ├── scripts/          # Build & validation
    └── toolchain/        # Runtime lock
```

## Runtime Fingerprint

Jalankan `zmux-info` atau `zpip doctor` untuk melihat:
- App version
- Python version & implementation
- SOABI & EXT_SUFFIX
- ABI (armeabi-v7a/arm64-v8a)
- Android API level
- Runtime ID
- p4a commit & NDK version
- Current working directory
- User package directory
- Free storage
- Installed packages

## Status

| Komponen | Status |
|----------|--------|
| Terminal UI | Implemented |
| Execution Engine | Implemented |
| zpip Package Manager | Implemented |
| GitHub Actions Build | CI-built |
| ARMv7 Support | Statically inspected |
| ARM64 Support | Statically inspected |
| Device Testing | Pending |
| Native Packages | Planned |

**Catatan:** Native package (seperti NumPy) belum tersedia. ZMUX akan memberikan pesan jujur jika package tidak tersedia untuk runtime/ABI tertentu.

## ZABAWHEELS Infrastructure

ZMUX menggunakan ZABAWHEELS sebagai:
1. **Package index** - Curated wheel repository
2. **Build pipeline** - APK build automation
3. **Runtime contract** - Reproducible builds
4. **Security validation** - Wheel inspection & verification

Lihat [ZABAWHEELS.md](ZABAWHEELS.md) untuk detail infrastructure.

## Development

### Setup
```bash
cd app
pip install -r requirements-dev.txt
pip install -e .
```

### Testing
```bash
cd app
pytest tests/
```

### Local Development
```bash
cd app
python main.py
# Terminal akan berjalan di http://127.0.0.1:5000
```

## Security

Lihat [docs/SECURITY.md](docs/SECURITY.md) untuk:
- Threat model
- Auth token mechanism
- Wheel validation
- Path traversal protection
- TLS/SSL context

## Limitations

### Terminal
- Built-in `cd` command membatasi traversal ke home directory untuk keamanan
- Shell commands (`/system/bin/sh`) dapat mengakses area yang diizinkan Android OS
- Tidak ada PTY (pseudo-terminal) - menggunakan subprocess pipe
- Interactive REPL terbatas pada line-buffered I/O

### Package Manager
- Native wheel hanya dari ZABAWHEELS index yang match runtime/ABI
- Pure Python `py3-none-any` boleh dari PyPI
- Tidak ada `--trusted-host` atau disable TLS verification
- Package seperti NumPy mungkin belum tersedia

## Roadmap

- [ ] Device testing (ARMv7 & ARM64)
- [ ] PTY support untuk full interactive REPL
- [ ] Native package builds (NumPy, Pillow, dll)
- [ ] Session management (multiple terminal tabs)
- [ ] File browser untuk working directory
- [ ] SSH client integration

## Kontribusi

Lihat [CONTRIBUTING.md](CONTRIBUTING.md) untuk guideline.

## License

[LICENSE](LICENSE)

## Credits

- **Python-for-Android** - Android Python runtime
- **Buildozer** - APK build tool
- **Flask** - Web framework
- **Waitress** - WSGI server

---

**ZMUX** — Terminal Python Android yang jujur dan transparan.
