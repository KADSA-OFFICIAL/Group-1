extends Control
## 설정창(#781). 타이틀 오른쪽 위 "설정" 버튼이 연다.
##
## 옵션은 셋이다 — 전체화면, 배경음악, 효과음. 전체화면 켜짐/꺼짐은 `DisplayMode`(#778)가
## 쥐고 있고 이 창은 그것을 부르고 글자만 맞춘다 — F11·창 테두리 단추로 바꿔도 글자가
## 따라오도록 `changed`를 받고, 열 때도 한 번 다시 읽는다(테두리 단추는 신호가 없다).
## 음량(#783)은 `AudioSettings`가 쥐고, 막대(`volume_bar.gd`)와 퍼센트 글자가 그 값을 따른다.
##
## 열려 있는 동안 키보드 포커스는 이 창의 컨트롤 넷(옵션 셋 + 닫기) 사이만 돈다. 아래 화면의 버튼으로
## 새면 Enter가 "게임 시작"을 눌러 버린다(방향키는 기하상 가장 가까운 버튼을 고른다).
## 아래 화면의 포커스·클릭 차단은 여는 쪽이 맡는다(`main_menu.gd`).

## 닫힐 때 쏜다 — 연 쪽이 포커스를 되돌려 받는다.
signal closed

@onready var _fullscreen_toggle: Button = %FullscreenToggle
@onready var _close_button: Button = %CloseButton
@onready var _music_bar: Control = %MusicBar
@onready var _sfx_bar: Control = %SfxBar
@onready var _music_percent: Label = %MusicPercent
@onready var _sfx_percent: Label = %SfxPercent

var is_open: bool = false


func _ready() -> void:
	visible = false
	_fullscreen_toggle.pressed.connect(_on_fullscreen_pressed)
	_close_button.pressed.connect(close)
	DisplayMode.changed.connect(_on_display_changed)
	_sync_fullscreen_text()
	_music_bar.value_changed.connect(_on_music_changed)
	_sfx_bar.value_changed.connect(_on_sfx_changed)
	AudioSettings.changed.connect(_on_audio_changed)
	_sync_audio()

	# 위에서 아래로 한 줄로 돌고(맨 아래에서 ↓는 맨 위로), 좌우로는 못 나간다. 막대는
	# ←/→를 스스로 먹지만(`volume_bar.gd`) 버튼에서 누른 ←/→가 새지 않게 이웃도 자기로 둔다.
	var order: Array[Control] = [_fullscreen_toggle, _music_bar, _sfx_bar, _close_button]
	for i in order.size():
		var c := order[i]
		c.focus_neighbor_top = order[posmod(i - 1, order.size())].get_path()
		c.focus_neighbor_bottom = order[posmod(i + 1, order.size())].get_path()
		c.focus_neighbor_left = c.get_path()
		c.focus_neighbor_right = c.get_path()
		# 마우스를 올린 컨트롤이 포커스를 가져간다 — 포커스가 곧 붉은 선·테두리라 안 그러면
		# 키보드로 고른 것과 마우스 아래 것이 둘 다 붉다(pause_menu.gd와 같은 이유).
		c.mouse_entered.connect(c.grab_focus)


func _unhandled_input(event: InputEvent) -> void:
	if is_open and event.is_action_pressed("ui_cancel"):
		close()
		get_viewport().set_input_as_handled()


func open() -> void:
	if is_open:
		return
	is_open = true
	visible = true
	_sync_fullscreen_text()
	_sync_audio()
	_fullscreen_toggle.grab_focus()


func close() -> void:
	if not is_open:
		return
	is_open = false
	visible = false
	Sfx.play(&"ui_click")
	closed.emit()


func _on_fullscreen_pressed() -> void:
	Sfx.play(&"ui_click")
	DisplayMode.toggle()


func _on_display_changed(_on: bool) -> void:
	_sync_fullscreen_text()


func _on_music_changed(value: int) -> void:
	AudioSettings.set_level(AudioSettings.MUSIC, value)


func _on_sfx_changed(value: int) -> void:
	AudioSettings.set_level(AudioSettings.SFX, value)
	# 효과음은 틀어져 있는 것이 없으니 바꿀 때 한 번 들려준다 — 배경음악은 재생 중이면
	# 막대를 만지는 순간 크기가 바뀌므로 따로 필요 없다.
	Sfx.play(&"ui_click")


func _on_audio_changed(_kind: StringName, _level: int) -> void:
	_sync_audio()


## 막대와 퍼센트를 `AudioSettings`에 맞춘다. 막대를 조용히 맞춰서(`set_value_silent`)
## 되돌려 쓰는 루프가 안 생긴다.
func _sync_audio() -> void:
	_music_bar.set_value_silent(AudioSettings.level(AudioSettings.MUSIC))
	_sfx_bar.set_value_silent(AudioSettings.level(AudioSettings.SFX))
	_music_percent.text = "%d%%" % (AudioSettings.level(AudioSettings.MUSIC) * 10)
	_sfx_percent.text = "%d%%" % (AudioSettings.level(AudioSettings.SFX) * 10)


func _sync_fullscreen_text() -> void:
	_fullscreen_toggle.text = DisplayMode.state_text()
