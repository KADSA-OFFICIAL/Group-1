class_name SubtitleDialogue
extends Control

## 자막형 대화창(#181) — 판·테두리·진행 힌트 없이 화자 이름과 대사만 남긴 표시.
## Claude Design 시안 "2D 공포 게임 대화 상자 / TURN 5"를 880x495 → 1600x900(배율 1.8182)으로
## 환산했다. 아래 상수 주석의 괄호 안 숫자가 시안 원본 값이다.
## 컷신(intro.tscn, ending.tscn)이 이 씬을 인스턴스해 show_line()으로 대사를 흘린다.
## 본편 HUD(hud.tscn)도 같은 씬을 써서 하단 알림을 낸다(#193) — 컷신과 달리 화면을
## 가리면 안 되므로 shade_alpha로 그라디언트만 옅게 깐다.
## 화자가 빈 문자열이면 지문·독백으로 보고, 이름 줄 없이 더 좁고 어둡게 표시한다 —
## 화자 있는 대사와의 구분은 오직 위치·크기·밝기로만 한다.

## 한 줄이 끝까지 찍혔을 때(또는 넘기기·비우기로 타이핑이 끝났을 때) 울린다.
## 붙잡힘 연출처럼 "대사를 다 보여준 뒤에" 진행해야 하는 쪽이 이걸 기다린다(#199).
signal typing_finished

const TYPING_SECONDS_PER_CHAR := 0.05

# 화자 있는 대사
const SPEECH_MARGIN_X := 138.0                       # (76)
const SPEECH_MARGIN_BOTTOM := 102.0                  # (56)
const SPEECH_FONT_SIZE := 33                         # (18)
const SPEECH_LINE_SPACING := 20                      # line-height 1.8
const SPEECH_COLOR := Color(0.918, 0.933, 0.914)     # #eaeee9

# 지문·독백
const MONOLOGUE_MARGIN_X := 255.0                    # (140)
const MONOLOGUE_MARGIN_BOTTOM := 116.0               # (64)
const MONOLOGUE_FONT_SIZE := 29                      # (16)
const MONOLOGUE_LINE_SPACING := 19                   # line-height 1.85
const MONOLOGUE_COLOR := Color(0.663, 0.698, 0.682)  # #a9b2ae

# 화자 이름
const NAME_FONT_SIZE := 20                           # (11)
const NAME_GLYPH_SPACING := 6                        # 자간 .28em
const NAME_COLOR := Color(0.624, 0.698, 0.682)       # #9fb2ae

const NAME_WEIGHT := 900.0
const TEXT_WEIGHT := 700.0

# 감정 태그는 이름 색과 타자 속도만 바꾼다 — 시안대로 공포 연출은 평상시와 동일하다.
const EMOTIONS: Dictionary = {
	"suspicion": {
		"name_color": Color(0.561, 0.690, 0.675),  # #8fb0ac
		"typing_scale": 1.25,                      # 타자 속도 −20%
	},
}

const FONT: FontFile = preload("res://assets/fonts/NotoSansKR-VF.ttf")
const WGHT_TAG := 0x77676874  # OpenType 가변 축 'wght'

## 하단 그라디언트 농도. 컷신은 1.0(시안 그대로), 본편 HUD는 게임 화면을 덜 가리게 낮춘다.
@export_range(0.0, 1.0, 0.05) var shade_alpha: float = 1.0

@onready var shade: TextureRect = $Shade
@onready var lines_box: VBoxContainer = $Lines
@onready var name_label: Label = $Lines/NameLabel
@onready var text_label: Label = $Lines/TextLabel

var typing: bool = false
var typing_tween: Tween

## 마지막 show_line()의 타이핑 소요 시간(초). 넘기는 입력이 없는 본편에서
## "타이핑이 끝나기 전에 자막이 사라지는" 일이 없도록 HUD가 표시 시간을 여기서 잰다.
var last_typing_seconds: float = 0.0


func _ready() -> void:
	shade.modulate.a = shade_alpha
	name_label.add_theme_font_override("font", _weighted_font(NAME_WEIGHT, NAME_GLYPH_SPACING))
	name_label.add_theme_font_size_override("font_size", NAME_FONT_SIZE)
	text_label.add_theme_font_override("font", _weighted_font(TEXT_WEIGHT, 0))
	clear()


## 대사 한 줄을 표시하고 타이핑을 시작한다. speaker가 비면 지문·독백으로 배치한다.
func show_line(speaker: String, text: String, emotion: String = "") -> void:
	var monologue := speaker.is_empty()
	var margin_x: float = MONOLOGUE_MARGIN_X if monologue else SPEECH_MARGIN_X

	lines_box.offset_left = margin_x
	lines_box.offset_right = -margin_x
	lines_box.offset_bottom = -(MONOLOGUE_MARGIN_BOTTOM if monologue else SPEECH_MARGIN_BOTTOM)

	name_label.visible = not monologue
	name_label.text = speaker
	name_label.add_theme_color_override("font_color", _name_color(emotion))

	text_label.add_theme_font_size_override("font_size", MONOLOGUE_FONT_SIZE if monologue else SPEECH_FONT_SIZE)
	text_label.add_theme_constant_override("line_spacing", MONOLOGUE_LINE_SPACING if monologue else SPEECH_LINE_SPACING)
	text_label.add_theme_color_override("font_color", MONOLOGUE_COLOR if monologue else SPEECH_COLOR)
	text_label.text = text

	visible = true
	_start_typing(emotion)


## 타이핑 중이면 남은 글자를 즉시 전부 표시한다. 실제로 건너뛰었으면 true.
func skip_typing() -> bool:
	if not typing:
		return false
	if typing_tween != null:
		typing_tween.kill()
	text_label.visible_characters = -1
	typing = false
	typing_finished.emit()
	return true


## 장면 전환 등으로 대사를 비운다 — 하단 그라디언트까지 같이 감춘다.
func clear() -> void:
	if typing_tween != null:
		typing_tween.kill()
	# 기다리던 쪽이 영영 깨어나지 못하는 일이 없도록, 도중에 비워도 신호는 낸다.
	if typing:
		typing = false
		typing_finished.emit()
	name_label.text = ""
	text_label.text = ""
	visible = false


## 장면 자막처럼 대화창 바깥에 있지만 같은 서체를 써야 하는 Label에 본문 서체를 입힌다.
func apply_font(label: Label, weight: float = 400.0) -> void:
	label.add_theme_font_override("font", _weighted_font(weight, 0))


func _start_typing(emotion: String) -> void:
	if typing_tween != null:
		typing_tween.kill()

	# 타이핑 효과: 왼쪽부터 한 글자씩 출력
	text_label.visible_characters = 0
	typing = true

	var total_chars := text_label.get_total_character_count()
	if total_chars == 0:
		total_chars = text_label.text.length()

	var seconds := total_chars * TYPING_SECONDS_PER_CHAR * _typing_scale(emotion)
	last_typing_seconds = seconds
	typing_tween = create_tween()
	typing_tween.tween_property(text_label, "visible_characters", total_chars, seconds)
	typing_tween.tween_callback(func() -> void:
		typing = false
		typing_finished.emit())


func _name_color(emotion: String) -> Color:
	if not EMOTIONS.has(emotion):
		return NAME_COLOR
	var color: Color = EMOTIONS[emotion]["name_color"]
	return color


func _typing_scale(emotion: String) -> float:
	if not EMOTIONS.has(emotion):
		return 1.0
	var scale_value: float = EMOTIONS[emotion]["typing_scale"]
	return scale_value


func _weighted_font(weight: float, glyph_spacing: int) -> FontVariation:
	var font := FontVariation.new()
	font.base_font = FONT
	# 가변 축 좌표를 정수 태그로 찾는 판본과 이름 문자열로 찾는 판본이 있어 셋 다 넣는다 —
	# 어느 쪽이 잡혀도 같은 값이라 결과는 같고, 하나도 안 잡히면 폰트 기본 굵기로 떨어진다.
	font.variation_opentype = {WGHT_TAG: weight, "weight": weight, "wght": weight}
	font.spacing_glyph = glyph_spacing
	return font
