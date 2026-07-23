"""
openrouter_client.py — OpenRouter (OpenAI-compatible) chat client.

We talk to OpenRouter, not the Anthropic API directly, so this uses the
OpenAI-style /chat/completions shape:
  POST https://openrouter.ai/api/v1/chat/completions
  Authorization: Bearer <key>
  body: {model|models, messages:[{role,content}], max_tokens, temperature}
  resp: {choices:[{message:{content}, finish_reason}], model}

Dependency-free (urllib) so it runs inside Ren'Py's bundled Python.

Fallback: OpenRouter's `models` array auto-falls-back to the next model if one
errors/is unavailable — we use it whenever a fallback model is configured.

PROMPT CACHING (the reason this file changed)
---------------------------------------------
Anthropic models on OpenRouter do NOT cache automatically — you mark explicit
breakpoints. A marked message's content becomes a list of parts, the last of
which carries cache_control:

    {"role": "system",
     "content": [{"type": "text", "text": "...",
                  "cache_control": {"type": "ephemeral"}}]}

Everything BEFORE and INCLUDING a breakpoint is cached; on the next call the
provider reuses the longest matching prefix. Reads cost ~10% of normal input;
writes cost ~125% (or ~200% with a 1-hour TTL). Since this game resends the
whole transcript every turn, this is the single biggest cost lever in the mod.

The director marks messages by setting `"cache": True` on them. That flag is
ours, not OpenRouter's — this module strips it and converts it.
"""

import json
import urllib.request
import urllib.error

DEFAULT_URL = "https://openrouter.ai/api/v1/chat/completions"

# Anthropic won't cache a prefix shorter than ~1024 tokens; below that the
# breakpoint is simply ignored, so there's no harm in always sending it.
_MIN_CACHE_CHARS = 2000


class LLMError(RuntimeError):
    """Transport / auth / credit failure (surfaced to the setter, not the player)."""


class LLMResult:
    def __init__(self, text, finish_reason, model, error=None, usage=None):
        self.text = text
        self.finish_reason = finish_reason      # "stop", "length", "content_filter", ...
        self.model = model                      # which model actually served it
        self.error = error                      # human string if something went wrong
        self.usage = usage or {}                # token counts incl. cache hits
        self.refused = finish_reason == "content_filter"

    def __repr__(self):
        return "LLMResult(model=%r, finish=%r, refused=%r, text=%r)" % (
            self.model, self.finish_reason, self.refused, (self.text or "")[:60])


def _cached_content(text, ttl):
    """Wrap a string as a single cache-marked content part."""
    control = {"type": "ephemeral"}
    if ttl and ttl != "5m":
        control["ttl"] = ttl                    # e.g. "1h"
    return [{"type": "text", "text": text, "cache_control": control}]


class LLMClient:
    def __init__(self, config):
        self.api_key = config.get("api_key", "")
        self.url = config.get("base_url", DEFAULT_URL)
        self.model = config.get("model", "openrouter/auto")
        self.fallback_model = (config.get("fallback_model") or "").strip()
        self.temperature = float(config.get("temperature", 0.9))
        self.max_tokens = int(config.get("max_tokens", 900))
        self.timeout = int(config.get("request_timeout_seconds", 90))
        self.referer = config.get("referer", "")
        self.title = config.get("title", "DDLC Director Mod")
        # caching
        self.cache_enabled = bool(config.get("enable_prompt_cache", True))
        self.cache_ttl = config.get("cache_ttl", "5m")      # "5m" or "1h"

    def _supports_cache(self):
        """Explicit cache_control is an Anthropic feature on OpenRouter."""
        if not self.cache_enabled:
            return False
        models = [self.model, self.fallback_model]
        return any(m and m.startswith("anthropic/") for m in models)

    def complete(self, system, messages):
        """
        system:   str — the static director prompt (becomes the system message,
                  and the first cache breakpoint).
        messages: list of {"role": "user"|"assistant", "content": str} — a
                  message may also carry "cache": True to place a rolling
                  breakpoint after it.
        Returns LLMResult. Raises LLMError on transport/auth/credit failure.
        """
        cache = self._supports_cache()

        if cache and len(system) >= _MIN_CACHE_CHARS:
            sys_msg = {"role": "system", "content": _cached_content(system, self.cache_ttl)}
        else:
            sys_msg = {"role": "system", "content": system}

        chat = [sys_msg]
        for m in messages:
            msg = dict(m)
            wants_cache = bool(msg.pop("cache", False))
            if cache and wants_cache and isinstance(msg.get("content"), str):
                msg["content"] = _cached_content(msg["content"], self.cache_ttl)
            chat.append(msg)

        body = {
            "messages": chat,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        # Ask OpenRouter to report cache hits so we can verify it's working.
        body["usage"] = {"include": True}

        # Use the fallback array when a second model is configured; otherwise a
        # single model. (OpenRouter tries them left-to-right.)
        if self.fallback_model and self.fallback_model != self.model:
            body["models"] = [self.model, self.fallback_model]
        else:
            body["model"] = self.model

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer %s" % self.api_key,
        }
        if self.referer:
            headers["HTTP-Referer"] = self.referer
        if self.title:
            headers["X-Title"] = self.title

        return self._parse(self._post(body, headers))

    # ---- internals -------------------------------------------------------

    def _post(self, body, headers):
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8")
            except Exception:
                pass
            msg = self._error_message(e.code, detail)
            raise LLMError(msg)
        except urllib.error.URLError as e:
            raise LLMError("Network error: %s" % (e.reason,))
        except Exception as e:  # noqa: BLE001
            raise LLMError("Unexpected error: %s" % (e,))

    @staticmethod
    def _error_message(code, detail):
        # Try to surface OpenRouter's structured error message.
        pretty = detail
        try:
            j = json.loads(detail)
            pretty = (j.get("error") or {}).get("message") or detail
        except Exception:
            pass
        if code == 402:
            return ("OpenRouter says: insufficient credit (402). Add funds, or set "
                    "\"model\" to a \":free\" model to test at $0. [%s]" % pretty[:200])
        if code == 401:
            return "OpenRouter says: bad API key (401). Check config.json. [%s]" % pretty[:200]
        return "OpenRouter HTTP %s: %s" % (code, pretty[:300])

    def _parse(self, resp):
        model = resp.get("model", self.model)
        usage = resp.get("usage") or {}
        choices = resp.get("choices") or []
        if not choices:
            err = (resp.get("error") or {}).get("message") or "no choices returned"
            return LLMResult("", None, model, error=err, usage=usage)
        first = choices[0]
        msg = first.get("message") or {}
        text = (msg.get("content") or "").strip()
        finish = first.get("finish_reason")
        return LLMResult(text=text, finish_reason=finish, model=model, usage=usage)
