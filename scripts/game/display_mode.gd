extends Node

## 전체화면 전환(#778). autoload로 둔다 — F11이 어느 씬에서나 먹어야 하고, 선택이
## 씬을 넘어 유지돼야 한다.
##
## **`WindowFit` 뒤에 선언한다.** 시작할 때 `WindowFit`이 창을 화면에 맞춘 **다음에**
## 전체화면으로 들어가야, 전체화면을 풀었을 때 Godot이 돌려놓는 "이전 창 크기"가
## 맞춘 크기가 된다(순서가 반대면 기본 1600x900 px로 돌아가 맥에서 800x450pt로 뜬다, #679).
##
## 트리가 멈춘 중(일시정지 메뉴·현관 선택지)에도 F11이 먹어야 하므로
## `PROCESS_MODE_ALWAYS`다. 전환은 창만 건드리고 트리 멈춤은 만지지 않는다.
##
## 논리 화면(1600x900)은 그대로다 — `stretch/mode = canvas_items`라 창이 커져도
## HUD·카메라 좌표는 안 바뀐다.

## 상태가 바뀌면 알린다(버튼 글자가 따라 바뀐다). F11·버튼·저장값 복원 모두 같은 길이다.
signal changed(fullscreen: bool)

const SETTINGS_PATH := "user://settings.cfg"
const SECTION := "display"
const KEY := "fullscreen"

## 헤드리스(CI·스모크)에는 창이 없어 `DisplayServer`가 모드를 안 바꾼다 — 그때를
## 위해 상태를 따로 쥐고, 그 상태는 파일에도 쓰지 않는다.
var _fullscreen: bool = false


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	if _headless():
		return
	var cfg := ConfigFile.new()
	if cfg.load(SETTINGS_PATH) == OK:
		set_fullscreen(bool(cfg.get_value(SECTION, KEY, false)), false)
	else:
		_fullscreen = _window_is_fullscreen()


func _input(event: InputEvent) -> void:
	if event.is_action_pressed(&"fullscreen") and not event.is_echo():
		toggle()
		get_viewport().set_input_as_handled()


func is_fullscreen() -> bool:
	# 창 테두리의 전체화면 단추(macOS 초록 단추)로 바꾼 것도 따라가려고 창을 직접 본다.
	if _headless():
		return _fullscreen
	return _window_is_fullscreen()


func toggle() -> void:
	set_fullscreen(not is_fullscreen())


## `persist`가 거짓이면 파일에 안 쓴다(저장값을 복원하는 중이다).
func set_fullscreen(on: bool, persist: bool = true) -> void:
	_fullscreen = on
	if not _headless():
		var want := DisplayServer.WINDOW_MODE_FULLSCREEN if on \
			else DisplayServer.WINDOW_MODE_WINDOWED
		if DisplayServer.window_get_mode() != want:
			DisplayServer.window_set_mode(want)
		if persist:
			_save(on)
	changed.emit(on)


## 메뉴 버튼 글자.
func button_text() -> String:
	return "전체화면: 켜짐" if is_fullscreen() else "전체화면: 꺼짐"


func _save(on: bool) -> void:
	var cfg := ConfigFile.new()
	cfg.load(SETTINGS_PATH)  # 없으면 비어 있는 채로 둔다 — 다른 키가 생기면 지우지 않는다.
	cfg.set_value(SECTION, KEY, on)
	cfg.save(SETTINGS_PATH)


func _window_is_fullscreen() -> bool:
	var mode := DisplayServer.window_get_mode()
	return mode == DisplayServer.WINDOW_MODE_FULLSCREEN \
		or mode == DisplayServer.WINDOW_MODE_EXCLUSIVE_FULLSCREEN


func _headless() -> bool:
	return DisplayServer.get_name() == "headless"
