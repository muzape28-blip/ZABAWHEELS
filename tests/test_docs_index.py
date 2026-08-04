"""Guardrails for Alpine-first documentation indexing/archive staging."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def test_docs_index_references_every_top_level_doc():
    index = (DOCS / "README.md").read_text(encoding="utf-8")
    missing = []
    for path in sorted(DOCS.glob("*.md")):
        if path.name == "README.md":
            continue
        if f"({path.name})" not in index and f"]({path.name})" not in index:
            missing.append(path.name)
    assert not missing, f"docs/README.md missing docs: {missing}"


def test_docs_index_defines_current_and_legacy_package_workflows():
    index = (DOCS / "README.md").read_text(encoding="utf-8")
    assert "Alpine-first documentation map" in index
    assert "apk" in index
    assert "python3 -m pip" in index or "venv/pip" in index
    assert "Legacy ZABAWHEELS package/wheelhouse docs" in index
    assert "Do not delete historical docs" in index


def test_archive_staging_readme_exists_without_moving_docs_yet():
    readme = (DOCS / "archive" / "README.md").read_text(encoding="utf-8")
    assert "Archive Staging" in readme
    assert "labeled in place rather than moved" in readme
    assert "Do not use this directory as a trash can" in readme


def test_package_docs_are_marked_legacy_in_place():
    for name in ("PACKAGE_COMPATIBILITY.md", "PACKAGE_LIFECYCLE.md"):
        text = (DOCS / name).read_text(encoding="utf-8")
        assert "Legacy ZABAWHEELS note" in text
        assert "Alpine" in text
        assert "venv" in text or "pip" in text
