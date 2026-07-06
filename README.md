# EVA Boss Rush — Vertical Slice

A 2D Evangelion fan game: a boss-rush action game where you pilot Unit-01
against the Angels. This repo is the **vertical slice** — one arena, one
fully mechanical boss fight (Sachiel), running entirely on placeholder
polygon art that hand-drawn sprites will replace piece by piece.

> Fan project. Non-commercial. Evangelion belongs to khara / Gainax.

## Run it

1. Install [Godot 4.3+](https://godotengine.org/download) (standard build, not .NET).
2. Open Godot → **Import** → select this folder's `project.godot`.
3. Press **F5** (or the play button).

The game is fully playable with the placeholder shapes — purple mech = you.

## Controls

| Input | Action |
|---|---|
| **A / D** or arrows | Move |
| **Space / W** | Jump |
| **Shift / L** | Dash — has invincibility frames; dodge *through* attacks |
| **J / X** | Melee combo (3 hits) |
| **K / C** | Prog knife finisher — only when the core is exposed |
| **R** | Restart |

## The combat loop

1. **Read the telegraph.** Every Sachiel attack flashes its hit zone first:
   orange rect = arm spear (jump it or dash through), red line = eye beam
   (get off the line), red ring = leap landing + ground shockwave (move away,
   then jump).
2. **Chip the AT Field** with melee. Hits ripple orange hexagons.
3. **Field break → stagger.** The core is exposed for a few seconds — combo it,
   and land the prog knife **[K]** for a big chunk.
4. **The field comes back stronger.** At 50% core HP the Angel enters phase 2:
   faster telegraphs, chained leaps.
5. **Watch the clock.** The umbilical cable gives 5:00 of power, then 60
   seconds of internal battery at reduced output. Battery empty = shutdown.
6. **Sync ratio** climbs with clean hits and perfect dodges, falls when you
   get hit. It scales your damage — and if you'd die above 60% sync,
   Unit-01 refuses to stop.

## Repo layout

```
project.godot          Godot project + input map
scenes/main.*          Arena, camera, power clock, win/lose
scenes/player/eva.*    Unit-01: movement, dash i-frames, combo, finisher, berserk
scenes/boss/sachiel.*  Angel state machine, telegraphs, AT Field/stagger loop
scenes/hud/hud.gd      NERV-styled HUD (built in code)
docs/DESIGN.md         Full slice design + tuning reference
docs/ART_PIPELINE.md   How your drawings replace the placeholders
```

## Roadmap

- [x] Vertical slice: movement + Sachiel fight, playable on placeholder art
- [ ] Tune the fight until it *feels* good (all numbers are consts at the top of each script)
- [ ] First art pass: Unit-01 idle/run/attack sprites (see `docs/ART_PIPELINE.md`)
- [ ] Sound: hits, alarms, the power-warning klaxon
- [ ] Second Angel (Shamshel — whip spacing test)
- [ ] Ramiel (bullet-hell positioning phase), Zeruel (the final exam)
