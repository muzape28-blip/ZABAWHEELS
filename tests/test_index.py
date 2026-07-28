"""ZABAWHEELS — Index validation tests."""

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = REPO_ROOT / "index"


def test_index_directory_structure():
    """Index must have experimental, candidate, and stable channels."""
    for channel in ["experimental", "candidate", "stable"]:
        channel_dir = INDEX_DIR / channel
        assert channel_dir.is_dir(), f"Missing index channel: {channel}"


def test_index_packages_json_structure():
    """Each packages.json must have required fields."""
    for channel in ["experimental", "candidate", "stable"]:
        packages_path = INDEX_DIR / channel / "packages.json"
        with open(packages_path) as f:
            data = json.load(f)

        assert data["schema_version"] == 1, f"Wrong schema_version in {channel}"
        assert isinstance(data["packages"], dict), f"packages must be dict in {channel}"
        assert "abis" in data, f"Missing 'abis' in {channel}"
        assert "armeabi-v7a" in data["abis"], f"Missing armeabi-v7a in {channel}"


def test_no_duplicate_packages_per_channel():
    """No duplicate package entries within a channel."""
    for channel in ["experimental", "candidate", "stable"]:
        packages_path = INDEX_DIR / channel / "packages.json"
        with open(packages_path) as f:
            data = json.load(f)

        packages = data.get("packages", {})
        names = list(packages.keys())
        assert len(names) == len(set(names)), f"Duplicate packages in {channel}"


def test_index_note_is_present():
    """Each channel packages.json should have a note explaining its state."""
    for channel in ["experimental", "candidate", "stable"]:
        packages_path = INDEX_DIR / channel / "packages.json"
        with open(packages_path) as f:
            data = json.load(f)
        assert "note" in data, f"Missing 'note' in {channel}/packages.json"
