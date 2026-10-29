extends Control
## 수위 접근 방향 표시(#327, 도트 화살표 #739) — 화면 가장자리에 뜨는 방향 화살표.
##
## 소리 단서(발소리·열쇠, #9)는 **어느 쪽인지**를 알려 주지 못한다. 위치 기반
## `AudioStreamPlayer2D`가 좌우 감쇠를 주긴 하지만 위아래는 구분이 안 되고,
## 하단 알림 텍스트는 거리만 말한다. 그래서 소리가 나도 어느 복도로 도망칠지
## 고를 수 없었다.
##
## **시야를 대신하는 것이 아니다.** 수위가 어디 있는지는 안 보여 준다 — 어느
## **방향**에서 오는지만 화면 테두리에 띄운다. 거리는 진하기로만 전한다.
##
## **화살표는 도트 스프라이트다**(#739). 예전에는 테두리에서 퍼지는 사다리꼴
## 그라디언트였는데 화살표가 아니라 손전등 빛줄기로 읽혔고, 갈매기·호·배지·
## 발자국·물결·두 눈 같은 매끈한 벡터 시안도 도트 화면에서 겉돌아 전부 거절됐다.
## 그림은 `tools/gen_alert_arrow.py`가 회색조로 굽고 색은 `modulate`로 입힌다.
## 도트 그림은 임의 각도로 돌리면 칸이 비틀리므로 **8방향으로 끊어** 곧은 것·
## 대각선 두 장을 90도 배수로만 돌린다.

## 이 거리 안이면 뜨기 시작한다. 소리 단서와 같은 값(EARSHOT)이라 "들리면
## 방향도 안다"가 된다.
const ALERT_RANGE := 720.0
## 이 안으로 들어오면 최대 진하기.
const CLOSE_RANGE := 260.0
## 진하기가 따라붙는 속도. 튀지 않게 한다.
const FADE_SPEED := 3.5
## 추격 중 맥동 주기(초)와 세기.
const PULSE_HZ := 2.4
const PULSE_AMOUNT := 0.35

const ARROW := preload("res://assets/ui/alert_arrow.png")
const ARROW_DIAG := preload("res://assets/ui/alert_arrow_diag.png")
## 도트 한 칸 = 화면 4px. 정수 배라야 도트 폭이 고르다.
const PIXEL_SCALE := 4.0
## 화살표 중심이 화면 가장자리에서 떨어지는 거리. 위쪽은 목표·소지품·진행 표
## (`TopLeft`·`TopRight`, y 16~92)를 피해 더 내린다.
const EDGE_MARGIN := 60.0
const TOP_MARGIN := 136.0
## 뒤 그림자가 밀려 나는 거리(도트)와 어둡히는 정도.
const SHADOW_OFFSET_DOTS := Vector2(2, 2)
const SHADOW_DARKEN := 0.62
## 가장 멀 때(들리기 시작할 때)의 불투명도.
const ALPHA_FLOOR := 0.45
## 추격 중 화살표가 수위 쪽으로 한 칸씩 내미는 폭(도트 수).
const CHASE_NUDGE_DOTS := 2

const CALM_COLOR := Color(0.86, 0.78, 0.42)   # 들리는 거리 — 호박
const CHASE_COLOR := Color(0.92, 0.28, 0.24)  # 추격 — 붉은색

var _player: Node2D = null
var _janitor: Node2D = null
var _strength: float = 0.0
var _chasing: bool = false
var _dir: Vector2 = Vector2.RIGHT
var _pulse: float = 0.0
## 화면 위 플레이어 자리. `_measure()`가 매 프레임 잡는다.
var _origin: Vector2 = Vector2.ZERO


func _ready() -> void:
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST


func _process(delta: float) -> void:
	_pulse += delta
	var want := _measure()
	_strength = move_toward(_strength, want, FADE_SPEED * delta)
	queue_redraw()


## 지금 얼마나 진해야 하는가. 못 찾거나 다른 층이면 0.
func _measure() -> float:
	if _player == null or not is_instance_valid(_player):
		_player = get_tree().get_first_node_in_group("player")
	if _janitor == null or not is_instance_valid(_janitor):
		_janitor = get_tree().get_first_node_in_group("janitor")
	if _player == null or _janitor == null:
		return 0.0
	# 다른 층의 수위는 알려 주지 않는다. 층을 옮기면 같은 노드가 재사용되므로
	# 물리 처리 여부로 "이 층에서 활동 중"인지 본다.
	if not _janitor.is_physics_processing():
		return 0.0
	if _janitor.get("my_floor") != _janitor.get("player_floor"):
		return 0.0

	var to := _janitor.global_position - _player.global_position
	var d := to.length()
	if d > ALERT_RANGE or d < 1.0:
		return 0.0
	_dir = to / d
	_origin = get_viewport().get_canvas_transform() * _player.global_position
	_chasing = float(_janitor.get("chase_hold")) > 0.0
	if d <= CLOSE_RANGE:
		return 1.0
	return 1.0 - (d - CLOSE_RANGE) / (ALERT_RANGE - CLOSE_RANGE)


func _draw() -> void:
	if _strength <= 0.01:
		return

	# 8방향으로 끊는다. 짝수 = 곧은 화살표, 홀수 = 대각선(↘가 1번, y가 아래로 큰 좌표).
	var octant := posmod(roundi(_dir.angle() / (PI * 0.25)), 8)
	var tex: Texture2D = ARROW if octant % 2 == 0 else ARROW_DIAG
	var turn := float(octant >> 1) * PI * 0.5
	var snapped := Vector2.from_angle(octant * PI * 0.25)

	# 자리는 끊은 방향이 아니라 실제 방향으로 잡는다 — 그래야 테두리를 따라
	# 매끄럽게 옮겨 다닌다. 기준점은 화면 중심이 아니라 플레이어다(hud_waypoint와
	# 같은 이유 — 카메라 한계 때문에 플레이어가 가운데에 없을 수 있다).
	var rect := get_viewport_rect()
	var inner := Rect2(rect.position + Vector2(EDGE_MARGIN, TOP_MARGIN),
		rect.size - Vector2(EDGE_MARGIN * 2.0, TOP_MARGIN + EDGE_MARGIN))
	var start := _origin.clamp(inner.position, inner.end)
	var anchor := start + _dir * _exit_distance(start, inner)

	# 멀어도 형체는 보이게 바닥을 깐다 — 진하기만으로 거리를 주면 들리기 시작할
	# 때 어둠에 묻혀 안 보인다.
	var alpha := lerpf(ALPHA_FLOOR, 1.0, _strength)
	if _chasing:
		var beat := 0.5 + 0.5 * cos(_pulse * TAU * PULSE_HZ)
		alpha *= 1.0 - PULSE_AMOUNT * beat
		# 박자에 맞춰 수위 쪽으로 도트 단위로 내민다(반 칸 이동은 도트가 번진다).
		anchor += snapped * PIXEL_SCALE * roundf((1.0 - beat) * CHASE_NUDGE_DOTS)
	var tint: Color = CHASE_COLOR if _chasing else CALM_COLOR

	# 뒤 그림자 — 같은 그림을 어둡게 해 오른쪽 아래로 밀어 깐다. 화살표가 서는
	# 가장자리는 시야 마스크로 새까매서 검은 그림자는 안 보이므로 제 색을 어둡게 쓴다.
	# 회전과 무관하게 화면 기준으로 민다(빛은 늘 왼쪽 위에서 온다).
	var shade := anchor.round() + SHADOW_OFFSET_DOTS * PIXEL_SCALE
	draw_set_transform(shade, turn, Vector2(PIXEL_SCALE, PIXEL_SCALE))
	draw_texture(tex, -tex.get_size() * 0.5, Color(tint.darkened(SHADOW_DARKEN), alpha))
	draw_set_transform(anchor.round(), turn, Vector2(PIXEL_SCALE, PIXEL_SCALE))
	draw_texture(tex, -tex.get_size() * 0.5, Color(tint, alpha))
	draw_set_transform(Vector2.ZERO)


## `origin`(사각형 안)에서 `_dir`로 나갈 때 `box` 경계까지의 거리.
func _exit_distance(origin: Vector2, box: Rect2) -> float:
	var reach := INF
	if _dir.x > 0.0:
		reach = minf(reach, (box.end.x - origin.x) / _dir.x)
	elif _dir.x < 0.0:
		reach = minf(reach, (box.position.x - origin.x) / _dir.x)
	if _dir.y > 0.0:
		reach = minf(reach, (box.end.y - origin.y) / _dir.y)
	elif _dir.y < 0.0:
		reach = minf(reach, (box.position.y - origin.y) / _dir.y)
	return 0.0 if reach == INF else reach
