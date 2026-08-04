"""Guardrails for the future REST /api/exec command-mode audit."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "REST_EXEC_COMMAND_MODE_AUDIT.md"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_command_mode_audit_declares_implemented_checkpoint_and_non_product_api():
    text = _doc()
    assert "implemented after audit checkpoint" in text
    assert "maintenance checklist for command-mode changes" in text
    assert "product terminal is the\nWebSocket Alpine PTY" in text


def test_command_mode_audit_defines_required_semantics():
    text = _doc()
    assert "No implicit Python fallback" in text
    assert "Known builtins still answer" in text
    assert "Unknown command-like input returns 127" in text
    assert "Python expressions are not evaluated" in text
    assert "Default behavior remains unchanged" in text
    assert "Metadata remains explicit" in text


def test_command_mode_audit_lists_guardrail_tests_needed_before_implementation():
    text = _doc()
    assert '{command: "echo hello", language: "command"}' in text
    assert '{command: "gti status", language: "command"}' in text
    assert '{command: "1 + 1", language: "command"}' in text
    assert '{command: "1 + 1"} -> legacy-auto still returns 2' in text
    assert "update this audit, the REST language\ncontract, and server tests" in text


def test_command_mode_audit_is_linked_from_docs_index_and_cleanup_checkpoint():
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    cleanup = (ROOT / "docs" / "ALPINE_FIRST_CLEANUP.md").read_text(encoding="utf-8")
    language_contract = (ROOT / "docs" / "REST_EXEC_LANGUAGE_CONTRACT.md").read_text(encoding="utf-8")
    assert "REST_EXEC_COMMAND_MODE_AUDIT.md" in docs_index
    assert "REST_EXEC_COMMAND_MODE_AUDIT.md" in language_contract
    assert "REST exec command-mode audit" in cleanup
    assert "tests/test_rest_exec_command_mode_audit_doc.py" in cleanup
