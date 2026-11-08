extends Area2D
## 방 창문 달빛(#274)을 **볼 수 있을 때만** 켠다(#292).
##
## Godot 2D에는 시야 판정이 없다 — 광원이 켜져 있으면 그 자리가 화면에 그려지고,
## 플레이어가 복도에 있든 방 안에 있든 똑같이 보인다. 달빛을 늘 켜 뒀더니
## **닫힌 문 너머 교실 내부가 다 보였다.** 벽 차단체(`LO_`)와 문짝 차단체(#256)는
## 빛이 방 **밖으로 새는 것**만 막는다 — 방 안이 화면에 그려지는 것은 못 막는다.
##
## 두 가지로 켠다.
##   * **문이 열려 있고 그 문 틈이 플레이어에게서 보인다** — `sliding_door.gd`가
##     `hold()`/`release()`로 알리고, 여기서 플레이어 → 문 틈 광선을 쏴 본다(#849).
##   * **플레이어가 방 안에 있다** — 이 Area2D가 직접 감지한다.
## 문 열림만 보던 때는 문 하나 열어 두면 **옆 방에서 벽 너머로** 그 방이 다
## 보였다(2층 1학년부 벽 앞에서 4반, #849). 광선이 벽(`RoomWalls` 등)에
## 막히면 끈다. 집기·벽 앞면 충돌(`WallBases`)·플레이어·수위는 뚫는다.
## 문만 보면 들어와서 문을 닫았을 때 캄캄해지고, 방만 보면 열린 문으로
## 들여다볼 때 달빛이 안 보인다. 둘 다 있어야 앞뒤가 맞는다.
##
## **안 보이는 Area2D도 몸을 감지한다** — `visible`은 그리기만 끄고 물리는
## 그대로다. 그래서 광원 묶음 자체를 Area2D로 두고 `visible`로 껐다 켠다.

## **늘 켜 두는 방**(#498). 1층 현관 로비가 그렇다 — 그 층이 밝은 이유가
## "현관에서 새어 나오는 빛"이라, 문을 닫아도 복도에서 그 빛이 보여야 한다.
## 닫힌 문 너머가 보이는 것(#292)이 여기서는 문제가 아니라 연출이다.
@export var always_on: bool = false

## 광선이 뚫는 몸(층 씬 루트의 자식 이름). `interact_marks.gd`의 `RAY_PASS`와 같다.
const RAY_PASS := ["PropBodies", "WallBases"]
## 문 틈을 몇 군데 겨눌지(가운데 + 양옆). 비스듬히 보면 가운데만 모서리에 걸린다.
const GAP_SPREAD := 40.0
## 시야를 다시 재는 간격(초). 걸음 한 번(160px)보다 훨씬 짧다.
const RECHECK_SECONDS := 0.1

## 열린 문들(sliding_door). 한 방에 문이 여럿일 수 있어 목록으로 둔다.
## 예전 `hold()`(인자 없음) 호출은 null로 들어와 "늘 보이는 문"으로 센다.
var _doors: Array = []
## 방 안에 있는 플레이어 수(0 또는 1).
var _inside: int = 0
## 열린 문 중 하나라도 플레이어에게서 보이는가(마지막으로 잰 값).
var _door_seen: bool = false
var _timer: float = 0.0
var _player: Node2D = null
var _ray_exclude: Array[RID] = []


func _ready() -> void:
	visible = always_on
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)
	set_physics_process(false)


## 문이 열렸다. sliding_door.gd가 부른다.
func hold(door: Node = null) -> void:
	_doors.append(door)
	_door_seen = _any_door_seen()
	_apply()


## 문이 닫혔다.
func release(door: Node = null) -> void:
	var i := _doors.find(door)
	if i >= 0:
		_doors.remove_at(i)
	elif not _doors.is_empty():
		_doors.pop_back()
	_door_seen = _any_door_seen()
	_apply()


## 열린 문이 있고 플레이어가 방 밖에 있을 때만 시야를 다시 잰다.
func _physics_process(delta: float) -> void:
	_timer -= delta
	if _timer > 0.0:
		return
	_timer = RECHECK_SECONDS
	var seen := _any_door_seen()
	if seen != _door_seen:
		_door_seen = seen
		_apply()


func _any_door_seen() -> bool:
	if _doors.is_empty():
		return false
	if _player == null or not is_instance_valid(_player):
		_player = get_tree().get_first_node_in_group("player") as Node2D
		_build_exclude()
	if _player == null:
		return true   # 플레이어가 없으면(에디터 단독 실행) 예전처럼 켠다.
	var space := get_world_2d().direct_space_state
	for door in _doors:
		if door == null or not is_instance_valid(door):
			return true
		var gap := _gap_of(door as Node)
		var along := Vector2(GAP_SPREAD, 0.0) if gap.size.x >= gap.size.y else Vector2(0.0, GAP_SPREAD)
		var c := gap.get_center()
		for to in [c, c - along, c + along]:
			var q := PhysicsRayQueryParameters2D.create(_player.global_position, to, 1, _ray_exclude)
			q.collide_with_areas = false
			if space.intersect_ray(q).is_empty():
				return true
	return false


## 문 틈 사각형. 문짝 충돌 폴리곤의 **닫힌 자리**(문짝이 비켜나도 틈은 그대로다).
func _gap_of(door: Node) -> Rect2:
	var zone := door.get_node_or_null("Zone") as Node2D
	var center := zone.global_position if zone != null else (door as Node2D).global_position
	return Rect2(center - Vector2(55.0, 8.0), Vector2(110.0, 16.0)) \
		if _door_horizontal(door) else Rect2(center - Vector2(8.0, 55.0), Vector2(16.0, 110.0))


func _door_horizontal(door: Node) -> bool:
	for poly in door.find_children("*", "CollisionPolygon2D", true, false):
		var pts := (poly as CollisionPolygon2D).polygon
		if pts.size() == 0:
			continue
		var lo := pts[0]
		var hi := pts[0]
		for pt in pts:
			lo = lo.min(pt)
			hi = hi.max(pt)
		return (hi.x - lo.x) >= (hi.y - lo.y)
	return true


## 광선에서 뺄 몸 — 플레이어, 수위, 집기, 벽 앞면 충돌. 층 씬 루트(`Lights`의 부모)에서 찾는다.
func _build_exclude() -> void:
	_ray_exclude = []
	if _player is CollisionObject2D:
		_ray_exclude.append((_player as CollisionObject2D).get_rid())
	for j in get_tree().get_nodes_in_group("janitor"):
		if j is CollisionObject2D:
			_ray_exclude.append((j as CollisionObject2D).get_rid())
	var root := get_parent().get_parent() if get_parent() != null else null
	if root == null:
		return
	for n in RAY_PASS:
		var body := root.get_node_or_null(n)
		if body is CollisionObject2D:
			_ray_exclude.append((body as CollisionObject2D).get_rid())


## 방 안에 있는 것이 **플레이어**인가.
##
## `collision_mask = 1`은 벽(`RoomWalls`)·집기(`PropBodies`)·문짝(`SDPanel`)
## StaticBody2D까지 전부 잡는다. 그것들이 방 안에 있으므로 그냥 세면 방이
## 늘 켜져 있다 — #234에서 미닫이문이 영구 개방됐던 것과 같은 함정이다.
## 움직이는 몸(CharacterBody2D)만 센다.
##
## 수위는 뺀다. 그가 들어왔다고 방이 밝아지면 안 보이는 곳에 있는 위치가
## 새어 나간다. 수위가 문을 열고 들어가면 문 쪽 조건으로 어차피 켜진다.
func _is_player(body: Node2D) -> bool:
	return body is CharacterBody2D and not body.is_in_group("janitor")


func _on_body_entered(body: Node2D) -> void:
	if not _is_player(body):
		return
	_inside += 1
	_apply()


func _on_body_exited(body: Node2D) -> void:
	if not _is_player(body):
		return
	_inside = maxi(0, _inside - 1)
	# 방 안에 있는 동안은 시야를 안 쟀으니 나가는 순간 다시 잰다.
	_door_seen = _any_door_seen()
	_apply()


func _apply() -> void:
	# 방 안이면 문과 상관없이 켜져 있으니 시야를 잴 필요가 없다.
	set_physics_process(not always_on and not _doors.is_empty() and _inside == 0)
	visible = always_on or _inside > 0 or (_door_seen and not _doors.is_empty())
