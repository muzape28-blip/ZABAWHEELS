"""
ZMUX Plugins — Addon Registry & Marketplace System
Expanded plugin catalog with functional implementations.
"""

# Plugin registry
MARKETPLACE_PLUGINS = {
    # === Core Plugins ===
    "auto_formatter": {
        "id": "auto_formatter",
        "name": "⚡ Auto-Code Formatter (PEP-8)",
        "author": "Zaba Core",
        "version": "2.0.0",
        "category": "formatting",
        "description": "Automatically formats indentation, spacing, and Python code structure per PEP-8 standards.",
        "description_id": "Secara otomatis merapikan indentasi, spasi, dan struktur kode Python sesuai standar PEP-8.",
        "type": "plugin",
        "mode": "offline",
    },
    "snippet_pack": {
        "id": "snippet_pack",
        "name": "📜 Pro Python Snippets Pack",
        "author": "Zaba Core",
        "version": "2.0.0",
        "category": "productivity",
        "description": "Quick code templates for Flask, BeautifulSoup scraper, AsyncIO, REST API, and more.",
        "description_id": "Template kode cepat untuk Flask, Web Scraper BeautifulSoup, AsyncIO, dan Rest API.",
        "type": "plugin",
        "mode": "offline",
    },
    "syntax_linter": {
        "id": "syntax_linter",
        "name": "🔍 Static Syntax Linter Guard",
        "author": "Zaba Core",
        "version": "2.0.0",
        "category": "quality",
        "description": "Detects colon errors, hanging brackets, indentation typos, and common bugs before running code.",
        "description_id": "Mendeteksi kesalahan titik dua ':', tanda kurung menggantung, dan typo indentasi sebelum kode di-run.",
        "type": "plugin",
        "mode": "offline",
    },
    "symbol_bar": {
        "id": "symbol_bar",
        "name": "⌨️ Extended Mobile Symbol Bar",
        "author": "Zaba Core",
        "version": "2.0.0",
        "category": "productivity",
        "description": "Displays quick symbol buttons (: , ( ), [ ], { }, =, TAB) above the keyboard for mobile typing.",
        "description_id": "Menampilkan bilah tombol simbol cepat di atas keyboard HP.",
        "type": "plugin",
        "mode": "offline",
    },

    # === New v1.0.0 Plugins ===
    "code_minifier": {
        "id": "code_minifier",
        "name": "🗜️ Python Code Minifier",
        "author": "Zaba Core",
        "version": "1.0.0",
        "category": "formatting",
        "description": "Minifies Python code by removing comments, docstrings, and excess whitespace. Great for sharing compact code.",
        "description_id": "Meminifikasi kode Python dengan menghapus komentar, docstring, dan spasi berlebih.",
        "type": "plugin",
        "mode": "offline",
    },
    "json_formatter": {
        "id": "json_formatter",
        "name": "📋 JSON Formatter & Validator",
        "author": "Zaba Core",
        "version": "1.0.0",
        "category": "formatting",
        "description": "Formats and validates JSON data with proper indentation. Detects syntax errors instantly.",
        "description_id": "Memformat dan memvalidasi data JSON dengan indentasi yang benar.",
        "type": "plugin",
        "mode": "offline",
    },
    "regex_tester": {
        "id": "regex_tester",
        "name": "🔤 Regex Tester & Visualizer",
        "author": "Zaba Core",
        "version": "1.0.0",
        "category": "testing",
        "description": "Test regular expressions with real-time matching, group capture, and pattern explanation.",
        "description_id": "Menguji regex dengan pencocokan real-time dan penjelasan pola.",
        "type": "plugin",
        "mode": "offline",
    },
    "color_picker": {
        "id": "color_picker",
        "name": "🎨 Color Picker & Converter",
        "author": "Zaba Core",
        "version": "1.0.0",
        "category": "design",
        "description": "Pick colors and convert between HEX, RGB, and HSV formats. Generates Python color constants.",
        "description_id": "Pilih warna dan konversi antara format HEX, RGB, dan HSV.",
        "type": "plugin",
        "mode": "offline",
    },
    "markdown_preview": {
        "id": "markdown_preview",
        "name": "📝 Markdown Preview Renderer",
        "author": "Zaba Core",
        "version": "1.0.0",
        "category": "productivity",
        "description": "Preview Markdown files rendered to formatted text. Supports headers, lists, code blocks, and links.",
        "description_id": "Preview file Markdown yang di-render ke teks berformat.",
        "type": "plugin",
        "mode": "offline",
    },
    "timer_profiler": {
        "id": "timer_profiler",
        "name": "⏱️ Code Timer & Profiler",
        "author": "Zaba Core",
        "version": "1.0.0",
        "category": "quality",
        "description": "Profiles code execution time per line and function. Identifies performance bottlenecks.",
        "description_id": "Profil waktu eksekusi kode per baris dan fungsi. Identifikasi bottleneck performa.",
        "type": "plugin",
        "mode": "offline",
    },
    "ascii_art": {
        "id": "ascii_art",
        "name": "🎭 ASCII Art Generator",
        "author": "Zaba Community",
        "version": "1.0.0",
        "category": "fun",
        "description": "Generate ASCII art from text. Multiple font styles available.",
        "description_id": "Buat seni ASCII dari teks. Berbagai gaya font tersedia.",
        "type": "plugin",
        "mode": "offline",
    },
    "todo_manager": {
        "id": "todo_manager",
        "name": "✅ TODO & Task Manager",
        "author": "Zaba Core",
        "version": "1.0.0",
        "category": "productivity",
        "description": "Extracts TODO/FIXME/HACK comments from code and manages task lists.",
        "description_id": "Mengekstrak komentar TODO/FIXME/HACK dari kode dan mengelola daftar tugas.",
        "type": "plugin",
        "mode": "offline",
    },

    # === New v1.1.0 Transform Plugins ===
    "auto_import_optimizer": {
        "id": "auto_import_optimizer",
        "name": "🔬 Auto-Import Optimizer",
        "author": "Zaba Core",
        "version": "1.1.0",
        "category": "productivity",
        "description": "AST-based unused import detector and optimizer. Finds and cleans up redundant import statements.",
        "description_id": "Pendeteksi dan pengoptimal import tak terpakai berbasis AST. Menemukan dan merapikan import mubazir.",
        "type": "plugin",
        "mode": "offline",
    },
    "duplicate_line_detector": {
        "id": "duplicate_line_detector",
        "name": "📊 Duplicate Line Detector",
        "author": "Zaba Core",
        "version": "1.1.0",
        "category": "quality",
        "description": "Finds duplicate lines of code to promote the DRY (Don't Repeat Yourself) principle.",
        "description_id": "Mendeteksi baris kode yang duplikat untuk mendorong prinsip DRY (Don't Repeat Yourself).",
        "type": "plugin",
        "mode": "offline",
    },
    "smart_comment_generator": {
        "id": "smart_comment_generator",
        "name": "🧠 Smart Comment Generator",
        "author": "Zaba Core",
        "version": "1.1.0",
        "category": "productivity",
        "description": "Generates docstrings dynamically for Python functions based on arguments and return statements.",
        "description_id": "Membuat docstring secara otomatis untuk fungsi Python berdasarkan argumen dan return.",
        "type": "plugin",
        "mode": "offline",
    },
    "code_beautifier_pro": {
        "id": "code_beautifier_pro",
        "name": "⚡ Code Beautifier Pro",
        "author": "Zaba Core",
        "version": "1.1.0",
        "category": "formatting",
        "description": "Formats your Python code to match standard PEP-8 spacing, omitting strings and comments.",
        "description_id": "Merapikan kode Python Anda agar sesuai standar spasi PEP-8, mengabaikan string dan komentar.",
        "type": "plugin",
        "mode": "offline",
    },
    "variable_type_hint_generator": {
        "id": "variable_type_hint_generator",
        "name": "🔐 Variable Type Hint Gen",
        "author": "Zaba Core",
        "version": "1.1.0",
        "category": "quality",
        "description": "Injects type hint annotations dynamically to promote safer and robust coding.",
        "description_id": "Menyisipkan anotasi type hint secara dinamis untuk mendorong kode yang lebih aman dan tangguh.",
        "type": "plugin",
        "mode": "offline",
    },
}

# Active plugins state (persisted in memory; can be saved to config)
_active_plugins: set = {"auto_formatter", "snippet_pack", "syntax_linter", "symbol_bar"}


def get_all_plugins() -> dict:
    """Get all available plugins with their active status."""
    result = {}
    for pid, info in MARKETPLACE_PLUGINS.items():
        item = info.copy()
        item["active"] = pid in _active_plugins
        result[pid] = item
    return result


def toggle_plugin(plugin_id: str) -> dict:
    """Toggle a plugin on/off. Returns updated plugin info."""
    if plugin_id not in MARKETPLACE_PLUGINS:
        return {"ok": False, "message": "Plugin not found"}

    if plugin_id in _active_plugins:
        _active_plugins.discard(plugin_id)
        return {"ok": True, "active": False, "message": f"Plugin '{plugin_id}' deactivated"}
    else:
        _active_plugins.add(plugin_id)
        return {"ok": True, "active": True, "message": f"Plugin '{plugin_id}' activated"}


def is_plugin_active(plugin_id: str) -> bool:
    """Check if a plugin is active."""
    return plugin_id in _active_plugins


def get_active_plugins() -> list[str]:
    """Get list of active plugin IDs."""
    return list(_active_plugins)


# Plugin snippet templates
SNIPPET_TEMPLATES = {
    "flask_app": {
        "name": "Flask Web App",
        "code": '''from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({"message": "Hello from ZMUX!"})

@app.route("/api/data")
def get_data():
    return jsonify({"items": []})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
''',
    },
    "web_scraper": {
        "name": "Web Scraper (BS4)",
        "code": '''import requests
from bs4 import BeautifulSoup

url = "https://example.com"
response = requests.get(url, timeout=10)

if response.status_code == 200:
    soup = BeautifulSoup(response.text, "html.parser")
    titles = soup.find_all("h1")
    for title in titles:
        print(title.get_text(strip=True))
else:
    print(f"Error: {response.status_code}")
''',
    },
    "async_fetch": {
        "name": "Async HTTP Fetcher",
        "code": '''import asyncio
import urllib.request

async def fetch(url):
    loop = asyncio.get_event_loop()
    req = urllib.request.Request(url)
    response = await loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10))
    data = response.read().decode("utf-8", errors="replace")
    print(f"Fetched {len(data)} bytes from {url}")
    return data

async def main():
    urls = ["https://httpbin.org/get", "https://httpbin.org/ip"]
    results = await asyncio.gather(*[fetch(u) for u in urls])
    for r in results:
        print(r[:200])

asyncio.run(main())
''',
    },
    "rest_api": {
        "name": "REST API Client",
        "code": '''import json
import urllib.request

def api_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def api_post(url, data, headers=None):
    body = json.dumps(data).encode()
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

# Example
result = api_get("https://httpbin.org/get")
print(json.dumps(result, indent=2))
''',
    },
    "file_io": {
        "name": "File I/O Template",
        "code": '''from pathlib import Path

# Read file
def read_file(filepath):
    path = Path(filepath)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None

# Write file
def write_file(filepath, content):
    Path(filepath).write_text(content, encoding="utf-8")

# Example
content = read_file("data.txt")
if content:
    print(content)
else:
    write_file("data.txt", "Hello, ZMUX!")
    print("File created!")
''',
    },
    "sqlite_crud": {
        "name": "SQLite CRUD Template",
        "code": '''import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / "app.db"
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Create table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE
    )
""")

# Insert
cursor.execute("INSERT OR IGNORE INTO users (name, email) VALUES (?, ?)", ("Zaba", "zaba@zabacode.dev"))

# Read
cursor.execute("SELECT * FROM users")
for row in cursor.fetchall():
    print(row)

conn.commit()
conn.close()
print("SQLite CRUD done!")
''',
    },
    "tinydb_doc": {
        "name": "TinyDB Document Store",
        "code": '''from tinydb import TinyDB, Query

db = TinyDB("app_db.json")

# Insert
db.insert({"name": "ZMUX", "version": "1.0.0", "type": "IDE"})

# Search
Item = Query()
results = db.search(Item.name == "ZMUX")
print("Found:", results)

# Update
db.update({"version": "1.0.1"}, Item.name == "ZMUX")

# All records
print("All:", db.all())

db.close()
''',
    },
    "class_template": {
        "name": "Python Class Template",
        "code": '''class DataProcessor:
    """Template class for data processing."""
    
    def __init__(self, name: str):
        self.name = name
        self._data = []
    
    @property
    def data(self):
        return self._data
    
    @data.setter
    def data(self, value):
        self._data = value
    
    def add(self, item):
        self._data.append(item)
    
    def process(self):
        return [str(x).upper() for x in self._data]
    
    def __len__(self):
        return len(self._data)
    
    def __repr__(self):
        return f"DataProcessor({self.name!r}, items={len(self)})"

# Usage
proc = DataProcessor("test")
proc.add("hello")
proc.add("world")
print(proc.process())
print(repr(proc))
''',
    },
}


def get_snippets() -> dict:
    """Get all available snippet templates."""
    return SNIPPET_TEMPLATES.copy()
