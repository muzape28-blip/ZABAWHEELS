"""
ZMUX p4a hook — inject explicit taskAffinity + documentLaunchMode
Coexistence fix with Zabacode (see ZABACODE docs/COEXISTENCE_FIX.md)

Zabacode 5000, Zmux 6000 — distinct ports prevent loopback cross-talk.
TaskAffinity fix prevents launcher task confusion on budget devices.
"""
from pathlib import Path

try:
    from pythonforandroid.toolchain import ToolchainCL
except Exception:
    ToolchainCL = object

def _patch_manifest(manifest_path: Path, package: str = "com.zaba.zmux"):
    if not manifest_path.exists():
        print(f"[p4a_hook ZMUX] Manifest not found at {manifest_path}")
        return False
    text = manifest_path.read_text(encoding="utf-8")
    original = text
    affinity = package
    if 'android:taskAffinity' in text:
        import re
        text = re.sub(r'android:taskAffinity="[^"]*"', f'android:taskAffinity="{affinity}"', text)
        print(f"[p4a_hook ZMUX] Updated existing taskAffinity to {affinity}")
    else:
        marker = 'android:name="org.kivy.android.PythonActivity"'
        if marker in text:
            text = text.replace(
                marker,
                f'{marker}\n                  android:taskAffinity="{affinity}"\n                  android:documentLaunchMode="intoExisting"'
            )
            print(f"[p4a_hook ZMUX] Injected taskAffinity={affinity}")
        else:
            text = text.replace(
                "<activity",
                f'<activity android:taskAffinity="{affinity}" android:documentLaunchMode="intoExisting"',
                1
            )
    if 'android:launchMode="singleTask"' in text:
        text = text.replace('android:launchMode="singleTask"', 'android:launchMode="singleTop"')
        print("[p4a_hook ZMUX] Changed singleTask -> singleTop")
    if text != original:
        manifest_path.write_text(text, encoding="utf-8")
        print(f"[p4a_hook ZMUX] Patched {manifest_path}")
        return True
    print("[p4a_hook ZMUX] No changes")
    return False

def before_apk_build(toolchain):
    dist_dir = getattr(getattr(toolchain, "_dist", None), "dist_dir", None)
    if not dist_dir:
        dist_dir = getattr(toolchain, "dist_dir", None)
    if not dist_dir:
        for p in Path(".buildozer").rglob("AndroidManifest.xml"):
            if "zmux" in str(p).lower():
                _patch_manifest(p)
        return
    dist_path = Path(dist_dir)
    for cand in [dist_path / "src" / "main" / "AndroidManifest.xml"]:
        if cand.exists():
            _patch_manifest(cand)

def after_apk_build(toolchain):
    return before_apk_build(toolchain)

if __name__ == "__main__":
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("app/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/dists/zmux/src/main/AndroidManifest.xml")
    _patch_manifest(path)
