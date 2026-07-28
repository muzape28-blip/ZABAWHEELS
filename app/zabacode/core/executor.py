"""
ZMUX Core — Isolated & Interactive Subprocess Code Execution Engine
Runs user Python code in isolated or interactive subprocesses.
Fixed for #18: Bound source size, output buffering, session duration
"""

import base64
import os
import queue
import signal
import subprocess
import sys
import threading
import time

from zabacode.core.paths import CACHE_DIR, FILES_DIR, USER_PACKAGES_DIR

# Limits
MAX_CODE_BYTES = 512 * 1024   # 512 KB
MAX_OUTPUT_CHARS = 256 * 1024  # 256 KB
DEFAULT_TIMEOUT = 30           # seconds
MAX_INTERACTIVE_DURATION = 120  # seconds — max lifetime of interactive session
MAX_INTERACTIVE_INACTIVITY = 60  # seconds — kill if no output and no input for this long
MAX_INTERACTIVE_BYTES = 8192   # max bytes per interactive input send
MAX_INTERACTIVE_QUEUE = 10000  # max chars buffered in queue at once (bounded)


def _truncate(text: str) -> str:
    """Truncate output to prevent memory overflow."""
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n[Output truncated]"


SAFE_INPUT_PATCH = """import builtins
_orig_input = builtins.input
def _safe_input(prompt=""):
    try:
        return _orig_input(prompt)
    except EOFError:
        return ""
builtins.input = _safe_input

"""

# Lines the SAFE_INPUT_PATCH prelude prepends, so tracebacks can be mapped
# back to the line numbers the user sees in the editor.
PRELUDE_LINE_COUNT = SAFE_INPUT_PATCH.count("\n")


# ---------------------------------------------------------------------------
# Generated-image capture
# ---------------------------------------------------------------------------
#
# Both execution modes need this, but for different reasons, so only the
# *collection* is shared — never the execution flow itself:
#
#   * batch (execute_code_isolated) snapshots once, after the process exits;
#   * interactive polls repeatedly while the process is still alive, because a
#     long-running script may emit several plots before it finishes.
#
# Android has no display, so `plt.show()` is a no-op there and `savefig()` is
# the only way to see a chart. That makes picking these files up the difference
# between matplotlib working and silently doing nothing.

IMAGE_SUFFIXES = ("*.png", "*.jpg", "*.jpeg")

# A single 8 MB base64 payload would stall the WebView bridge on a low-end
# phone, so oversized renders are reported rather than shipped.
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _snapshot_images() -> set:
    """Paths of image files currently in the working directory."""
    found: set = set()
    for pattern in IMAGE_SUFFIXES:
        found |= set(FILES_DIR.glob(pattern))
    return found


def _encode_images(paths) -> list:
    """Encode image files as data URIs, skipping anything unreadable."""
    encoded = []
    for img_path in sorted(paths):
        try:
            raw = img_path.read_bytes()
            if len(raw) > MAX_IMAGE_BYTES:
                continue
            mime = "image/png" if img_path.suffix.lower() == ".png" else "image/jpeg"
            encoded.append({
                "name": img_path.name,
                "data_uri": f"data:{mime};base64,{base64.b64encode(raw).decode('utf-8')}",
            })
        except OSError:
            # Half-written file (the script is still saving it) — it will be
            # picked up on the next poll.
            continue
    return encoded


def collect_new_images(baseline: set) -> tuple[list, set]:
    """Encode images created since ``baseline``.

    Returns ``(encoded_images, new_baseline)`` so a caller polling in a loop can
    advance its baseline and never send the same plot twice.
    """
    current = _snapshot_images()
    fresh = current - baseline
    if not fresh:
        return [], current

    encoded = _encode_images(fresh)
    # Only files that were actually encoded advance the baseline; a file still
    # being written stays "new" so the next poll retries it.
    delivered = {p for p in fresh if any(e["name"] == p.name for e in encoded)}
    return encoded, baseline | delivered


def normalize_code(code: str) -> str:
    """
    Normalize Python code to prevent EOF/syntax errors.
    - Convert Windows line endings (\r\n) to Unix (\n)
    - Remove BOM if present
    - Trim trailing whitespace per line
    - Handle from __future__ import statements properly at the absolute top of the file
    """
    code = code.replace('\r\n', '\n').replace('\r', '\n')
    if code.startswith('\ufeff'):
        code = code[1:]
    lines = code.split('\n')
    normalized_lines = [line.rstrip() for line in lines]

    # Extract __future__ imports to keep them at the absolute top of the generated file
    future_lines = []
    other_lines = []

    for line in normalized_lines:
        stripped = line.strip()
        if stripped.startswith('from __future__ import'):
            future_lines.append(line)
        else:
            other_lines.append(line)

    if future_lines:
        return '\n'.join(future_lines) + '\n\n' + SAFE_INPUT_PATCH + '\n'.join(other_lines)
    return SAFE_INPUT_PATCH + '\n'.join(normalized_lines)


def execute_code_isolated(code: str, stdin_data: str = "", timeout: int = DEFAULT_TIMEOUT) -> dict:
    """
    Run user code in a separate subprocess.
    This isolates process lifetime, not filesystem/network privileges.
    Treat code as trusted unless a platform-level sandbox is added.
    
    Returns dict with: ok, stdout, stderr, timeout, images
    """
    if not isinstance(code, str) or len(code.encode("utf-8")) > MAX_CODE_BYTES:
        return {
            "ok": False,
            "stdout": "",
            "stderr": "Source code terlalu besar.",
            "timeout": False,
            "images": []
        }

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    temp_script = FILES_DIR / "_active_run.py"

    try:
        code = normalize_code(code)
        temp_script.write_text(code, encoding="utf-8")

        env = os.environ.copy()
        python_path = f"{USER_PACKAGES_DIR}:{FILES_DIR}:{env.get('PYTHONPATH', '')}".strip(":")
        env["PYTHONPATH"] = python_path
        env["PYTHONNOUSERSITE"] = "1"
        env["TMPDIR"] = str(CACHE_DIR)
        env["TEMP"] = str(CACHE_DIR)
        env["TMP"] = str(CACHE_DIR)

        existing_images = _snapshot_images()

        proc = subprocess.Popen(
            [sys.executable, "_active_run.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            cwd=str(FILES_DIR),
            env=env,
            start_new_session=os.name != "nt",
        )

        try:
            stdout_text, stderr_text = proc.communicate(input=stdin_data, timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    proc.kill()
            else:
                proc.kill()
            stdout_text, stderr_text = proc.communicate()
            return {
                "ok": False,
                "stdout": _truncate(stdout_text or ""),
                "stderr": _truncate(
                    (stderr_text or "").replace("_active_run.py", "main.py")
                    + f"\n[Process timed out after {timeout}s]"
                ),
                "timeout": True,
                "images": [],
            }

        image_data, _ = collect_new_images(existing_images)

        stderr_cleaned = stderr_text.replace('_active_run.py', 'main.py') if stderr_text else ""

        return {
            "ok": proc.returncode == 0,
            "stdout": _truncate(stdout_text or ""),
            "stderr": _truncate(stderr_cleaned),
            "timeout": False,
            "images": image_data
        }
    except Exception as e:
        return {
            "ok": False,
            "stdout": "",
            "stderr": str(e),
            "timeout": False,
            "images": []
        }


# ---------------------------------------------------------------------------
# Interactive Subprocess Execution Engine — Bounded (Fix #18)
# ---------------------------------------------------------------------------

class InteractiveSession:
    def __init__(self):
        self.proc = None
        self.output_queue: queue.Queue = queue.Queue(maxsize=MAX_INTERACTIVE_QUEUE)
        self.threads: list[threading.Thread] = []
        self.active = False
        self.start_time: float | None = None
        self.last_activity: float | None = None
        self.total_chars: int = 0
        self.output_truncated: bool = False
        # Images already present when the run started, plus everything already
        # delivered to the client. Without this the same plot would be re-sent
        # on every 150 ms poll.
        self.image_baseline: set = set()


_session = InteractiveSession()

# waitress serves with threads=4, so concurrent requests can touch _session
# simultaneously. Without this lock a second /start can kill a process the
# first request is still wiring up, leaking the child and corrupting state.
_session_lock = threading.RLock()


def _mask_runner_filename(chunks: list) -> list:
    """Rewrite ``_active_run.py`` -> ``main.py`` across a batch of stream chunks.

    The interactive reader emits one character at a time, so the substring is
    split across items. Join per stream, replace, then re-emit as a single chunk
    per stream while preserving the original stdout/stderr ordering.
    """
    if not chunks:
        return chunks

    merged: list = []
    for stream_type, text in chunks:
        if merged and merged[-1][0] == stream_type:
            merged[-1][1].append(text)
        else:
            merged.append((stream_type, [text]))

    return [
        (stream_type, "".join(parts).replace("_active_run.py", "main.py"))
        for stream_type, parts in merged
    ]


def _read_stream_char(stream, session: InteractiveSession, stream_type: str):
    """Asynchronously read characters from subprocess output streams — bounded."""
    try:
        while True:
            char = stream.read(1)
            if not char:
                break

            # Bound total output to prevent memory bloat from tight printing loops
            with _session_lock:
                if session.total_chars >= MAX_OUTPUT_CHARS:
                    if not session.output_truncated:
                        session.output_truncated = True
                        # Try to push truncation notice once
                        try:
                            session.output_queue.put_nowait((stream_type, "\n[Output truncated — flooding limit reached]\n"))
                        except queue.Full:
                            pass
                    # Stop reading further to avoid unbounded memory
                    break
                session.total_chars += 1
                session.last_activity = time.time()

            # Bounded queue — if full, drop oldest? For simplicity, try put with timeout, drop if full
            try:
                session.output_queue.put((stream_type, char), timeout=0.1)
            except queue.Full:
                # Queue full — mark truncated and keep draining to avoid blocking child
                with _session_lock:
                    session.output_truncated = True
                # Drop char, continue to drain stream but don't queue
                continue
    except Exception:
        pass


def start_interactive_session(code: str) -> dict:
    """Spawns an interactive unbuffered subprocess and starts listener threads — bounded."""
    with _session_lock:
        global _session
        stop_interactive_session()

        # --- Fix #18: Reject oversized source ---
        if not isinstance(code, str):
            return {"ok": False, "message": "Field 'code' must be a string."}
        if len(code.encode("utf-8")) > MAX_CODE_BYTES:
            return {
                "ok": False,
                "message": f"Source too large: {len(code.encode('utf-8'))} bytes > {MAX_CODE_BYTES} bytes limit. Split your code or clear editor.",
            }

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        temp_script = FILES_DIR / "_active_run.py"

        try:
            # Do not include safe input patch so input() acts interactively
            code_normalized = code.replace('\r\n', '\n').replace('\r', '\n')
            if code_normalized.startswith('\ufeff'):
                code_normalized = code_normalized[1:]

            temp_script.write_text(code_normalized, encoding="utf-8")

            env = os.environ.copy()
            python_path = f"{USER_PACKAGES_DIR}:{FILES_DIR}:{env.get('PYTHONPATH', '')}".strip(":")
            env["PYTHONPATH"] = python_path
            env["PYTHONNOUSERSITE"] = "1"
            env["TMPDIR"] = str(CACHE_DIR)
            env["TEMP"] = str(CACHE_DIR)
            env["TMP"] = str(CACHE_DIR)
            env["PYTHONUNBUFFERED"] = "1"

            _session.proc = subprocess.Popen(
                [sys.executable, "-u", "_active_run.py"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                cwd=str(FILES_DIR),
                env=env,
                start_new_session=os.name != "nt",
            )
            _session.active = True
            _session.output_queue = queue.Queue(maxsize=MAX_INTERACTIVE_QUEUE)
            _session.start_time = time.time()
            _session.last_activity = time.time()
            _session.total_chars = 0
            _session.output_truncated = False
            # Snapshot before the child can write anything, so pre-existing
            # files from an earlier run are never re-reported as new.
            _session.image_baseline = _snapshot_images()

            t_out = threading.Thread(
                target=_read_stream_char,
                args=(_session.proc.stdout, _session, "stdout"),
                daemon=True,
            )
            t_err = threading.Thread(
                target=_read_stream_char,
                args=(_session.proc.stderr, _session, "stderr"),
                daemon=True,
            )
            t_out.start()
            t_err.start()
            _session.threads = [t_out, t_err]

            return {"ok": True, "message": "Interactive process started"}
        except Exception as e:
            return {"ok": False, "message": f"Failed to start interactive session: {e}"}


def send_interactive_input(text: str) -> dict:
    """Send interactive input to the running subprocess's stdin."""
    with _session_lock:
        global _session
        if not _session.active or not _session.proc:
            return {"ok": False, "message": "No active interactive session found."}

        # Bound input size to avoid flooding
        if len(text.encode("utf-8")) > MAX_INTERACTIVE_BYTES:
            return {"ok": False, "message": "Input too large (max 8KB per send)."}

        try:
            _session.proc.stdin.write(text)
            _session.proc.stdin.flush()
            _session.last_activity = time.time()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "message": f"Failed to send input: {e}"}


def get_interactive_output() -> dict:
    """Collect all pending outputs from the unbuffered subprocess streams — bounded with timeout."""
    with _session_lock:
        global _session
        if not _session.active or not _session.proc:
            return {"ok": False, "done": True, "output": [], "output_truncated": _session.output_truncated}

        # Check max duration
        now = time.time()
        if _session.start_time and (now - _session.start_time) > MAX_INTERACTIVE_DURATION:
            # Timeout — kill session
            try:
                if _session.proc.poll() is None:
                    if os.name != "nt":
                        try:
                            os.killpg(_session.proc.pid, signal.SIGKILL)
                        except OSError:
                            _session.proc.kill()
                    else:
                        _session.proc.kill()
            except Exception:
                pass
            _session.active = False
            return {
                "ok": True,
                "done": True,
                "output": [],
                "exit_code": -1,
                "timeout": True,
                "message": f"Interactive session exceeded max duration {MAX_INTERACTIVE_DURATION}s and was stopped.",
                "output_truncated": _session.output_truncated,
            }

        # Check inactivity timeout
        if _session.last_activity and (now - _session.last_activity) > MAX_INTERACTIVE_INACTIVITY:
            try:
                if _session.proc.poll() is None:
                    if os.name != "nt":
                        try:
                            os.killpg(_session.proc.pid, signal.SIGKILL)
                        except OSError:
                            _session.proc.kill()
                    else:
                        _session.proc.kill()
            except Exception:
                pass
            _session.active = False
            return {
                "ok": True,
                "done": True,
                "output": [],
                "exit_code": -1,
                "timeout": True,
                "message": f"Interactive session inactivity timeout {MAX_INTERACTIVE_INACTIVITY}s — stopped.",
                "output_truncated": _session.output_truncated,
            }

        output_chars = []
        while not _session.output_queue.empty():
            try:
                item = _session.output_queue.get_nowait()
                output_chars.append(item)
            except queue.Empty:
                break

        # Match the isolated runner and hide the internal scratch filename, so
        # tracebacks read "main.py" in both execution modes. Output is streamed
        # character by character, so rewrite the reassembled batch instead.
        output_chars = _mask_runner_filename(output_chars)

        done = _session.proc.poll() is not None

        # Pick up any chart the script saved. Done while the process is still
        # running too, so a loop that emits several plots shows them as they
        # appear rather than all at the end. On the final poll this also
        # catches images flushed just before exit.
        images, _session.image_baseline = collect_new_images(_session.image_baseline)

        if done:
            _session.active = False
            exit_code = _session.proc.returncode
            return {
                "ok": True,
                "done": True,
                "output": output_chars,
                "exit_code": exit_code,
                "images": images,
                "output_truncated": _session.output_truncated,
            }

        return {
            "ok": True,
            "done": False,
            "output": output_chars,
            "images": images,
            "output_truncated": _session.output_truncated,
        }


def stop_interactive_session() -> dict:
    """Forcefully kills the active interactive subprocess and releases resources."""
    with _session_lock:
        global _session
        if not _session.proc:
            return {"ok": False, "message": "No running process found."}

        try:
            if _session.proc.poll() is None:
                if os.name != "nt":
                    try:
                        os.killpg(_session.proc.pid, signal.SIGKILL)
                    except OSError:
                        _session.proc.kill()
                else:
                    _session.proc.kill()
            _session.active = False
            _session.proc = None
            _session.start_time = None
            _session.last_activity = None
            return {"ok": True, "message": "Process successfully stopped."}
        except Exception as e:
            return {"ok": False, "message": f"Failed to stop process: {e}"}
