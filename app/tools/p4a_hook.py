"""
ZMUX p4a hook — Android manifest, task and native splash customisation.

The webview bootstrap creates a normal ``PythonActivity`` then shows the
Buildozer presplash while Python/WebView initialise. Android 12+ additionally
shows a *system* starting window before that code runs. Without an explicit
API-31 splash theme, Android supplied the device-default white screen and
purple loading bars. This hook installs a dark ZMUX splash theme directly in
the generated Gradle project, where p4a will package it.

It also keeps the task-affinity coexistence fix with Zabacode: ZMUX uses port
8000 and an explicit ``com.zaba.zmux`` task affinity.
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    from pythonforandroid.toolchain import ToolchainCL
except Exception:
    ToolchainCL = object


_SPLASH_THEME = "@style/Theme.ZMUX.Splash"
_SPLASH_BASE_VALUES = """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<resources>
    <color name=\"zmux_splash_background\">#0D1117</color>
    <!-- Pre-Android-12 starting window: never flash device-default white. -->
    <style name=\"Theme.ZMUX.Splash\" parent=\"@style/KivySupportCutout\">
        <item name=\"android:windowBackground\">@color/zmux_splash_background</item>
        <item name=\"android:colorAccent\">#52E878</item>
    </style>
</resources>
"""

# Kept in values-v31 so older Android releases never try to parse Android-12
# attributes. The parent preserves p4a's KivySupportCutout behaviour after the
# system hands control to PythonActivity.
_SPLASH_V31_VALUES = """<?xml version=\"1.0\" encoding=\"utf-8\"?>
<resources>
    <style name=\"Theme.ZMUX.Splash\" parent=\"@style/KivySupportCutout\">
        <item name=\"android:windowBackground\">@color/zmux_splash_background</item>
        <item name=\"android:windowSplashScreenBackground\">@color/zmux_splash_background</item>
        <item name=\"android:windowSplashScreenAnimatedIcon\">@drawable/zmux_splash_icon</item>
        <item name=\"android:windowSplashScreenIconBackgroundColor\">@color/zmux_splash_background</item>
        <item name=\"android:windowSplashScreenAnimationDuration\">0</item>
        <item name=\"android:colorAccent\">#52E878</item>
    </style>
</resources>
"""

# An adaptive foreground must be transparent: using the composed launcher PNG
# here is what produced a dark square inside Android's white rounded mask.
# This vector is only the Z>_ mark on the dark theme supplied above.
_SPLASH_ICON_VECTOR = """<vector xmlns:android=\"http://schemas.android.com/apk/res/android\"
    android:width=\"108dp\" android:height=\"108dp\"
    android:viewportWidth=\"108\" android:viewportHeight=\"108\">
    <path android:fillColor=\"@android:color/transparent\"
        android:strokeColor=\"#52E878\" android:strokeWidth=\"9.5\"
        android:strokeLineCap=\"round\" android:strokeLineJoin=\"round\"
        android:pathData=\"M25.7,31.2 L52.5,31.2 L28.9,68.6 L54.7,68.6\" />
    <path android:fillColor=\"@android:color/transparent\"
        android:strokeColor=\"#52E878\" android:strokeWidth=\"9.5\"
        android:strokeLineCap=\"round\" android:strokeLineJoin=\"round\"
        android:pathData=\"M62.7,40.6 L78.9,54 L62.7,67.4\" />
    <path android:fillColor=\"@android:color/transparent\"
        android:strokeColor=\"#52E878\" android:strokeWidth=\"9.5\"
        android:strokeLineCap=\"round\" android:pathData=\"M79.8,73.5 L90,73.5\" />
</vector>
"""


def _write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = path.read_text(encoding="utf-8")
    except OSError:
        existing = None
    if existing == content:
        return False
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def _install_splash_resources(manifest_path: Path) -> bool:
    """Install generated resources beside the p4a manifest, idempotently."""
    res = manifest_path.parent / "res"
    changed = False
    changed |= _write_if_changed(res / "values" / "zmux_splash.xml", _SPLASH_BASE_VALUES)
    changed |= _write_if_changed(res / "values-v31" / "zmux_splash.xml", _SPLASH_V31_VALUES)
    changed |= _write_if_changed(res / "drawable" / "zmux_splash_icon.xml", _SPLASH_ICON_VECTOR)
    return changed


def _apply_splash_theme(text: str) -> tuple[str, bool]:
    """Point only PythonActivity at the ZMUX system-splash theme."""
    pattern = re.compile(
        r'(<activity\b[^>]*android:name="org\.kivy\.android\.PythonActivity"[\s\S]*?</activity>)'
    )
    match = pattern.search(text)
    if not match:
        return text, False
    activity = match.group(1)
    if "android:theme=" in activity:
        themed = re.sub(r'android:theme="[^"]*"', f'android:theme="{_SPLASH_THEME}"', activity, count=1)
    else:
        themed = activity.replace(
            'android:name="org.kivy.android.PythonActivity"',
            f'android:name="org.kivy.android.PythonActivity"\n                  android:theme="{_SPLASH_THEME}"',
            1,
        )
    if themed == activity:
        return text, False
    return text[:match.start()] + themed + text[match.end():], True


def _patch_manifest(manifest_path: Path, package: str = "com.zaba.zmux"):
    if not manifest_path.exists():
        print(f"[p4a_hook ZMUX] Manifest not found at {manifest_path}")
        return False
    text = manifest_path.read_text(encoding="utf-8")
    original = text
    affinity = package
    if 'android:taskAffinity' in text:
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
                1,
            )
    if 'android:launchMode="singleTask"' in text:
        text = text.replace('android:launchMode="singleTask"', 'android:launchMode="singleTop"')
        print("[p4a_hook ZMUX] Changed singleTask -> singleTop")
    text, themed = _apply_splash_theme(text)
    if themed:
        print("[p4a_hook ZMUX] Applied Android 12+ ZMUX splash theme")
    if text != original:
        manifest_path.write_text(text, encoding="utf-8")
    resources_changed = _install_splash_resources(manifest_path)
    if text != original or resources_changed:
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
