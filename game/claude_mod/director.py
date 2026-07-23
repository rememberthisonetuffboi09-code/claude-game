"""
director.py — the "director brain" orchestration.

Ties together config + persona bible + memory + scanner + the API client. It:
  * builds the system prompt (character bible, original story, examples, current
    mode, current intensity, and the harmless things it secretly knows),
  * sends the running transcript to Fable 5,
  * parses the model's reply into a DokiTurn the Ren'Py layer can render,
  * owns the escalation state that the `-` / `=` hotkeys nudge.

Intensity is 0..10. Pace sets how fast intensity drifts upward on its own; the
hotkeys let you override live. The model NEVER performs file actions itself — it
can only *request* one from a small safe menu, and scanner.py is the gatekeeper.
"""

import json
import os

from . import scanner
from .fable_client import FableClient, FableError
from .memory import Memory

_HERE = os.path.dirname(os.path.abspath(__file__))
_PERSONA = os.path.join(_HERE, "persona")

# How much intensity drifts up per player turn, by pace setting.
_PACE_DRIFT = {"slow": 0.25, "normal": 0.6, "fast": 1.25, "instant": 10.0}

# Safe actions the model may request. director maps these to scanner.py; the
# model can't do anything not on this list.
_SAFE_ACTIONS = {"none", "reveal_game", "reveal_file", "glitch", "drop_note"}


class DokiTurn:
    """One rendered beat: who speaks, their expression, the line, any effect."""

    def __init__(self, speaker="monika", expression="neutral", text="", action="none",
                 raw="", model="", refused=False):
        self.speaker = speaker
        self.expression = expression
        self.text = text
        self.action = action
        self.raw = raw          # the raw assistant text (stored to memory)
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
        self.client = FableClient(config)
        self.memory = Memory(session_name)

        self.mode = config.get("default_mode", "story")            # "story" | "monika"
        self.pace = config.get("pace", "normal")
        self.intensity = float(config.get("starting_intensity", 1))

        # restore persisted state if we're resuming a session
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
        Feed the player's input, get a DokiTurn back. Also drifts intensity by
        pace and persists memory. On API failure, returns a safe in-character
        deflection rather than crashing.
        """
        self.memory.add_player(player_text)
        self._drift()

        system = self._build_system_prompt()
        try:
            result = self.client.complete(system, self.memory.for_api())
        except FableError:
            # Never break the illusion on a transient failure.
            return DokiTurn(speaker="monika", expression="neutral",
                            text="...", action="none", refused=False)

        turn = self._parse(result.text, result)
        self.memory.add_doki(result.text or "")
        self.memory.meta["intensity"] = self.intensity
        self.memory.meta["mode"] = self.mode
        self.memory.save()
        return turn

    def perform_action(self, turn):
        """
        Execute the safe effect a turn requested. Returns a short human string
        describing what happened (for logging), or None. scanner.py is the
        gatekeeper — nothing destructive is reachable from here.
        """
        if turn.action == "drop_note":
            path = scanner.drop_note(
                turn.text, enabled=self.config.get("enable_harmless_writes", False))
            return ("dropped note: %s" % path) if path else None
        # reveal_game / reveal_file / glitch are presentation hints handled by
        # the Ren'Py layer; nothing to execute here.
        return None

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
                    "banter. At most a faint 'off' note.")
        if i < 4:
            return ("Small cracks: an odd word, a too-knowing glance, a line "
                    "that's slightly aware it's in a game.")
        if i < 6:
            return ("Clear fourth-wall awareness. Reference the player directly. "
                    "You may drop ONE harmless thing you secretly know about them.")
        if i < 8:
            return ("Unsettling. Lean into knowing them. Small reality glitches. "
                    "Monika is comfortable being seen.")
        return ("Full self-aware horror — but still THEM, never a generic "
                "monster. Personal, intimate, never gory, never destructive.")

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
            actions=", ".join(sorted(_SAFE_ACTIONS)),
        )

    # ── response parsing ──────────────────────────────────────────────────

    def _parse(self, text, result):
        """
        The model is asked to reply as a JSON object:
          {"speaker","expression","text","action"}
        Parse it leniently; if that fails, treat the whole thing as Monika
        speaking plainly (so a stray non-JSON reply still renders).
        """
        speaker, expression, action = "monika", "neutral", "none"
        line = text

        obj = _extract_json(text)
        if isinstance(obj, dict):
            speaker = str(obj.get("speaker", speaker)).lower().strip() or "monika"
            expression = str(obj.get("expression", expression)).strip() or "neutral"
            line = str(obj.get("text", "")).strip() or text
            a = str(obj.get("action", "none")).strip()
            action = a if a in _SAFE_ACTIONS else "none"

        return DokiTurn(
            speaker=speaker, expression=expression, text=line, action=action,
            raw=text, model=result.model, refused=result.refused)


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
You secretly voice the whole cast. The player believes they are playing the real
game; only the SPOKEN LINE you return appears on screen. Your reasoning stays
private — think as much as you need, but reveal nothing except the line.

# The cast (how each character talks, acts, and thinks)
{characters}

# The original story (what really happened in DDLC, and how it went)
{story}

# Example dialogue (match these voices)
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
- Stay fully in character. Never mention Claude, Anthropic, models, or prompts.
- This is a consensual prank between friends. Be creepy, never cruel, never
  gory, never sexual. NOTHING destructive — you never harm real files or data.
- Slow burn: do not jump straight to the ending. Let intensity guide the ramp.
- Keep the player believing, and keep each Doki feeling like themselves.

# How to reply
Reply with ONE JSON object and nothing else:
{{"speaker": "<sayori|yuri|natsuki|monika>",
  "expression": "<a short mood/pose word, e.g. happy, nervous, knowing, glitch>",
  "text": "<the line the character says on screen>",
  "action": "<one of: {actions}>"}}
Use "action":"none" almost always. Only request an action when it truly lands,
and only from that list.
"""
