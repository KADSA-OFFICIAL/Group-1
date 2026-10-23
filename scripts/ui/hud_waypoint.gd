extends Control

## 화면 위 방향 표시(#478, 화살표는 #688) — 월드의 한 곳을 화면에서 가리킨다.
##
## 도입부에서 숨을 캐비넷을 알려 주려고 만들었다. 예전에는 월드 안의
## 상호작용 표시(`Mark_HideArtCabinet`)를 부풀렸는데, 그 표시가 **월드에 있다는
## 것이 문제였다**: 미술실은 폭 1100px이고 시작 지점(300, 700)에서 캐비넷
## (76, 450)이 화면 밖일 수 있고, 화면 안이어도 `WallFade` 마스크가 플레이어
## 에게서 389px 밖을 완전히 검게 칠하므로 **어둠 속에서 부푼다.**
##
## 여기는 HUD(CanvasLayer 3)라 어둠도 마스크도 안 탄다.
##
## **화살표는 글자가 아니라 직접 그린다**(#688). 처음에는 `◀▶▲▼` 글자를 Label에
## 넣었는데, 폰트에 글리프가 없으면 네모로 깨지고 위·아래·왼쪽·오른쪽 네 방향뿐이라
## 대각선에 있는 목표는 방향이 틀렸다. 지금은 `_draw()`로 삼각 화살표를 그려
## 목표를 향해 **회전**시킨다.
##
## - 목표가 화면 밖: **플레이어에서 목표로 향하는 선**이 화면 가장자리(`MARGIN` 안쪽)와
##   만나는 점에 화살표가 선다. X·Y를 따로 clamp하면 위치가 모서리로 쏠려 방향이
##   그 자리에서 본 목표와 어긋난다.
## - 목표가 화면 안: 목표 위에서 아래를 가리킨다(위쪽 공간이 모자라면 아래에서 위로).

## 화면 가장자리에서 이만큼 떨어뜨린다.
const MARGIN := 64.0
const PULSE_TIME := 0.55
const PULSE_ALPHA := 0.45

## 화살표 크기. 길이는 꼭짓점에서 꼬리까지, 폭은 한쪽 날개까지의 거리다.
const ARROW_LENGTH := 44.0
const ARROW_HALF_WIDTH := 24.0
## 꼬리 가운데가 안쪽으로 파인 정도(길이에 대한 비율).
const ARROW_NOTCH := 0.32
const OUTLINE_WIDTH := 5.0
const ARROW_FILL := Color(1.0, 0.78, 0.32, 1.0)
const ARROW_OUTLINE := Color(0.0, 0.0, 0.0, 1.0)

## 목표가 화면 안일 때 화살표 끝이 목표에서 떨어지는 거리와 오르내림.
const ON_SCREEN_LIFT := 40.0
const BOB_PX := 6.0
const BOB_SPEED := 6.0

## 화살표와 문구 사이 간격, 문구가 화면 가장자리에서 떨어질 최소 거리.
const TEXT_GAP := 10.0
const TEXT_EDGE := 8.0

@onready var text_label: Label = $Text

var _target: Vector2 = Vector2.ZERO
var _tracking: bool = false
var _pulse: Tween = null
var _player: Node2D = null

## `_update()`가 매 프레임 정하고 `_draw()`가 읽는다.
var _anchor: Vector2 = Vector2.ZERO
var _angle: float = 0.0


func _ready() -> void:
	visible = false
	set_process(false)


## 월드 좌표 한 곳을 가리키기 시작한다.
func show_at(world_position: Vector2, text: String = "") -> void:
	_target = world_position
	_tracking = true
	_player = get_tree().get_first_node_in_group("player") as Node2D
	text_label.text = text
	text_label.visible = not text.is_empty()
	# 크기를 문구에 맞춘다. 안 줄이면 이전 문구의 크기가 남아 위치 계산이 어긋난다.
	text_label.reset_size()
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
	var canvas: Transform2D = vp.get_canvas_transform()
	var screen: Vector2 = canvas * _target
	var rect := vp.get_visible_rect()
	var inner := rect.grow(-MARGIN)

	if inner.has_point(screen):
		_place_on_screen(screen, inner)
	else:
		_place_at_edge(screen, canvas, rect, inner)
	_place_text(rect)
	queue_redraw()


## 목표가 화면 안 — 목표 위에서 아래를 가리킨다. 위에 자리가 없으면 아래에서 위로.
func _place_on_screen(screen: Vector2, inner: Rect2) -> void:
	var bob := sin(Time.get_ticks_msec() * 0.001 * BOB_SPEED) * BOB_PX
	var reach := ON_SCREEN_LIFT + ARROW_LENGTH * 0.5
	if screen.y - reach - BOB_PX >= inner.position.y:
		_angle = PI * 0.5
		_anchor = screen + Vector2(0.0, -reach + bob)
	else:
		_angle = -PI * 0.5
		_anchor = screen + Vector2(0.0, reach - bob)


## 목표가 화면 밖 — 플레이어에서 목표로 향하는 선이 가장자리와 만나는 점에 선다.
func _place_at_edge(screen: Vector2, canvas: Transform2D, rect: Rect2, inner: Rect2) -> void:
	# 기준점은 플레이어다. 카메라 한계 때문에 플레이어가 화면 한가운데에 없을 수
	# 있고, 걸어갈 방향은 화면 중심이 아니라 플레이어에서 본 방향이다.
	var origin := rect.get_center()
	if is_instance_valid(_player):
		origin = canvas * _player.global_position
	# 선의 출발점이 안쪽 사각형 밖이면 교차점이 정해지지 않으므로 안으로 끌어넣는다.
	origin = origin.clamp(inner.position, inner.end)

	var to_target := screen - origin
	if to_target.length_squared() < 0.0001:
		to_target = Vector2.DOWN
	var dir := to_target.normalized()
	_angle = dir.angle()
	_anchor = origin + dir * _exit_distance(origin, dir, inner)


## `origin`(안쪽 사각형 안)에서 `dir`로 나갈 때 사각형 경계까지의 거리.
## 가로·세로 경계 중 먼저 만나는 쪽이 답이다.
func _exit_distance(origin: Vector2, dir: Vector2, inner: Rect2) -> float:
	var reach := INF
	if dir.x > 0.0:
		reach = minf(reach, (inner.end.x - origin.x) / dir.x)
	elif dir.x < 0.0:
		reach = minf(reach, (inner.position.x - origin.x) / dir.x)
	if dir.y > 0.0:
		reach = minf(reach, (inner.end.y - origin.y) / dir.y)
	elif dir.y < 0.0:
		reach = minf(reach, (inner.position.y - origin.y) / dir.y)
	return 0.0 if reach == INF else reach


## 문구는 화살표 뒤쪽(= 화면 안쪽)에 둔다. 화면 밖으로 삐져나가면 안 읽히므로 가둔다.
func _place_text(rect: Rect2) -> void:
	if not text_label.visible:
		return
	var label_size := text_label.size
	var behind := Vector2.from_angle(_angle + PI)
	# 문구 사각형의 중심에서 그 가장자리까지, 뒤쪽 방향으로 잰 반 길이.
	var support := absf(behind.x) * label_size.x * 0.5 + absf(behind.y) * label_size.y * 0.5
	var center := _anchor + behind * (ARROW_LENGTH * 0.5 + TEXT_GAP + support)
	var top_left := center - label_size * 0.5
	var lo := rect.position + Vector2(TEXT_EDGE, TEXT_EDGE)
	var hi := rect.end - label_size - Vector2(TEXT_EDGE, TEXT_EDGE)
	text_label.position = top_left.clamp(lo, hi.max(lo))


func _draw() -> void:
	if not _tracking:
		return
	var half := ARROW_LENGTH * 0.5
	var tip := Vector2(half, 0.0)
	var wing_top := Vector2(-half, -ARROW_HALF_WIDTH)
	var notch := Vector2(-half + ARROW_LENGTH * ARROW_NOTCH, 0.0)
	var wing_bottom := Vector2(-half, ARROW_HALF_WIDTH)

	# 꼬리가 파여 오목한 모양이라 삼각형 둘로 나눠 칠한다(오목 다각형은 삼각분할이
	# 실패할 수 있다).
	var xf := Transform2D(_angle, _anchor)
	var p_tip := xf * tip
	var p_top := xf * wing_top
	var p_notch := xf * notch
	var p_bottom := xf * wing_bottom

	# 윤곽을 먼저 그린다. 선은 가장자리 한가운데에 걸치므로 안쪽 절반은 아래 칠이 덮는다.
	draw_polyline(PackedVector2Array([p_tip, p_top, p_notch, p_bottom, p_tip]),
		ARROW_OUTLINE, OUTLINE_WIDTH, true)
	draw_colored_polygon(PackedVector2Array([p_tip, p_top, p_notch]), ARROW_FILL)
	draw_colored_polygon(PackedVector2Array([p_tip, p_notch, p_bottom]), ARROW_FILL)
