"""Guardrails for the REST /api/exec implicit Python audit."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "REST_EXEC_PYTHON_AUDIT.md"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_rest_exec_python_audit_declares_legacy_scope_and_no_behavior_change():
    text = _doc()
    assert "audit-only checkpoint. No behavior change" in text
    assert "legacy `TerminalSession` / `PythonShell`" in text
    assert "product terminal does **not** use this endpoint" in text


def test_rest_exec_python_audit_documents_metadata_contract():
    text = _doc()
    assert "legacy-auto-command-or-python" in text
    assert "explicit_language" in text
    assert "legacy_input_mode" in text
    assert "deprecation" in text


def test_rest_exec_python_audit_documents_migration_path():
    text = _doc()
    assert "REST_EXEC_LANGUAGE_CONTRACT.md" in text
    assert "avoid changing `stdout` unexpectedly" in text


def test_rest_exec_python_audit_is_linked_from_docs_index_and_cleanup_checkpoint():
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    cleanup = (ROOT / "docs" / "ALPINE_FIRST_CLEANUP.md").read_text(encoding="utf-8")
    assert "REST_EXEC_PYTHON_AUDIT.md" in docs_index
    assert "REST exec Python audit" in cleanup
    assert "tests/test_rest_exec_python_audit_doc.py" in cleanup
