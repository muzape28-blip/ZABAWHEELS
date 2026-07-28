#!/usr/bin/env bash
# ZABACODE local check — mirrors CI quality gates (Fix #26)
# Usage: ./tools/check.sh or bash tools/check.sh
# This reproduces the same checks that run in .github/workflows/build_apk.yml

set -e

echo "=== ZABACODE Local Check (mirrors CI) ==="

echo "[1/5] Install deps from locked file (if available) or dev file"
if [ -f requirements.lock ]; then
  echo "Using requirements.lock"
  pip install -r requirements.lock -q || pip install -r requirements-dev.txt -q
else
  pip install -r requirements-dev.txt -q
fi
pip install ruff mypy pytest pytest-cov -q

echo "[2/5] Ruff Linter (critical: E9,F821)"
ruff check . --select=E9,F821

echo "[3/5] Ruff Linter (full, non-blocking)"
ruff check . --select=E,F,W,I --exit-zero || true

echo "[4/5] Mypy Type Checking on Core Modules (blocking)"
mypy --ignore-missing-imports zabacode/core/security.py zabacode/core/executor.py zabacode/core/net.py zabacode/core/keystore.py zabacode/core/ai_provider.py zabacode/core/oracle.py

echo "[4b/5] Mypy wider sweep (non-blocking)"
mypy --ignore-missing-imports zabacode/ --exclude 'zabacode/(files|cache|logs|user_packages)/' || true

echo "[5/5] Pytest Unit Tests"
python -m pytest -v

echo "[6/5] Security checks (no unverified SSL, Ace bundled, CSP, certifi, no CDN)"
if grep -R "ssl._create_unverified_context" zabacode/ --exclude-dir=user_packages; then
  echo "❌ Found unverified SSL context!"
  exit 1
else
  echo "✅ No unverified SSL context"
fi

if [ ! -f assets/vendor/ace/ace.js ]; then
  echo "❌ Ace not bundled"
  exit 1
else
  echo "✅ Ace bundled"
fi

if ! grep -q "Content-Security-Policy" zabacode/web_app.py; then
  echo "❌ CSP missing"
  exit 1
else
  echo "✅ CSP present"
fi

if ! grep -q "certifi" buildozer.spec; then
  echo "❌ certifi missing from buildozer.spec"
  exit 1
else
  echo "✅ certifi in spec"
fi

if grep -q "cdnjs.cloudflare.com\|unpkg.com\|jsdelivr.net" templates/index.html; then
  echo "❌ External CDN found — breaks offline-first"
  exit 1
else
  echo "✅ No external CDN"
fi

python -c "
from zabacode.core.ai_provider import ALLOWED_PROVIDERS, PROVIDER_HANDLERS
print(f'Providers: {sorted(ALLOWED_PROVIDERS)}')
assert len(ALLOWED_PROVIDERS) >= 6
print('✅ Provider registry OK')
"

echo ""
echo "=== All local checks passed — mirrors CI gate ==="
echo "To reproduce CI exactly, use pinned Actions SHAs in build_apk.yml and requirements.lock"
