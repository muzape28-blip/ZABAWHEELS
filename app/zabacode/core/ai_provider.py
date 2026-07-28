"""
ZMUX Core — Multi-Provider AI Chat Handlers
Supports: OpenRouter, Gemini, Groq, Mistral, DeepSeek, Ollama (local), Custom Endpoint (OpenAI-compatible)
Philosophy: Tools stay as tools, not permanent branding. Custom endpoint is genuinely useful, offline Oracle remains the true offline intelligence.
"""

import json
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict

from zabacode.core.net import TLS_HELP_MESSAGE, get_ssl_context

ALLOWED_PROVIDERS = {"openrouter", "gemini", "groq", "mistral", "deepseek", "ollama", "custom"}

# Default system prompt (Tsundere persona, English)
SYSTEM_PROMPT = (
    "You are ZMUX AI, an adaptive, sharp-tongued/tsundere coding assistant. "
    "You like to tease Zaba, but are extremely expert at helping with Python coding on Android. "
    "Answer concisely, directly, and go straight to the solution in English."
)


def _handle_url_error(e: Exception, provider_name: str) -> dict:
    """Handle URL errors from AI providers, returning error dict with rate-limit flag."""
    is_rate_limit = False
    if isinstance(e, urllib.error.HTTPError):
        if e.code in (429, 402):
            is_rate_limit = True
        try:
            err_body = e.read().decode("utf-8", errors="ignore")
            err_json = json.loads(err_body)
            if isinstance(err_json.get("error"), dict):
                msg = err_json["error"].get("message", str(e))
            else:
                msg = err_json.get("error") or str(e)

            lower_msg = msg.lower()
            if any(
                w in lower_msg
                for w in (
                    "rate limit",
                    "quota",
                    "credit",
                    "billing",
                    "balance",
                    "insufficient",
                    "exhausted",
                )
            ):
                is_rate_limit = True

            return {
                "ok": False,
                "message": f"{provider_name} error ({e.code}): {msg}",
                "is_rate_limit": is_rate_limit,
            }
        except Exception:
            return {
                "ok": False,
                "message": f"{provider_name} error ({e.code})",
                "is_rate_limit": is_rate_limit,
            }

    if isinstance(e, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(e):
        return {
            "ok": False,
            "message": f"{provider_name}: {TLS_HELP_MESSAGE}",
            "is_rate_limit": False,
            "tls_error": True,
        }

    err_str = str(e)
    lower_err = err_str.lower()
    if any(
        w in lower_err
        for w in (
            "rate limit",
            "quota",
            "credit",
            "billing",
            "balance",
            "insufficient",
            "exhausted",
        )
    ):
        is_rate_limit = True
    return {"ok": False, "message": f"{provider_name} error: {e}", "is_rate_limit": is_rate_limit}


def call_openrouter(api_key: str, message: str, code_context: str = "", model: str = "") -> dict:
    """Call OpenRouter API."""
    actual_model = model if (model and model.strip()) else "qwen/qwen-2.5-coder-32b-instruct:free"
    user_content = (
        f"Active code editor content:\n```python\n{code_context}\n```\n\nQuestion: {message}"
        if code_context
        else message
    )
    body = json.dumps(
        {
            "model": actual_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        }
    ).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/muzape28-blip/ZMUX",
            "X-Title": "ZMUX Mobile IDE",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45, context=get_ssl_context()) as resp:
            data = json.loads(resp.read())
        return {"ok": True, "reply": data["choices"][0]["message"]["content"]}
    except Exception as e:
        return _handle_url_error(e, "OpenRouter")


def call_gemini(api_key: str, message: str, code_context: str = "", model: str = "") -> dict:
    """Call Google Gemini API."""
    actual_model = model if (model and model.strip()) else "gemini-1.5-flash"
    user_content = (
        f"Active code editor content:\n```python\n{code_context}\n```\n\nQuestion: {message}"
        if code_context
        else message
    )
    body = json.dumps(
        {"contents": [{"parts": [{"text": SYSTEM_PROMPT + "\n\n" + user_content}]}]}
    ).encode()
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{actual_model}:generateContent?key={api_key}",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45, context=get_ssl_context()) as resp:
            data = json.loads(resp.read())
        reply = data["candidates"][0]["content"]["parts"][0]["text"]
        return {"ok": True, "reply": reply}
    except Exception as e:
        return _handle_url_error(e, "Gemini")


def call_groq(api_key: str, message: str, code_context: str = "", model: str = "") -> dict:
    """Call Groq API."""
    actual_model = model if (model and model.strip()) else "llama-3.1-8b-instant"
    user_content = (
        f"Active code editor content:\n```python\n{code_context}\n```\n\nQuestion: {message}"
        if code_context
        else message
    )
    body = json.dumps(
        {
            "model": actual_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45, context=get_ssl_context()) as resp:
            data = json.loads(resp.read())
        return {"ok": True, "reply": data["choices"][0]["message"]["content"]}
    except Exception as e:
        return _handle_url_error(e, "Groq")


def call_mistral(api_key: str, message: str, code_context: str = "", model: str = "") -> dict:
    """Call Mistral API."""
    actual_model = model if (model and model.strip()) else "codestral-latest"
    user_content = (
        f"Active code editor content:\n```python\n{code_context}\n```\n\nQuestion: {message}"
        if code_context
        else message
    )
    body = json.dumps(
        {
            "model": actual_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.mistral.ai/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45, context=get_ssl_context()) as resp:
            data = json.loads(resp.read())
        return {"ok": True, "reply": data["choices"][0]["message"]["content"]}
    except Exception as e:
        return _handle_url_error(e, "Mistral")


def call_deepseek(api_key: str, message: str, code_context: str = "", model: str = "") -> dict:
    """Call DeepSeek API."""
    actual_model = model if (model and model.strip()) else "deepseek-coder"
    user_content = (
        f"Active code editor content:\n```python\n{code_context}\n```\n\nQuestion: {message}"
        if code_context
        else message
    )
    body = json.dumps(
        {
            "model": actual_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        }
    ).encode()
    req = urllib.request.Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60, context=get_ssl_context()) as resp:
            data = json.loads(resp.read())
        return {"ok": True, "reply": data["choices"][0]["message"]["content"]}
    except Exception as e:
        return _handle_url_error(e, "DeepSeek")


def call_ollama(api_key: str, message: str, code_context: str = "", model: str = "") -> dict:
    """Call Ollama local API (offline-capable, runs on localhost)."""
    actual_model = model if (model and model.strip()) else "codellama"
    user_content = (
        f"Active code editor content:\n```python\n{code_context}\n```\n\nQuestion: {message}"
        if code_context
        else message
    )
    body = json.dumps(
        {
            "model": actual_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
        }
    ).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120, context=get_ssl_context()) as resp:
            data = json.loads(resp.read())
        return {"ok": True, "reply": data.get("message", {}).get("content", "")}
    except Exception as e:
        return _handle_url_error(e, "Ollama")


def call_custom_endpoint(api_key: str, message: str, code_context: str = "", model: str = "") -> Dict[str, Any]:
    """
    Call Custom OpenAI-compatible Endpoint.

    This is the genuinely useful part of the former 'arena' provider:
    user puts URL in API key field (e.g. https://your-server.com/v1 or http://192.168.1.10:11434/v1)
    We normalize to /v1/chat/completions and call it with verified TLS.

    If api_key is NOT a URL, return a helpful error explaining how to use it.

    Philosophically neutral: no branding, just a tool. Offline intelligence remains Zaba Oracle.
    """
    user_content = (
        f"Active code editor content:\n```python\n{code_context}\n```\n\nQuestion: {message}"
        if code_context
        else message
    )

    # Require URL
    if not api_key or not api_key.strip():
        return {
            "ok": False,
            "message": "Custom endpoint requires URL in API key field. Example: https://api.your-server.com/v1 or http://192.168.1.10:11434/v1",
            "needs_key": True,
            "provider": "custom",
        }

    raw = api_key.strip()
    if not raw.startswith("http://") and not raw.startswith("https://"):
        return {
            "ok": False,
            "message": "Custom endpoint API key must be a URL starting with http:// or https://. Example: https://api.example.com/v1",
            "needs_key": True,
            "provider": "custom",
        }

    endpoint = raw.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        if endpoint.endswith("/v1"):
            endpoint = endpoint + "/chat/completions"
        elif "/v1/" not in endpoint:
            endpoint = endpoint + "/v1/chat/completions"
        # else: assume user already gave full path like /v1/chat/completions or custom path

    actual_model = model if (model and model.strip()) else "custom-default"
    body = json.dumps(
        {
            "model": actual_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        }
    ).encode()

    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60, context=get_ssl_context()) as resp:
            data = json.loads(resp.read())

        # OpenAI shape
        if isinstance(data, dict):
            choices = data.get("choices")
            if isinstance(choices, list) and len(choices) > 0:
                first = choices[0]
                if isinstance(first, dict):
                    msg_obj = first.get("message")
                    if isinstance(msg_obj, dict):
                        content = msg_obj.get("content")
                        if isinstance(content, str):
                            return {"ok": True, "reply": content, "provider": "custom"}
            # Ollama shape
            msg_field = data.get("message")
            if isinstance(msg_field, dict):
                c = msg_field.get("content")
                if isinstance(c, str):
                    return {"ok": True, "reply": c, "provider": "custom"}
            # generic fallback dump
            return {
                "ok": True,
                "reply": json.dumps(data)[:4000],
                "provider": "custom",
            }

        return {"ok": False, "message": "Custom endpoint returned unexpected format", "provider": "custom"}

    except Exception as e:
        # Let _handle_url_error produce actionable message, but keep provider = custom
        err = _handle_url_error(e, "Custom Endpoint")
        err["provider"] = "custom"
        return err


# Provider registry — neutral names, no permanent tool branding
PROVIDER_HANDLERS = {
    "openrouter": call_openrouter,
    "gemini": call_gemini,
    "groq": call_groq,
    "mistral": call_mistral,
    "deepseek": call_deepseek,
    "ollama": call_ollama,
    "custom": call_custom_endpoint,
}

# Provider display info — neutral
PROVIDER_INFO = {
    "openrouter": {
        "name": "OpenRouter",
        "mode": "online",
        "icon": "🌐",
        "models": "Multi-model (free & paid)",
    },
    "gemini": {
        "name": "Google Gemini",
        "mode": "online",
        "icon": "✨",
        "models": "Gemini 1.5 Flash",
    },
    "groq": {
        "name": "Groq",
        "mode": "online",
        "icon": "⚡",
        "models": "Llama 3.1 8B (ultra-fast)",
    },
    "mistral": {
        "name": "Mistral",
        "mode": "online",
        "icon": "🌀",
        "models": "Codestral",
    },
    "deepseek": {
        "name": "DeepSeek",
        "mode": "online",
        "icon": "🔍",
        "models": "DeepSeek Coder",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "mode": "offline",
        "icon": "🖥️",
        "models": "CodeLlama / Local models",
    },
    "custom": {
        "name": "Custom Endpoint",
        "mode": "online",
        "icon": "🔧",
        "models": "OpenAI-compatible URL (e.g. http://192.168.1.10:11434/v1)",
    },
}
