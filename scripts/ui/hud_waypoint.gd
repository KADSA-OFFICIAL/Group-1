extends Control

## 화면 위 방향 표시(#478) — 월드의 한 곳을 화면에서 가리킨다.
##
## 도입부에서 숨을 캐비넷을 알려 주려고 만들었다. 예전에는 월드 안의
## 상호작용 표시(`Mark_HideArtCabinet`)를 부풀렸는데, 그 표시가 **월드에 있다는
## 것이 문제였다**: 미술실은 폭 1100px이고 시작 지점(300, 700)에서 캐비넷
## (76, 450)이 화면 밖일 수 있고, 화면 안이어도 `WallFade` 마스크가 플레이어
## 에게서 389px 밖을 완전히 검게 칠하므로 **어둠 속에서 부푼다.**
##
## 여기는 HUD(CanvasLayer 3)라 어둠도 마스크도 안 탄다. 목표가 화면 밖이면
## 가장자리에 붙고 화살표로 방향을 알린다.

## 화면 가장자리에서 이만큼 떨어뜨린다.
const MARGIN := 64.0
## 가장자리에 붙었다고 볼 여유. 이보다 안쪽이면 "화면 안"이라 화살표를 안 쓴다.
const EDGE_SLACK := 2.0
const PULSE_TIME := 0.55
const PULSE_ALPHA := 0.45

@onready var marker: Control = $Marker
@onready var arrow_label: Label = $Marker/Row/Arrow
@onready var text_label: Label = $Marker/Row/Text

var _target: Vector2 = Vector2.ZERO
var _tracking: bool = false
var _pulse: Tween = null


func _ready() -> void:
	visible = false
	set_process(false)


## 월드 좌표 한 곳을 가리키기 시작한다.
func show_at(world_position: Vector2, text: String = "") -> void:
	_target = world_position
	_tracking = true
	text_label.text = text
	text_label.visible = not text.is_empty()
	visible = true
	set_process(true)
	_start_pulse()
	_update()


func clear() -> void:
	_tracking = false
	visible = false
	set_process(false)
	if _pulse != null:
		_pulse.kill()
		_pulse = null
	modulate.a = 1.0


## 층을 옮기거나 죽으면 HUD는 살아남지만 가리킬 곳은 사라진다 — 남겨 두면
## 다음 층 화면에 표시가 붙박인다.
func _exit_tree() -> void:
	clear()


func _start_pulse() -> void:
	if _pulse != null:
		_pulse.kill()
	modulate.a = 1.0
	_pulse = create_tween().set_loops()
	_pulse.tween_property(self, "modulate:a", PULSE_ALPHA, PULSE_TIME) \
		.set_trans(Tween.TRANS_SINE)
	_pulse.tween_property(self, "modulate:a", 1.0, PULSE_TIME) \
		.set_trans(Tween.TRANS_SINE)


func _process(_delta: float) -> void:
	if _tracking:
		_update()


func _update() -> void:
	var vp := get_viewport()
	if vp == null:
		return
	# 월드 → 화면. HUD는 CanvasLayer라 제 변환이 없으므로 뷰포트의 것을 쓴다.
	var screen: Vector2 = vp.get_canvas_transform() * _target
	var rect := vp.get_visible_rect()
	var min_x := rect.position.x + MARGIN
	var max_x := rect.end.x - MARGIN
	var min_y := rect.position.y + MARGIN
	var max_y := rect.end.y - MARGIN

	var clamped := Vector2(clampf(screen.x, min_x, max_x), clampf(screen.y, min_y, max_y))
	marker.position = clamped - marker.size * 0.5

	# 가장자리에 붙었으면 어느 쪽으로 밀렸는지가 곧 방향이다 — 회전 없이
	# 글자 하나로 알린다. 화면 안이면 그 자리를 짚는 표시만 둔다.
	var dx: float = screen.x - clamped.x
	var dy: float = screen.y - clamped.y
	if absf(dx) <= EDGE_SLACK and absf(dy) <= EDGE_SLACK:
		arrow_label.text = "◆"
	elif absf(dx) > absf(dy):
		arrow_label.text = "◀" if dx < 0.0 else "▶"
	else:
		arrow_label.text = "▲" if dy < 0.0 else "▼"
