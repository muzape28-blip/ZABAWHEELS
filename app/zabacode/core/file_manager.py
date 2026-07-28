"""
ZMUX Core — Safe File System & Path Traversal Protection
CRUD operations for user files with comprehensive security validation.
"""

import re

from zabacode.core.paths import FILES_DIR

MAX_FILE_BYTES = 512 * 1024  # 512 KB


def secure_filename(filename: str) -> str | None:
    """
    Validate and secure a filename.
    
    Security protections:
    - Block path traversal (.., /, \\)
    - Block null bytes
    - Block dotfiles and hidden files
    - Block underscore-prefixed system files
    - Auto-append .py extension
    
    Returns secured filename or None if invalid.
    """
    if not filename:
        return None

    if ".." in filename or "/" in filename or "\\" in filename or "\x00" in filename:
        return None

    filename = filename.strip()

    if filename.startswith(".") or filename.startswith("_"):
        return None

    if not filename or filename == ".py":
        return None

    # Only allow alphanumeric, dash, underscore, and dot
    if not re.match(r'^[A-Za-z0-9][A-Za-z0-9_\-\.]*$', filename):
        return None

    if not filename.endswith(".py"):
        filename += ".py"

    return filename


def list_files() -> list[dict]:
    """List all user .py files (excluding hidden/system files)."""
    files = []
    for p in FILES_DIR.glob("*.py"):
        if not p.name.startswith(".") and not p.name.startswith("_"):
            files.append({"name": p.name, "size": p.stat().st_size})
    return files


def read_file(filename: str) -> dict:
    """Read a user file's content. Returns dict with ok, content, message."""
    secured = secure_filename(filename)
    if not secured:
        return {"ok": False, "message": "Invalid filename"}

    file_path = FILES_DIR / secured
    if not file_path.exists():
        return {"ok": False, "message": f"File '{filename}' not found"}

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return {"ok": True, "content": content, "filename": secured}
    except Exception as e:
        return {"ok": False, "message": f"Failed to read file: {e}"}


def save_file(filename: str, content: str) -> dict:
    """Save content to a user file. Returns dict with ok, filename, message."""
    secured = secure_filename(filename)
    if not secured:
        return {"ok": False, "message": "Invalid filename"}

    if not isinstance(content, str) or len(content.encode("utf-8")) > MAX_FILE_BYTES:
        return {"ok": False, "message": "File content too large"}

    file_path = FILES_DIR / secured
    try:
        file_path.write_text(content, encoding="utf-8")
        return {"ok": True, "filename": secured, "message": f"File '{secured}' saved successfully"}
    except Exception as e:
        return {"ok": False, "message": f"Failed to save file: {e}"}


def delete_file(filename: str) -> dict:
    """Delete a user file. Returns dict with ok, message."""
    secured = secure_filename(filename)
    if not secured:
        return {"ok": False, "message": "Invalid filename"}

    file_path = FILES_DIR / secured
    if not file_path.exists():
        return {"ok": False, "message": f"File '{filename}' not found"}

    try:
        file_path.unlink()
        return {"ok": True, "message": f"File '{secured}' deleted successfully"}
    except Exception as e:
        return {"ok": False, "message": f"Failed to delete file: {e}"}
