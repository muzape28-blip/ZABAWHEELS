"""
ZMUX Core — Path Resolution & Directory Management
Handles APP_DIR detection for Android, Kivy, and Desktop environments.

Data directory policy (documented, tested):
- On Android (ANDROID_PRIVATE env or Kivy storage): APP_DIR = Android private files dir,
  FILES_DIR = APP_DIR / "files" (e.g., /data/data/com.zaba.zabacode/files/files on some
  devices due to p4a behavior — but we normalize to avoid double nesting)
- On Desktop fallback (no Android env): APP_DIR = project root (where main.py lives),
  so FILES_DIR = project_root / "files" — matches documentation "files/ at project root"
  and avoids confusion of editing visible root files/ while app reads zabacode/files/

All runtime dirs are gitignored to prevent accidental commits of user files.
"""

import os
from pathlib import Path


def resolve_app_dir() -> Path:
    """
    Resolve the application directory based on runtime environment.
    
    Priority:
    1. ANDROID_PRIVATE env var (Python-for-Android webview bootstrap)
    2. Kivy android storage via pyjnius
    3. Fallback: project root (where main.py lives) for desktop development
    """
    # 1. Android private storage (p4a webview bootstrap)
    # ANDROID_PRIVATE may already point to .../files, so we use it directly as APP_DIR
    # and FILES_DIR will be APP_DIR / "files" — but we handle double files nesting below
    if "ANDROID_PRIVATE" in os.environ:
        p = Path(os.environ["ANDROID_PRIVATE"])
        # If ANDROID_PRIVATE already ends with /files, avoid double nesting to /files/files
        # Check if parent of current file's project root logic would cause double files
        # We keep as-is, but FILES_DIR logic below will handle deduplication
        return p

    # 2. Kivy Android activity files dir
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        activity = PythonActivity.mActivity
        return Path(activity.getFilesDir().getAbsolutePath())
    except Exception:
        pass

    # 3. Desktop fallback: project root (where main.py lives)
    # __file__ = .../zabacode/core/paths.py -> parent = core, parent.parent = zabacode, parent.parent.parent = project root
    return Path(__file__).resolve().parent.parent.parent


APP_DIR = resolve_app_dir()

# Critical directories
KEYS_FILE = APP_DIR / ".zabacode_keys_encrypted.json"
USER_PACKAGES_DIR = APP_DIR / "user_packages"
# Handle case where APP_DIR already ends with "files" (some Android setups)
# to avoid double files/files path that confuses developers
if APP_DIR.name == "files":
    FILES_DIR = APP_DIR
else:
    FILES_DIR = APP_DIR / "files"
CACHE_DIR = APP_DIR / "cache"
TOKEN_FILE = APP_DIR / ".zabacode_auth_token"
LOG_DIR = APP_DIR / "logs"

# Ensure all directories exist
for directory in [USER_PACKAGES_DIR, FILES_DIR, CACHE_DIR, LOG_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
