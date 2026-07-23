"""
fable_client.py — minimal Anthropic Messages API client for the DDLC mod.

Why raw HTTPS instead of the `anthropic` SDK: this runs inside Ren'Py's bundled
CPython on a friend's machine, where we can't `pip install` anything. `urllib`
is in the standard library and always available, so the game works after simply
dropping in an API key — no dependencies.

Model wiring (see the claude-api guidance):
  * Primary model: claude-fable-5  — Anthropic's most capable model; thinking is
    ALWAYS ON (we never send a `thinking` field; sending one would 400). The raw
    chain of thought is never returned and defaults to hidden, which is exactly
    what we want: the "director brain" thinks privately, only the spoken line is
    returned.
  * Refusal safety net: claude-opus-4-8 via the server-side `fallbacks` param, so
    if Fable 5's safety classifiers decline a creepy line, Opus 4.8 re-serves it
    inside the same call and the character never breaks.
  * Speed: controlled with output_config.effort ("low" = snappy, our default).
"""

import json
import urllib.request
import urllib.error

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
FALLBACK_BETA = "server-side-fallback-2026-06-01"


class FableError(RuntimeError):
    """Raised when the API call fails outright (network/auth/etc.)."""


class FableResult:
    """The outcome of one completion."""

    def __init__(self, text, stop_reason, model, refused):
        self.text = text                # concatenated assistant text
        self.stop_reason = stop_reason  # "end_turn", "refusal", "max_tokens", ...
        self.model = model              # which model actually served it
        self.refused = refused          # True if the whole chain refused

    def __repr__(self):
        return "FableResult(model=%r, stop=%r, refused=%r, text=%r)" % (
            self.model, self.stop_reason, self.refused, self.text[:60])


class FableClient:
    def __init__(self, config):
        self.api_key = config["api_key"]
        self.model = config.get("model", "claude-fable-5")
        self.fallback_model = config.get("fallback_model", "claude-opus-4-8")
        self.effort = config.get("effort", "low")
        self.max_tokens = int(config.get("max_tokens", 1024))
        self.timeout = int(config.get("request_timeout_seconds", 90))

    def complete(self, system, messages):
        """
        system:   str — the full director/system prompt.
        messages: list of {"role": "user"|"assistant", "content": str}.
        Returns a FableResult. Raises FableError on transport/auth failure.
        """
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": messages,
            "output_config": {"effort": self.effort},
        }
        headers = {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }

        # Wire the Opus 4.8 refusal fallback (only when it differs from primary).
        if self.fallback_model and self.fallback_model != self.model:
            body["fallbacks"] = [{"model": self.fallback_model}]
            headers["anthropic-beta"] = FALLBACK_BETA

        # NOTE: we deliberately send NO `thinking` field. On Fable 5 thinking is
        # always on, and any explicit thinking config returns a 400.

        raw = self._post(body, headers)
        return self._parse(raw)

    # ---- internals -------------------------------------------------------

    def _post(self, body, headers):
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(API_URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8")
            except Exception:
                pass
            raise FableError("API HTTP %s: %s" % (e.code, detail[:500]))
        except urllib.error.URLError as e:
            raise FableError("Network error: %s" % (e.reason,))
        except Exception as e:  # noqa: BLE001 — surface anything else cleanly
            raise FableError("Unexpected error: %s" % (e,))

    def _parse(self, resp):
        stop_reason = resp.get("stop_reason")
        model = resp.get("model", self.model)
        refused = stop_reason == "refusal"

        # Concatenate all text blocks; skip thinking/fallback/other block types.
        parts = []
        for block in resp.get("content", []) or []:
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        text = "".join(parts).strip()

        return FableResult(text=text, stop_reason=stop_reason, model=model, refused=refused)
