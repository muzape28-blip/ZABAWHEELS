"""
ZMUX Core — Security: Auth Token, Encryption, Key Storage
Handles local session auth tokens, XOR-Base64 encryption, and Android Keystore integration.
"""

import secrets
import sys

from zabacode.core.keystore import decrypt_payload, encrypt_payload
from zabacode.core.paths import KEYS_FILE, TOKEN_FILE, USER_PACKAGES_DIR

# ---------------------------------------------------------------------------
# Auth Token Management
# ---------------------------------------------------------------------------

def _load_or_create_token() -> str:
    """Load existing auth token or generate a new 128-bit hex token."""
    if TOKEN_FILE.exists():
        try:
            token = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if len(token) >= 16:
                return token
        except Exception:
            pass

    token = secrets.token_hex(16)
    try:
        TOKEN_FILE.write_text(token, encoding="utf-8")
    except Exception:
        pass
    return token


AUTH_TOKEN = _load_or_create_token()

# Ensure user_packages in sys.path
if str(USER_PACKAGES_DIR) not in sys.path:
    sys.path.insert(0, str(USER_PACKAGES_DIR))


# ---------------------------------------------------------------------------
# Android Keystore / Encrypted Preferences Integration
# Centralized provider list to avoid missing new providers like 'custom'
# ---------------------------------------------------------------------------

def _get_all_providers() -> list[str]:
    """Centralized provider list — dependency-safe, avoids missing custom."""
    try:
        # Lazy import to avoid circular dependency at module load
        from zabacode.core.ai_provider import ALLOWED_PROVIDERS
        return sorted(ALLOWED_PROVIDERS)
    except Exception:
        # Fallback if ai_provider not importable (tests, etc.)
        return ["openrouter", "gemini", "groq", "mistral", "deepseek", "ollama", "custom"]


def _try_keystore_load() -> dict:
    """Attempt to load keys from Android EncryptedSharedPreferences."""
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        MasterKey = autoclass('androidx.security.crypto.MasterKey')
        EncryptedSharedPreferences = autoclass('androidx.security.crypto.EncryptedSharedPreferences')

        activity = PythonActivity.mActivity
        masterKey = MasterKey.Builder(activity).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
        prefs = EncryptedSharedPreferences.create(
            activity, "zabacode_secure_keys", masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SKEY,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
        keys = {}
        for p in _get_all_providers():
            val = prefs.getString(p, "")
            if val:
                keys[p] = val
        if keys:
            return keys
    except Exception:
        pass
    return {}


def _try_keystore_save(provider: str, api_key: str) -> bool:
    """Attempt to save a key to Android EncryptedSharedPreferences."""
    try:
        from jnius import autoclass
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        MasterKey = autoclass('androidx.security.crypto.MasterKey')
        EncryptedSharedPreferences = autoclass('androidx.security.crypto.EncryptedSharedPreferences')

        activity = PythonActivity.mActivity
        masterKey = MasterKey.Builder(activity).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
        prefs = EncryptedSharedPreferences.create(
            activity, "zabacode_secure_keys", masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SKEY,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
        editor = prefs.edit()
        editor.putString(provider, api_key)
        editor.apply()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public Key Storage API
# ---------------------------------------------------------------------------

_MEMORY_KEYS: dict[str, str] = {}


def load_keys() -> dict:
    """Load keys from Android Keystore; use local encrypted file or memory when unavailable."""
    keystore_keys = _try_keystore_load()
    if keystore_keys:
        # Even if keystore returns some keys, merge with file fallback for providers
        # that might not have been in old keystore list (e.g., custom added later)
        # File fallback is consulted only if keystore returned empty before, but now we merge
        # to avoid losing custom when old install had only 6 providers
        try:
            if KEYS_FILE.exists() and not _MEMORY_KEYS:
                loaded = decrypt_payload(KEYS_FILE.read_text(encoding="utf-8"))
                if loaded:
                    for k, v in loaded.items():
                        if k not in keystore_keys:
                            keystore_keys[k] = v
        except Exception:
            pass
        return keystore_keys

    # Check memory first, if empty, load from the authenticated encrypted file
    if not _MEMORY_KEYS and KEYS_FILE.exists():
        try:
            loaded = decrypt_payload(KEYS_FILE.read_text(encoding="utf-8"))
            if loaded:
                _MEMORY_KEYS.update(loaded)
        except Exception:
            pass

    return dict(_MEMORY_KEYS)


def save_key(provider: str, api_key: str) -> None:
    """Store keys in Android Keystore or keep them persistently in local file when unavailable."""
    provider = provider.strip()
    api_key = api_key.strip()
    if _try_keystore_save(provider, api_key):
        return
    _MEMORY_KEYS[provider] = api_key

    # Persist keys encrypted under this installation's random master secret
    try:
        KEYS_FILE.write_text(encrypt_payload(_MEMORY_KEYS), encoding="utf-8")
        try:
            import os
            import stat
            os.chmod(KEYS_FILE, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
    except Exception:
        pass


def verify_token(token: str) -> bool:
    """Verify an auth token using constant-time comparison."""
    import hmac
    if not token:
        return False
    return hmac.compare_digest(token, AUTH_TOKEN)
