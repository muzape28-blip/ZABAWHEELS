"""Guardrails for the Alpine-first cleanup checkpoint document."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "ALPINE_FIRST_CLEANUP.md"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_cleanup_doc_records_product_contract_and_package_workflow():
    text = _doc()
    assert "User-facing shell      = Alpine Linux in a real PTY" in text
    assert "Package workflow      = apk + Python venv/pip inside Alpine" in text
    assert "apk add <package>" in text
    assert "python3 -m pip install <name>" in text
    assert "They must not route users to `zpip install ...` or `linux apk add ...`." in text


def test_cleanup_doc_lists_all_completed_phases():
    text = _doc()
    for phase in range(1, 29):
        assert f"| {phase} |" in text
    assert "`pty.toggle`" in text
    assert "`~/.zmuxrc`" in text
    assert "Runtime info legacy package labeling" in text
    assert "`zpip` dispatch metadata" in text
    assert "REST `zpip` metadata" in text
    assert "REST status/input/prompt/stop labeling" in text
    assert "REST compatibility docs" in text
    assert "Python fallback quarantine" in text
    assert "Python fallback audit" in text
    assert "Strict host-command preview" in text
    assert "REST exec Python audit" in text
    assert "REST exec language contract design" in text
    assert "REST exec language scaffold" in text
    assert "REST exec explicit Python" in text
    assert "REST exec command-mode audit" in text
    assert "REST exec command mode" in text
    assert "REST exec language migration guide" in text
    assert "README REST boundary polish" in text


def test_cleanup_doc_lists_removal_prerequisites_for_major_legacy_surfaces():
    text = _doc()
    assert "Before removing `zpip.py`" in text
    assert "Before removing `PythonShell` / `TerminalSession`" in text
    assert "Before removing package pipeline files" in text
    assert "Before disabling `pty.toggle`" in text


def test_cleanup_doc_is_referenced_from_docs_index():
    index = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "ALPINE_FIRST_CLEANUP.md" in index
    assert "Cleanup checkpoint" in index


def test_cleanup_doc_mentions_guardrail_tests_added_so_far():
    text = _doc()
    for rel in (
        "app/tests/test_runtime_info.py",
        "app/tests/test_command_registry.py",
        "app/tests/test_legacy_package_paths.py",
        "app/tests/test_host_console_quarantine.py",
        "app/tests/test_python_fallback_quarantine.py",
        "tests/test_python_fallback_audit_doc.py",
        "app/tests/test_rc_quarantine.py",
        "tests/test_rest_compatibility_doc.py",
        "tests/test_rest_exec_python_audit_doc.py",
        "tests/test_rest_exec_language_contract_doc.py",
        "tests/test_rest_exec_language_migration_doc.py",
        "tests/test_rest_exec_command_mode_audit_doc.py",
        "tests/test_legacy_package_pipeline.py",
        "tests/test_docs_index.py",
        "tests/test_readme_alpine_first.py",
        "tests/test_readme_rest_boundary.py",
    ):
        assert rel in text
