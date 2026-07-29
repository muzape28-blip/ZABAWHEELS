"""
ZMUX Path Resolution & Directory Management

Handles APP_DIR detection for Android and Desktop environments.
All runtime directories are app-private and gitignored.
"""

import os
from pathlib import Path


def resolve_app_dir() -> Path:
    """
    Resolve the application directory based on runtime environment.
    
    Priority:
    1. ANDROID_PRIVATE env var (Python-for-Android webview bootstrap)
    2. Fallback: project root (where main.py lives) for desktop development
    """
    # 1. Android private storage (p4a webview bootstrap)
    if "ANDROID_PRIVATE" in os.environ:
        return Path(os.environ["ANDROID_PRIVATE"])

    # 2. Desktop fallback: project root (where main.py lives)
    return Path(__file__).resolve().parent.parent


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
