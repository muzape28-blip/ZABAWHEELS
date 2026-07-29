"""ZMUX v1.0.0 — Android Terminal for Python development."""

import os
import traceback
from pathlib import Path


def _write_crash_log() -> None:
    app_dir = Path(os.environ.get("ANDROID_PRIVATE", Path(__file__).parent))
    try:
        app_dir.mkdir(parents=True, exist_ok=True)
        (app_dir / "zmux_crash.log").write_text(traceback.format_exc(), encoding="utf-8")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        from zmux.server import run_server
        run_server()
    except Exception:
        _write_crash_log()
        raise
