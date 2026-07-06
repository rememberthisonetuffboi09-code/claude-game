extends Node2D
## Operation controller: builds the arena and background, spawns Unit-01 and
## the Angel, drives the camera, and owns the umbilical power clock and the
## win/lose state. Everything visual here is placeholder mood-setting that
## real backgrounds will replace (see docs/ART_PIPELINE.md).

const EvaScene := preload("res://scenes/player/eva.tscn")
const SachielScene := preload("res://scenes/boss/sachiel.tscn")
const HudScene := preload("res://scenes/hud/hud.tscn")

const ARENA_HALF_WIDTH := 1350.0
const FLOOR_Y := 500.0
const UMBILICAL_SECONDS := 300.0
const BATTERY_SECONDS := 60.0

var eva: Eva
var sachiel: Sachiel
var hud: Hud
var camera: Camera2D

var external_power := UMBILICAL_SECONDS
var battery := BATTERY_SECONDS
var on_battery := false
var match_over := false
var shake := 0.0
var hit_stop_active := false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	add_to_group("main")
	Engine.time_scale = 1.0
	randomize()
	_build_background()
	_build_arena()

	eva = EvaScene.instantiate()
	eva.global_position = Vector2(-500.0, FLOOR_Y)
	add_child(eva)

	sachiel = SachielScene.instantiate()
	sachiel.global_position = Vector2(450.0, FLOOR_Y)
	sachiel.arena_left = -ARENA_HALF_WIDTH + 150.0
	sachiel.arena_right = ARENA_HALF_WIDTH - 150.0
	add_child(sachiel)

	camera = Camera2D.new()
	camera.limit_left = int(-ARENA_HALF_WIDTH)
	camera.limit_right = int(ARENA_HALF_WIDTH)
	camera.limit_top = -700
	camera.limit_bottom = int(FLOOR_Y) + 220
	camera.position_smoothing_enabled = true
	camera.position_smoothing_speed = 6.0
	add_child(camera)
	camera.make_current()

	hud = HudScene.instantiate()
	add_child(hud)
	hud.setup(self, eva, sachiel)

	eva.died.connect(_on_eva_died)
	eva.perfect_dodge.connect(
			func(): hud.flash_message("", "PERFECT EVADE  //  SYNC RISING", 0.8))
	eva.berserk_started.connect(_on_berserk)
	sachiel.defeated.connect(_on_angel_defeated)
	sachiel.at_field_broken.connect(
			func():
				hud.flash_message("AT FIELD NEUTRALIZED", "CORE EXPOSED - STRIKE NOW [K]", 2.5)
				add_shake(14.0)
				hit_stop(0.15))
	sachiel.stagger_ended.connect(
			func(): hud.flash_message("AT FIELD RESTORED", "", 1.5))
	sachiel.phase_changed.connect(
			func():
				hud.flash_message("PATTERN SHIFT", "TARGET ACCELERATING", 2.0)
				add_shake(20.0))
	sachiel.landed.connect(func(): add_shake(16.0))

	hud.flash_message("ANGEL DETECTED - PATTERN BLUE",
			"ELIMINATE THE TARGET  //  UMBILICAL POWER: 05:00", 3.5)


func _process(delta: float) -> void:
	if Input.is_action_just_pressed("restart"):
		Engine.time_scale = 1.0
		get_tree().paused = false
		get_tree().reload_current_scene()
		return
	if match_over:
		return

	_tick_power(delta)

	# camera frames both combatants, weighted toward the pilot
	var target: Vector2 = eva.global_position * 0.62 + sachiel.global_position * 0.38
	camera.position = target + Vector2(0.0, -170.0)
	# fast exponential falloff reads as impact, the linear term kills the tail
	shake = maxf(0.0, shake - (shake * 6.0 + 8.0) * delta)
	camera.offset = Vector2(randf_range(-shake, shake), randf_range(-shake, shake))


func _tick_power(delta: float) -> void:
	if not on_battery:
		external_power -= delta
		if external_power <= 0.0:
			external_power = 0.0
			on_battery = true
			eva.power_low = true
			hud.flash_message("UMBILICAL CABLE SEVERED",
					"INTERNAL BATTERY - 60 SECONDS OF OPERATION", 3.0)
	else:
		battery -= delta
		if battery <= 0.0:
			battery = 0.0
			_finish(false, "ACTIVITY LIMIT REACHED",
					"UNIT-01 SHUTDOWN  //  OPERATION FAILED")


func add_shake(amount: float) -> void:
	shake = maxf(shake, amount)


## Freeze the whole game for a beat on big impacts. Combat scripts trigger it
## via get_tree().call_group("main", "hit_stop", seconds).
func hit_stop(duration: float, frozen_scale: float = 0.05) -> void:
	if hit_stop_active or match_over:
		return
	hit_stop_active = true
	Engine.time_scale = frozen_scale
	# real-time timer: unaffected by the time_scale it is timing
	await get_tree().create_timer(duration, true, false, true).timeout
	Engine.time_scale = 1.0
	hit_stop_active = false


func _on_berserk() -> void:
	add_shake(22.0)
	hud.flash_message("UNIT-01 SIGNAL LOST", "... UNIT-01 HAS GONE BERSERK", 3.0)


func _on_eva_died() -> void:
	_finish(false, "UNIT-01 SILENT", "PILOT SIGNAL LOST  //  OPERATION FAILED")


func _on_angel_defeated() -> void:
	if match_over:
		return
	add_shake(25.0)
	hit_stop(0.45)
	await get_tree().create_timer(1.2).timeout
	_finish(true, "PATTERN BLUE ELIMINATED",
			"TARGET SILENT  //  FINAL SYNC RATIO %.1f%%" % eva.sync_ratio)


func _finish(won: bool, title: String, sub: String) -> void:
	if match_over:
		return
	match_over = true
	hud.show_result(won, title, sub)
	get_tree().paused = true


# -- placeholder arena & backdrop ---------------------------------------------

func _build_arena() -> void:
	var width := ARENA_HALF_WIDTH * 2.0
	# floor
	_add_static_rect(Vector2(0.0, FLOOR_Y + 100.0), Vector2(width + 800.0, 200.0))
	# side walls
	_add_static_rect(Vector2(-ARENA_HALF_WIDTH - 50.0, -300.0), Vector2(100.0, 2000.0))
	_add_static_rect(Vector2(ARENA_HALF_WIDTH + 50.0, -300.0), Vector2(100.0, 2000.0))


func _add_static_rect(pos: Vector2, size: Vector2) -> void:
	var body := StaticBody2D.new()
	body.position = pos
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = size
	shape.shape = rect
	body.add_child(shape)
	add_child(body)


func _build_background() -> void:
	# night sky
	_add_color_rect(Vector2(-2900.0, -2100.0), Vector2(5800.0, 3200.0),
			Color(0.055, 0.06, 0.11))
	# moon
	var moon := Polygon2D.new()
	var pts := PackedVector2Array()
	for i in 24:
		var ang := TAU * float(i) / 24.0
		pts.append(Vector2(cos(ang), sin(ang)) * 110.0)
	moon.polygon = pts
	moon.color = Color(0.85, 0.85, 0.8, 0.9)
	moon.position = Vector2(700.0, -520.0)
	add_child(moon)
	# tokyo-3 skyline silhouettes
	var rng := RandomNumberGenerator.new()
	rng.seed = 3  # stable skyline between runs
	var x := -ARENA_HALF_WIDTH - 400.0
	while x < ARENA_HALF_WIDTH + 400.0:
		var w := rng.randf_range(90.0, 220.0)
		var h := rng.randf_range(180.0, 620.0)
		_add_color_rect(Vector2(x, FLOOR_Y - h), Vector2(w, h),
				Color(0.085, 0.095, 0.15))
		x += w + rng.randf_range(20.0, 90.0)
	# ground slab
	_add_color_rect(Vector2(-2900.0, FLOOR_Y), Vector2(5800.0, 600.0),
			Color(0.12, 0.12, 0.14))


func _add_color_rect(pos: Vector2, size: Vector2, color: Color) -> void:
	var rect := ColorRect.new()
	rect.position = pos
	rect.size = size
	rect.color = color
	add_child(rect)
