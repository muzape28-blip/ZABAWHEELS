"""Guardrails for REST compatibility boundary documentation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "REST_COMPATIBILITY.md"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_rest_doc_defines_websocket_as_product_terminal_path():
    text = _doc()
    assert "authenticated WebSocket" in text
    assert "PTYTerminalSession" in text
    assert "PRoot -> Alpine" in text
    assert "Do not build new terminal UX on `/api/exec`" in text


def test_rest_doc_splits_current_and_legacy_endpoints():
    text = _doc()
    assert "Current/non-legacy REST surface" in text
    assert "`GET /`" in text
    assert "`GET /api/health`" in text
    assert "Legacy compatibility REST surface" in text
    for endpoint in ("POST /api/exec", "POST /api/input", "POST /api/stop", "GET /api/status", "GET /api/prompt"):
        assert f"`{endpoint}`" in text


def test_rest_doc_maintainer_rules_protect_health_and_legacy_metadata():
    text = _doc()
    assert "`/api/health` must remain side-effect-free" in text
    assert "legacy/deprecation metadata" in text
    assert "Do not describe `/api/status` or `/api/prompt` as Alpine PTY state" in text


def test_rest_doc_is_linked_from_docs_index_and_cleanup_checkpoint():
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    cleanup = (ROOT / "docs" / "ALPINE_FIRST_CLEANUP.md").read_text(encoding="utf-8")
    assert "REST_COMPATIBILITY.md" in docs_index
    assert "REST compatibility docs" in cleanup
    assert "tests/test_rest_compatibility_doc.py" in cleanup
