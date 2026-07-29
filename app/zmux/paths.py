"""
ZMUX Path Resolution & Directory Management

Handles APP_DIR detection for Android and Desktop environments.
All runtime directories are app-private and gitignored.
"""

import os
from pathlib import Path


def _is_writable(path: Path) -> bool:
    """Check if a directory can be created and written to."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".zmux_write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def resolve_app_dir() -> Path:
    """
    Resolve the application directory based on runtime environment.
    
    Priority:
    1. ANDROID_PRIVATE / ANDROID_ARGUMENT / ANDROID_APP_PATH env vars (p4a webview bootstrap)
    2. Fallback: project root (where main.py lives) for desktop development
    3. Safe Android / POSIX writable fallbacks
    """
    for env_key in ("ANDROID_PRIVATE", "ANDROID_ARGUMENT", "ANDROID_APP_PATH"):
        val = os.environ.get(env_key)
        if val:
            candidate = Path(val)
            if _is_writable(candidate):
                return candidate

    default_root = Path(__file__).resolve().parent.parent
    if _is_writable(default_root):
        return default_root

    for candidate_str in (
        os.environ.get("HOME", ""),
        os.environ.get("TMPDIR", ""),
        "/data/local/tmp/zmux",
        "/cache/zmux",
        "/tmp/zmux",
    ):
        if candidate_str:
            candidate = Path(candidate_str)
            if _is_writable(candidate):
                return candidate

    return default_root


APP_DIR = resolve_app_dir()

# Critical directories - all app-private
HOME_DIR = APP_DIR / "home"
PROJECTS_DIR = HOME_DIR / "projects"
CACHE_DIR = APP_DIR / "cache"
DOWNLOADS_DIR = CACHE_DIR / "downloads"
STAGING_DIR = APP_DIR / "staging"
USER_PACKAGES_DIR = APP_DIR / "user_packages"
INSTALLED_DIR = APP_DIR / "installed"
LOG_DIR = APP_DIR / "logs"

# Ensure all directories exist
for directory in [
    HOME_DIR,
    PROJECTS_DIR,
    CACHE_DIR,
    DOWNLOADS_DIR,
    STAGING_DIR,
    USER_PACKAGES_DIR,
    INSTALLED_DIR,
    LOG_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)
