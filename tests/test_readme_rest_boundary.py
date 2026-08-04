"""Guardrails for README REST/WebSocket boundary guidance."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_root_readme_documents_websocket_as_terminal_path_and_rest_as_legacy():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Developer API boundary" in text
    assert "authenticated WebSocket connected to the Alpine PTY" in text
    assert "REST terminal-session endpoints" in text
    assert "retained for legacy compatibility" in text
    assert "should not be used for new terminal UX" in text


def test_root_readme_links_rest_boundary_and_migration_docs():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/REST_COMPATIBILITY.md" in text
    assert "docs/REST_EXEC_LANGUAGE_MIGRATION.md" in text
    assert '"language": "command"' in text
    assert '"language": "python"' in text
    assert '"language": "legacy-auto"' in text


def test_app_readme_warns_rest_endpoints_are_compatibility_only():
    text = (ROOT / "app" / "README.md").read_text(encoding="utf-8")
    assert "REST compatibility note" in text
    assert "WebView terminal uses the authenticated WebSocket" in text
    assert "compatibility-only" in text
    assert "/api/exec" in text
    assert "../docs/REST_EXEC_LANGUAGE_MIGRATION.md" in text


def test_cleanup_checkpoint_records_readme_rest_boundary_phase():
    text = (ROOT / "docs" / "ALPINE_FIRST_CLEANUP.md").read_text(encoding="utf-8")
    assert "checkpoint after phases 1–28" in text
    assert "README REST boundary polish" in text
