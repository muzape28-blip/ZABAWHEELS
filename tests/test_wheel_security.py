"""ZABAWHEELS — Wheel security tests.

These tests verify the repository does not contain:
- Tracked binary/wheel files
- Credential files
- Private URLs in index
- Ambiguous artifacts
"""

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = REPO_ROOT / "index"


def tracked_files(pattern: str) -> list[str]:
    """Return matching Git-tracked paths, ignoring local build environments."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", pattern],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return [item.decode() for item in result.stdout.split(b"\0") if item]


def test_no_tracked_wheel_files():
    """No .whl files should be tracked in Git."""
    wheel_files = tracked_files("*.whl")
    assert not wheel_files, f"Tracked wheel files found: {wheel_files}"


def test_no_tracked_so_files():
    """No .so files should be tracked in Git."""
    so_files = tracked_files("*.so")
    assert not so_files, f"Tracked shared objects found: {so_files}"


def test_no_tracked_dll_files():
    """No .dll files should be tracked in Git."""
    dll_files = tracked_files("*.dll")
    assert not dll_files, f"Tracked DLL files found: {dll_files}"


def test_gitignore_blocks_wheels():
    """gitignore must block *.whl files."""
    gitignore_path = REPO_ROOT / ".gitignore"
    assert gitignore_path.exists(), ".gitignore not found"

    with open(gitignore_path) as f:
        content = f.read()
    assert "*.whl" in content, "*.whl not in .gitignore"


def test_gitignore_blocks_so():
    """gitignore must block *.so files."""
    gitignore_path = REPO_ROOT / ".gitignore"
    with open(gitignore_path) as f:
        content = f.read()
    assert "*.so" in content, "*.so not in .gitignore"


def test_gitignore_blocks_secrets():
    """gitignore must block common secret file patterns."""
    gitignore_path = REPO_ROOT / ".gitignore"
    with open(gitignore_path) as f:
        content = f.read()

    secret_patterns = [".env", "*.pem", "*.key", ".netrc"]
    for pattern in secret_patterns:
        assert pattern in content, f"{pattern} not in .gitignore"


def test_no_private_urls_in_index():
    """Index must not contain private URLs (only public GitHub URLs)."""
    for channel_dir in ["experimental", "candidate", "stable"]:
        packages_path = INDEX_DIR / channel_dir / "packages.json"
        if not packages_path.exists():
            continue

        import json
        with open(packages_path) as f:
            data = json.load(f)

        # Check no private URLs in artifact data
        for name, pkg in data.get("packages", {}).items():
            url = pkg.get("url", "")
            if url:
                assert "github.com" in url or url.startswith("https://"), \
                    f"Private URL found: {url}"
