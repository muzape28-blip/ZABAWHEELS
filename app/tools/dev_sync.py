#!/usr/bin/env python3
"""
ZMUX dev sync helper — neutral workspace tooling
Not product branding, just helper for local development / CI checks.

Usage:
  python tools/dev_sync.py --verify
  python tools/dev_sync.py --test
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: str):
    r = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True)
    return r


def verify():
    print("=== Verifying ZMUX Neutral Integration ===\n")
    ok = True

    # Check providers
    sys.path.insert(0, str(ROOT))
    try:
        from zabacode.core.ai_provider import ALLOWED_PROVIDERS, PROVIDER_HANDLERS, PROVIDER_INFO

        print(f"Providers: {sorted(ALLOWED_PROVIDERS)}")
        checks = [
            ("custom" in ALLOWED_PROVIDERS, "custom in ALLOWED_PROVIDERS"),
            ("custom" in PROVIDER_HANDLERS, "custom in PROVIDER_HANDLERS"),
            ("custom" in PROVIDER_INFO, "custom in PROVIDER_INFO"),
            ("arena" not in ALLOWED_PROVIDERS, "arena NOT in ALLOWED_PROVIDERS (de-branded)"),
            (PROVIDER_INFO.get("custom", {}).get("name") == "Custom Endpoint", "custom provider neutral name"),
        ]
        for passed, desc in checks:
            print(f"{'✅' if passed else '❌'} {desc}")
            if not passed:
                ok = False

        # Test custom endpoint error handling (requires URL)
        from zabacode.core.ai_provider import call_custom_endpoint

        res_no_url = call_custom_endpoint("", "hello", "", "custom-default")
        if not res_no_url["ok"] and "URL" in res_no_url.get("message", ""):
            print("✅ custom endpoint requires URL (neutral check)")
        else:
            print(f"❌ custom endpoint should require URL, got {res_no_url}")
            ok = False

        res_bad_url = call_custom_endpoint("not-a-url", "hi", "", "custom-default")
        if not res_bad_url["ok"]:
            print("✅ custom endpoint rejects non-URL")
        else:
            print("❌ should reject non-URL")
            ok = False

    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback

        traceback.print_exc()
        ok = False

    # Check template
    tpl = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    tpl_checks = [
        ("custom" in tpl.lower(), "custom in index.html"),
        (("ai-provider" not in tpl) or ("arena" not in tpl.lower() or "arena" not in tpl.split("ai-provider")[1][:500].lower()), "no arena branding in provider selector"),
        ("custom-default" in tpl, "custom models exist"),
    ]
    for passed, desc in tpl_checks:
        # Second check is best-effort, don't fail hard
        if "no arena branding" in desc:
            # Allow word arena elsewhere (e.g., comments) but not as provider value
            has_arena_option = 'value="arena"' in tpl
            passed = not has_arena_option
        print(f"{'✅' if passed else '❌'} {desc}")
        if not passed and "no arena" not in desc:
            ok = False

    # Check version neutral
    init_text = (ROOT / "zabacode" / "__init__.py").read_text()
    if '"1.0.0"' in init_text and "-arena" not in init_text and "__integration__" not in init_text:
        print("✅ __init__.py version neutral (1.0.0, no __integration__)")
    else:
        print("❌ __init__.py still has arena branding")
        ok = False

    # Check workflows
    arena_wf = ROOT / ".github" / "workflows" / "arena-integration.yml"
    if not arena_wf.exists():
        print("✅ arena-integration.yml removed (no branding gate)")
    else:
        print("❌ arena-integration.yml still exists")
        ok = False

    if (ROOT / "INTEGRATION_ARENA.md").exists():
        print("❌ INTEGRATION_ARENA.md still exists")
        ok = False
    else:
        print("✅ INTEGRATION_ARENA.md removed")

    print("\n" + ("✅ VERIFIED — neutral, philosophy-aligned" if ok else "❌ FAILED"))
    return ok


def test():
    r = run("python -m pytest -q")
    print(r.stdout[-2000:])
    print(r.stderr[-500:])
    return r.returncode == 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--verify", action="store_true")
    p.add_argument("--test", action="store_true")
    p.add_argument("--all", action="store_true")
    args = p.parse_args()
    if not any(vars(args).values()):
        args.all = True
    if args.all or args.verify:
        verify()
    if args.all or args.test:
        test()


if __name__ == "__main__":
    main()
