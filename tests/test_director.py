#!/usr/bin/env python3
"""
Offline test suite for the v2 director — no network, no API credits.

Run:  python3 tests/test_director.py
Covers: parsing (beat + legacy + non-JSON), crack-budget gates, the
enforcement reroll, once-per-session actions, cache-prefix stability, band
transitions, and the client's cache_control conversion.
"""

import json
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "game"))

from claude_mod import director as D                     # noqa: E402
from claude_mod.director import Director, Beat           # noqa: E402
from claude_mod.openrouter_client import LLMClient, LLMResult, _cached_content  # noqa: E402

PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print("  %s %s%s" % ("✓" if cond else "✗", name, (" — " + detail) if (detail and not cond) else ""))


class FakeClient:
    """Returns queued canned responses; records every call's messages."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, system, messages):
        self.calls.append({"system": system, "messages": [dict(m) for m in messages]})
        text = self.responses.pop(0) if self.responses else self.responses_default()
        return LLMResult(text=text, finish_reason="stop", model="fake", usage={})

    @staticmethod
    def responses_default():
        return json.dumps({"turns": [{"speaker": "monika", "expression": "warm",
                                      "text": "Okay, everyone!"}], "crack": "none"})


def beat_json(crack="none", text="Poems out, everyone!", speaker="sayori", n=1):
    turns = [{"speaker": speaker, "expression": "happy", "text": text} for _ in range(n)]
    return json.dumps({"turns": turns, "music": "keep", "background": "keep",
                       "effect": "none", "action": "none", "crack": crack})


def fresh(config_extra=None, session="__test__"):
    cfg = {"api_key": "test", "model": "anthropic/claude-fable-5",
           "enable_local_scan": False, "pace": "normal", "starting_intensity": 0}
    cfg.update(config_extra or {})
    mem_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                           "game", "claude_mod", "memory")
    shutil.rmtree(mem_dir, ignore_errors=True)
    d = Director(cfg, session_name=session)
    d.client = FakeClient([])
    return d


def cleanup():
    mem_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                           "game", "claude_mod", "memory")
    shutil.rmtree(mem_dir, ignore_errors=True)


# ── 1. parsing ─────────────────────────────────────────────────────────────
print("[parsing]")
d = fresh()
r = LLMResult(beat_json(n=3, crack="none"), "stop", "fake")
b = d._parse(r)
check("beat shape: 3 turns", len(b) == 3)
check("beat crack label", b.crack == "none")

legacy = json.dumps({"speaker": "natsuki", "expression": "pouty",
                     "text": "Hmph.", "crack": "hairline"})
b = d._parse(LLMResult(legacy, "stop", "fake"))
check("legacy single-line shape", len(b) == 1 and b.speaker == "natsuki" and b.crack == "hairline")

b = d._parse(LLMResult("just plain text", "stop", "fake"))
check("non-JSON fallback -> monika line", b.speaker == "monika" and b.text == "just plain text")

b = d._parse(LLMResult(beat_json(n=9), "stop", "fake"))
check("over-long beat clamped to max", len(b) <= D._MAX_LINES)

bad = json.dumps({"turns": [{"speaker": "monika", "text": "hi"}],
                  "music": "disco", "background": "mars", "effect": "explode",
                  "action": "rm_rf", "crack": "gaping"})
b = d._parse(LLMResult(bad, "stop", "fake"))
check("invalid symbols -> safe defaults",
      b.music == "keep" and b.background == "keep" and b.effect == "none"
      and b.action == "none" and b.crack == "none")

# ── 2. crack budget gates ─────────────────────────────────────────────────
print("[crack gates]")
d = fresh()
d.intensity = 1.0
check("fresh session: hairline DENIED before 12 clean turns", not d._crack_allowed("hairline"))
d.turns_since_crack = 12
check("hairline allowed after 12 clean turns", d._crack_allowed("hairline"))
check("visible over ceiling at band 0-2", not d._crack_allowed("visible"))
check("open over ceiling at band 0-2", not d._crack_allowed("open"))

d.intensity = 4.0
d.turns_since_crack = 5
check("band 3-4: visible allowed after cooldown", d._crack_allowed("visible"))
d.turns_since_crack = 3
check("band 3-4: visible denied inside cooldown", not d._crack_allowed("visible"))

d.intensity = 5.5
d.turns_since_crack = 10
d.open_used_this_band = False
check("band 5-6: first open allowed", d._crack_allowed("open"))
d.open_used_this_band = True
check("band 5-6: second open DENIED", not d._crack_allowed("open"))
d.turns_since_crack = 10
check("band 5-6 after open spent: hairline still fine", d._crack_allowed("hairline"))

d.intensity = 9.5
check("band 9-10: breach allowed", d._crack_allowed("breach"))

# ── 3. enforcement reroll ─────────────────────────────────────────────────
print("[enforcement]")
d = fresh()
d.intensity = 1.0                       # band 0-2, fresh -> nothing allowed
d.client = FakeClient([
    beat_json(crack="open", text="I can see you.", speaker="monika"),   # violates
    beat_json(crack="none", text="Poems out!", speaker="monika"),       # retry ok
])
b = d.respond("hello")
check("reroll fired (2 API calls)", len(d.client.calls) == 2)
check("shipped beat is the retry", b.text == "Poems out!" and b.crack == "none")
note_msg = d.client.calls[1]["messages"][-1]["content"]
check("reroll note rides the volatile tail", "BUDGET ENFORCEMENT" in note_msg)
check("memory stores retry text not the violation", "Poems out!" in d.memory.messages[-1]["content"])

d2 = fresh(session="__test2__")
d2.intensity = 1.0
d2.client = FakeClient([
    beat_json(crack="open", text="I see you.", speaker="monika"),
    beat_json(crack="open", text="Still see you.", speaker="monika"),   # retry ALSO bad
])
b2 = d2.respond("hello")
check("stubborn retry: label downgraded, game continues", b2.crack == "none")
check("no third call", len(d2.client.calls) == 2)

# ── 4. once-per-session actions ───────────────────────────────────────────
print("[actions]")
d = fresh(session="__test3__", config_extra={"enable_harmless_writes": False})
beat = Beat(action="reveal_game")
d.perform_action(beat)
check("action recorded as used", "reveal_game" in d.actions_used)
second = d.perform_action(Beat(action="reveal_game"))
check("second use of same action -> None", second is None)

# ── 5. cache-prefix stability ─────────────────────────────────────────────
print("[cache]")
d = fresh(session="__test4__")
d.client = FakeClient([beat_json(), beat_json(), beat_json()])
s1 = d._system_prompt()
d.respond("turn one")
s2 = d._system_prompt()
check("system prompt byte-identical across turns", s1 == s2)
d.respond("turn two")
msgs = d._messages()
check("rolling breakpoint on second-to-last message",
      len(msgs) >= 2 and msgs[-2].get("cache") is True)
check("live block on tail only, not in memory",
      "LIVE DIRECTOR STATE" in msgs[-1]["content"]
      and all("LIVE DIRECTOR STATE" not in m["content"] for m in d.memory.messages))
d.set_mode("monika")
check("set_mode invalidates static cache", d._system_cache is None)

# client-side conversion
parts = _cached_content("x" * 10, "5m")
check("cache_control part shape",
      parts[0]["cache_control"] == {"type": "ephemeral"} and parts[0]["type"] == "text")
parts = _cached_content("x", "1h")
check("1h ttl carried", parts[0]["cache_control"].get("ttl") == "1h")

cl = LLMClient({"api_key": "k", "model": "anthropic/claude-fable-5"})
check("anthropic model supports cache", cl._supports_cache())
cl2 = LLMClient({"api_key": "k", "model": "deepseek/deepseek-chat-v3-0324:free"})
check("non-anthropic model skips cache", not cl2._supports_cache())

captured = {}
class CaptureClient(LLMClient):
    def _post(self, body, headers):
        captured["body"] = body
        return {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                "model": self.model, "usage": {}}
cc = CaptureClient({"api_key": "k", "model": "anthropic/claude-fable-5"})
cc.complete("S" * 3000, [{"role": "user", "content": "a", "cache": True},
                         {"role": "user", "content": "b"}])
body = captured["body"]
check("system message carries cache_control",
      isinstance(body["messages"][0]["content"], list)
      and "cache_control" in body["messages"][0]["content"][-1])
check("marked user message converted",
      isinstance(body["messages"][1]["content"], list))
check("unmarked message untouched", isinstance(body["messages"][2]["content"], str))
check("our 'cache' flag stripped from wire format",
      all("cache" not in m for m in body["messages"]))
check("usage reporting requested", body.get("usage") == {"include": True})

# ── 6. band transitions ───────────────────────────────────────────────────
print("[bands]")
d = fresh(session="__test5__")
d.intensity = 6.0
d._sync_band()
d.open_used_this_band = True
d.cracks_this_band = 2
d.escalate(1.5)   # -> 7.5, new band
check("band change resets cracks_this_band", d.cracks_this_band == 0)
check("open_used persists 5-6 -> 7-8 (once per session)", d.open_used_this_band)
d.deescalate(4.0)  # -> 3.5, below 5
check("dropping below 5 re-arms the open crack", not d.open_used_this_band)

# persistence round-trip
d.intensity = 5.5
d.open_used_this_band = True
d._persist()
d_re = Director(d.config, session_name="__test5__")
check("open_used survives restart", bool(d_re.memory.meta.get("open_used_this_band")))

cleanup()
print("\n%d passed, %d failed" % (len(PASS), len(FAIL)))
if FAIL:
    print("FAILED:", ", ".join(FAIL))
    raise SystemExit(1)
print("ALL GREEN")
