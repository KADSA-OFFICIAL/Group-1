extends Control
## 수위 접근 방향 표시(#327) — 화면 가장자리에 뜨는 방향 쐐기.
##
## 소리 단서(발소리·열쇠, #9)는 **어느 쪽인지**를 알려 주지 못한다. 위치 기반
## `AudioStreamPlayer2D`가 좌우 감쇠를 주긴 하지만 위아래는 구분이 안 되고,
## 하단 알림 텍스트는 거리만 말한다. 그래서 소리가 나도 어느 복도로 도망칠지
## 고를 수 없었다.
##
## **시야를 대신하는 것이 아니다.** 수위가 어디 있는지는 안 보여 준다 — 어느
## **방향**에서 오는지만 화면 테두리에 띄운다. 거리는 진하기로만 전한다.

## 이 거리 안이면 뜨기 시작한다. 소리 단서와 같은 값(EARSHOT)이라 "들리면
## 방향도 안다"가 된다.
const ALERT_RANGE := 720.0
## 이 안으로 들어오면 최대 진하기.
const CLOSE_RANGE := 260.0
## 쐐기가 화면 안쪽으로 뻗는 깊이(px)와 테두리에서의 폭.
const WEDGE_DEPTH := 190.0
const WEDGE_WIDTH := 520.0
## 진하기가 따라붙는 속도. 튀지 않게 한다.
const FADE_SPEED := 3.5
## 추격 중 맥동 주기(초)와 세기.
const PULSE_HZ := 2.4
const PULSE_AMOUNT := 0.28

const CALM_COLOR := Color(0.86, 0.78, 0.42)   # 들리는 거리 — 호박
const CHASE_COLOR := Color(0.92, 0.28, 0.24)  # 추격 — 붉은색

var _player: Node2D = null
var _janitor: Node2D = null
var _strength: float = 0.0
var _chasing: bool = false
var _dir: Vector2 = Vector2.RIGHT
var _pulse: float = 0.0


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
	_chasing = float(_janitor.get("chase_hold")) > 0.0
	if d <= CLOSE_RANGE:
		return 1.0
	return 1.0 - (d - CLOSE_RANGE) / (ALERT_RANGE - CLOSE_RANGE)


func _draw() -> void:
	if _strength <= 0.01:
		return

	var rect := get_viewport_rect().size
	var center := rect * 0.5
	# 화면 테두리에서 방향이 만나는 점. 축마다 필요한 배율 중 작은 쪽이 먼저 닿는다.
	var sx := INF if is_zero_approx(_dir.x) else (rect.x * 0.5) / absf(_dir.x)
	var sy := INF if is_zero_approx(_dir.y) else (rect.y * 0.5) / absf(_dir.y)
	var edge := center + _dir * minf(sx, sy)

	var side := Vector2(-_dir.y, _dir.x) * (WEDGE_WIDTH * 0.5)
	var inner := edge - _dir * WEDGE_DEPTH

	var alpha := _strength * (0.85 if _chasing else 0.55)
	if _chasing:
		alpha *= 1.0 - PULSE_AMOUNT * (0.5 + 0.5 * cos(_pulse * TAU * PULSE_HZ))
	var tint: Color = CHASE_COLOR if _chasing else CALM_COLOR

	# 테두리 쪽 두 점은 진하고 안쪽 두 점은 투명하다 — draw_polygon이 정점마다
	# 색을 받으므로 그라디언트가 공짜다(셰이더 없이).
	var pts := PackedVector2Array([
		edge + side, edge - side, inner - side * 0.55, inner + side * 0.55])
	var cols := PackedColorArray([
		Color(tint, alpha), Color(tint, alpha),
		Color(tint, 0.0), Color(tint, 0.0)])
	draw_polygon(pts, cols)
