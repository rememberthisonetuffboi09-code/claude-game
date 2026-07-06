class_name Eva
extends CharacterBody2D
## Player-controlled Evangelion Unit-01.
## All combat is manual: run, jump, dash (with i-frames), a 3-hit melee combo,
## and a prog-knife finisher on a staggered Angel. Full design: docs/DESIGN.md.
##
## Animation contract: if a child AnimatedSprite2D named "Anim" exists, this
## script plays animations on it by name (see docs/ART_PIPELINE.md). With no
## "Anim" node the game runs fine on the placeholder Visual polygons.

signal died
signal perfect_dodge
signal berserk_started

enum State { MOVE, DASH, ATTACK, FINISHER, HURT, DEAD }

# -- movement tuning ---------------------------------------------------------
const SPEED := 430.0
const ACCEL := 2600.0
const JUMP_VELOCITY := -860.0
const GRAVITY := 2100.0
const FALL_GRAVITY := 2700.0
const DASH_SPEED := 980.0
const DASH_TIME := 0.16
const DASH_COOLDOWN := 0.4

# -- combat tuning -----------------------------------------------------------
const COMBO_DAMAGE := [10.0, 10.0, 16.0]
const COMBO_WINDUP := [0.10, 0.10, 0.16]
const COMBO_RECOVER := [0.16, 0.16, 0.26]
const COMBO_REACH := 130.0
const ATTACK_BUFFER := 0.18
const ATTACK_STEP_SPEED := 160.0

const FINISHER_DAMAGE := 60.0
const FINISHER_TRIGGER_RANGE := 320.0
const FINISHER_STRIKE_T := 0.25
const FINISHER_TIME := 0.75

const HURT_TIME := 0.32
const HIT_IFRAMES := 0.7
const KNOCKBACK := Vector2(380.0, -300.0)

const BERSERK_TIME := 6.0
const BERSERK_SYNC_MIN := 60.0
const BERSERK_DAMAGE_MULT := 2.0
const BERSERK_SPEED_MULT := 1.25

const SYNC_START := 40.0
const SYNC_PER_HIT := 2.0
const SYNC_PER_DODGE := 6.0
const SYNC_FINISHER := 10.0
const SYNC_LOSS_ON_HIT := 8.0

# -- state -------------------------------------------------------------------
var max_hp := 100.0
var hp := max_hp
var sync_ratio := SYNC_START
var power_low := false  # set by Main while running on internal battery

var state: State = State.MOVE
var state_t := 0.0
var facing := 1
var dash_dir := 1
var combo_step := 0
var struck := false  # current attack/finisher already applied its damage
var attack_buffer_t := 0.0
var dash_cooldown_t := 0.0
var air_dash_left := 1
var iframes_t := 0.0

var berserk_used := false
var berserk_t := 0.0

var finisher_from := Vector2.ZERO
var finisher_to := Vector2.ZERO

var slash_t := 0.0    # melee swing flash, drawn in _draw()
var trail: Array = []  # recent global positions for the dash afterimage

@onready var visual: Node2D = $Visual


func _ready() -> void:
	add_to_group("player")


func _physics_process(delta: float) -> void:
	if state == State.DEAD:
		_apply_gravity(delta)
		move_and_slide()
		return

	state_t += delta
	dash_cooldown_t = maxf(0.0, dash_cooldown_t - delta)
	iframes_t = maxf(0.0, iframes_t - delta)
	attack_buffer_t = maxf(0.0, attack_buffer_t - delta)
	slash_t = maxf(0.0, slash_t - 4.0 * delta)
	if Input.is_action_just_pressed("attack"):
		attack_buffer_t = ATTACK_BUFFER

	if berserk_t > 0.0:
		berserk_t -= delta
		if berserk_t <= 0.0:
			_end_berserk()

	match state:
		State.MOVE:
			_state_move(delta)
		State.DASH:
			_state_dash(delta)
		State.ATTACK:
			_state_attack(delta)
		State.FINISHER:
			_state_finisher(delta)
		State.HURT:
			_state_hurt(delta)

	if state != State.DASH and not trail.is_empty():
		trail.pop_front()
	queue_redraw()


# -- states ------------------------------------------------------------------

func _state_move(delta: float) -> void:
	var dir := Input.get_axis("move_left", "move_right")
	if dir != 0.0:
		facing = 1 if dir > 0.0 else -1
		visual.scale.x = float(facing)
	velocity.x = move_toward(velocity.x, dir * SPEED * _speed_mult(), ACCEL * delta)
	_apply_gravity(delta)
	if is_on_floor():
		air_dash_left = 1
		if Input.is_action_just_pressed("jump"):
			velocity.y = JUMP_VELOCITY
	move_and_slide()

	if Input.is_action_just_pressed("dash") and _can_dash():
		_start_dash()
		return
	if attack_buffer_t > 0.0:
		attack_buffer_t = 0.0
		_start_attack(0)
		return
	if Input.is_action_just_pressed("finisher"):
		_try_finisher()
		return

	if not is_on_floor():
		play_anim("jump" if velocity.y < 0.0 else "fall")
	elif absf(velocity.x) > 10.0:
		play_anim("run")
	else:
		play_anim("idle")


func _state_dash(_delta: float) -> void:
	velocity = Vector2(dash_dir * DASH_SPEED, 0.0)
	move_and_slide()
	trail.append(global_position)
	if trail.size() > 12:
		trail.pop_front()
	if state_t >= DASH_TIME:
		_enter_move()


func _state_attack(delta: float) -> void:
	_apply_gravity(delta)
	velocity.x = move_toward(velocity.x, 0.0, 1800.0 * delta)
	move_and_slide()

	var windup: float = COMBO_WINDUP[combo_step]
	if not struck and state_t >= windup:
		struck = true
		_melee_strike(COMBO_DAMAGE[combo_step])
	# dash-cancel out of recovery keeps the combo feeling responsive
	if struck and Input.is_action_just_pressed("dash") and _can_dash():
		_start_dash()
		return
	if state_t >= windup + COMBO_RECOVER[combo_step]:
		if attack_buffer_t > 0.0 and combo_step < COMBO_DAMAGE.size() - 1:
			attack_buffer_t = 0.0
			_start_attack(combo_step + 1)
		else:
			_enter_move()


func _state_finisher(_delta: float) -> void:
	velocity = Vector2.ZERO
	global_position = finisher_from.lerp(finisher_to, minf(state_t / 0.2, 1.0))
	if not struck and state_t >= FINISHER_STRIKE_T:
		struck = true
		slash_t = 0.3
		var boss = _get_boss()
		if boss != null:
			boss.take_hit(FINISHER_DAMAGE * _damage_mult(), true, global_position)
			_gain_sync(SYNC_FINISHER)
	if state_t >= FINISHER_TIME:
		_enter_move()


func _state_hurt(delta: float) -> void:
	_apply_gravity(delta)
	velocity.x = move_toward(velocity.x, 0.0, 1200.0 * delta)
	move_and_slide()
	if state_t >= HURT_TIME:
		_enter_move()


# -- transitions -------------------------------------------------------------

func _enter_move() -> void:
	state = State.MOVE
	state_t = 0.0


func _can_dash() -> bool:
	return dash_cooldown_t <= 0.0 and (is_on_floor() or air_dash_left > 0)


func _start_dash() -> void:
	if not is_on_floor():
		air_dash_left -= 1
	var dir := Input.get_axis("move_left", "move_right")
	dash_dir = facing if dir == 0.0 else (1 if dir > 0.0 else -1)
	facing = dash_dir
	visual.scale.x = float(facing)
	dash_cooldown_t = DASH_COOLDOWN
	state = State.DASH
	state_t = 0.0
	trail.clear()
	play_anim("dash")


func _start_attack(step: int) -> void:
	state = State.ATTACK
	state_t = 0.0
	combo_step = step
	struck = false
	velocity.x = facing * ATTACK_STEP_SPEED
	play_anim("attack_%d" % (step + 1))


func _try_finisher() -> void:
	var boss = _get_boss()
	if boss == null or not boss.staggered:
		return
	var core: Vector2 = boss.core_global_position()
	if global_position.distance_to(core) > FINISHER_TRIGGER_RANGE:
		return
	facing = 1 if core.x >= global_position.x else -1
	visual.scale.x = float(facing)
	state = State.FINISHER
	state_t = 0.0
	struck = false
	finisher_from = global_position
	finisher_to = Vector2(core.x - facing * 80.0, global_position.y)
	play_anim("finisher")


# -- combat ------------------------------------------------------------------

func _melee_strike(base_damage: float) -> void:
	slash_t = 0.25
	var boss = _get_boss()
	if boss == null:
		return
	var probe := global_position + Vector2(facing * COMBO_REACH * 0.6, -60.0)
	if boss.hit_from(probe, COMBO_REACH):
		boss.take_hit(base_damage * _damage_mult(), false, probe)
		_gain_sync(SYNC_PER_HIT)


func take_hit(damage: float, from_x: float) -> void:
	if state == State.DEAD:
		return
	if state == State.DASH:
		_gain_sync(SYNC_PER_DODGE)
		perfect_dodge.emit()
		return
	if is_invulnerable():
		return

	hp = maxf(0.0, hp - damage)
	sync_ratio = maxf(0.0, sync_ratio - SYNC_LOSS_ON_HIT)
	_flash_damage()
	if hp <= 0.0:
		if not berserk_used and sync_ratio >= BERSERK_SYNC_MIN:
			_start_berserk()
		else:
			_die()
		return
	state = State.HURT
	state_t = 0.0
	iframes_t = HIT_IFRAMES
	velocity = Vector2(signf(global_position.x - from_x) * KNOCKBACK.x, KNOCKBACK.y)
	play_anim("hurt")


func is_invulnerable() -> bool:
	return state == State.DASH or state == State.FINISHER \
		or iframes_t > 0.0 or berserk_t > 0.0


func _start_berserk() -> void:
	berserk_used = true
	berserk_t = BERSERK_TIME
	hp = 1.0
	sync_ratio = 100.0
	state = State.MOVE
	state_t = 0.0
	visual.modulate = Color(1.0, 0.35, 0.35)
	berserk_started.emit()
	play_anim("berserk")


func _end_berserk() -> void:
	berserk_t = 0.0
	hp = maxf(hp, 15.0)
	visual.modulate = Color.WHITE


func _die() -> void:
	state = State.DEAD
	visual.modulate = Color(0.4, 0.4, 0.45)
	play_anim("die")
	died.emit()


func _gain_sync(amount: float) -> void:
	sync_ratio = minf(100.0, sync_ratio + amount)


func _damage_mult() -> float:
	var mult := 0.8 + sync_ratio * 0.005  # 0.8x at 0 sync, 1.3x at 100
	if berserk_t > 0.0:
		mult *= BERSERK_DAMAGE_MULT
	if power_low:
		mult *= 0.6
	return mult


func _speed_mult() -> float:
	return BERSERK_SPEED_MULT if berserk_t > 0.0 else 1.0


# -- helpers -----------------------------------------------------------------

func _apply_gravity(delta: float) -> void:
	if not is_on_floor():
		var g := GRAVITY if velocity.y < 0.0 else FALL_GRAVITY
		velocity.y += g * delta


# returns untyped on purpose: keeps eva.gd decoupled from the boss script,
# so any Angel in the "boss" group with the same contract works
func _get_boss():
	return get_tree().get_first_node_in_group("boss")


func _flash_damage() -> void:
	visual.modulate = Color(1.0, 0.25, 0.25)
	var target := Color(1.0, 0.35, 0.35) if berserk_t > 0.0 else Color.WHITE
	var tw := create_tween()
	tw.tween_property(visual, "modulate", target, 0.25)


func play_anim(anim_name: String) -> void:
	var anim := get_node_or_null("Anim") as AnimatedSprite2D
	if anim == null:
		return
	anim.flip_h = facing < 0
	if anim.sprite_frames != null and anim.sprite_frames.has_animation(anim_name):
		if anim.animation != anim_name or not anim.is_playing():
			anim.play(anim_name)


func _draw() -> void:
	# dash afterimage trail
	for i in trail.size():
		var p := to_local(trail[i])
		var a := float(i) / maxf(1.0, float(trail.size())) * 0.25
		draw_rect(Rect2(p + Vector2(-16.0, -100.0), Vector2(32.0, 100.0)), Color(0.6, 0.4, 1.0, a))
	# melee swing flash
	if slash_t > 0.0:
		var base := 0.0 if facing > 0 else PI
		draw_arc(Vector2(0.0, -60.0), 95.0, base - 0.9, base + 0.9, 16,
				Color(1.0, 1.0, 1.0, minf(slash_t * 3.0, 0.9)), 7.0)
