"""ZABAWHEELS — Manifest validation tests."""

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = REPO_ROOT / "index"
SCHEMA_DIR = REPO_ROOT / "schemas"


def test_index_channels_exist():
    """All three index channels must exist."""
    for channel in ["experimental", "candidate", "stable"]:
        channel_dir = INDEX_DIR / channel
        assert channel_dir.exists(), f"Index channel missing: {channel}/"


def test_index_channel_has_packages_json():
    """Each channel must have a packages.json."""
    for channel in ["experimental", "candidate", "stable"]:
        packages_path = INDEX_DIR / channel / "packages.json"
        assert packages_path.exists(), f"packages.json missing in {channel}/"

        with open(packages_path) as f:
            data = json.load(f)
        assert "schema_version" in data
        assert "packages" in data


def test_manifest_schema_is_valid_json():
    """package-manifest.schema.json must be valid JSON."""
    schema_path = SCHEMA_DIR / "package-manifest.schema.json"
    assert schema_path.exists(), "package-manifest.schema.json not found"

    with open(schema_path) as f:
        schema = json.load(f)
    assert schema.get("title") == "ZABAWHEELS Package Manifest"


def test_runtime_schema_is_valid_json():
    """runtime.schema.json must be valid JSON."""
    schema_path = SCHEMA_DIR / "runtime.schema.json"
    assert schema_path.exists(), "runtime.schema.json not found"

    with open(schema_path) as f:
        schema = json.load(f)
    assert schema.get("title") == "ZABAWHEELS Runtime Lock"


def test_recipe_schema_is_valid_json():
    """recipe.schema.json must be valid JSON."""
    schema_path = SCHEMA_DIR / "recipe.schema.json"
    assert schema_path.exists(), "recipe.schema.json not found"

    with open(schema_path) as f:
        schema = json.load(f)
    assert schema.get("title") == "ZABAWHEELS Package Recipe"


def test_device_report_schema_is_valid_json():
    """device-report.schema.json must be valid JSON."""
    schema_path = SCHEMA_DIR / "device-report.schema.json"
    assert schema_path.exists(), "device-report.schema.json not found"

    with open(schema_path) as f:
        schema = json.load(f)
    assert schema.get("title") == "ZABAWHEELS Device Test Report"
