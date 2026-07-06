# Art Pipeline — replacing placeholders with your drawings

The game runs on placeholder polygons so it is playable from day one.
Every sprite you finish visibly upgrades it, one animation at a time —
you never need a "full art pass" before seeing your work in motion.

## How the hookup works

Both `eva.gd` and `sachiel.gd` call `play_anim("name")` at the right
moments. The helper looks for a child **AnimatedSprite2D named `Anim`**:

- No `Anim` node → nothing happens, placeholders keep working.
- `Anim` exists but is missing that animation → that one call no-ops.

So you can add sprites **one animation at a time**:

1. Open `scenes/player/eva.tscn` in Godot.
2. Add an `AnimatedSprite2D` child of the root, rename it exactly `Anim`.
3. Create a `SpriteFrames` resource on it, add an animation with an exact
   name from the contract below, import your frames into it.
4. Position the sprite so the **feet sit at y = 0** (the root origin).
5. When enough animations exist, hide or delete the `Visual` node.

**Draw facing RIGHT** (Eva) / **LEFT** (Sachiel). Flipping is handled in
code via `flip_h` — never draw both directions.

## Animation contract

### Unit-01 (`eva.tscn` → Anim)

| Name | Suggested frames | Notes |
|---|---|---|
| `idle` | 4–6, loop | Breathing sway. Restrained — it's a weapon at rest |
| `run` | 6–8, loop | Weight! A 40m biomech, not a platformer mascot |
| `jump` / `fall` | 2–3 each | Poses more than motion |
| `dash` | 2–3 + smear | One big smear frame reads better than five clean ones |
| `attack_1/2/3` | 3–5 each | Anticipation ≥ strike. Strike = 1–2 frames MAX, huge spacing |
| `finisher` | 6–10 | Prog knife into the core. The money shot — spend here |
| `hurt` | 1–2 | Big silhouette break |
| `berserk` | 4–6, loop | Hunched, feral. Jaw. You know the scene |
| `die` | 3–5, no loop | Slump |

### Sachiel (`sachiel.tscn` → Anim)

| Name | Notes |
|---|---|
| `idle` | Slow, wrong, organic sway |
| `walk` | Deliberate. Heavy |
| `spear` | Windup must fill the full 0.55s telegraph — long anticipation, instant strike |
| `beam` | Face lights during aim, recoil on fire |
| `leap` | Crouch (telegraph) → airborne pose → landing crunch |
| `stagger` | Limp, core pulsing — sell "HIT ME NOW" |
| `die` | Slump/burst — you can re-time `_die()` once you know the animation length |

## Timing: animate like Gainax, not like Disney

The code telegraphs are your timing sheet — final animation must keep
anticipation at least as long as the placeholder flash, or the fight
becomes unfair and *feels* worse despite looking better.

- **Anime timing**: hold poses, then snap. 3–5 *meaningful* frames beat
  12 mushy ones. Work on 2s/3s (12.5/8 fps), not 25 fps.
- **Smears** for the dash and sword arcs — one stretched frame sells speed.
- **Silhouette first**: flip your canvas, squint. If idle/windup/strike
  read identically in silhouette, the player can't read the fight.
- Iteration order that keeps morale up: `idle` → `run` → `attack_1`
  (reuse as 2/3 initially) → `dash` → boss `spear` → everything else.

## Canvas / scale reference

The placeholder models ARE the scale reference: match their proportions and
your sprites will drop in at the correct size. Exact placeholder dimensions
(origin = feet at y0, art may overhang — gameplay hitboxes stay in code):

| | World size | Landmarks (y from feet) |
|---|---|---|
| **Unit-01** | 72 wide (pylon to pylon) × 160 tall, 198 with horn | pelvis −64…−86, chest top −126, pylons −120…−142, head −134…−160, eye ≈ −149 |
| **Sachiel** | ~184 wide (hand to hand) × 236 tall | legs to −90, core center −95, face mask −148…−198, hump top −220 |

Workflow: draw at **2× world size** and set the sprite's `scale` to 0.5 —
crisp at native zoom, and you keep resolution headroom.

- **Unit-01 canvas**: 192 × 448 px (character ~144 × 400 within it,
  margin for smears and effects)
- **Sachiel canvas**: 448 × 512 px (character ~368 × 472 within it)

Sanity check before committing to a style: draw ONE pose of Unit-01 at that
size, drop it in as a single-frame `idle`, and stand next to Sachiel in game.
Adjust proportions until the matchup silhouette feels right, THEN batch the
remaining animations.

## Tools & export

- **Aseprite** (pixel art) or **Krita / Clip Studio** (hand-drawn) →
  export sprite sheets or numbered PNGs; both import straight into
  `SpriteFrames` (drag the files into the animation's frame list).
- Keep sources in an untracked `art-src/` folder or a separate drive;
  commit only exported PNGs to `assets/` when they're game-ready.

## Later (don't start here)

- Backgrounds: `main.gd::_build_background()` builds the skyline — replace
  with layered `Parallax2D` paintings when combat art is done.
- Event illustrations for fight intros/outros (the VN-style money art).
- UI skin: the HUD is deliberately plain code — restyle once the MAGI
  aesthetic direction is locked.
