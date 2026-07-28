"""ZMUX v1.0.0 — WebView shell entry point for the native Python core."""

import os
import traceback
from pathlib import Path


def _write_crash_log() -> None:
    app_dir = Path(os.environ.get("ANDROID_PRIVATE", Path(__file__).parent))
    try:
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / "zabacode_crash.log").write_text(traceback.format_exc(), encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from zabacode.web_app import run_webview_server
        run_webview_server()
    except Exception:
        _write_crash_log()
        raise
