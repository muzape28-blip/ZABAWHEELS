"""Guardrails for the proposed REST /api/exec language contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "REST_EXEC_LANGUAGE_CONTRACT.md"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_language_contract_is_validation_scaffold_and_non_product_api():
    text = _doc()
    assert "validation scaffold" in text
    assert "`language: \"legacy-auto\"` is accepted" in text
    assert "`language: \"python\"` explicitly executes embedded Python" in text
    assert "`language:\n\"command\"` explicitly executes command-like input" in text
    assert "This does not make REST `/api/exec` the product terminal API" in text


def test_language_contract_documents_current_metadata_and_future_payloads():
    text = _doc()
    assert '"legacy_input_mode": "legacy-auto-command-or-python"' in text
    assert '"explicit_language": false' in text
    assert '"language": "legacy-auto"' in text
    assert '"language": "python"' in text
    assert '"language": "command"' in text


def test_language_contract_lists_suggested_values_and_guardrails():
    text = _doc()
    assert "legacy-auto  current compatibility behavior" in text
    assert "python       explicit embedded Python execution" in text
    assert "command      strict command-like handling" in text
    assert "Continue validating `language` strictly" in text
    assert "Do not change `stdout` for legacy-auto responses unexpectedly" in text


def test_language_contract_is_linked_from_docs_index_and_cleanup_checkpoint():
    docs_index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    cleanup = (ROOT / "docs" / "ALPINE_FIRST_CLEANUP.md").read_text(encoding="utf-8")
    assert "REST_EXEC_LANGUAGE_CONTRACT.md" in docs_index
    assert "REST_EXEC_COMMAND_MODE_AUDIT.md" in docs_index
    assert "REST exec language contract design" in cleanup
    assert "tests/test_rest_exec_language_contract_doc.py" in cleanup
