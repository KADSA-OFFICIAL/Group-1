extends Control
## 크레딧 창(#865). 타이틀 오른쪽 아래 "크레딧" 버튼이 연다.
##
## 내용은 아래 `SECTIONS` 표 하나가 쥔다 — 제목 한 줄 + 줄 목록. 사람·에셋이 바뀌면 여기만
## 고치면 되고, 저장소의 `CREDITS.md`(파일 단위 표)도 같이 고친다. 새 글자(이름 등)를 넣으면
## 글꼴 서브셋을 다시 굽는다(`python3 tools/gen_font_subsets.py`, #853) — 안 그러면 네모로 깨진다.
##
## 맨 아래 엔진 고지는 의무다 — Godot은 MIT라 배포하는 게임이 라이선스 전문을 실어야 하고,
## 엔진에 들어 있는 FreeType·ENet·Mbed TLS도 고지를 요구한다. 전부 엔진에서 읽어 오므로
## (`Engine.get_license_text()`·`get_copyright_info()`) 엔진 버전을 올려도 손댈 것이 없다.
##
## 열려 있는 동안 포커스는 닫기 버튼에만 있고 ↑/↓는 본문을 굴린다. 아래 타이틀 버튼의
## 포커스·클릭 차단은 여는 쪽이 맡는다(`main_menu.gd`, 설정창 #781과 같은 방식).

## 닫힐 때 쏜다 — 연 쪽이 포커스를 되돌려 받는다.
signal closed

## 한 번 누를 때 굴리는 양(px).
const SCROLL_STEP := 72

const SECTIONS := [
	["만든 사람", [
		"기획 — 김근형",
		"프로그래밍 — 윤준서 · 이원재",
		"디자인 — 고범서 · 정해원",
	]],
	["그림", [
		"Haunted School Tiles — Thurraya (CC BY-NC 4.0)",
		"Top Down Pixel Art Horror — AnisAous",
	]],
	["소리", [
		"Horror Sound Pack — Phlegmlee (CC0 1.0)",
		"Free Horror SFX vol.1 — Liminal Games (CC0 1.0)",
	]],
	["글꼴", [
		"East Sea Dokdo · Yeon Sung · Noto Sans KR",
		"SIL Open Font License 1.1",
	]],
]

const NOTE := "이 밖의 그림·소리·음악은 팀이 직접 만들었습니다. 학교 프로젝트(비상업)입니다."

const TITLE_FONT := preload("res://assets/fonts/YeonSung-Regular.ttf")
const BODY_FONT := preload("res://assets/fonts/NotoSansKR-VF.ttf")
const HEADING_COLOR := Color(0.91, 0.86, 0.75)
const HEADING_SHADOW := Color(0.42, 0.07, 0.06)
const LINE_COLOR := Color(0.86, 0.82, 0.74)
const DIM_COLOR := Color(0.55, 0.52, 0.47)

@onready var _close_button: Button = %CloseButton
@onready var _scroll: ScrollContainer = %Scroll
@onready var _body: VBoxContainer = %Body

var is_open: bool = false


func _ready() -> void:
	visible = false
	_close_button.pressed.connect(close)
	# 포커스는 닫기 버튼 하나뿐이다 — 방향키가 아래 화면으로 새지 않게 이웃을 자기로 둔다.
	for side in ["focus_neighbor_top", "focus_neighbor_bottom", "focus_neighbor_left", "focus_neighbor_right"]:
		_close_button.set(side, _close_button.get_path())
	_close_button.mouse_entered.connect(_close_button.grab_focus)
	_build()


func _unhandled_input(event: InputEvent) -> void:
	if is_open and event.is_action_pressed("ui_cancel"):
		close()
		get_viewport().set_input_as_handled()


## ↑/↓는 GUI보다 먼저 받는다 — 늦으면 닫기 버튼의 포커스 이동이 먼저 먹어 버린다
## (`_unhandled_input`까지 안 내려온다).
func _input(event: InputEvent) -> void:
	if not is_open:
		return
	if event.is_action_pressed("ui_down", true) or event.is_action_pressed("move_down", true):
		scroll_by(SCROLL_STEP)
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("ui_up", true) or event.is_action_pressed("move_up", true):
		scroll_by(-SCROLL_STEP)
		get_viewport().set_input_as_handled()


func open() -> void:
	if is_open:
		return
	is_open = true
	visible = true
	_scroll.scroll_vertical = 0
	_close_button.grab_focus()


func close() -> void:
	if not is_open:
		return
	is_open = false
	visible = false
	Sfx.play(&"ui_click")
	closed.emit()


func scroll_by(amount: int) -> void:
	_scroll.scroll_vertical += amount


## 본문 전체를 한 문자열로 — 스모크가 내용을 확인할 때 쓴다.
func body_text() -> String:
	var parts: PackedStringArray = []
	for label in _body.find_children("*", "Label", true, false):
		parts.append((label as Label).text)
	return "\n".join(parts)


func _build() -> void:
	for section in SECTIONS:
		_body.add_child(_heading(section[0]))
		for line in section[1]:
			_body.add_child(_line(line, LINE_COLOR, 20))
		_body.add_child(_gap(14))

	_body.add_child(_heading("엔진"))
	_body.add_child(_line("Godot Engine — MIT License", LINE_COLOR, 20))
	_body.add_child(_line(Engine.get_license_text().strip_edges(), DIM_COLOR, 14, true))
	_body.add_child(_gap(10))
	_add_third_party()
	_body.add_child(_gap(18))
	_body.add_child(_line(NOTE, DIM_COLOR, 16))


## 엔진에 들어 있는 구성 요소 중 고지가 필요한 것(Godot 문서 "Complying with licenses").
## FreeType은 정해진 문구 한 줄, ENet(Expat)·Mbed TLS(Apache-2.0)는 저작권 줄 + 라이선스 전문.
## 연도·문구는 엔진에서 읽어 엔진을 올려도 맞는다.
func _add_third_party() -> void:
	var licenses := Engine.get_license_info()
	for info in Engine.get_copyright_info():
		var component := String(info.get("name", ""))
		var key := component.to_lower()
		if not (key.contains("freetype") or key == "enet" or key.contains("mbed tls")):
			continue
		for part in info.get("parts", []):
			var copyright := ", ".join(PackedStringArray(part.get("copyright", [])))
			var license := String(part.get("license", ""))
			if key.contains("freetype"):
				var year := copyright.get_slice(",", 0)
				_body.add_child(_line("Portions of this software are copyright © %s The FreeType Project (www.freetype.org). All rights reserved." % year, DIM_COLOR, 15, true))
			else:
				_body.add_child(_line("%s — © %s (%s)" % [component, copyright, license], DIM_COLOR, 15, true))
				if licenses.has(license):
					_body.add_child(_line(String(licenses[license]).strip_edges(), DIM_COLOR, 13, true))
			_body.add_child(_gap(8))


func _heading(text: String) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_override("font", TITLE_FONT)
	label.add_theme_font_size_override("font_size", 30)
	label.add_theme_color_override("font_color", HEADING_COLOR)
	label.add_theme_color_override("font_shadow_color", HEADING_SHADOW)
	label.add_theme_constant_override("shadow_offset_x", 2)
	label.add_theme_constant_override("shadow_offset_y", 2)
	return label


## 한국어 줄은 자동 줄바꿈을 안 건다 — 한글 음절 사이에서 끊긴다(#770). 짧게 쓴다.
## 영어 전문(엔진 라이선스)만 단어 단위로 접는다.
func _line(text: String, color: Color, size: int, wrap: bool = false) -> Label:
	var label := Label.new()
	label.text = text
	label.add_theme_font_override("font", BODY_FONT)
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	if wrap:
		label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		label.custom_minimum_size.x = 1.0
	return label


func _gap(height: int) -> Control:
	var gap := Control.new()
	gap.custom_minimum_size = Vector2(0, height)
	return gap
