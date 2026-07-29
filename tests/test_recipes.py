"""ZABAWHEELS — Recipe validation tests."""

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from scripts.verify_source_lock import local_source_hash


REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = REPO_ROOT / "packages"
TOOLCHAIN_DIR = REPO_ROOT / "toolchain"
SCHEMA_DIR = REPO_ROOT / "schemas"


def test_all_recipes_are_valid_yaml():
    """Every recipe.yaml file should be valid YAML."""
    if not PACKAGES_DIR.exists():
        pytest.skip("packages/ directory not found")

    recipe_files = []
    for package_dir in PACKAGES_DIR.iterdir():
        if package_dir.is_dir() and package_dir.name != "package-template":
            recipe_path = package_dir / "recipe.yaml"
            if recipe_path.exists():
                recipe_files.append(recipe_path)

    if not recipe_files:
        pytest.skip("No recipe files found")

    for recipe_path in recipe_files:
        with open(recipe_path) as f:
            recipe = yaml.safe_load(f)
        assert recipe is not None, f"Empty recipe: {recipe_path}"
        assert isinstance(recipe, dict), f"Recipe must be dict: {recipe_path}"


def test_recipes_conform_to_json_schema():
    """Every non-template recipe must conform to recipe.schema.json."""
    schema = json.loads((SCHEMA_DIR / "recipe.schema.json").read_text("utf-8"))
    validator = Draft202012Validator(schema)
    for recipe_path in PACKAGES_DIR.glob("*/recipe.yaml"):
        if recipe_path.parent.name == "package-template":
            continue
        recipe = yaml.safe_load(recipe_path.read_text("utf-8"))
        errors = sorted(validator.iter_errors(recipe), key=lambda item: list(item.path))
        assert not errors, f"Schema errors in {recipe_path}: {[e.message for e in errors]}"


def test_recipes_have_required_fields():
    """Every recipe must have required fields."""
    required_fields = [
        "package", "version", "upstream_url", "upstream_license",
        "source_url", "build_system", "native", "smoke_test",
        "status", "target_abis", "min_android_api",
    ]

    if not PACKAGES_DIR.exists():
        pytest.skip("packages/ directory not found")

    recipe_files = []
    for package_dir in PACKAGES_DIR.iterdir():
        if package_dir.is_dir() and package_dir.name != "package-template":
            recipe_path = package_dir / "recipe.yaml"
            if recipe_path.exists():
                recipe_files.append(recipe_path)

    if not recipe_files:
        pytest.skip("No recipe files found")

    for recipe_path in recipe_files:
        with open(recipe_path) as f:
            recipe = yaml.safe_load(f)
        for field in required_fields:
            assert field in recipe, f"Missing '{field}' in {recipe_path.parent.name}"


def test_recipe_statuses_are_valid():
    """Every recipe status must be a valid lifecycle state."""
    valid_statuses = [
        "planned", "researching", "recipe-ready", "building", "built",
        "inspected", "installable", "imported", "smoke-passed",
        "device-verified", "stable", "broken", "blocked", "deprecated", "revoked",
    ]

    for package_dir in PACKAGES_DIR.iterdir():
        if package_dir.is_dir() and package_dir.name != "package-template":
            recipe_path = package_dir / "recipe.yaml"
            if recipe_path.exists():
                with open(recipe_path) as f:
                    recipe = yaml.safe_load(f)
                status = recipe.get("status", "")
                assert status in valid_statuses, \
                    f"Invalid status '{status}' in {package_dir.name}"


def test_recipe_target_abis_are_valid():
    """Every recipe target_abis must contain valid ABI strings."""
    for package_dir in PACKAGES_DIR.iterdir():
        if package_dir.is_dir() and package_dir.name != "package-template":
            recipe_path = package_dir / "recipe.yaml"
            if recipe_path.exists():
                with open(recipe_path) as f:
                    recipe = yaml.safe_load(f)
                abis = recipe.get("target_abis", [])
                for abi in abis:
                    assert abi in ("armeabi-v7a", "arm64-v8a"), \
                        f"Invalid ABI '{abi}' in {package_dir.name}"


def test_non_local_sources_have_sha256():
    """Non-local packages must have source_sha256."""
    for package_dir in PACKAGES_DIR.iterdir():
        if package_dir.is_dir() and package_dir.name != "package-template":
            recipe_path = package_dir / "recipe.yaml"
            if recipe_path.exists():
                with open(recipe_path) as f:
                    recipe = yaml.safe_load(f)
                source_url = recipe.get("source_url", "")
                if source_url != "local" and source_url != "":
                    sha256 = recipe.get("source_sha256", "")
                    assert sha256, \
                        f"source_sha256 required for non-local: {package_dir.name}"


def test_zaba_native_smoke_recipe_exists():
    """zaba-native-smoke recipe must exist (first package)."""
    recipe_path = PACKAGES_DIR / "zaba-native-smoke" / "recipe.yaml"
    assert recipe_path.exists(), "zaba-native-smoke recipe.yaml not found"

    with open(recipe_path) as f:
        recipe = yaml.safe_load(f)

    assert recipe["package"] == "zaba-native-smoke"
    assert recipe["native"] is True
    assert recipe["smoke_test"] != ""


def test_local_sources_match_source_lock():
    """Every local package must match both the recipe and source lock hashes."""
    lock = json.loads((TOOLCHAIN_DIR / "source-lock.json").read_text("utf-8"))
    for name, record in lock.get("packages", {}).items():
        if record.get("source") != "local":
            continue
        package_dir = REPO_ROOT / record["source_url"]
        actual = local_source_hash(package_dir)
        recipe = yaml.safe_load((package_dir / "recipe.yaml").read_text("utf-8"))
        assert record["sha256"] == actual, f"Stale source lock for {name}"
        assert recipe["source_sha256"] == actual, f"Stale recipe hash for {name}"
