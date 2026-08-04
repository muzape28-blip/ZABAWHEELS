"""Guardrails for the REST /api/exec language migration guide."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "REST_EXEC_LANGUAGE_MIGRATION.md"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_migration_guide_warns_rest_exec_is_not_product_terminal_api():
    text = _doc()
    assert "WebSocket + Alpine PTY" in text
    assert "Do not build new terminal\nfeatures on `/api/exec`" in text
    assert "existing clients that still call legacy `POST /api/exec`" in text


def test_migration_guide_documents_all_three_modes():
    text = _doc()
    assert "`legacy-auto`" in text
    assert "`python`" in text
    assert "`command`" in text
    assert "No implicit Python fallback" in text


def test_migration_guide_has_examples_for_python_and_command_semantics():
    text = _doc()
    assert '"language": "python"' in text
    assert "print(21 + 21)" in text
    assert "returns a Python `NameError` rather than a directory listing" in text
    assert '"language": "command"' in text
    assert "gti status" in text
    assert "This must not return `2`" in text


def test_migration_guide_lists_response_metadata_and_checklist():
    text = _doc()
    assert "legacy_input_mode" in text
    assert "explicit_language" in text
    assert "language" in text
    assert "Stop using `/api/exec` for interactive terminal UX" in text
    assert "Use `language=\"python\"` for Python snippets" in text
    assert "Use `language=\"command\"` for command-like snippets" in text


def test_migration_guide_is_linked_from_docs_index_and_cleanup_checkpoint():
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    cleanup = (ROOT / "docs" / "ALPINE_FIRST_CLEANUP.md").read_text(encoding="utf-8")
    assert "REST_EXEC_LANGUAGE_MIGRATION.md" in docs_index
    assert "REST exec language migration guide" in cleanup
    assert "tests/test_rest_exec_language_migration_doc.py" in cleanup
