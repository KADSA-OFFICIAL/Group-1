extends Node

## 음량 설정(#783). autoload로 둔다 — 설정창은 타이틀에서 열리지만 음량은 씬을
## 넘어 유지돼야 하고, 시작할 때 저장값을 곧바로 적용해야 타이틀 음악이 처음부터
## 고른 크기로 울린다.
##
## **버스가 둘이다**: `Music`(앰비언트·추격 BGM·타이틀/프롤로그/엔딩 테마·운동장
## 바람)과 `SFX`(`Sfx.play()` 효과음 + 수위의 위치 소리 + 점프스케어). 예전에는
## `Master` 하나뿐이라 음악만 줄이고 수위 발소리(위치 단서)는 그대로 둘 수 없었다.
## `default_bus_layout.tres`를 두지 않고 여기서 만든다 — 한 곳에서 이름·연결을
## 쥐고, 파일이 없을 때(에디터에서 한 씬만 돌릴 때)도 버스가 있다.
##
## **`Sfx`보다 앞에 선언한다.** `Sfx._ready()`가 플레이어에 버스 이름을 적는데,
## 이름만 적어도 재생할 때 찾으므로 순서가 틀려도 죽지는 않는다 — 다만 그때까지
## 버스가 없으면 조용히 `Master`로 떨어진다.
##
## 단계는 0~10(`MAX_LEVEL`)이고 **10이 지금까지의 크기(0dB)**다. 곡마다 `Sfx`의
## `VOLUMES`·`THEME_DB`로 맞춘 균형은 그 아래에서 그대로 유지된다 — 버스는 그 위에
## 일괄로 얹힌다. 0이면 음량이 아니라 **버스를 음소거**한다(`linear_to_db(0)`은
## -inf라 믹서가 NaN을 낼 수 있다).

## 단계가 바뀌면 알린다(설정창 막대가 따라온다). 저장값 복원도 같은 길이다.
signal changed(kind: StringName, level: int)

const SETTINGS_PATH := "user://settings.cfg"
const SECTION := "audio"

const MUSIC := &"music"
const SFX := &"sfx"
const MUSIC_BUS := &"Music"
const SFX_BUS := &"SFX"

const MAX_LEVEL := 10
const DEFAULT_LEVEL := 10

## 헤드리스(CI·스모크)에는 소리 장치가 없고 사용자 파일을 건드리면 안 되므로,
## 거기서는 단계만 쥐고 파일은 읽지도 쓰지도 않는다(`DisplayMode`와 같은 규약).
var _levels: Dictionary = {MUSIC: DEFAULT_LEVEL, SFX: DEFAULT_LEVEL}


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_ensure_bus(MUSIC_BUS)
	_ensure_bus(SFX_BUS)
	if not _headless():
		var cfg := ConfigFile.new()
		if cfg.load(SETTINGS_PATH) == OK:
			for kind: StringName in [MUSIC, SFX]:
				_levels[kind] = clampi(int(cfg.get_value(SECTION, String(kind), DEFAULT_LEVEL)), 0, MAX_LEVEL)
	for kind: StringName in [MUSIC, SFX]:
		_apply(kind)


func level(kind: StringName) -> int:
	return int(_levels.get(kind, DEFAULT_LEVEL))


## `persist`가 거짓이면 파일에 안 쓴다(저장값을 복원하는 중이다).
func set_level(kind: StringName, value: int, persist: bool = true) -> void:
	if not _levels.has(kind):
		return
	_levels[kind] = clampi(value, 0, MAX_LEVEL)
	_apply(kind)
	if persist and not _headless():
		_save(kind)
	changed.emit(kind, _levels[kind])


func bus_name(kind: StringName) -> StringName:
	return MUSIC_BUS if kind == MUSIC else SFX_BUS


func _apply(kind: StringName) -> void:
	var idx := AudioServer.get_bus_index(bus_name(kind))
	if idx < 0:
		return
	var lv: int = _levels[kind]
	AudioServer.set_bus_mute(idx, lv <= 0)
	AudioServer.set_bus_volume_db(idx, linear_to_db(float(lv) / MAX_LEVEL) if lv > 0 else 0.0)


func _ensure_bus(bus: StringName) -> void:
	if AudioServer.get_bus_index(bus) >= 0:
		return
	AudioServer.add_bus()
	var idx := AudioServer.bus_count - 1
	AudioServer.set_bus_name(idx, bus)
	AudioServer.set_bus_send(idx, &"Master")


func _save(kind: StringName) -> void:
	var cfg := ConfigFile.new()
	cfg.load(SETTINGS_PATH)  # 없으면 비어 있는 채로 둔다 — 전체화면 등 다른 키를 지우지 않는다.
	cfg.set_value(SECTION, String(kind), _levels[kind])
	cfg.save(SETTINGS_PATH)


func _headless() -> bool:
	return DisplayServer.get_name() == "headless"
