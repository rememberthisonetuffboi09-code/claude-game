# Design — EVA Boss Rush

## Pillars

1. **Combat is manual.** Every dodge, hit, and finisher is player-executed.
   No stat-check resolution, ever.
2. **Animation is the mechanics.** Bosses are readable through their tells.
   The placeholder telegraphs (drawn in `_draw()`) define the *timing*
   contract that final animation must honor: anticipation ≥ strike.
3. **Eva's canon is the systems.** Umbilical timer, AT Field, exposed core,
   sync ratio, berserk — nothing invented, everything mechanized.
4. **Boss rush scope.** No trash mobs, no levels. Every Angel is a
   handcrafted fight. 4–5 Angels = a complete game.

## The core loop (one fight)

```
read telegraph → dodge/punish → chip AT Field → FIELD BREAK
   → core exposed (stagger) → combo + prog knife finisher
   → field returns stronger → repeat under a shrinking power clock
```

Sources of tension stack: boss pressure (moment-to-moment), AT Field
progress (medium-term), umbilical power (whole-fight doom clock).

## Player — Unit-01 (`scenes/player/eva.gd`)

| System | Rule |
|---|---|
| HP | 100. Boss hits take 16–24. |
| Dash | 0.16s, full i-frames, 0.4s cooldown, 1 air dash. Dodging *through* an attack = perfect evade, +6 sync. |
| Combo | 3 hits (10/10/16 base), buffered input, dash-cancelable recovery. |
| Finisher | Prog knife [K], only while boss is staggered and in range. 60 base damage, ends the stagger early (risk/reward: burst vs. full combo time). |
| Sync ratio | Starts 40%. +2 per hit landed, +6 perfect evade, +10 finisher, −8 when hit. Damage scale: `0.8 + sync × 0.005` (0.8×–1.3×). |
| Berserk | Lethal hit while sync ≥ 60% and not yet used: survive at 1 HP, 6s of 2× damage / 1.25× speed / invulnerable, then drop to 15 HP. Once per sortie. |
| Power | Main owns it: 5:00 umbilical → cable severed → 60s battery at 0.6× damage → shutdown = loss. |

## Boss — Sachiel (`scenes/boss/sachiel.gd`)

Health model: **AT Field** (100, absorbs everything while up) over
**Core HP** (300, only damageable during stagger).

| Attack | Telegraph | Answer |
|---|---|---|
| Spear (close) | Orange zone flashes 0.55s | Jump over the low band, or dash through |
| Beam (ranged) | Red aim line locks your position, 0.85s | Leave the line — it does not track after lock |
| Leap (any range) | Red ring marks landing + shockwave radius | Move off the mark, then **jump** the ground shockwave |

**Stagger:** 6s, core exposed, pulsing ring. Ended early by the finisher.
Each break: field max +20. **Phase 2** at core ≤ 50%: telegraphs ~30%
faster, walk faster, leap chains twice, shorter stagger (4.5s).

Design intent per attack: spear teaches vertical dodge, beam teaches
horizontal spacing, leap teaches sequenced dodges (move → jump). Phase 2
re-asks the same questions faster.

## Tuning

Every number is a `const` at the top of its script — no magic numbers in
function bodies. Current values are first-guess; expected iteration:

- Fight length target: 2.5–4 min (≈ 2–3 field breaks).
- If stagger burst feels too strong, cut in-stagger melee damage before
  touching finisher damage (the finisher should stay the star).
- If the fight feels passive, shorten boss idle waits before touching
  damage numbers.

## Deliberately NOT in the slice

- Sound (biggest bang-for-buck after tuning — add early)
- Hit-stop / freeze frames (add with first real animation pass)
- Berserk as a *controlled loss* (auto-attack AI) — currently just a buff
- Pilot/story framing between fights
- Menus, save, options

## Future Angels (one gimmick each)

| Angel | Fight thesis |
|---|---|
| Shamshel | Whips: mid-range is death, spacing test — stay out or all the way in |
| Ramiel | No melee phase 1: bullet-hell drill defense, then a sniper-window duel |
| Zeruel | The final exam: every previous mechanic, brutal timings, guaranteed cable cut at 50% |
