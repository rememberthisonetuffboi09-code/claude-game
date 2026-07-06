class_name Sachiel
extends CharacterBody2D
## The Third Angel. Boss state machine with three telegraphed attacks:
##   SPEAR - close-range arm lance. Answer: jump over it, or dash through it.
##   BEAM  - locked-target eye beam. Answer: leave the line before it fires.
##   LEAP  - jump to the pilot's position + ground shockwave. Answer: move off
##           the landing mark, then jump the shockwave.
## Damage loop: hits drain the AT Field -> field break -> STAGGER window where
## the core takes damage (prog-knife finisher for a big chunk) -> field
## restores stronger. Core at 50%: phase 2, everything gets faster.
##
## All telegraphs are drawn in _draw() so they stay readable with placeholder
## art AND become the timing reference when real animation goes in.

signal defeated
signal at_field_broken
signal stagger_ended
signal phase_changed
signal landed

enum State { IDLE, WALK, SPEAR, BEAM, LEAP, STAGGER, DEAD }

# -- body geometry (matches the placeholder Visual polygons) ------------------
const BODY_HALF_W := 90.0
const BODY_HEIGHT := 235.0
const CORE_OFFSET := Vector2(0.0, -95.0)
const FACE_OFFSET := Vector2(0.0, -185.0)

# -- tuning ------------------------------------------------------------------
const GRAVITY := 2100.0
const WALK_SPEED := 130.0
const AT_FIELD_BASE := 100.0
const AT_FIELD_GROWTH := 20.0   # field max grows per break
const CORE_HP_MAX := 300.0
const STAGGER_TIME := 6.0
const STAGGER_TIME_P2 := 4.5

const SPEAR_DAMAGE := 16.0
const SPEAR_REACH := 260.0
const SPEAR_WINDUP := 0.55
const SPEAR_WINDUP_P2 := 0.38

const BEAM_DAMAGE := 24.0
const BEAM_WINDUP := 0.85
const BEAM_WINDUP_P2 := 0.6
const BEAM_FIRE_TIME := 0.5
const BEAM_HALF_WIDTH := 42.0

const LEAP_DAMAGE := 20.0
const LEAP_WINDUP := 0.45
const LEAP_WINDUP_P2 := 0.32
const LEAP_FLIGHT_TIME := 0.62
const LEAP_ARC_HEIGHT := 340.0
const SHOCKWAVE_RADIUS := 300.0

# -- state -------------------------------------------------------------------
var at_field := AT_FIELD_BASE
var at_field_max := AT_FIELD_BASE
var core_hp := CORE_HP_MAX
var staggered := false
var phase := 1

var arena_left := -1200.0   # set by Main after instancing
var arena_right := 1200.0

var state: State = State.IDLE
var state_t := 0.0
var idle_wait := 1.4
var facing := -1
var struck_this_attack := false
var enraged := false        # attack immediately after a stagger ends

var beam_from := Vector2.ZERO
var beam_to := Vector2.ZERO
var leap_from := Vector2.ZERO
var leap_to := Vector2.ZERO
var leap_num := 0           # phase 2 chains a second hop

var strike_flash_t := 0.0
var shock_t := 0.0          # expanding shockwave ring after landing
var core_flash_t := 0.0
var at_flashes: Array = []  # [{pos: Vector2 (local), t: float}] hex ripples

@onready var visual: Node2D = $Visual


func _ready() -> void:
	add_to_group("boss")


func _physics_process(delta: float) -> void:
	strike_flash_t = maxf(0.0, strike_flash_t - delta)
	shock_t = maxf(0.0, shock_t - delta)
	core_flash_t = maxf(0.0, core_flash_t - delta)
	for f in at_flashes:
		f.t -= delta
	at_flashes = at_flashes.filter(func(f): return f.t > 0.0)

	if state == State.DEAD:
		queue_redraw()
		return
	state_t += delta

	match state:
		State.IDLE:
			_state_idle(delta)
		State.WALK:
			_state_walk(delta)
		State.SPEAR:
			_state_spear(delta)
		State.BEAM:
			_state_beam(delta)
		State.LEAP:
			_state_leap(delta)
		State.STAGGER:
			_state_stagger(delta)
	queue_redraw()


# -- states ------------------------------------------------------------------

func _state_idle(delta: float) -> void:
	_stand(delta)
	_face_player()
	play_anim("idle")
	if state_t >= idle_wait:
		_choose_attack()


func _state_walk(delta: float) -> void:
	var player := _get_player()
	if player == null:
		_stand(delta)
		return
	_face_player()
	velocity.x = float(facing) * WALK_SPEED * (1.4 if phase == 2 else 1.0)
	if not is_on_floor():
		velocity.y += GRAVITY * delta
	move_and_slide()
	play_anim("walk")
	var dx := absf(player.global_position.x - global_position.x)
	if dx < 280.0:
		_start_spear()
	elif state_t >= 1.5:
		_to_idle(0.2)


func _state_spear(delta: float) -> void:
	_stand(delta)
	var windup := SPEAR_WINDUP_P2 if phase == 2 else SPEAR_WINDUP
	if not struck_this_attack and state_t >= windup:
		struck_this_attack = true
		strike_flash_t = 0.15
		var player := _get_player()
		if player != null:
			var d: Vector2 = player.global_position - global_position
			if d.x * facing > -20.0 and absf(d.x) < BODY_HALF_W + SPEAR_REACH \
					and d.y > -120.0 and d.y < 40.0:
				player.take_hit(SPEAR_DAMAGE, global_position.x)
	if state_t >= windup + (0.35 if phase == 2 else 0.5):
		_to_idle(randf_range(0.5, 1.0))


func _state_beam(delta: float) -> void:
	_stand(delta)
	var windup := BEAM_WINDUP_P2 if phase == 2 else BEAM_WINDUP
	if state_t >= windup and state_t < windup + BEAM_FIRE_TIME:
		if not struck_this_attack:
			var player := _get_player()
			if player != null:
				var center: Vector2 = player.global_position + Vector2(0.0, -60.0)
				var closest := Geometry2D.get_closest_point_to_segment(center, beam_from, beam_to)
				if center.distance_to(closest) < BEAM_HALF_WIDTH:
					struck_this_attack = true
					player.take_hit(BEAM_DAMAGE, global_position.x)
	if state_t >= windup + BEAM_FIRE_TIME + 0.7:
		_to_idle(randf_range(0.5, 1.1))


func _state_leap(delta: float) -> void:
	var windup := LEAP_WINDUP_P2 if phase == 2 else LEAP_WINDUP
	if state_t < windup:
		_stand(delta)
		return
	# ballistic flight along a parabola, then a ground shockwave on landing
	var t := clampf((state_t - windup) / LEAP_FLIGHT_TIME, 0.0, 1.0)
	global_position = leap_from.lerp(leap_to, t) + Vector2(0.0, -sin(PI * t) * LEAP_ARC_HEIGHT)
	if t >= 1.0 and not struck_this_attack:
		struck_this_attack = true
		shock_t = 0.35
		landed.emit()
		var player := _get_player()
		if player != null and player.is_on_floor() \
				and absf(player.global_position.x - global_position.x) < SHOCKWAVE_RADIUS:
			player.take_hit(LEAP_DAMAGE, global_position.x)
	if t >= 1.0 and state_t >= windup + LEAP_FLIGHT_TIME + 0.5:
		if phase == 2 and leap_num == 0:
			leap_num = 1
			_start_leap()
		else:
			_to_idle(randf_range(0.4, 0.9))


func _state_stagger(delta: float) -> void:
	_stand(delta)
	play_anim("stagger")
	var duration := STAGGER_TIME_P2 if phase == 2 else STAGGER_TIME
	if state_t >= duration:
		_end_stagger()


# -- attack selection --------------------------------------------------------

func _choose_attack() -> void:
	var player := _get_player()
	if player == null:
		_to_idle(0.5)
		return
	var dx := absf(player.global_position.x - global_position.x)
	var roll := randf()
	if dx > 650.0:
		if roll < 0.55:
			_start_beam()
		elif roll < 0.85:
			_start_leap()
		else:
			_start_walk()
	elif dx > 300.0:
		if roll < 0.4:
			_start_walk()
		elif roll < 0.75:
			_start_leap()
		else:
			_start_beam()
	else:
		if roll < 0.6:
			_start_spear()
		elif roll < 0.85:
			_start_leap()
		else:
			_start_beam()


func _to_idle(wait: float) -> void:
	state = State.IDLE
	state_t = 0.0
	idle_wait = 0.15 if enraged else wait * (0.6 if phase == 2 else 1.0)
	enraged = false


func _start_walk() -> void:
	state = State.WALK
	state_t = 0.0


func _start_spear() -> void:
	_face_player()
	state = State.SPEAR
	state_t = 0.0
	struck_this_attack = false
	play_anim("spear")


func _start_beam() -> void:
	_face_player()
	state = State.BEAM
	state_t = 0.0
	struck_this_attack = false
	beam_from = global_position + FACE_OFFSET
	var player := _get_player()
	var target := beam_from + Vector2(float(facing) * 800.0, 120.0)
	if player != null:
		target = player.global_position + Vector2(0.0, -60.0)
	beam_to = beam_from + (target - beam_from).normalized() * 2400.0
	play_anim("beam")


func _start_leap() -> void:
	_face_player()
	state = State.LEAP
	state_t = 0.0
	struck_this_attack = false
	leap_from = global_position
	var target_x := global_position.x + float(facing) * 400.0
	var player := _get_player()
	if player != null:
		target_x = player.global_position.x
	leap_to = Vector2(clampf(target_x, arena_left, arena_right), global_position.y)
	play_anim("leap")


# -- damage ------------------------------------------------------------------

func take_hit(damage: float, is_finisher: bool = false, from_pos: Vector2 = Vector2.ZERO) -> void:
	if state == State.DEAD:
		return
	if staggered:
		core_hp = maxf(0.0, core_hp - damage)
		core_flash_t = 0.3
		if phase == 1 and core_hp <= CORE_HP_MAX * 0.5:
			phase = 2
			phase_changed.emit()
		if core_hp <= 0.0:
			_die()
			return
		if is_finisher:
			_end_stagger()
	else:
		at_field = maxf(0.0, at_field - damage)
		var flash_pos := to_local(from_pos) if from_pos != Vector2.ZERO \
				else Vector2(float(-facing) * BODY_HALF_W, -120.0)
		at_flashes.append({"pos": flash_pos, "t": 0.35})
		if at_field <= 0.0:
			_start_stagger()


func _start_stagger() -> void:
	staggered = true
	state = State.STAGGER
	state_t = 0.0
	velocity = Vector2.ZERO
	at_field_broken.emit()


func _end_stagger() -> void:
	staggered = false
	at_field_max += AT_FIELD_GROWTH
	at_field = at_field_max
	enraged = true
	leap_num = 0
	stagger_ended.emit()
	_to_idle(0.2)


func _die() -> void:
	state = State.DEAD
	staggered = false
	velocity = Vector2.ZERO
	play_anim("die")
	visual.modulate = Color(0.5, 0.5, 0.5)
	var tw := create_tween()
	tw.tween_property(visual, "modulate", Color(0.3, 0.3, 0.35, 0.6), 1.2)
	defeated.emit()


## Melee probe used by the player: is `pos` within `reach` of the body rect?
func hit_from(pos: Vector2, reach: float) -> bool:
	var rect := Rect2(global_position + Vector2(-BODY_HALF_W, -BODY_HEIGHT),
			Vector2(BODY_HALF_W * 2.0, BODY_HEIGHT))
	var closest := pos.clamp(rect.position, rect.position + rect.size)
	return pos.distance_to(closest) <= reach


func core_global_position() -> Vector2:
	return global_position + CORE_OFFSET


# -- helpers -----------------------------------------------------------------

func _stand(delta: float) -> void:
	velocity.x = move_toward(velocity.x, 0.0, 2000.0 * delta)
	if not is_on_floor():
		velocity.y += GRAVITY * delta
	move_and_slide()


func _face_player() -> void:
	var player := _get_player()
	if player == null:
		return
	facing = 1 if player.global_position.x >= global_position.x else -1
	visual.scale.x = float(-facing)  # placeholder faces left by default


# untyped on purpose: dynamic access keeps this script decoupled from eva.gd
func _get_player():
	return get_tree().get_first_node_in_group("player")


func play_anim(anim_name: String) -> void:
	var anim := get_node_or_null("Anim") as AnimatedSprite2D
	if anim == null:
		return
	anim.flip_h = facing > 0
	if anim.sprite_frames != null and anim.sprite_frames.has_animation(anim_name):
		if anim.animation != anim_name or not anim.is_playing():
			anim.play(anim_name)


# -- telegraphs & fx ---------------------------------------------------------

func _draw() -> void:
	var windup: float
	match state:
		State.SPEAR:
			windup = SPEAR_WINDUP_P2 if phase == 2 else SPEAR_WINDUP
			if state_t < windup:
				var a := 0.15 + 0.25 * (state_t / windup)
				var x0 := BODY_HALF_W if facing > 0 else -(BODY_HALF_W + SPEAR_REACH)
				draw_rect(Rect2(Vector2(x0, -150.0), Vector2(SPEAR_REACH, 170.0)),
						Color(1.0, 0.55, 0.1, a))
		State.BEAM:
			windup = BEAM_WINDUP_P2 if phase == 2 else BEAM_WINDUP
			var from_l := to_local(beam_from)
			var to_l := to_local(beam_to)
			if state_t < windup:
				var pulse := 0.35 + 0.3 * sin(state_t * 24.0)
				draw_line(from_l, to_l, Color(1.0, 0.15, 0.15, pulse), 3.0)
			elif state_t < windup + BEAM_FIRE_TIME:
				draw_line(from_l, to_l, Color(1.0, 0.2, 0.2, 0.55), BEAM_HALF_WIDTH * 2.0)
				draw_line(from_l, to_l, Color(1.0, 1.0, 1.0, 0.95), BEAM_HALF_WIDTH * 0.8)
		State.LEAP:
			var land_l := to_local(leap_to)
			draw_arc(land_l, 60.0, 0.0, TAU, 32, Color(1.0, 0.3, 0.1, 0.8), 4.0)
			draw_arc(land_l, SHOCKWAVE_RADIUS, 0.0, TAU, 48, Color(1.0, 0.3, 0.1, 0.25), 3.0)
		State.STAGGER:
			var pulse_r := 78.0 + sin(state_t * 8.0) * 10.0
			draw_arc(CORE_OFFSET, pulse_r, 0.0, TAU, 32, Color(1.0, 0.2, 0.2, 0.85), 5.0)
		_:
			pass
	# spear strike flash
	if strike_flash_t > 0.0 and state == State.SPEAR:
		var x0 := BODY_HALF_W if facing > 0 else -(BODY_HALF_W + SPEAR_REACH)
		draw_rect(Rect2(Vector2(x0, -150.0), Vector2(SPEAR_REACH, 170.0)),
				Color(1.0, 1.0, 1.0, strike_flash_t * 4.0))
	# expanding shockwave ring on landing
	if shock_t > 0.0:
		var k := 1.0 - shock_t / 0.35
		draw_arc(Vector2.ZERO, 60.0 + k * (SHOCKWAVE_RADIUS - 60.0), 0.0, TAU, 48,
				Color(1.0, 0.6, 0.2, 0.7 * (1.0 - k)), 8.0)
	# core hit flash
	if core_flash_t > 0.0:
		draw_circle(CORE_OFFSET, 34.0, Color(1.0, 0.9, 0.9, core_flash_t * 2.5))
	# AT-field hex ripples where melee hits land
	for f in at_flashes:
		var alpha: float = f.t * 2.2
		var radius: float = 55.0 + (0.35 - f.t) * 160.0
		var points := PackedVector2Array()
		for i in 6:
			var ang := TAU * float(i) / 6.0 + PI / 6.0
			points.append(f.pos + Vector2(cos(ang), sin(ang)) * radius)
		points.append(points[0])
		draw_polyline(points, Color(1.0, 0.55, 0.1, alpha), 3.0)
