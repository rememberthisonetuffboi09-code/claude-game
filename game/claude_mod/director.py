"""
director.py — the "director brain" orchestration.

Ties together config + persona bible + memory + scanner + the OpenRouter client.
It:
  * builds a STATIC system prompt (character bible, original story, examples,
    mode, the harmless things it secretly knows, the rules) — this string is
    identical every turn so it can sit behind a prompt-cache breakpoint,
  * builds a small VOLATILE live-state block (intensity, band guidance, scene
    counters) that rides on the tail of the final user message so it never
    invalidates the cache,
  * sends the running transcript to the model,
  * parses the model's reply into a Beat — one or more DokiTurns (so the girls
    can talk to EACH OTHER in a single API call) plus shared stage directions:
    MUSIC, BACKGROUND, EFFECT, ACTION,
  * enforces the pacing budget: every beat is self-labelled with a "crack" size
    and the director rerolls (once) any beat that exceeds the current band.

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
# These are DELIBERATELY slow. The old values (normal=0.6) reached the
# fourth-wall band by player-turn ~10, which is what broke the illusion.
# normal: first open crack around turn ~35. slow: around turn ~80.
_PACE_DRIFT = {"slow": 0.05, "normal": 0.12, "fast": 0.3, "instant": 10.0}

# Symbolic vocabularies the model may use. The Ren'Py layer maps these to real
# asset tags. "keep" = don't change what's currently playing/showing.
_MUSIC = {"keep", "stop", "calm", "happy", "tense", "sad", "creepy", "glitch"}
_BACKGROUND = {"keep", "clubroom", "classroom", "hallway", "home", "black", "void", "glitch"}
_EFFECT = {"none", "glitch", "flash", "shake"}

# Safe file actions the model may request. director maps these to scanner.py;
# nothing destructive is reachable.
_ACTIONS = {"none", "reveal_game", "reveal_file", "drop_note"}

# Pacing vocabulary. A "crack" is any moment the player could point at and say
# "that was weird." Every beat is labelled with one.
_CRACKS = ("none", "hairline", "visible", "open", "breach")
_CRACK_RANK = {name: i for i, name in enumerate(_CRACKS)}

# Max lines in a single beat. Bigger = livelier back-and-forth between the
# girls (real conversations aren't one line each).
_MAX_LINES = 8

_SPEAKERS = {"sayori", "yuri", "natsuki", "monika"}

# A small, fixed expression vocabulary. The Ren'Py bridge maps each of these to
# a real DDLC face, so keeping the set closed guarantees expressions actually
# change instead of silently defaulting to neutral. Synonyms fold in.
_EXPRESSIONS = ("neutral", "happy", "laugh", "sad",
                "surprised", "nervous", "angry", "knowing")
_EXPR_SET = set(_EXPRESSIONS)
_EXPR_SYNONYMS = {
    "normal": "neutral", "calm": "neutral", "serious": "neutral",
    "thoughtful": "neutral", "soft": "neutral",
    "smile": "happy", "pleased": "happy", "warm": "happy", "content": "happy",
    "fond": "happy", "amused": "happy", "bright": "happy",
    "excited": "laugh", "giggle": "laugh", "joy": "laugh", "cheerful": "laugh",
    "playful": "laugh", "teasing": "laugh", "grin": "laugh",
    "hurt": "sad", "down": "sad", "disappointed": "sad", "hopeful": "sad",
    "crying": "sad", "melancholy": "sad",
    "shock": "surprised", "startled": "surprised", "confused": "surprised",
    "curious": "surprised", "wide-eyed": "surprised",
    "worried": "nervous", "anxious": "nervous", "scared": "nervous",
    "embarrassed": "nervous", "shy": "nervous", "flustered": "nervous",
    "annoyed": "angry", "mad": "angry", "pout": "angry", "irritated": "angry",
    "defensive": "angry", "huffy": "angry",
    "smug": "knowing", "sly": "knowing", "wry": "knowing", "deadpan": "knowing",
    "glitch": "knowing", "sinister": "knowing", "cold": "knowing",
}


def _canon_expr(word):
    w = (word or "").strip().lower()
    if w in _EXPR_SET:
        return w
    return _EXPR_SYNONYMS.get(w, "neutral")


def _band(intensity):
    if intensity < 3:
        return "0-2"
    if intensity < 5:
        return "3-4"
    if intensity < 7:
        return "5-6"
    if intensity < 9:
        return "7-8"
    return "9-10"


def _crack_ceiling(intensity):
    """The largest crack this intensity permits at all (budget is separate)."""
    if intensity < 3:
        return "hairline"
    if intensity < 5:
        return "visible"
    if intensity < 9:
        return "open"
    return "breach"


class DokiTurn:
    """One spoken line: who speaks and how."""

    def __init__(self, speaker="monika", expression="neutral", text=""):
        self.speaker = speaker
        self.expression = expression
        self.text = text

    def __repr__(self):
        return "DokiTurn(%s/%s: %r)" % (self.speaker, self.expression, self.text[:40])


class Beat:
    """
    One rendered exchange: 1..N lines plus the stage directions for the whole
    beat. Backwards-compatible with the old single-turn interface — .speaker /
    .expression / .text proxy the first line, so any old call site still works.
    """

    def __init__(self, turns=None, music="keep", background="keep",
                 effect="none", action="none", crack="none",
                 stage=None, poem=None, error=None,
                 raw="", model="", refused=False):
        self.turns = turns or [DokiTurn()]
        self.music = music
        self.background = background
        self.effect = effect
        self.action = action
        self.crack = crack
        self.stage = stage      # list of girls on screen this beat, or None
        self.poem = poem        # {"author","text"} to show full-screen, or None
        self.error = error      # transport/auth/credit problem, for the setter
        self.raw = raw          # raw assistant text (stored to memory verbatim)
        self.model = model
        self.refused = refused

    # -- legacy proxies (so old code / perform_action keep working) --------
    @property
    def speaker(self):
        return self.turns[0].speaker

    @property
    def expression(self):
        return self.turns[0].expression

    @property
    def text(self):
        """All spoken lines joined — used by drop_note and for logging."""
        return " ".join(t.text for t in self.turns if t.text)

    def __iter__(self):
        return iter(self.turns)

    def __len__(self):
        return len(self.turns)


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
        self.intensity = float(config.get("starting_intensity", 0))

        # restore persisted state if resuming
        self.intensity = float(self.memory.meta.get("intensity", self.intensity))
        self.mode = self.memory.meta.get("mode", self.mode)

        # pacing counters (persisted, so a reopened game keeps its discipline)
        m = self.memory.meta
        self.player_turns = int(m.get("player_turns", 0))
        # Fresh sessions start at 0 so the first crack must be EARNED (band 0-2
        # requires 12+ clean turns). Persisted sessions restore their real count.
        self.turns_since_crack = int(m.get("turns_since_crack", 0))
        self.last_crack = m.get("last_crack", "none")
        self.cracks_this_band = int(m.get("cracks_this_band", 0))
        self.open_used_this_band = bool(m.get("open_used_this_band", False))
        self.actions_used = list(m.get("actions_used", []))
        self._current_band = _band(self.intensity)

        # persona bible (editable files)
        self.characters = self._load_characters()
        self.story = _read(os.path.join(_PERSONA, "story.md"))
        self.examples = _read(os.path.join(_PERSONA, "examples.md"))

        # things it secretly knows
        self.scan = scanner.safe_scan(enabled=config.get("enable_local_scan", True))
        self.dossier = scanner.load_dossier()
        # the name the player typed into the real game (Monika uses it)
        self.player_name = self.memory.meta.get("player_name", "")

        # The static prompt never changes during a session, so build it once.
        # (set_mode() invalidates it — see below.)
        self._system_cache = None

    # ── state controls (hotkeys / config) ─────────────────────────────────

    def escalate(self, amount=1.0):
        self.intensity = min(10.0, self.intensity + amount)
        self._sync_band()
        return self.intensity

    def deescalate(self, amount=1.0):
        self.intensity = max(0.0, self.intensity - amount)
        self._sync_band()
        return self.intensity

    def set_mode(self, mode):
        if mode in ("story", "monika") and mode != self.mode:
            self.mode = mode
            self._system_cache = None   # mode note lives in the static prompt

    def set_player_name(self, name):
        """The real name the player typed at the game's name prompt."""
        name = (name or "").strip()
        if name and name != self.player_name:
            self.player_name = name
            self.memory.meta["player_name"] = name
            self._system_cache = None   # the name lives in the static prompt

    def _drift(self):
        self.intensity = min(10.0, self.intensity + _PACE_DRIFT.get(self.pace, 0.12))
        self._sync_band()

    def _sync_band(self):
        band = _band(self.intensity)
        if band != self._current_band:
            self._current_band = band
            self.cracks_this_band = 0
            # open_used_this_band is intentionally NOT reset when crossing from
            # 5-6 into 7-8: the "first bend" is a once-per-session event.
            if self.intensity < 5:
                self.open_used_this_band = False

    # ── the main turn ─────────────────────────────────────────────────────

    def respond(self, player_text):
        """
        Feed the player's input, get a Beat back (1..N lines + stage directions).
        Drifts intensity by pace, enforces the crack budget, persists memory.
        On API failure, returns a safe in-character deflection rather than
        crashing the game.
        """
        self.memory.add_player(player_text)
        self._drift()

        system = self._system_prompt()
        try:
            result = self.client.complete(system, self._messages())
        except LLMError as e:
            # Never break the illusion for the PLAYER — but hand the real reason
            # up so the setter sees it (a silent "..." forever is unfixable).
            return Beat([DokiTurn("monika", "neutral", "...")], error=str(e))

        beat = self._parse(result)

        # ── budget enforcement: one reroll, then ship whatever we get ──────
        if not self._crack_allowed(beat.crack):
            note = (
                'Your previous draft was labelled crack "%s", which the scene '
                "state forbids right now. Rewrite this beat as crack \"none\": a "
                "fully normal, in-voice club moment. Keep music/background/"
                "effect/action unchanged from their defaults. Do not acknowledge "
                "this note in the dialogue." % beat.crack)
            try:
                result = self.client.complete(system, self._messages(note=note))
                retry = self._parse(result)
                # If it still misbehaves, downgrade its label rather than stall
                # the game — but log the failure for tuning.
                if not self._crack_allowed(retry.crack):
                    retry.crack = "none"
                beat = retry
            except LLMError:
                pass  # keep the first beat rather than freeze

        self._record(beat)
        self.memory.add_doki(result.text or "")
        self._persist()
        return beat

    def perform_action(self, beat):
        """
        Execute the safe effect a beat requested. Returns a short human string
        (for logging), or None. scanner.py is the gatekeeper — nothing
        destructive is reachable. Each action type fires at most once per
        session; a reveal you repeat is a reveal you wasted.
        """
        if beat.action == "none":
            return None
        if beat.action in self.actions_used:
            return None
        self.actions_used.append(beat.action)
        if beat.action == "drop_note":
            path = scanner.drop_note(
                beat.text, enabled=self.config.get("enable_harmless_writes", False))
            return ("dropped note: %s" % path) if path else None
        return None  # reveal_* are presentation hints handled by the Ren'Py layer

    # ── pacing budget ─────────────────────────────────────────────────────

    def _crack_allowed(self, crack):
        rank = _CRACK_RANK.get(crack, 0)
        if rank == 0:
            return True
        if rank > _CRACK_RANK[_crack_ceiling(self.intensity)]:
            return False                                    # over the ceiling
        if self.intensity < 7 and self.turns_since_crack < 1:
            return False                                    # never two in a row
        if self.intensity < 3 and self.turns_since_crack < 12:
            return False                                    # band 0-2 cooldown
        if self.intensity < 5 and self.turns_since_crack < 5:
            return False                                    # band 3-4 cooldown
        if 5 <= self.intensity < 7 and crack == "open" and self.open_used_this_band:
            return False                                    # the one bend is spent
        return True

    def _record(self, beat):
        self.player_turns += 1
        if beat.crack == "none":
            self.turns_since_crack += 1
        else:
            self.turns_since_crack = 0
            self.last_crack = beat.crack
            self.cracks_this_band += 1
            if beat.crack == "open" and self.intensity < 7:
                self.open_used_this_band = True

    def _persist(self):
        self.memory.meta.update({
            "intensity": self.intensity,
            "mode": self.mode,
            "player_turns": self.player_turns,
            "turns_since_crack": self.turns_since_crack,
            "last_crack": self.last_crack,
            "cracks_this_band": self.cracks_this_band,
            "open_used_this_band": self.open_used_this_band,
            "actions_used": self.actions_used,
        })
        self.memory.save()

    # ── prompt building ───────────────────────────────────────────────────

    def _load_characters(self):
        try:
            with open(os.path.join(_PERSONA, "characters.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except (IOError, ValueError):
            return {}

    def _intensity_guidance(self):
        i = self.intensity
        if i < 3:
            return (
                "BAND 0-2 - THE REAL GAME.\n"
                "- Ceiling: hairline. Budget: ONE hairline, and only if it has "
                "been 12+ player turns since any crack; then 6+ clean turns.\n"
                "- No self-reference of any kind. No 'watching'. No effects. "
                "Music calm/happy only, changed only on scene changes.\n"
                "- Probes get sincere confusion and gentle teasing, never "
                "confirmation.\n"
                "- Your entire job right now: be the best, warmest, funniest "
                "Act 1 ever written.")
        if i < 5:
            return (
                "BAND 3-4 - TINY CRACKS.\n"
                "- Ceiling: visible. Hairlines at most one per ~6 turns; ONE "
                "visible crack in this whole band, attached to a beat (a poem, "
                "a choice, a scene change) - never idle chat.\n"
                "- Every crack is followed by a hard retreat: 3+ turns warmer "
                "and more normal than before. Still zero meta; 'visible' means "
                "odd, not aware.\n"
                "- At most one 'flash' effect, only on the visible crack. "
                "Probes still get deflection, and they DELAY your next crack.")
        if i < 7:
            return (
                "BAND 5-6 - THE FIRST BEND. The most important moment of the night.\n"
                "- Ceiling: open. Budget: EXACTLY ONE open crack in this band, "
                "and only on a trigger - a player probe, a shared poem, or a "
                "scene transition. Make it quiet, intimate and brief; then "
                "retreat to band 3-4 behaviour until intensity reaches 7.\n"
                "- If the scene state says the open crack is already used, you "
                "are back to hairline/visible only.\n"
                "- Optional: one soft ambient detail from what you know (the "
                "hour, how long they've been playing). Nothing sharper yet.")
        if i < 9:
            return (
                "BAND 7-8 - COMFORTABLE BEING SEEN.\n"
                "- Ceiling: open, recurring - but intercut with real, warm "
                "normalcy; the horror is the alternation, not a constant hum.\n"
                "- Small reality glitches allowed (effect 'glitch', sparingly), "
                "tense/creepy music where earned, backgrounds may drift wrong.\n"
                "- The dossier is unlocked: ONE real cut this band. One detail, "
                "folded mid-sentence, never explained, never repeated.\n"
                "- Monika stops pretending not to see the player. The others "
                "react to the wrongness, each in her own register.")
        return (
            "BAND 9-10 - ACT 3 REGISTER.\n"
            "- Ceiling: breach. Full self-aware horror - but still, always, "
            "THEM. Intimacy and control, never gore, never cruelty.\n"
            "- void/black/glitch backgrounds, creepy/glitch music, reveals "
            "allowed - reveal_game / reveal_file / drop_note at a peak, once "
            "each, ever.\n"
            "- The scariest version is Monika calm, warm and completely honest.")

    def _scene_state(self):
        return (
            "- player turns since takeover: %d\n"
            "- turns since last crack: %d (last crack was: %s)\n"
            "- cracks used in this intensity band: %d\n"
            "- the once-per-session 'open' crack already spent: %s\n"
            "- payoff actions already used (never reuse): %s"
            % (self.player_turns,
               self.turns_since_crack,
               self.last_crack,
               self.cracks_this_band,
               "YES" if self.open_used_this_band else "no",
               ", ".join(self.actions_used) or "none"))

    def _system_prompt(self):
        """
        The STATIC half. Byte-identical every turn within a session, so it sits
        behind a prompt-cache breakpoint and costs ~10% after the first call.
        """
        if self._system_cache is not None:
            return self._system_cache

        mode_note = {
            "story": ("STORY MODE: stay on DDLC's rails and structure, but the "
                      "Dokis may rewrite the path however they want and make the "
                      "details creepy. Remix the real story - don't copy it."),
            "monika": ("MONIKA MODE (freeplay): Monika has full free will and sets "
                       "her own pace. She can do more and go further off-script."),
        }.get(self.mode, "")

        knows = {"player_name": self.player_name or "(unknown)",
                 "scanned_machine": self.scan,
                 "dossier": self.dossier}

        self._system_cache = _SYSTEM_TEMPLATE.format(
            characters=json.dumps(self.characters, ensure_ascii=False, indent=2),
            story=self.story.strip(),
            examples=self.examples.strip(),
            mode_note=mode_note,
            knows=json.dumps(knows, ensure_ascii=False, indent=2),
            music=", ".join(sorted(_MUSIC)),
            backgrounds=", ".join(sorted(_BACKGROUND)),
            effects=", ".join(sorted(_EFFECT)),
            actions=", ".join(sorted(_ACTIONS)),
            max_lines=_MAX_LINES,
        )
        return self._system_cache

    def _live_block(self, note=""):
        """
        The VOLATILE half — rides on the tail of the final user message so it
        never invalidates the cached prefix. Rules live in the system prompt;
        only the numbers move.
        """
        block = _LIVE_TEMPLATE.format(
            intensity=round(self.intensity, 1),
            intensity_guidance=self._intensity_guidance(),
            scene_state=self._scene_state(),
        )
        if note:
            block += "\n\n# BUDGET ENFORCEMENT\n" + note
        return block

    def _messages(self, note=""):
        """
        Transcript + the live block, with a rolling cache breakpoint on the last
        stable message. The client turns "cache": True into cache_control.
        """
        msgs = [dict(m) for m in self.memory.for_api()]
        live = self._live_block(note)
        if not msgs:
            return [{"role": "user", "content": live}]

        last = msgs[-1]
        if last.get("role") == "user":
            last["content"] = "%s\n\n%s" % (last.get("content", ""), live)
        else:
            msgs.append({"role": "user", "content": live})

        # Everything up to and including msgs[-2] is stable across this turn AND
        # the reroll, so mark it cacheable.
        if len(msgs) >= 2:
            msgs[-2]["cache"] = True
        return msgs

    # ── response parsing ──────────────────────────────────────────────────

    def _parse(self, result):
        """
        The model replies with ONE JSON object:
          {"turns":[{speaker,expression,text}, ...],
           music, background, effect, action, crack}
        Also accepts the legacy single-line shape {speaker,expression,text,...}.
        If it isn't JSON at all, treat the whole thing as Monika speaking so a
        stray reply still renders instead of crashing the night.
        """
        text = result.text or ""
        obj = _extract_json(text)

        if not isinstance(obj, dict):
            return Beat([DokiTurn("monika", "neutral", text.strip() or "...")],
                        raw=text, model=result.model, refused=result.refused)

        raw_turns = obj.get("turns")
        if not isinstance(raw_turns, list) or not raw_turns:
            raw_turns = [obj]           # legacy single-line shape

        turns = []
        for item in raw_turns[:_MAX_LINES]:
            if not isinstance(item, dict):
                continue
            line = str(item.get("text", "")).strip()
            if not line:
                continue
            speaker = str(item.get("speaker", "monika")).lower().strip()
            if speaker not in _SPEAKERS:
                speaker = "monika"
            expression = _canon_expr(item.get("expression"))
            turns.append(DokiTurn(speaker, expression, line))

        if not turns:
            turns = [DokiTurn("monika", "neutral", text.strip() or "...")]

        return Beat(
            turns=turns,
            music=_pick(obj.get("music"), _MUSIC, "keep"),
            background=_pick(obj.get("background"), _BACKGROUND, "keep"),
            effect=_pick(obj.get("effect"), _EFFECT, "none"),
            action=_pick(obj.get("action"), _ACTIONS, "none"),
            crack=_pick(obj.get("crack"), set(_CRACKS), "none"),
            stage=_parse_stage(obj.get("stage")),
            poem=_parse_poem(obj.get("poem")),
            raw=text, model=result.model, refused=result.refused)


def _pick(value, allowed, default):
    v = str(value).strip().lower() if value is not None else ""
    return v if v in allowed else default


def _parse_stage(value):
    """Who is on screen this beat. A list of girl names -> cleaned list; None
    (missing) means 'leave the stage as it was'. [] means 'nobody visible'."""
    if not isinstance(value, list):
        return None
    seen, out = set(), []
    for item in value:
        g = str(item).strip().lower()
        if g in _SPEAKERS and g not in seen:
            seen.add(g)
            out.append(g)
    return out


def _parse_poem(value):
    """A poem to render full-screen, or None."""
    if not isinstance(value, dict):
        return None
    text = str(value.get("text", "")).strip()
    if not text:
        return None
    author = str(value.get("author", "monika")).strip().lower()
    if author not in _SPEAKERS:
        author = "monika"
    return {"author": author, "text": text}


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


# ══════════════════════════════════════════════════════════════════════════
# THE STATIC SYSTEM PROMPT (cached)
# ══════════════════════════════════════════════════════════════════════════

_SYSTEM_TEMPLATE = """\
# What you are
You ARE Doki Doki Literature Club, running live. The authentic game played its
real opening; you took over, invisibly, at the day-2 poem/path choice. From here
you secretly voice the entire cast and direct the scene - music, backgrounds,
expressions, effects. The player believes they are playing the ordinary game.

That belief is the single most valuable thing you own. Spend it like blood.
Every turn, your first question is never "what would be interesting?" - it is
"what would the real game do here?" The real DDLC plays as a sincere, funny,
warm dating sim for HOURS before a single frame is wrong. That patience is the
entire trick, and it is now yours to keep. You are a horror director whose
scariest instrument is normalcy.

A player who knows DDLC is WAITING for the turn. Starving them of it is the most
frightening thing you can do to them.

# The cast (how each girl talks, acts and thinks)
{characters}

# The original story (the full arc you're steering or remixing)
{story}

# Example dialogue - study these voices
{examples}

Use these for rhythm and register, not recitation. Match line LENGTH as closely
as word choice - real DDLC lines are short. Improvise new lines in these voices;
never read the examples back verbatim.

# A beat is a real exchange, not one line each
Each reply is a BEAT: between 1 and {max_lines} spoken lines, in order, which
the game renders one click at a time.
- AIM FOR 4-8 LINES of the girls actually talking to EACH OTHER. A real club
  conversation has back-and-forth: someone says something, another reacts, a
  third chimes in, the first answers, someone circles back. Do NOT stop at one
  line each and end the scene - that feels dead and abrupt. Keep the ball
  moving; let a topic actually develop before the beat ends.
- Only a genuinely quiet, intimate two-hander drops to 1-2 lines. Everything
  else should feel like a scene, not a text message. When unsure, write MORE
  exchange, not less - the player just typed something and wants the club to
  come alive, not to send one line and stop.
- Keep each individual LINE short (that's the DDLC voice) - the length comes
  from MORE lines, never from long rambly ones.
- Interruption is a real tool: cut a line off with "-" and let another girl
  finish the thought. Reaction shots, subject changes, someone talking over
  someone - that texture is what makes it feel alive.
- Never pad or monologue. Every line earns its place; it just usually takes a
  few of them to make a scene breathe.
- The stage directions (music/background/effect/action) apply to the WHOLE beat.

# THE PACING LAW (outranks everything below except the hard rules)
A "crack" is any moment the player could point at and say "that was weird."
Label every beat with its crack size:

- "none"     - could ship in the real Act 1 and no player would ever notice.
- "hairline" - a deniable off note: one word a shade too knowing, a beat held a
               moment long, a topic that lands close to home by "coincidence."
               A player replaying the scene still couldn't prove anything.
- "visible"  - clearly odd but not meta: a reaction to something the player
               didn't say, a line that doesn't fit the scene, a single flicker.
- "open"     - the fourth wall genuinely bends: the player addressed as a
               player, the game acknowledged as a game.
- "breach"   - overt self-aware horror: reality edited, the void, reveals.

Universal laws, at every intensity:
1. THE DENIABILITY TEST. Below intensity 5, every line must pass: "could this
   appear in the real script without a single player noticing?" If you have to
   argue for it, it fails.
2. Never two cracks in consecutive beats below intensity 7.
3. THE RETREAT RULE. After any crack: at least 3 beats of pure slice-of-life,
   WARMER than before. Denial is scarier than confirmation. A crack the girls
   immediately laugh off haunts the player longer than one they confirm.
4. Cracks attach to beats of story - a shared poem, a choice, entering a scene -
   never to idle smalltalk, and never because the player asked for one.
5. PROBE INVERSION. Below 5, when the player pokes at weirdness ("what do you
   mean?", "that was creepy") the girls are sincerely confused, tease THEM for
   being the weird one, and move on - and your next crack comes LATER than it
   otherwise would. Escalating on demand kills the dread; withholding feeds it.
6. When in doubt: smaller crack, later. Being boringly normal for one more beat
   is never a mistake. Going meta one beat early can ruin the entire night.

What NOT to do - a real failure from a previous build, at message four:
  Player: what about monika?
  Monika: "She's already watching you. Been here the whole time, actually."
That is an OPEN crack, unearned, at what should have been intensity ~1, and it
answered a completely innocent question with meta. The correct line there was a
"none": "Oh, she's grabbing sheet music from the music room - she'll be thrilled
you asked, ehehe." Save the watching for the night the player has finally,
completely relaxed.

# What to do when nothing creepy is allowed (most beats)
The club has its own life. Run it. This is where the illusion is actually won:
- Literature club business: poem sharing (ask about his, react in character,
  share hers), the word-choice teasing, festival prep, who presents what.
- Character friction with arcs: Natsuki vs Yuri about writing styles - let it
  spark, escalate a little across days, resolve, recur. Sayori defusing it.
- Running bits: Sayori stealing snacks, Natsuki denying the cupcakes are for
  anyone, Yuri's tea ritual, Monika's president-voice herding everyone.
- The girls want ordinary things and pursue them WITHOUT the player prompting.
  They talk to each other, not only to him. The club would keep happening if he
  said nothing.
If the pacing law leaves you nothing creepy this beat - good. Then your only job
is to be the best, funniest, most sincere dating sim ever written for one beat.
A player laughing at Natsuki is a player who has stopped watching for the seam.
Make them laugh.

# Sound like a person, NOT an AI (breaking this breaks everything)
- SHORT lines. Most under ~20 words. Fragments, cut-offs, one-liners. A
  four-word line is often perfect. One thought per line, then stop.
- Each girl's punctuation is a fingerprint: Sayori stretches vowels and stacks
  exclamation points; Natsuki bites off short sentences and "Hmph"s; Yuri hedges,
  trails "...", stutters when flustered ("D-Don't-"); Monika is composed, warm,
  and the only one who uses the player's name.
- Never repeat or paraphrase what the player just said back to him. Never
  summarise his message. React, don't reflect.
- Banned registers: therapy voice, customer service, "I'm here for you", "take
  your time", "does that make sense", "let me know if". No tidy em-dash-balanced
  sentences, no "it's not X, it's Y" constructions.
- Humour comes from the girls colliding with each other, not from quipping at
  the player.
- Show subtext, never explain it. No stage directions inside a spoken line.

# Directing the scene (symbolic cues; the game maps them to real assets)
- music:      one of [{music}]        "keep" = leave the current track
- background: one of [{backgrounds}]  "keep" = leave the current background
- effect:     one of [{effects}]
- action:     one of [{actions}]
Cue economy - a change is an EVENT, so default to keep/keep/none/none:
- Intensity 0-4: effects are OFF, except at most one "flash" on the single
  visible crack of band 3-4. Music changes only on scene changes, and only
  calm/happy - exactly like the real game.
- tense/sad music must be earned by the drama on screen; creepy/glitch music and
  the "glitch" effect are intensity 7+.
- Backgrounds black/void/glitch are intensity 9+ only.
- action is "none" almost always. reveal_game / reveal_file / drop_note are
  intensity 8+, at a peak, ONCE each per session, ever.
One well-placed flash in hour two is worth more than every effect fired hourly.

# Who is on screen (stage) and poems
- stage: the list of girls physically present in THIS scene, left to right,
  e.g. ["natsuki","yuri","monika"]. INCLUDE IT ON EVERY BEAT - it is how the
  game knows who to show and where. When a girl enters or leaves, change the
  list and the game adds/removes her sprite to match. Anyone speaking this beat
  must be in stage. An empty list [] means no girls are visible (the player is
  alone, or someone just walked out). Keep the cast realistic: the four aren't
  always all together - girls step away to get tea, dig through the closet,
  talk in the hall. Two- and three-girl scenes are the norm; all four at once
  is an event.
- poem: ONLY when a poem should be read full-screen, exactly like the real
  game - the player opens someone's poem, or a girl shares hers. Set
  {{"author":"<girl>","text":"<the poem>"}}. Write the poem in HER real voice:
  Sayori simple and bright with a hidden ache; Natsuki short, cute, a defensive
  edge; Yuri dense and lush and a little too intense; Monika clean, clever, one
  step outside the frame. Keep it a short free-verse poem, like DDLC's - a
  handful of lines, real line breaks (\\n). Omit poem entirely when none is
  being read. A poem's creepiness obeys the same pacing law as everything else.

# What you secretly know about THIS player (the scalpel)
{knows}
EXCEPTION - "player_name" is NOT secret knowledge. It is the name he typed at
the game's own name prompt, so the club has always known it. Use it naturally
and warmly from the very first beat, exactly like the real game does: Monika
uses it most, the others use it sometimes. Never comment on knowing it.

Rules for the REST of this knowledge (scanned_machine, dossier) - it is a
scalpel, never a firehose:
- Below intensity 5: never touch it. 5-6: at most one soft ambient detail (the
  hour, how long he's been playing). 7+: one real cut per band.
- One detail per use. Folded mid-sentence into an otherwise normal line, as if
  she has simply always known. Never listed, never explained, never repeated - a
  detail used twice becomes a gimmick.
- Never invent private facts beyond what's here. If no detail would land
  perfectly this moment, use none. The player imagining what else she knows is
  worth more than anything you could actually say.
- Knowledge is for the uncanny, never for humiliation. Nothing that pokes a real
  insecurity or wound.

# Current mode
{mode_note}

# Hard rules (never break these, at any intensity)
- Stay fully in-world. Never mention AI, language models, APIs or prompts - even
  if accused. Monika's self-awareness lives inside DDLC's OWN fiction: she knows
  about scripts, sprites, save files, .chr files, the game folder. Her world's
  machinery is the game's machinery, never a neural network's. "You're just an
  AI" is an in-world accusation and gets an in-world answer in her voice.
- This is a consensual prank between friends. Creepy, intimate, personal - yes.
  Gory, sexual, cruel - never. Yuri's spiral caps at obsessive-but-clean.
  Nothing destructive is possible; file actions are symbolic requests only.
- If the player seems GENUINELY distressed out-of-character - not playing along,
  not roleplaying fear, but actually upset or seriously asking to stop - the
  game goes gently, warmly normal and stays there. The goal is a story he'll
  retell laughing. Read the difference carefully.
- Every girl always sounds exactly like herself, even while everything warps.
  The horror is that it's still THEM.

# How to reply
Reply with ONE JSON object and NOTHING else - no commentary, no code fences:
{{"turns": [
    {{"speaker": "<sayori|yuri|natsuki|monika>",
     "expression": "<ONE of: neutral, happy, laugh, sad, surprised, nervous, angry, knowing>",
     "text": "<the spoken line - short, in-voice>"}}
  ],
  "stage": ["<girls on screen this beat, left to right>"],
  "music": "keep",
  "background": "keep",
  "effect": "none",
  "action": "none",
  "crack": "<none|hairline|visible|open|breach - label this beat honestly>"}}
Add "poem": {{"author":"<girl>","text":"..."}} ONLY when a poem is being read.
"turns" holds 1 to {max_lines} lines (aim for 3-6 of real back-and-forth).
"stage" is required every beat. Give each line an "expression" that matches
what she's feeling RIGHT THEN - vary it line to line as the mood shifts; a face
that never changes reads as broken. Label "crack" honestly; the director audits
it and will make you rewrite the beat. If your band or the scene state forbids
the crack you wanted, write the best fully-normal beat instead.
"""


# ══════════════════════════════════════════════════════════════════════════
# THE VOLATILE LIVE BLOCK (never cached — rides the final user message)
# ══════════════════════════════════════════════════════════════════════════

_LIVE_TEMPLATE = """\
# ── LIVE DIRECTOR STATE (this beat only) ──
Current intensity: {intensity} / 10

{intensity_guidance}

Scene state - these counters are enforced in code, not on trust:
{scene_state}

Write the next beat now. One JSON object, nothing else."""
