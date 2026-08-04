"""Guardrails for the PythonShell fallback audit document."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "PYTHON_FALLBACK_AUDIT.md"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_audit_doc_declares_no_behavior_change_and_legacy_scope():
    text = _doc()
    assert "audit-only checkpoint. No behavior change" in text
    assert "legacy host-side `PythonShell`" in text
    assert "not** Alpine PTY UX" in text


def test_audit_doc_records_current_fallback_examples():
    text = _doc()
    assert "gti status" in text
    assert "command not found" in text
    assert "definitely_an_undefined_name + 1" in text
    assert "Python NameError" in text
    assert "force_python=True" in text


def test_audit_doc_lists_guardrails_and_risks():
    text = _doc()
    assert "app/tests/test_python_fallback_quarantine.py" in text
    assert "app/tests/test_env_rc_crash.py::TestCommandNotFound" in text
    assert "app/tests/test_pty_websocket.py::TestPythonReplMode::test_repl_is_pure_python_not_shell" in text
    assert "Old REST `/api/exec` callers" in text
    assert "Legacy `~/.zmuxrc` migration hooks" in text
    assert "ZMUX_STRICT_HOST_COMMANDS=1" in text


def test_audit_doc_is_linked_from_docs_index_and_cleanup_checkpoint():
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    cleanup = (ROOT / "docs" / "ALPINE_FIRST_CLEANUP.md").read_text(encoding="utf-8")
    assert "PYTHON_FALLBACK_AUDIT.md" in docs_index
    assert "Python fallback audit" in cleanup
    assert "tests/test_python_fallback_audit_doc.py" in cleanup
