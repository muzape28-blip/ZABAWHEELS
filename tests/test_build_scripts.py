"""Regression tests for build input validation and index generation."""

import json
from pathlib import Path

import pytest

from scripts import build, generate_index, generate_manifest


RUNTIME_ID = "zmux-py314-api26-p4a5c192d7b7308-r1"


def _manifest(name: str, abi: str, channel: str) -> dict:
    return {
        "schema_version": 1,
        "name": name,
        "version": "1.0.0",
        "runtime_id": RUNTIME_ID,
        "abi": abi,
        "channel": channel,
        "artifact": {
            "filename": f"{name}.whl",
            "url": f"https://example.invalid/{name}.whl",
            "size": 1,
            "sha256": "a" * 64,
        },
        "native": {"has_extensions": True},
        "verification": {"build_passed": True},
    }


def test_build_rejects_package_path_traversal():
    with pytest.raises(SystemExit):
        build.package_directory("../toolchain")


def test_build_rejects_version_that_differs_from_recipe():
    assert not build.run_build(
        "zaba-native-smoke", "9.9.9", "armeabi-v7a", "experimental", True
    )


def test_prepare_source_copies_only_locked_files(tmp_path):
    source = build.prepare_source(
        "zaba-native-smoke", {"source_url": "local"}, tmp_path
    )

    copied = {
        path.relative_to(source).as_posix()
        for path in source.rglob("*")
        if path.is_file()
    }
    assert "pyproject.toml" in copied
    assert "README.md" in copied
    assert "src/zaba_native_smoke/_smoke.pyx" in copied
    assert "recipe.yaml" not in copied
    assert not any("__pycache__" in path for path in copied)


def test_manifest_rejects_version_that_differs_from_recipe():
    with pytest.raises(ValueError, match="Recipe version"):
        generate_manifest.generate_manifest(
            "zaba-native-smoke",
            "9.9.9",
            RUNTIME_ID,
            "armeabi-v7a",
            "experimental",
        )


def test_manifest_records_publication_metadata(tmp_path):
    wheel = tmp_path / "zaba_native_smoke-0.1.0-py3-none-any.whl"
    wheel.write_bytes(b"test wheel")
    artifact_url = f"https://example.invalid/releases/{wheel.name}"

    manifest = generate_manifest.generate_manifest(
        "zaba-native-smoke",
        "0.1.0",
        RUNTIME_ID,
        "armeabi-v7a",
        "experimental",
        str(wheel),
        artifact_url,
        True,
        True,
    )

    assert manifest["artifact"]["url"] == artifact_url
    assert manifest["artifact"]["sha256"]
    assert manifest["verification"]["build_passed"] is True
    assert manifest["verification"]["elf_inspected"] is True


def test_all_channel_index_is_merged_before_writing(tmp_path, monkeypatch):
    source_index = tmp_path / "source-index"
    for channel in ("experimental", "candidate", "stable"):
        (source_index / channel).mkdir(parents=True)

    (source_index / "experimental" / "alpha-1.0.0-armeabi-v7a.json").write_text(
        json.dumps(_manifest("alpha", "armeabi-v7a", "experimental")),
        encoding="utf-8",
    )
    (source_index / "candidate" / "beta-1.0.0-arm64-v8a.json").write_text(
        json.dumps(_manifest("beta", "arm64-v8a", "candidate")),
        encoding="utf-8",
    )
    # Aggregate channel files must not be interpreted as package manifests.
    (source_index / "candidate" / "index.json").write_text(
        json.dumps({"schema_version": 1, "packages": {"not-a-manifest": {}}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(generate_index, "INDEX_DIR", source_index)
    output = tmp_path / "output"
    assert generate_index.generate_index(str(output), "all")

    runtime_dir = output / "v1" / "runtimes" / RUNTIME_ID
    armv7 = json.loads((runtime_dir / "armeabi-v7a.json").read_text("utf-8"))
    arm64 = json.loads((runtime_dir / "arm64-v8a.json").read_text("utf-8"))
    packages = json.loads((runtime_dir / "packages.json").read_text("utf-8"))

    assert set(armv7["packages"]) == {"alpha"}
    assert set(arm64["packages"]) == {"beta"}
    assert set(packages["packages"]) == {"alpha", "beta"}


class TestTallocNeedRewrite:
    """The talloc NEEDED rewrite must preserve byte length exactly.

    Regression: a naive b"libtalloc.so\\x00" replacement is 13 bytes vs the
    14-byte needle, shrinking the file by one byte and shifting every section
    header — the shipped binary then failed on-device with
    "empty/missing DT_HASH/DT_GNU_HASH" and garbage DT entries.
    """

    def test_needle_and_replacement_are_same_length(self):
        from scripts.build_proot_android import (
            TALLOC_NEEDED,
            TALLOC_NEEDED_REPLACEMENT,
        )
        assert len(TALLOC_NEEDED) == 14
        assert len(TALLOC_NEEDED_REPLACEMENT) == len(TALLOC_NEEDED)

    def test_patch_preserves_file_size(self, tmp_path):
        from scripts.build_proot_android import patch_talloc_names
        lib = tmp_path / "libproot.so"
        payload = b"\x7fELF" + b"prefix libtalloc.so.2 suffix" + b"\x00" * 64
        lib.write_bytes(payload)
        patch_talloc_names(tmp_path)
        patched = lib.read_bytes()
        assert len(patched) == len(payload)
        assert b"libtalloc.so.2" not in patched
        assert b"libtalloc.so\x00\x00" in patched

    def test_patch_would_fail_loudly_if_length_changed(self, tmp_path, monkeypatch):
        from scripts import build_proot_android as b
        lib = tmp_path / "libproot.so"
        lib.write_bytes(b"\x7fELF" + b"x libtalloc.so.2 y" + b"\x00" * 64)
        monkeypatch.setattr(b, "TALLOC_NEEDED_REPLACEMENT", b"libtalloc.so\x00")
        with pytest.raises(SystemExit, match="file size"):
            b.patch_talloc_names(tmp_path)


class TestVerifyNeeded:
    """verify_needed() must check the right binding for each file:
    libproot.so *needs* libtalloc.so (DT_NEEDED); libtalloc.so *is* the
    library, so its binding is its SONAME."""

    def _make_out(self, tmp_path):
        (tmp_path / "libproot.so").write_bytes(b"\x7fELF")
        (tmp_path / "libtalloc.so").write_bytes(b"\x7fELF")
        return tmp_path

    def test_accepts_correctly_patched_binaries(self, tmp_path, monkeypatch):
        from scripts import build_proot_android as b
        out = self._make_out(tmp_path)
        outputs = {
            "libproot.so": (
                " 0x1 (NEEDED) Shared library: [libtalloc.so]\n"
                " 0x1 (NEEDED) Shared library: [libc.so]\n"
            ),
            "libtalloc.so": (
                " 0x1 (NEEDED) Shared library: [libc.so]\n"
                " 0xe (SONAME) Library soname: [libtalloc.so]\n"
            ),
        }

        def fake_readelf(cmd, **kw):
            import subprocess as sp
            name = cmd[-1].split("/")[-1]
            if name not in outputs:
                raise sp.CalledProcessError(1, cmd)  # static loader: skip
            class R:
                stdout = outputs[name]
            return R()

        monkeypatch.setattr(b.subprocess, "run", fake_readelf)
        b.verify_needed(out, b.Path("/fake/tc"))  # must not raise

    def test_rejects_wrong_talloc_soname(self, tmp_path, monkeypatch):
        from scripts import build_proot_android as b
        out = self._make_out(tmp_path)
        outputs = {
            "libproot.so": " 0x1 (NEEDED) Shared library: [libtalloc.so]\n",
            "libtalloc.so": " 0xe (SONAME) Library soname: [libtalloc.so.2]\n",
        }

        def fake_readelf(cmd, **kw):
            import subprocess as sp
            name = cmd[-1].split("/")[-1]
            class R:
                stdout = outputs[name]
            return R()

        monkeypatch.setattr(b.subprocess, "run", fake_readelf)
        with pytest.raises(SystemExit, match="SONAME"):
            b.verify_needed(out, b.Path("/fake/tc"))

    def test_rejects_wrong_proot_needed(self, tmp_path, monkeypatch):
        from scripts import build_proot_android as b
        out = self._make_out(tmp_path)
        outputs = {
            "libproot.so": " 0x1 (NEEDED) Shared library: [libtalloc.so.2]\n",
            "libtalloc.so": " 0xe (SONAME) Library soname: [libtalloc.so]\n",
        }

        def fake_readelf(cmd, **kw):
            import subprocess as sp
            name = cmd[-1].split("/")[-1]
            class R:
                stdout = outputs[name]
            return R()

        monkeypatch.setattr(b.subprocess, "run", fake_readelf)
        # The unresolved libtalloc.so.2 NEEDED is caught by the first loop.
        with pytest.raises(SystemExit, match="Unresolvable DT_NEEDED"):
            b.verify_needed(out, b.Path("/fake/tc"))
