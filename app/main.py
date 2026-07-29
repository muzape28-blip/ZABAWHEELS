"""ZMUX v1.0.0 — Android Terminal for Python development."""

import os
import traceback
from pathlib import Path


def _write_crash_log() -> None:
    exc_text = traceback.format_exc()
    candidates = [
        os.environ.get("ANDROID_PRIVATE"),
        os.environ.get("ANDROID_ARGUMENT"),
        os.environ.get("ANDROID_APP_PATH"),
        str(Path(__file__).resolve().parent),
        "/data/local/tmp",
    ]
    for c in candidates:
        if not c:
            continue
        try:
            p = Path(c)
            p.mkdir(parents=True, exist_ok=True)
            (p / "zmux_crash.log").write_text(exc_text, encoding="utf-8")
        except Exception:
            continue


if __name__ == "__main__":
    try:
        from zmux.server import run_server
        run_server()
    except Exception:
        _write_crash_log()
        raise
