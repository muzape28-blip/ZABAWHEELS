# Custom Endpoint — OpenAI-Compatible URL

ZMUX v1.0.0 includes a neutral **Custom Endpoint** provider.

Philosophy: Tools stay as tools. This provider lets you bring your own LLM without permanent branding in app identity.

## How to Use

1. Open ZMUX → AI Panel → Provider dropdown → `🔧 custom endpoint`
2. Go to Settings → AI API Keys → Custom Endpoint
3. In API key field, paste URL of your OpenAI-compatible server:
   - `https://api.your-server.com/v1`
   - `http://192.168.1.10:11434/v1` (Ollama with OpenAI compat)
   - `http://localhost:8000/v1` (LocalAI, vLLM, etc.)
4. Pick model: `custom-default`, `custom-openai-compatible`, `custom-ollama-compatible`
5. Chat — code context from active editor is sent automatically

## What Happens

```
User message + active code
  → web_app.py /api/ai/chat (provider=custom)
  → ai_provider.py call_custom_endpoint(api_key=URL, message, code, model)
  → Normalize URL to /v1/chat/completions
  → urllib.request.urlopen(..., context=get_ssl_context()) — verified TLS via certifi
  → Parse OpenAI shape (choices[0].message.content) or Ollama shape (message.content)
  → Return reply
```

If URL invalid or server down, `_handle_url_error` returns actionable message, and Oracle fallback answers if `allow_offline=True`.

## Why Keep This?

- Self-hosting friendly, avoids vendor lock-in
- Local network LLM (e.g., Ollama on PC, phone connects via LAN)
- Verified TLS, not bypass
- No branding — just a tool, identity stays with community

## Offline Intelligence

True offline brain remains **Zaba Oracle** (`oracle.py`):
- `humanize_traceback()` — plain English error + fix
- `analyze_buffer()` — AST review
- `offline_reply()` — rule-based assistant, no network

Custom endpoint is optional online extension, not replacement for Oracle.

## Security

- Uses shared `get_ssl_context()` (certifi bundle), no `ssl._create_unverified_context()`
- CSP headers active, loopback-only server, token auth
- API keys encrypted via keystore.py (AES-GCM) or in-memory only

## Examples

**Ollama on same LAN:**
- Run on PC: `ollama serve` + `ollama run codellama`
- Enable OpenAI compat: Ollama already serves `/api/chat` and OpenAI compat at `/v1/chat/completions` if using proxy, or use direct custom URL `http://192.168.1.10:11434/v1`
- In ZMUX, set custom key to `http://192.168.1.10:11434/v1`

**LocalAI:**
- LocalAI serves OpenAI-compatible: `http://192.168.1.10:8080/v1`
- Set as key, model `custom-default`

**vLLM:**
- vLLM with `--served-model-name` exposes `/v1/chat/completions`
- Set URL accordingly

---

Neutral tool, community-owned.
