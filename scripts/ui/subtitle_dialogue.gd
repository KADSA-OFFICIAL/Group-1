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

# 화자별 스탠딩 일러스트(#280). 컷신에서만 쓴다 — 본편 HUD는 화면을 가리면 안 된다.
# 표에 없는 화자(수위·지문)는 그림 없이 지나간다.
const PORTRAITS: Dictionary = {
	"이설": preload("res://assets/portraits/iseol.png"),
}
const PORTRAIT_FADE := 0.22
# 말하지 않는 동안에는 **끄지 않고 어둡게** 둔다 — 껐다 켜면 한 장면 안에서
# 그림이 깜빡인다. 지문이 대사 사이에 자주 끼는 프롤로그에서 특히 심하다.
const PORTRAIT_DIM := Color(0.40, 0.42, 0.48, 1.0)
# 스탠딩이 서는 폭(화면 **오른쪽**, #286). 화자가 바뀔 때마다 여백을 움직이면
# 글이 좌우로 튀므로, 컷신에서는 스탠딩이 아직 없어도 이 폭을 늘 비워 둔다.
const PORTRAIT_TEXT_MARGIN := 430.0

# 감춰져 있던 자막이 처음 뜰 때의 페이드(#436). 하단 그라디언트(Shade)가 한 프레임에
# 튀어나오면, 1.7초에 걸쳐 천천히 드러나는 장면 배경과 부딪혀 대화창이 화면에 붙여
# 놓은 UI로 보인다. 선택창 페이드(intro.gd의 CHOICE_FADE_SECONDS)와 같은 길이다.
const APPEAR_FADE := 0.4

const FONT: FontFile = preload("res://assets/fonts/NotoSansKR-VF.ttf")
const WGHT_TAG := 0x77676874  # OpenType 가변 축 'wght'

## 하단 그라디언트 농도. 컷신은 1.0(시안 그대로), 본편 HUD는 게임 화면을 덜 가리게 낮춘다.
@export_range(0.0, 1.0, 0.05) var shade_alpha: float = 1.0

## 스탠딩 일러스트를 쓸지. 컷신만 켠다(#280) — 본편 HUD 알림에 사람 그림이 서면
## 게임 화면을 가린다. 켜면 자막 왼쪽에 스탠딩 자리를 비운다.
@export var portraits_enabled: bool = false

@onready var shade: TextureRect = $Shade
@onready var lines_box: VBoxContainer = $Lines
@onready var name_label: Label = $Lines/NameLabel
@onready var text_label: Label = $Lines/TextLabel
@onready var portrait: TextureRect = $Portrait

var typing: bool = false
var typing_tween: Tween
var portrait_tween: Tween
var appear_tween: Tween

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

	# 스탠딩이 서는 쪽(오른쪽) 여백만 넓힌다. 왼쪽은 그대로라 글이 살짝 왼쪽으로
	# 치우치는데, 사람 그림 옆에 글이 붙는 것이 가운데 정렬보다 자연스럽다.
	lines_box.offset_left = margin_x
	lines_box.offset_right = -(maxf(margin_x, PORTRAIT_TEXT_MARGIN) if portraits_enabled else margin_x)
	lines_box.offset_bottom = -(MONOLOGUE_MARGIN_BOTTOM if monologue else SPEECH_MARGIN_BOTTOM)

	name_label.visible = not monologue
	name_label.text = speaker
	name_label.add_theme_color_override("font_color", _name_color(emotion))

	text_label.add_theme_font_size_override("font_size", MONOLOGUE_FONT_SIZE if monologue else SPEECH_FONT_SIZE)
	text_label.add_theme_constant_override("line_spacing", MONOLOGUE_LINE_SPACING if monologue else SPEECH_LINE_SPACING)
	text_label.add_theme_color_override("font_color", MONOLOGUE_COLOR if monologue else SPEECH_COLOR)
	text_label.text = text

	_update_portrait(speaker)
	# 감춰져 있다가 처음 뜨는 줄에서만 페이드한다 — 같은 장면에서 줄이 넘어갈 때는
	# 이미 떠 있으므로 다시 걸면 글을 읽는 내내 화면이 깜빡인다.
	var appearing := not visible
	visible = true
	if appearing:
		_fade_in()
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
	# 장면이 바뀌면 스탠딩도 없앤다 — 다음 장면은 다른 장소다.
	if portrait_tween != null:
		portrait_tween.kill()
	portrait.texture = null
	portrait.visible = false
	# 페이드 도중에 비워질 수 있다 — 트윈을 죽이고 농도를 되돌려 두지 않으면
	# 다음에 뜰 때 반쯤 투명한 채로 남는다.
	if appear_tween != null:
		appear_tween.kill()
	modulate.a = 1.0
	visible = false


## 장면 자막처럼 대화창 바깥에 있지만 같은 서체를 써야 하는 Label에 본문 서체를 입힌다.
func apply_font(label: Label, weight: float = 400.0) -> void:
	label.add_theme_font_override("font", _weighted_font(weight, 0))


## 자막판 전체를 투명에서 띄운다. Shade만 페이드하면 검은 띠가 차오르는 동안
## 화자 이름과 첫 글자가 허공에 먼저 떠 있게 되므로, 그림자와 글을 함께 올린다.
## Shade 자체의 농도(shade_alpha)는 건드리지 않는다 — 본편 HUD는 그 값이 낮다.
func _fade_in() -> void:
	if appear_tween != null:
		appear_tween.kill()
	modulate.a = 0.0
	appear_tween = create_tween()
	appear_tween.tween_property(self, "modulate:a", 1.0, APPEAR_FADE)


func _update_portrait(speaker: String) -> void:
	if not portraits_enabled:
		return
	if PORTRAITS.has(speaker):
		portrait.texture = PORTRAITS[speaker]
		_fade_portrait(Color.WHITE)
	elif portrait.texture != null:
		_fade_portrait(PORTRAIT_DIM)


func _fade_portrait(target: Color) -> void:
	if portrait_tween != null:
		portrait_tween.kill()
	if not portrait.visible:
		portrait.modulate = Color(target, 0.0)   # 처음 등장은 투명에서 떠오른다
		portrait.visible = true
	portrait_tween = create_tween()
	portrait_tween.tween_property(portrait, "modulate", target, PORTRAIT_FADE)


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
