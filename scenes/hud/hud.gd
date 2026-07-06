class_name Hud
extends CanvasLayer
## NERV-styled combat HUD, built entirely in code so there is no scene layout
## to maintain. Polls the match state every frame instead of wiring dozens of
## signals. Colors follow the MAGI terminal look: orange on black.

const ORANGE := Color(1.0, 0.48, 0.0)
const GREEN := Color(0.35, 1.0, 0.5)
const RED := Color(0.95, 0.15, 0.2)
const DIM := Color(0.75, 0.75, 0.78)

# untyped on purpose: the HUD reads whatever match/pilot/target it's given
var main = null
var eva = null
var boss = null

var hp_bar: ProgressBar
var sync_label: Label
var power_label: Label
var at_bar: ProgressBar
var core_bar: ProgressBar
var msg_label: Label
var sub_label: Label
var overlay: ColorRect

var msg_t := 0.0
var clock := 0.0
var result_shown := false


func setup(main_node: Node, eva_node: Node, boss_node: Node) -> void:
	main = main_node
	eva = eva_node
	boss = boss_node


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	layer = 10

	# darkening overlay for the result screen
	overlay = ColorRect.new()
	overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	overlay.color = Color(0.0, 0.0, 0.0, 0.55)
	overlay.visible = false
	add_child(overlay)

	# left block: pilot readout
	var left := VBoxContainer.new()
	left.position = Vector2(24.0, 20.0)
	left.add_theme_constant_override("separation", 4)
	add_child(left)
	left.add_child(_make_label("EVA UNIT-01", ORANGE, 18))
	hp_bar = _make_bar(GREEN)
	left.add_child(hp_bar)
	sync_label = _make_label("SYNC RATIO 40.0%", DIM, 15)
	left.add_child(sync_label)
	power_label = _make_label("UMBILICAL 05:00", Color.WHITE, 26)
	left.add_child(power_label)

	# right block: target readout
	var right := VBoxContainer.new()
	right.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	right.offset_left = -388.0
	right.offset_right = -24.0
	right.offset_top = 20.0
	right.add_theme_constant_override("separation", 4)
	add_child(right)
	right.add_child(_make_label("TARGET: SACHIEL // PATTERN BLUE", ORANGE, 18))
	var at_title := _make_label("AT FIELD", DIM, 13)
	right.add_child(at_title)
	at_bar = _make_bar(ORANGE)
	right.add_child(at_bar)
	right.add_child(_make_label("CORE", DIM, 13))
	core_bar = _make_bar(RED)
	right.add_child(core_bar)

	# center messages
	msg_label = _make_label("", ORANGE, 44)
	msg_label.set_anchors_preset(Control.PRESET_TOP_WIDE)
	msg_label.offset_top = 150.0
	msg_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(msg_label)
	sub_label = _make_label("", Color.WHITE, 20)
	sub_label.set_anchors_preset(Control.PRESET_TOP_WIDE)
	sub_label.offset_top = 215.0
	sub_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(sub_label)

	# controls hint
	var hint := _make_label(
			"A/D MOVE   SPACE JUMP   SHIFT DASH (I-FRAMES)   J ATTACK   K PROG KNIFE (CORE EXPOSED)   R RESTART",
			Color(1.0, 1.0, 1.0, 0.35), 13)
	hint.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	hint.offset_top = -36.0
	hint.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	add_child(hint)


func _process(delta: float) -> void:
	if eva == null or boss == null or main == null:
		return
	clock += delta

	hp_bar.max_value = eva.max_hp
	hp_bar.value = eva.hp
	if eva.berserk_t > 0.0:
		sync_label.text = "SYNC RATIO %.1f%%  //  BERSERK" % eva.sync_ratio
		sync_label.add_theme_color_override("font_color", RED)
	else:
		sync_label.text = "SYNC RATIO %.1f%%" % eva.sync_ratio
		sync_label.add_theme_color_override("font_color", DIM)

	if not main.on_battery:
		var s := int(maxf(0.0, main.external_power))
		power_label.text = "UMBILICAL %02d:%02d" % [int(s / 60.0), s % 60]
		power_label.add_theme_color_override(
				"font_color", Color.WHITE if s > 60 else ORANGE)
		power_label.visible = true
	else:
		power_label.text = "BATTERY %04.1f" % maxf(0.0, main.battery)
		power_label.add_theme_color_override("font_color", RED)
		power_label.visible = fmod(clock, 0.5) < 0.35  # alarm blink

	at_bar.max_value = boss.at_field_max
	at_bar.value = boss.at_field
	core_bar.max_value = boss.CORE_HP_MAX
	core_bar.value = boss.core_hp

	if not result_shown:
		msg_t = maxf(0.0, msg_t - delta)
		if msg_t <= 0.0:
			msg_label.text = ""
			sub_label.text = ""


func flash_message(title: String, sub: String, duration: float) -> void:
	if result_shown:
		return
	msg_label.text = title
	sub_label.text = sub
	msg_t = duration


func show_result(won: bool, title: String, sub: String) -> void:
	result_shown = true
	overlay.visible = true
	msg_label.text = title
	msg_label.add_theme_color_override("font_color", GREEN if won else RED)
	sub_label.text = sub + "\n\n[R] RESTART"


# -- widget factory -----------------------------------------------------------

func _make_label(text: String, color: Color, size: int) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_color_override("font_color", color)
	label.add_theme_font_size_override("font_size", size)
	return label


func _make_bar(fill_color: Color) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.show_percentage = false
	bar.custom_minimum_size = Vector2(360.0, 18.0)
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0.0, 0.0, 0.0, 0.55)
	bg.border_color = Color(1.0, 1.0, 1.0, 0.25)
	bg.set_border_width_all(1)
	bar.add_theme_stylebox_override("background", bg)
	var fg := StyleBoxFlat.new()
	fg.bg_color = fill_color
	bar.add_theme_stylebox_override("fill", fg)
	return bar
