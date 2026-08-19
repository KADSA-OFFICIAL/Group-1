extends Node2D
## 교실 미닫이문 — 두 짝이 양옆으로 밀린다.
##
## 문 앞에 서면 열리고 멀어지면 닫힌다. E를 누를 필요는 없다. 교실 문은 한
## 판에 수십 개라 조사형으로 만들면 이동이 조작으로 뒤덮인다.
##
## 수위도 같은 존을 밟으므로 문을 열고 지나간다. 그래서 경로탐색·도달성은
## 문을 늘 열린 것으로 본다 — `SDPanel*`로 시작하는 StaticBody2D는
## janitor.gd의 _collect_blockers와 tools/verify_floor_reach.py,
## tools/verify_janitor_route.py에서 건너뛴다. 이 이름 규칙을 바꾸면 세 곳을
## 함께 고쳐야 한다.
##
## 광원 차단체는 달지 않는다. 학교 교실 문은 상단이 유리라 닫혀 있어도 빛이
## 샌다는 설정이고, 차단체를 여닫이에 맞춰 켜고 끄면 조명 튜닝(#74)이 흔들린다.

## 짝 하나가 밀려나는 거리. 문 틈 폭의 절반이면 틈이 완전히 열린다.
@export var travel: float = 55.0
@export var open_time: float = 0.26

var _left: StaticBody2D
var _right: StaticBody2D
var _shapes: Array[CollisionPolygon2D] = []
var _zone: Area2D
var _inside: int = 0
var _open: bool = false
var _tween: Tween


func _ready() -> void:
	_left = get_node_or_null("SDPanelL") as StaticBody2D
	_right = get_node_or_null("SDPanelR") as StaticBody2D
	_zone = get_node_or_null("Zone") as Area2D
	if _left == null or _right == null or _zone == null:
		push_error("sliding_door: SDPanelL/SDPanelR/Zone이 없다 — %s" % name)
		return
	for panel in [_left, _right]:
		var shape := panel.get_node_or_null("Shape") as CollisionPolygon2D
		if shape != null:
			_shapes.append(shape)
	_zone.body_entered.connect(_on_body_entered)
	_zone.body_exited.connect(_on_body_exited)


func _on_body_entered(_body: Node2D) -> void:
	_inside += 1
	if _inside == 1:
		_set_open(true)


func _on_body_exited(_body: Node2D) -> void:
	_inside = maxi(0, _inside - 1)
	if _inside == 0:
		_set_open(false)


func _set_open(open: bool) -> void:
	if open == _open or _left == null:
		return
	_open = open

	# 열 때는 충돌부터 끈다 — 문에 붙어 선 채로 열면 미는 동안 몸이 낀다.
	# 닫을 때는 다 닫힌 뒤에 켠다. 순서를 반대로 하면 닫히는 판이 플레이어를
	# 벽으로 밀어 넣는다.
	if open:
		_set_solid(false)
		Sfx.play(&"door_open")

	if _tween != null and _tween.is_valid():
		_tween.kill()
	var offset := travel if open else 0.0
	_tween = create_tween().set_parallel(true)
	_tween.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	_tween.tween_property(_left, "position", Vector2(-offset, 0.0), open_time)
	_tween.tween_property(_right, "position", Vector2(offset, 0.0), open_time)
	if not open:
		_tween.chain().tween_callback(_set_solid.bind(true))


func _set_solid(solid: bool) -> void:
	for shape in _shapes:
		shape.set_deferred("disabled", not solid)
