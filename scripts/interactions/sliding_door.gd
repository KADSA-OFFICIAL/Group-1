extends Area2D
## 방 미닫이문 — 한 짝이 옆으로 밀린다(#252로 교실 밖 방에도 붙는다).
##
## **플레이어는 E로 여닫는다.** 그래서 스크립트가 부모 Node2D가 아니라 Area2D
## 본체에 붙어 있다 — 플레이어의 InteractionArea는 겹치는 Area2D 중
## `interact()`를 가진 것을 찾고 `prompt_text`를 읽어 안내를 띄운다
## (player_controller._find_interactable / _update_interact_prompt).
## 그래서 이 존은 `collision_layer = 2`(플레이어가 찾는 층)여야 한다.
##
## **수위는 E 없이 지나간다.** 같은 존이 `collision_mask = 1`로 몸도 감지해서,
## `janitor` 그룹이 들어오면 저절로 열고 나가면 닫는다. 수위가 문에 막히면
## 추격이 깨진다 — `SDPanel*`은 경로탐색에서 늘 열린 것으로 취급되므로
## (janitor._collect_blockers·verify_floor_reach·verify_janitor_route·
## verify_hiding_spots) 격자와 실제가 어긋나 문 앞에서 끼인다.
##
## 문짝 시각은 몸체 안이 아니라 WallGlow(CanvasLayer) 안에 있다 — 레이어 0에
## 두면 문 표식·벽 시각이 z_index와 무관하게 덮어 문이 아예 안 보인다(#234).
## 몸체와 시각을 NodePath로 이어 붙이고 같은 트윈으로 함께 민다.
##
## 문짝에는 광원 차단체가 붙는다(#256). 없을 때는 문 틈이 벽 없는 구간이라
## 닫힌 문 너머가 훤히 보여서 문이 있으나 마나였다. 차단체는 문짝 몸체의
## 자식이라 문과 함께 움직인다 — 열리면 벽 쪽으로 비켜나 그 자리 벽 차단체와
## 겹치고 문 틈이 빈다. 그래서 여닫이에 맞춰 켜고 끄는 코드가 없다.

## 문짝이 밀려나는 거리와 방향. 문 틈 폭 전체를 비켜야 완전히 열린다.
@export var travel: float = 110.0
## 사선 벽(오른쪽 중간 띠)에서는 벽 기울기만큼 세로로도 밀려야 벽에 붙어 있다.
## 축정렬 벽에서는 0이라 씬에 아예 적히지 않는다.
@export var travel_y: float = 0.0
@export var open_time: float = 0.28
## WallGlow 안의 문짝 시각. 몸체와 같은 거리만큼 함께 움직인다.
@export var leaf_visual: NodePath
## 플레이어 안내 문구. 상태에 따라 바뀐다(player_controller가 매 프레임 읽는다).
@export var prompt_text: String = "문 열기"
## 문은 늘 겹치는 자리에 있어 단서·아이템보다 낮아야 한다(#301).
@export var interact_priority: int = 4
## 이 문이 여는 방의 창문 달빛 묶음(#292). 닫힌 문 너머가 보이면 안 되므로
## 방 광원은 평소에 꺼져 있고, 문이 열릴 때만 켠다. 창 없는 방은 비어 있다.
@export var room_lights: NodePath

const PROMPT_OPEN := "문 열기"
const PROMPT_CLOSE := "문 닫기"

var _panel: StaticBody2D
var _shape: CollisionPolygon2D
var _leaf: Node2D
var _tween: Tween
## 플레이어가 E로 연 상태인지. 수위 자동 개방과 따로 센다 — 수위가 지나갔다고
## 플레이어가 열어 둔 문이 닫히면 안 된다.
var _held_open: bool = false
var _janitors: int = 0
var _open: bool = false
var _lights: Node = null


func _ready() -> void:
	_panel = get_node_or_null("SDPanel") as StaticBody2D
	_leaf = get_node_or_null(leaf_visual) as Node2D
	_lights = get_node_or_null(room_lights)
	if _panel != null:
		# 충돌 노드 이름이 방마다 다르다(<방키>DoorCollision) — 이름은
		# verify_scenes의 벽↔차단체 1:1 검사에 편입되려고 그렇게 붙였다.
		# 그래서 이름 대신 타입으로 찾는다.
		for child in _panel.get_children():
			if child is CollisionPolygon2D:
				_shape = child
				break
	if _panel == null or _shape == null or _leaf == null:
		push_error("sliding_door: SDPanel/충돌/문짝 시각을 찾지 못했다 — %s" % name)
		return
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)


## 플레이어가 E를 눌렀을 때. player_controller가 이 이름으로 호출한다.
func interact(_player: Node) -> void:
	_held_open = not _held_open
	Sfx.play(&"door_open")
	_apply()


func _on_body_entered(body: Node2D) -> void:
	if not body.is_in_group("janitor"):
		return
	_janitors += 1
	if _janitors == 1:
		Sfx.play(&"door_open")
		_apply()


func _on_body_exited(body: Node2D) -> void:
	if not body.is_in_group("janitor"):
		return
	_janitors = maxi(0, _janitors - 1)
	_apply()


func _apply() -> void:
	var want := _held_open or _janitors > 0
	prompt_text = PROMPT_CLOSE if _held_open else PROMPT_OPEN
	if want == _open or _panel == null:
		return
	_open = want
	# 방 달빛은 문 상태를 따라간다(#292). 여기가 상태가 **바뀌는 순간**이라
	# hold/release가 정확히 한 번씩 짝을 이룬다.
	if _lights != null:
		_lights.call("hold" if _open else "release")

	# 열 때는 충돌부터 끈다 — 문에 붙어 선 채로 열면 미는 동안 몸이 낀다.
	# 닫을 때는 다 닫힌 뒤에 켠다. 순서를 반대로 하면 닫히는 판이 플레이어를
	# 벽으로 밀어 넣는다.
	if _open:
		_set_solid(false)

	if _tween != null and _tween.is_valid():
		_tween.kill()
	var offset := Vector2(travel, travel_y) if _open else Vector2.ZERO
	_tween = create_tween().set_parallel(true)
	_tween.set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
	for node in [_panel, _leaf]:
		if node != null:
			_tween.tween_property(node, "position", offset, open_time)
	if not _open:
		_tween.chain().tween_callback(_set_solid.bind(true))


func _set_solid(solid: bool) -> void:
	if _shape != null:
		_shape.set_deferred("disabled", not solid)
