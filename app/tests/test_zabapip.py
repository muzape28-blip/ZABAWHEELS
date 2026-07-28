import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from zabacode.core import zabapip


def _wheel(path: Path, package: str = "demo_pkg") -> None:
    dist = package.replace("_", "-") + "-1.0.0.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{package}/__init__.py", "VALUE = 42\n")
        archive.writestr(f"{dist}/WHEEL", "Wheel-Version: 1.0\nTag: py3-none-any\n")
        archive.writestr(f"{dist}/METADATA", f"Name: {package}\nVersion: 1.0.0\n")
        archive.writestr(f"{dist}/RECORD", "")


def _sandbox(monkeypatch, tmp_path):
    user = tmp_path / "user"
    state = tmp_path / "installed"
    staging = tmp_path / "staging"
    downloads = tmp_path / "downloads"
    for item in (user, state, staging, downloads):
        item.mkdir()
    monkeypatch.setattr(zabapip, "USER_PACKAGES_DIR", user)
    monkeypatch.setattr(zabapip, "STATE_DIR", state)
    monkeypatch.setattr(zabapip, "STAGING_DIR", staging)
    monkeypatch.setattr(zabapip, "DOWNLOAD_DIR", downloads)
    monkeypatch.setattr(zabapip, "DB_FILE", state / "packages.json")
    return user


def test_dispatch_is_allowlisted():
    assert not zabapip.dispatch("rm -rf /")["ok"]
    assert not zabapip.dispatch("zpip install")["ok"]
    assert zabapip.dispatch("zpip list")["ok"]


def test_dependency_cycle_is_rejected(monkeypatch, tmp_path):
    _sandbox(monkeypatch, tmp_path)
    manifest = {
        "name": "cycle", "version": "1.0.0", "dependencies": ["cycle>=1"],
        "artifact": {"url": "https://example.invalid/cycle.whl", "sha256": "0" * 64},
    }
    monkeypatch.setattr(zabapip, "resolve", lambda *args, **kwargs: manifest)
    result = zabapip.install("cycle")
    assert not result["ok"]
    assert "Dependency cycle" in result["error"]


def test_archive_traversal_is_rejected(tmp_path):
    wheel = tmp_path / "evil.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("../outside", "bad")
        archive.writestr("x.dist-info/WHEEL", "Wheel-Version: 1.0")
        archive.writestr("x.dist-info/RECORD", "")
    with pytest.raises(ValueError, match="Unsafe archive path"):
        zabapip._safe_members(wheel)


def test_transactional_install_verify_and_uninstall(monkeypatch, tmp_path):
    user = _sandbox(monkeypatch, tmp_path)
    source = tmp_path / "demo.whl"
    _wheel(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {
        "name": "demo-pkg", "version": "1.0.0", "runtime_id": "py3-none-any",
        "abi": "any", "channel": "pypi", "artifact": {"url": "https://example.invalid/demo.whl", "sha256": digest},
    }
    monkeypatch.setattr(zabapip, "resolve", lambda *args, **kwargs: manifest)

    def fake_download(url, expected, destination):
        shutil.copy2(source, destination)
        return destination.stat().st_size, expected

    monkeypatch.setattr(zabapip, "_download", fake_download)
    result = zabapip.install("demo-pkg")
    assert result["ok"], result
    assert (user / "demo_pkg" / "__init__.py").is_file()
    assert zabapip.verify("demo-pkg")["ok"]
    removed = zabapip.uninstall("demo-pkg")
    assert removed["ok"] and not (user / "demo_pkg" / "__init__.py").exists()


def test_failed_upgrade_restores_owned_file(monkeypatch, tmp_path):
    user = _sandbox(monkeypatch, tmp_path)
    owned = user / "demo_pkg" / "__init__.py"
    owned.parent.mkdir(parents=True)
    owned.write_text("VALUE = 1\n")
    zabapip._save_db({"demo-pkg": {"version": "0.9", "files": ["demo_pkg/__init__.py"]}})
    source = tmp_path / "broken.whl"
    _wheel(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {"version": "1.0", "artifact": {"url": "https://example.invalid/x", "sha256": digest}}
    monkeypatch.setattr(zabapip, "resolve", lambda *a, **k: manifest)
    monkeypatch.setattr(zabapip, "_download", lambda u, h, d: (shutil.copy2(source, d).stat().st_size, h))
    monkeypatch.setattr(zabapip, "_smoke_test", lambda *a: (_ for _ in ()).throw(ValueError("boom")))
    result = zabapip.install("demo-pkg")
    assert not result["ok"] and result["rolled_back"]
    assert owned.read_text() == "VALUE = 1\n"
