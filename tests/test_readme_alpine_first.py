"""Guardrails for the root README staying Alpine-first."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def test_root_readme_points_to_docs_index_and_legacy_pipeline_policy():
    text = _readme()
    assert "docs/README.md" in text
    assert "docs/LEGACY_PACKAGE_PIPELINE.md" in text
    assert "retained only for migration" in text


def test_root_readme_package_guidance_is_alpine_first():
    text = _readme()
    assert "apk add" in text
    assert "python3 -m venv" in text
    assert "python3 -m pip install" in text
    assert "zpip install" not in text
    assert "linux apk add" not in text


def test_root_readme_documentation_section_classifies_legacy_docs():
    text = _readme()
    assert "Documentation map" in text
    assert "Legacy package pipeline" in text
    assert "Historical docs" in text


def test_historical_root_reports_are_labeled():
    for name in ("ROADMAP_STATUS.md", "REFACTOR_REPORT.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "Historical" in text or "Historical".lower() in text.lower()
        assert "Alpine-first" in text
        assert "docs/README.md" in text
