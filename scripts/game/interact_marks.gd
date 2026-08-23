extends Node2D
## 상호작용 표시(#301) — 가까이 가야 보이는 작은 빛.
##
## 표시는 **어둠을 받으면 안 된다.** 레이어 0에 두면 `CanvasModulate`(0.1)에
## 곱해져 손전등이 정확히 그 위를 비출 때만 보인다. 그래서 `WallGlow`
## (CanvasLayer) 안에 둔다 — 대신 **늘 보이므로** 여기서 거리로 껐다 켠다.
## 안 그러면 닫힌 문 너머 단서까지 훤히 드러나 #292를 되돌린다.
##
## 표시마다 Area2D를 달지 않고 **이 노드가 한꺼번에 훑는다.** 층당 표시가
## 백 개 남짓이라 거리 계산이 그만큼인데, 그마저 `INTERVAL`로 솎아 낸다
## (실측: 4층 3266노드에서 0.87ms/frame).
##
## 표시는 CanvasLayer 안이라 상호작용 Area2D의 **자식이 될 수 없다.** 주운
## 아이템·열린 문이 사라지면 표시만 남으므로, 이름으로 임자를 찾아 없어졌으면
## 같이 끈다 — 그쪽 스크립트를 건드리지 않아도 된다.

## 이 거리 안에 들어야 뜬다. 방 이름(#307)은 더 멀리서 보여야 하므로 씬에서 올린다.
@export var reveal_distance: float = 210.0
## 완전히 밝아지는 거리. 이 사이는 서서히 밝아진다.
@export var full_distance: float = 120.0
## 거리를 다시 재는 주기(초). 매 프레임 잴 필요가 없다.
const INTERVAL := 0.08
## 밝기가 따라붙는 속도. 튀지 않고 스미듯 나타나게 한다.
const FADE_SPEED := 6.0
## 이미 본 단서의 밝기 배수. 지워 버리면 뭘 봤는지 되짚을 수 없다.
const READ_ALPHA := 0.3
## 표시 이름 앞머리. 뒤가 임자 노드 이름이다.
const PREFIX := "Mark_"

var _player: Node2D = null
var _timer: float = 0.0
## 자식 -> 목표 밝기. _process가 여기로 수렴시킨다.
var _target: Dictionary = {}


func _ready() -> void:
	for child in get_children():
		if child is CanvasItem:
			(child as CanvasItem).modulate.a = 0.0
			_target[child] = 0.0


func _process(delta: float) -> void:
	_timer -= delta
	if _timer <= 0.0:
		_timer = INTERVAL
		_refresh()

	for child in get_children():
		if not (child is CanvasItem):
			continue
		var item := child as CanvasItem
		var want: float = _target.get(child, 0.0)
		if is_equal_approx(item.modulate.a, want):
			continue
		item.modulate.a = move_toward(item.modulate.a, want, FADE_SPEED * delta)


## 표시의 임자. `Mark_<이름>` 규칙으로 층 씬 루트에서 찾는다.
## 씬 루트는 `WallGlow/Marks`의 두 단계 위다.
##
## 앞머리가 `Mark_`가 아니면 임자가 없는 것이다(방 이름 라벨, #307) — 자기
## 자신을 돌려줘 '늘 살아 있음'으로 친다.
func _owner_of(mark: Node) -> Node:
	if not String(mark.name).begins_with(PREFIX):
		return mark
	var root := get_parent().get_parent()
	if root == null:
		return null
	return root.get_node_or_null(String(mark.name).trim_prefix(PREFIX))


func _refresh() -> void:
	if _player == null or not is_instance_valid(_player):
		_player = get_tree().get_first_node_in_group("player")
		if _player == null:
			return

	var origin := _player.global_position
	for child in get_children():
		if not (child is CanvasItem):
			continue
		var owner_node := _owner_of(child)
		if owner_node == null:
			_target[child] = 0.0       # 주웠거나 열려서 사라졌다
			continue
		# 라벨은 Node2D가 아니라 Control이라 global_position이 좌상단이다.
		var at: Vector2 = ((child as Control).get_global_rect().get_center()
				  if child is Control else (child as Node2D).global_position)
		var d := origin.distance_to(at)
		var a := 0.0
		if d <= full_distance:
			a = 1.0
		elif d < reveal_distance:
			a = 1.0 - (d - full_distance) / (reveal_distance - full_distance)
		if a > 0.0 and owner_node.get("investigated") == true:
			a *= READ_ALPHA
		_target[child] = a
