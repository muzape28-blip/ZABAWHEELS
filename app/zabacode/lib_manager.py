"""
ZMUX Library Manager — zabapip + PyPI Direct Extractor
Expanded library catalog with offline/online capability indicators.

Mode definitions:
  offline  — Works completely without internet (pure Python, no external deps)
  online   — Requires internet to function (API clients, web scrapers)
  hybrid   — Core features work offline, some features need internet
  buildtime — Requires compiled C-extensions, must be in buildozer.spec
"""

import io
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.request
import zipfile

from zabacode.core.net import TLS_HELP_MESSAGE, get_ssl_context
from zabacode.core.paths import CACHE_DIR, USER_PACKAGES_DIR

_PACKAGE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")


# ---------------------------------------------------------------------------
# Library Catalog — Expanded with offline/online/hybrid mode indicators
# ---------------------------------------------------------------------------

KNOWN_LIBRARIES = {
    # === Web & Networking ===
    "requests": {
        "tier": "runtime", "category": "Web & API",
        "mode": "online",
        "reason": "HTTP client paling populer untuk Python. Memerlukan internet untuk request."
    },
    "httpx": {
        "tier": "runtime", "category": "Web & API",
        "mode": "online",
        "reason": "Async & sync HTTP client modern dengan HTTP/2. Memerlukan internet."
    },
    "urllib3": {
        "tier": "runtime", "category": "Web & API",
        "mode": "online",
        "reason": "HTTP client tangguh penyokong requests. Memerlukan internet."
    },
    "flask": {
        "tier": "runtime", "category": "Web & API",
        "mode": "hybrid",
        "reason": "Micro web framework. Bisa jalan lokal (127.0.0.1) tanpa internet."
    },
    "fastapi": {
        "tier": "runtime", "category": "Web & API",
        "mode": "hybrid",
        "reason": "Web framework berperforma tinggi ASGI. Bisa jalan lokal."
    },
    "aiohttp": {
        "tier": "runtime", "category": "Web & API",
        "mode": "online",
        "reason": "HTTP client/server asinkronus. Memerlukan internet untuk client mode."
    },
    "websockets": {
        "tier": "runtime", "category": "Web & API",
        "mode": "hybrid",
        "reason": "WebSocket client/server. Server bisa jalan offline, client perlu jaringan."
    },
    "selenium": {
        "tier": "runtime", "category": "Web & API",
        "mode": "online",
        "reason": "Browser automation framework. Memerlukan internet & browser."
    },

    # === Web Scraping ===
    "beautifulsoup4": {
        "tier": "runtime", "category": "Web & Scraping",
        "mode": "hybrid",
        "reason": "HTML/XML parser. Parsing bisa offline, fetch data perlu internet."
    },
    "lxml": {
        "tier": "buildtime", "category": "Web & Scraping",
        "mode": "hybrid",
        "reason": "High-performance XML/HTML parser (C-ext). Parsing offline, fetch online."
    },
    "mechanize": {
        "tier": "runtime", "category": "Web & Scraping",
        "mode": "online",
        "reason": "Stateful programmatic web browsing. Memerlukan internet."
    },
    "feedparser": {
        "tier": "runtime", "category": "Web & Scraping",
        "mode": "online",
        "reason": "RSS/Atom feed parser. Fetch feed perlu internet."
    },

    # === Data, Math & Science ===
    "numpy": {
        "tier": "buildtime", "category": "Data & Math",
        "mode": "offline",
        "reason": "Komputasi matriks C-extension. 100% offline setelah install. Tambahkan ke buildozer.spec."
    },
    "pandas": {
        "tier": "buildtime", "category": "Data & Math",
        "mode": "offline",
        "reason": "Analisis & manipulasi data. 100% offline setelah install. Tambahkan ke buildozer.spec."
    },
    "scipy": {
        "tier": "buildtime", "category": "Data & Math",
        "mode": "offline",
        "reason": "Modul ilmiah C-extension. 100% offline. Tambahkan ke buildozer.spec."
    },
    "matplotlib": {
        "tier": "buildtime", "category": "Data & Math",
        "mode": "offline",
        "reason": "Visualisasi grafik 2D. 100% offline setelah install. Tambahkan ke buildozer.spec."
    },
    "sympy": {
        "tier": "runtime", "category": "Data & Math",
        "mode": "offline",
        "reason": "Matematika simbolik & aljabar murni Python. 100% offline."
    },
    "statistics": {
        "tier": "runtime", "category": "Data & Math",
        "mode": "offline",
        "reason": "Built-in Python statistics module. 100% offline (stdlib)."
    },
    "cmath": {
        "tier": "runtime", "category": "Data & Math",
        "mode": "offline",
        "reason": "Built-in complex math module. 100% offline (stdlib)."
    },

    # === Database & Storage ===
    "tinydb": {
        "tier": "runtime", "category": "Database",
        "mode": "offline",
        "reason": "Dokumen NoSQL JSON ringan murni Python. 100% offline."
    },
    "peewee": {
        "tier": "runtime", "category": "Database",
        "mode": "offline",
        "reason": "ORM sederhana & ekspresif. 100% offline (SQLite)."
    },
    "sqlalchemy": {
        "tier": "runtime", "category": "Database",
        "mode": "offline",
        "reason": "Toolkit SQL & ORM standar industri. 100% offline (SQLite)."
    },
    "redis": {
        "tier": "runtime", "category": "Database",
        "mode": "online",
        "reason": "Client untuk Redis server. Memerlukan Redis server berjalan."
    },
    "dataset": {
        "tier": "runtime", "category": "Database",
        "mode": "offline",
        "reason": "Simplified SQLite abstraction. 100% offline."
    },
    "sqlite3": {
        "tier": "runtime", "category": "Database",
        "mode": "offline",
        "reason": "Built-in SQLite3 module. 100% offline (stdlib)."
    },

    # === AI & Automation ===
    "openai": {
        "tier": "runtime", "category": "AI & Automation",
        "mode": "online",
        "reason": "Pustaka API resmi OpenAI. Memerlukan API key & internet."
    },
    "google-generativeai": {
        "tier": "runtime", "category": "AI & Automation",
        "mode": "online",
        "reason": "SDK resmi Google Gemini AI. Memerlukan API key & internet."
    },
    "schedule": {
        "tier": "runtime", "category": "AI & Automation",
        "mode": "offline",
        "reason": "Penjadwalan job/task berkala. 100% offline."
    },
    "pyttsx3": {
        "tier": "runtime", "category": "AI & Automation",
        "mode": "offline",
        "reason": "Text-to-speech offline engine. 100% offline (uses system TTS)."
    },
    "speechrecognition": {
        "tier": "runtime", "category": "AI & Automation",
        "mode": "hybrid",
        "reason": "Speech recognition library. Google API mode online, Sphinx mode offline."
    },

    # === Formatting & Utilities ===
    "rich": {
        "tier": "runtime", "category": "Utilities",
        "mode": "offline",
        "reason": "Teks berformat, warna terminal, tabel kaya. 100% offline."
    },
    "colorama": {
        "tier": "runtime", "category": "Utilities",
        "mode": "offline",
        "reason": "Format warna ANSI terminal. 100% offline."
    },
    "tabulate": {
        "tier": "runtime", "category": "Utilities",
        "mode": "offline",
        "reason": "Format cetak tabel dari array/dict. 100% offline."
    },
    "pydantic": {
        "tier": "runtime", "category": "Utilities",
        "mode": "offline",
        "reason": "Validasi data & pengaturan bertipe. 100% offline."
    },
    "pytz": {
        "tier": "runtime", "category": "Utilities",
        "mode": "offline",
        "reason": "Pengelolaan zona waktu dunia. 100% offline."
    },
    "pyjwt": {
        "tier": "runtime", "category": "Utilities",
        "mode": "offline",
        "reason": "Enkodasi dan dekodasi JSON Web Tokens. 100% offline."
    },
    "python-dotenv": {
        "tier": "runtime", "category": "Utilities",
        "mode": "offline",
        "reason": "Load .env environment variables. 100% offline."
    },
    "click": {
        "tier": "runtime", "category": "Utilities",
        "mode": "offline",
        "reason": "Command-line interface creation kit. 100% offline."
    },
    "tqdm": {
        "tier": "runtime", "category": "Utilities",
        "mode": "offline",
        "reason": "Progress bar untuk loops & iterasi. 100% offline."
    },
    "loguru": {
        "tier": "runtime", "category": "Utilities",
        "mode": "offline",
        "reason": "Logging library yang simpel dan powerful. 100% offline."
    },
    "pathlib2": {
        "tier": "runtime", "category": "Utilities",
        "mode": "offline",
        "reason": "Backport of pathlib. 100% offline."
    },

    # === Cryptography & Security ===
    "cryptography": {
        "tier": "buildtime", "category": "Security",
        "mode": "offline",
        "reason": "Cryptographic primitives (C-ext). 100% offline. Tambahkan ke buildozer.spec."
    },
    "bcrypt": {
        "tier": "buildtime", "category": "Security",
        "mode": "offline",
        "reason": "Password hashing (C-ext). 100% offline. Tambahkan ke buildozer.spec."
    },
    "passlib": {
        "tier": "runtime", "category": "Security",
        "mode": "offline",
        "reason": "Password hashing library. 100% offline."
    },
    "hashlib": {
        "tier": "runtime", "category": "Security",
        "mode": "offline",
        "reason": "Built-in hash functions. 100% offline (stdlib)."
    },

    # === Media, Image & Audio ===
    "pillow": {
        "tier": "buildtime", "category": "Media & Images",
        "mode": "offline",
        "reason": "Pemrosesan gambar PIL (C-ext). 100% offline. Tambahkan ke buildozer.spec."
    },
    "pygame": {
        "tier": "buildtime", "category": "Games & Media",
        "mode": "offline",
        "reason": "Engine game 2D & grafik (C-ext). 100% offline. Tambahkan ke buildozer.spec."
    },
    "pydub": {
        "tier": "runtime", "category": "Games & Media",
        "mode": "offline",
        "reason": "Manipulasi audio sederhana. 100% offline."
    },
    "mutagen": {
        "tier": "runtime", "category": "Games & Media",
        "mode": "offline",
        "reason": "Audio metadata reader/writer. 100% offline."
    },

    # === Testing ===
    "pytest": {
        "tier": "runtime", "category": "Testing",
        "mode": "offline",
        "reason": "Testing framework yang powerful. 100% offline."
    },
    "unittest": {
        "tier": "runtime", "category": "Testing",
        "mode": "offline",
        "reason": "Built-in testing framework. 100% offline (stdlib)."
    },
    "mock": {
        "tier": "runtime", "category": "Testing",
        "mode": "offline",
        "reason": "Mock object library. 100% offline."
    },

    # === Serialization & Data Format ===
    "orjson": {
        "tier": "buildtime", "category": "Data Format",
        "mode": "offline",
        "reason": "Ultra-fast JSON parser (Rust). 100% offline. Tambahkan ke buildozer.spec."
    },
    "toml": {
        "tier": "runtime", "category": "Data Format",
        "mode": "offline",
        "reason": "TOML parser/writer. 100% offline."
    },
    "pyyaml": {
        "tier": "runtime", "category": "Data Format",
        "mode": "offline",
        "reason": "YAML parser/emitter. 100% offline."
    },
    "csv": {
        "tier": "runtime", "category": "Data Format",
        "mode": "offline",
        "reason": "Built-in CSV reader/writer. 100% offline (stdlib)."
    },

    # === Networking & Protocol ===
    "paramiko": {
        "tier": "runtime", "category": "Networking",
        "mode": "online",
        "reason": "SSH2 protocol library. Memerlukan SSH server."
    },
    "ftplib": {
        "tier": "runtime", "category": "Networking",
        "mode": "online",
        "reason": "Built-in FTP client. Memerlukan FTP server."
    },
    "smtplib": {
        "tier": "runtime", "category": "Networking",
        "mode": "online",
        "reason": "Built-in SMTP email client. Memerlukan email server."
    },
    "socket": {
        "tier": "runtime", "category": "Networking",
        "mode": "hybrid",
        "reason": "Built-in low-level networking. Bisa lokal atau remote."
    },
}


# ---------------------------------------------------------------------------
# Package Detection
# ---------------------------------------------------------------------------

_IMPORT_MAP = {
    "beautifulsoup4": "bs4",
    "google-generativeai": "google.generativeai",
    "python-dotenv": "dotenv",
    "pillow": "PIL",
    "pyjwt": "jwt",
    "pyyaml": "yaml",
    "speechrecognition": "speech_recognition",
}


def is_package_installed(package_name: str) -> bool:
    """Check if a package is installed and importable."""
    module = _IMPORT_MAP.get(package_name.lower(), package_name.lower().replace("-", "_"))
    try:
        __import__(module)
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Installation Engine
# ---------------------------------------------------------------------------

def _fallback_pypi_download(name: str) -> tuple[bool, str]:
    """Install a pure-Python wheel with verified TLS, SHA-256 and archive-path checks.

    Certificate verification is never bypassed: a MITM could otherwise swap the
    wheel for arbitrary code that we would extract and import.
    """
    import hashlib

    try:
        ctx = get_ssl_context()
        pypi_url = f"https://pypi.org/pypi/{name}/json"
        req = urllib.request.Request(pypi_url, headers={"User-Agent": "ZMUX/1.0.0"})

        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))

        target_wheel_url = None
        expected_sha256 = ""
        for item in data.get("urls", []):
            if item.get("filename", "").lower().endswith("none-any.whl"):
                target_wheel_url = item.get("url")
                expected_sha256 = (item.get("digests") or {}).get("sha256", "")
                break

        if not target_wheel_url:
            return False, f"'{name}' requires a compiled C-extension. Please add it to buildozer.spec and rebuild the APK."

        wheel_req = urllib.request.Request(target_wheel_url, headers={"User-Agent": "ZMUX/1.0.0"})
        with urllib.request.urlopen(wheel_req, timeout=60, context=ctx) as resp_wheel:
            wheel_bytes = resp_wheel.read()

        # Integrity: the wheel must match the hash PyPI advertised.
        if expected_sha256:
            actual = hashlib.sha256(wheel_bytes).hexdigest()
            if actual != expected_sha256:
                return False, f"Integrity check failed for '{name}': the downloaded wheel does not match the SHA-256 published by PyPI. Installation aborted."

        with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as z:
            base = USER_PACKAGES_DIR.resolve()
            for member in z.infolist():
                target = (base / member.filename).resolve()
                if target != base and base not in target.parents:
                    raise ValueError("Wheel contains unsafe path.")
            z.extractall(base)

        return True, f"'{name}' installed successfully via Direct PyPI Extractor!"
    except ssl.SSLCertVerificationError:
        return False, f"Cannot install '{name}': {TLS_HELP_MESSAGE}"
    except Exception as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            return False, f"Cannot install '{name}': {TLS_HELP_MESSAGE}"
        return False, f"Direct Extractor Error: {e}"


def install_library(name: str) -> dict:
    """Install through the transactional ZMUX package manager.

    The legacy direct extractor and unrestricted pip fallback are deliberately
    not used: both could leave a partially upgraded environment.  ``zpip``
    verifies the advertised hash, extracts into staging, smoke-imports, commits
    owned files, and rolls back on every failure.
    """
    from zabacode.core.zabapip import install

    result = install(name)
    if result.get("ok"):
        result["message"] = (
            f"'{result['package']}' {result.get('version', '')} installed "
            f"transactionally ({result.get('files', 0)} files)."
        )
    else:
        result["message"] = result.get("error", "Installation failed")
    return result


def get_library_info(name: str) -> dict | None:
    """Get library info including install status."""
    info = KNOWN_LIBRARIES.get(name)
    if not info:
        return None
    result = info.copy()
    result["name"] = name
    result["installed"] = is_package_installed(name)
    return result


def get_all_libraries() -> dict:
    """Get all libraries with their info and install status."""
    result = {}
    for name, info in KNOWN_LIBRARIES.items():
        item = info.copy()
        item["installed"] = is_package_installed(name)
        result[name] = item
    return result
