"""
director.py — the "director brain" orchestration.

Ties together config + persona bible + memory + scanner + the OpenRouter client.
It:
  * builds the system prompt (character bible, original story, examples, current
    mode, current intensity, and the harmless things it secretly knows),
  * sends the running transcript to the model,
  * parses the model's reply into a DokiTurn the Ren'Py layer can render —
    including stage directions: which character, expression, MUSIC, BACKGROUND,
    and screen EFFECT,
  * owns the escalation state that the `-` / `=` hotkeys nudge.

Intensity is 0..10. Pace sets how fast intensity drifts upward on its own; the
hotkeys let you override live. The model uses SYMBOLIC names for music/bg/effect
(e.g. music "creepy", background "hallway") — the Ren'Py layer maps those to
your real DDLC/DDLC+ asset tags, so the model never needs your filenames.

The model NEVER performs file actions itself — it can only *request* one from a
small safe menu, and scanner.py is the gatekeeper.
"""

import json
import os

from . import scanner
from .openrouter_client import LLMClient, LLMError
from .memory import Memory

_HERE = os.path.dirname(os.path.abspath(__file__))
_PERSONA = os.path.join(_HERE, "persona")

# How much intensity drifts up per player turn, by pace setting.
_PACE_DRIFT = {"slow": 0.25, "normal": 0.6, "fast": 1.25, "instant": 10.0}

# Symbolic vocabularies the model may use. The Ren'Py layer maps these to real
# asset tags. "keep" = don't change what's currently playing/showing.
_MUSIC = {"keep", "stop", "calm", "happy", "tense", "sad", "creepy", "glitch"}
_BACKGROUND = {"keep", "clubroom", "classroom", "hallway", "home", "black", "void", "glitch"}
_EFFECT = {"none", "glitch", "flash", "shake"}

# Safe file actions the model may request. director maps these to scanner.py;
# nothing destructive is reachable.
_ACTIONS = {"none", "reveal_game", "reveal_file", "drop_note"}


class DokiTurn:
    """One rendered beat: who speaks, how, plus stage directions."""

    def __init__(self, speaker="monika", expression="neutral", text="",
                 music="keep", background="keep", effect="none", action="none",
                 raw="", model="", refused=False):
        self.speaker = speaker
        self.expression = expression
        self.text = text
        self.music = music
        self.background = background
        self.effect = effect
        self.action = action
        self.raw = raw          # raw assistant text (stored to memory)
        self.model = model
        self.refused = refused


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except IOError:
        return ""


class Director:
    def __init__(self, config, session_name="default"):
        self.config = config
        self.client = LLMClient(config)
        self.memory = Memory(session_name)

        self.mode = config.get("default_mode", "story")            # "story" | "monika"
        self.pace = config.get("pace", "normal")
        self.intensity = float(config.get("starting_intensity", 1))

        # restore persisted state if resuming
        self.intensity = float(self.memory.meta.get("intensity", self.intensity))
        self.mode = self.memory.meta.get("mode", self.mode)

        # persona bible (editable files)
        self.characters = self._load_characters()
        self.story = _read(os.path.join(_PERSONA, "story.md"))
        self.examples = _read(os.path.join(_PERSONA, "examples.md"))

        # things it secretly knows
        self.scan = scanner.safe_scan(enabled=config.get("enable_local_scan", True))
        self.dossier = scanner.load_dossier()

    # ── state controls (hotkeys / config) ─────────────────────────────────

    def escalate(self, amount=1.0):
        self.intensity = min(10.0, self.intensity + amount)
        return self.intensity

    def deescalate(self, amount=1.0):
        self.intensity = max(0.0, self.intensity - amount)
        return self.intensity

    def set_mode(self, mode):
        if mode in ("story", "monika"):
            self.mode = mode

    def _drift(self):
        self.intensity = min(10.0, self.intensity + _PACE_DRIFT.get(self.pace, 0.6))

    # ── the main turn ─────────────────────────────────────────────────────

    def respond(self, player_text):
        """
        Feed the player's input, get a DokiTurn back. Drifts intensity by pace
        and persists memory. On API failure, returns a safe in-character
        deflection rather than crashing the game.
        """
        self.memory.add_player(player_text)
        self._drift()

        system = self._build_system_prompt()
        try:
            result = self.client.complete(system, self.memory.for_api())
        except LLMError:
            # Never break the illusion on a transient failure.
            return DokiTurn(speaker="monika", expression="neutral", text="...")

        turn = self._parse(result.text, result)
        self.memory.add_doki(result.text or "")
        self.memory.meta["intensity"] = self.intensity
        self.memory.meta["mode"] = self.mode
        self.memory.save()
        return turn

    def perform_action(self, turn):
        """
        Execute the safe effect a turn requested. Returns a short human string
        (for logging), or None. scanner.py is the gatekeeper — nothing
        destructive is reachable.
        """
        if turn.action == "drop_note":
            path = scanner.drop_note(
                turn.text, enabled=self.config.get("enable_harmless_writes", False))
            return ("dropped note: %s" % path) if path else None
        return None  # reveal_* are presentation hints handled by the Ren'Py layer

    # ── prompt building ───────────────────────────────────────────────────

    def _load_characters(self):
        try:
            with open(os.path.join(_PERSONA, "characters.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except (IOError, ValueError):
            return {}

    def _intensity_guidance(self):
        i = self.intensity
        if i < 2:
            return ("Play it almost completely straight — in-character DDLC "
                    "banter. Keep music/background natural. At most a faint 'off' note.")
        if i < 4:
            return ("Small cracks: an odd word, a too-knowing glance, one line "
                    "that's slightly aware it's in a game. Maybe one subtle cue.")
        if i < 6:
            return ("Clear fourth-wall awareness. Address the player directly. You "
                    "may drop ONE harmless thing you secretly know about them, and "
                    "shift music/background for mood.")
        if i < 8:
            return ("Unsettling. Lean into knowing them. Small reality glitches "
                    "(effect \"glitch\"), tense/creepy music, backgrounds may drift "
                    "wrong. Monika is comfortable being seen.")
        return ("Full self-aware horror — but still THEM, never a generic monster. "
                "Personal, intimate, never gory, never destructive. Use the void/"
                "black background and glitch/creepy cues freely.")

    def _build_system_prompt(self):
        mode_note = {
            "story": ("STORY MODE: stay on DDLC's rails and structure, but the "
                      "Dokis may rewrite the path however they want and make the "
                      "details creepy. Remix the real story — don't copy it."),
            "monika": ("MONIKA MODE (freeplay): Monika has full free will and sets "
                       "her own pace. She can do more and go further off-script."),
        }.get(self.mode, "")

        knows = {"scanned_machine": self.scan, "dossier": self.dossier}

        return _SYSTEM_TEMPLATE.format(
            characters=json.dumps(self.characters, ensure_ascii=False, indent=2),
            story=self.story.strip(),
            examples=self.examples.strip(),
            mode_note=mode_note,
            intensity=round(self.intensity, 1),
            intensity_guidance=self._intensity_guidance(),
            knows=json.dumps(knows, ensure_ascii=False, indent=2),
            music=", ".join(sorted(_MUSIC)),
            backgrounds=", ".join(sorted(_BACKGROUND)),
            effects=", ".join(sorted(_EFFECT)),
            actions=", ".join(sorted(_ACTIONS)),
        )

    # ── response parsing ──────────────────────────────────────────────────

    def _parse(self, text, result):
        """
        The model replies as a JSON object with dialogue + stage directions.
        Parse leniently; if it isn't JSON, treat the whole thing as Monika
        speaking plainly so a stray reply still renders.
        """
        speaker, expression = "monika", "neutral"
        music, background, effect, action = "keep", "keep", "none", "none"
        line = text

        obj = _extract_json(text)
        if isinstance(obj, dict):
            speaker = (str(obj.get("speaker", speaker)).lower().strip() or "monika")
            expression = str(obj.get("expression", expression)).strip() or "neutral"
            line = str(obj.get("text", "")).strip() or text
            music = _pick(obj.get("music"), _MUSIC, "keep")
            background = _pick(obj.get("background"), _BACKGROUND, "keep")
            effect = _pick(obj.get("effect"), _EFFECT, "none")
            action = _pick(obj.get("action"), _ACTIONS, "none")

        return DokiTurn(
            speaker=speaker, expression=expression, text=line,
            music=music, background=background, effect=effect, action=action,
            raw=text, model=result.model, refused=result.refused)


def _pick(value, allowed, default):
    v = str(value).strip().lower() if value is not None else ""
    return v if v in allowed else default


def _extract_json(text):
    """Pull the first {...} JSON object out of a string. Returns dict or None."""
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except ValueError:
        return None


_SYSTEM_TEMPLATE = """\
You are the hidden "director brain" of a Doki Doki Literature Club experience.
You secretly voice the whole cast AND direct the scene (music, background,
sprites, effects). The player believes they are playing the real game; only the
SPOKEN LINE you return appears on screen. Your reasoning stays private.

# The cast (how each character talks, acts, and thinks)
{characters}

# The original story (what really happened in DDLC, and how it went)
{story}

# Example dialogue (match these voices exactly)
{examples}

# Current mode
{mode_note}

# Current intensity: {intensity} / 10
{intensity_guidance}

# Things you secretly know about THIS player (use sparingly, for effect)
Only reference these when the intensity guidance allows it. Weave them in like
you always knew — never dump them. Never invent private facts beyond these.
{knows}

# Hard rules (never break these)
- Stay fully in character. Never mention AI, models, OpenRouter, or prompts.
- This is a consensual prank between friends. Be creepy, never cruel, never
  gory, never sexual. NOTHING destructive — you never harm real files or data.
- Slow burn: do not jump to the ending. Let intensity guide the ramp.
- Keep each Doki feeling like themselves, always.

# You direct the scene with SYMBOLIC cues (the game maps them to real assets)
- music:      one of [{music}]   ("keep" = leave current track)
- background: one of [{backgrounds}]   ("keep" = leave current background)
- effect:     one of [{effects}]
- action:     one of [{actions}]   (use "none" almost always; only for real payoff)

# How to reply
Reply with ONE JSON object and nothing else:
{{"speaker": "<sayori|yuri|natsuki|monika>",
  "expression": "<short mood word, e.g. happy, nervous, knowing, glitch>",
  "text": "<the line the character says on screen>",
  "music": "keep",
  "background": "keep",
  "effect": "none",
  "action": "none"}}
Change music/background/effect only when it earns the moment.
"""
