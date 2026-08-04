"""Guardrails for the quarantined legacy ZABAWHEELS package pipeline."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def _workflow(path: str) -> dict:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def test_build_package_workflow_is_explicitly_legacy_and_templated():
    workflow_path = ROOT / ".github/workflows/build-package.yml"
    template_path = ROOT / "workflow-templates/build-package.yml"
    assert workflow_path.read_text(encoding="utf-8") == template_path.read_text(encoding="utf-8")

    workflow = _workflow(".github/workflows/build-package.yml")
    assert workflow["name"] == "Legacy Build Package Wheel"
    assert workflow["env"]["LEGACY_ZABAWHEELS_PIPELINE"] == "1"

    raw = workflow_path.read_text(encoding="utf-8")
    assert "Legacy ZABAWHEELS wheelhouse pipeline" in raw
    assert "Alpine apk plus Python venv/pip" in raw


def test_validate_workflow_labels_package_checks_as_legacy_and_templated():
    workflow_path = ROOT / ".github/workflows/validate.yml"
    template_path = ROOT / "workflow-templates/validate.yml"
    assert workflow_path.read_text(encoding="utf-8") == template_path.read_text(encoding="utf-8")

    workflow = _workflow(".github/workflows/validate.yml")
    assert workflow["jobs"]["validate"]["name"] == "YAML, app tests, and legacy package contracts"

    raw = workflow_path.read_text(encoding="utf-8")
    assert "Legacy package checks" in raw
    assert "Alpine apk and Python venv/pip" in raw


def test_legacy_package_pipeline_doc_sets_maintainer_rules():
    doc = (ROOT / "docs/LEGACY_PACKAGE_PIPELINE.md").read_text(encoding="utf-8")
    assert "retained for migration" in doc
    assert "Do **not** add new user-facing features to `zpip`" in doc
    assert "apk search <name>" in doc
    assert "python3 -m pip install <name>" in doc
    assert "Removal prerequisites" in doc
