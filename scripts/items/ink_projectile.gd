extends Node2D

## 던진 잉크통(#169). 바라보는 방향으로 날아가다 벽에 맞거나 사거리를 다하면
## 그 자리에서 터지고, 터진 지점 반경 안의 수위 눈을 잠시 멀게 한다.
##
## 물리 바디를 쓰지 않고 프레임마다 레이캐스트로 벽을 확인한다. Area2D로 하면
## 층 씬의 상호작용 존(collision_layer 2)과 섞이고, RigidBody2D는 이 게임에
## 물리 상호작용이 하나도 없는데 혼자 튀는 물체가 된다.
##
## 플레이어(player_controller.gd)가 던질 때 launch()로 방향을 넣어 준다.
##
## ── 맞히지 못했던 세 가지(#600) ────────────────────────────────
## 이것은 게임의 **유일한 방어 수단**이고 한 판에 하나뿐인데, 던지면 거의 늘
## "빗나갔다"가 됐다(사용자 보고). 원인이 셋이었다.
##
## ① **조준 수단이 없었다.** 던지는 방향이 `facing_direction` — 마지막으로
##    이동한 방향이라, 도망치면서 Q를 누르면 캔이 도망치는 쪽(수위 반대편)으로
##    날아갔다. 뒤로 던지려면 몸을 돌려야 하고 그건 수위 쪽으로 걸어가는 것이다.
##    → 사거리 안에 수위가 있고 벽으로 막히지 않았으면 **그쪽으로 날아간다**(`_aim`).
## ② **코앞에서는 몸을 통과했다.** `PhysicsRayQueryParameters2D.hit_from_inside`가
##    기본 `false`라 **레이의 출발점을 품은 충돌체는 아예 보고되지 않는다.** 캔이
##    이설 앞 24px에서 출발하므로 수위가 앞쪽 33px(24 + 캡슐 반경 9) 안에 있으면
##    레이가 그를 못 보고 캔이 몸을 지나쳤다 — 붙잡히는 거리가 30px이니 **가장
##    급할 때 정확히 안 맞았다.** → 수위는 물리 레이에 맡기지 않고 이번 tick에
##    지나간 **선분과의 거리**로 직접 잰다(`_segment_distance`).
## ③ **집기가 사선을 막았다.** `WALL_MASK`(1)는 벽·문짝만이 아니라 집기
##    (`PropBodies`의 `PC_*`)까지 잡아, 방 안이나 사물함 옆에서 던지면 책상에
##    맞고 터졌다. 위에서 내려다보는 화면에서 던진 물건이 책상에 막히는 것은
##    그림으로도 설명되지 않는다 — 넘어 날아가는 것이 자연스럽다.
##    → 집기·수위·이설은 넘어가고 **벽과 닫힌 문짝만** 캔을 세운다(`_passes_through`).

const SPEED := 560.0
const MAX_RANGE := 540.0        # 수위 인지 거리(320)보다 넉넉히 — 보고 나서 던질 여유
const SPLASH_RADIUS := 120.0
const BLIND_SECONDS := 5.0      # 플레이어 속도 320 기준 약 1600px 도주 거리
const SPLASH_SECONDS := 0.8     # 터진 자국이 보이는 시간
const WALL_MASK := 1            # 벽·바리케이드(janitor.gd와 같은 레이어)
const WALL_BACKOFF := 10.0      # 벽에 박혀 그려지지 않게 접점에서 물러나는 거리
## 수위 몸에 닿았다고 보는 거리(#600). 캡슐 반경 9 + 캔 반쪽 7 + 여유.
const JANITOR_HIT_RADIUS := 22.0
## 집기를 넘어갈 때 레이를 다시 쏘는 횟수 상한(#600). 층의 집기 충돌체(`PC_*`)는
## **전부 `PropBodies` 하나의 자식 도형**이라 한 번 넘어가면 그 도형만 빠진다 —
## 교실을 가로지르는 조준 레이(최대 540px)는 책상 여러 개를 지나므로 넉넉히 둔다.
## 다 써도 못 끝내면 "막히지 않았다"로 본다(조준은 그쪽이 관대하다).
const RAY_HOPS := 12
## 집기 충돌체가 모여 있는 StaticBody2D 이름 — gen_floors.py의 규약이다.
## 벽은 `RoomWalls`·`StairWalls`, 문짝은 `SDPanel`로 따로 있어 그것만 캔을 세운다.
const PROP_BODIES := "PropBodies"

@onready var can: Polygon2D = $Can
@onready var splash: Polygon2D = $Splash

var direction: Vector2 = Vector2.RIGHT
var travelled: float = 0.0
var landed: bool = false
## 조준은 **첫 물리 프레임에** 한다(#600). 던지는 순간은 `_unhandled_input`
## 안이라 물리 프레임이 아니고, 공간 질의(`direct_space_state`)는 물리 프레임에서만
## 믿을 수 있다. 한 tick(16.7ms) 늦게 정해지는 것은 눈에 보이지 않는다.
var _aimed: bool = false


func _ready() -> void:
	splash.visible = false


## 플레이어가 던지는 순간 호출한다. 방향이 0이면 아래로 던진다(가만히 서서
## 던질 때 facing_direction이 비어 있는 경우 대비). 사거리 안에 수위가 있으면
## 첫 물리 프레임에 그쪽으로 다시 잡는다(#600).
func launch(from: Vector2, throw_direction: Vector2) -> void:
	position = from
	direction = throw_direction.normalized() if throw_direction != Vector2.ZERO \
		else Vector2.DOWN


func _physics_process(delta: float) -> void:
	if landed:
		return

	if not _aimed:
		_aimed = true
		direction = _aim(global_position, direction)

	var step := SPEED * delta
	var next_position := position + direction * step

	# 수위는 레이에 맡기지 않고 직접 잰다(#600 ②). 한 tick에 9.3px 나아가므로
	# 프레임 끝 자리만 재면 스쳐 지나간 것을 놓친다 — **지나간 선분**으로 본다.
	var janitor := _janitor()
	if janitor != null and _segment_distance(position, next_position,
			janitor.global_position) <= JANITOR_HIT_RADIUS:
		# 터짐 그림이 수위 위에 오도록 그의 자리에서 터뜨린다.
		_land(janitor.global_position)
		return

	var hit := _cast(position, next_position)
	if not hit.is_empty():
		_land(hit["position"] - direction * WALL_BACKOFF)
		return

	position = next_position
	can.rotation += TAU * delta   # 굴러가는 느낌
	travelled += step
	if travelled >= MAX_RANGE:
		_land(position)


## 사거리 안에 수위가 있고 벽으로 막히지 않았으면 그쪽으로 던진다(#600 ①).
## 없으면 바라보는 방향 그대로 — 예전 동작이다.
func _aim(from: Vector2, facing: Vector2) -> Vector2:
	var janitor := _janitor()
	if janitor == null:
		return facing
	var to_janitor: Vector2 = janitor.global_position - from
	var distance := to_janitor.length()
	if distance < 0.001 or distance > MAX_RANGE:
		return facing
	# 벽 뒤에 있으면 조준해도 벽에 터진다 — 그럴 때는 바라보는 방향이 낫다.
	if not _cast(from, janitor.global_position).is_empty():
		return facing
	return to_janitor / distance


## 지금 이 층에서 활동 중인 수위. 활동하지 않는 층에서는 숨겨져 있고(4층 안전
## 구간, `janitor._apply_active`), 게임 오버·연출 중에는 물리 처리가 꺼져 있다 —
## 그때는 조준도 피격도 없다.
func _janitor() -> Node2D:
	var janitor := get_tree().get_first_node_in_group("janitor") as Node2D
	if janitor == null or not janitor.visible or not janitor.is_physics_processing():
		return null
	return janitor


## 캔을 세우는 첫 충돌. 넘어가는 것(집기·수위·이설)은 건너뛰고 다시 쏜다.
func _cast(from: Vector2, to: Vector2) -> Dictionary:
	var space := get_world_2d().direct_space_state
	if space == null:
		return {}
	var along := from.direction_to(to)
	var at := from
	for _hop in RAY_HOPS:
		var query := PhysicsRayQueryParameters2D.create(at, to, WALL_MASK)
		var hit := space.intersect_ray(query)
		if hit.is_empty():
			return {}
		if not _passes_through(hit["collider"]):
			return hit
		# 넘어가는 것은 맞은 자리 **안쪽**에서 다시 쏜다 — `hit_from_inside`가
		# 기본 false라 출발점을 품은 충돌체는 다음 레이에서 빠진다.
		at = hit["position"] + along
	return {}


## 캔이 넘어가는 것 — 집기(위로 날아간다), 수위(맞히는 것이 목적이라 따로 잰다),
## 이설(던진 사람). 캔을 세우는 것은 벽과 닫힌 문짝뿐이다.
func _passes_through(collider: Object) -> bool:
	var node := collider as Node
	if node == null:
		return false
	if node.is_in_group("janitor") or node.is_in_group("player"):
		return true
	# 집기는 몸 하나(`PropBodies`)에 도형 수백 개로 들어 있다 — 충돌체로 돌아오는
	# 것은 그 몸이므로 부모가 아니라 **이름 자체**를 본다.
	return String(node.name) == PROP_BODIES


## 점에서 선분까지의 거리.
func _segment_distance(from: Vector2, to: Vector2, point: Vector2) -> float:
	var span := to - from
	var length_squared := span.length_squared()
	if length_squared < 0.001:
		return from.distance_to(point)
	var t := clampf((point - from).dot(span) / length_squared, 0.0, 1.0)
	return (from + span * t).distance_to(point)


func _land(at: Vector2) -> void:
	landed = true
	global_position = at
	can.visible = false
	splash.visible = true
	Sfx.play(&"ink_splash")

	_splash_on_janitor()

	var tween := create_tween()
	tween.tween_property(splash, "modulate:a", 0.0, SPLASH_SECONDS)
	tween.tween_callback(queue_free)


## 터진 지점 근처의 수위를 멀게 한다. 수위는 활동하지 않는 층에서 숨겨져 있으므로
## `_janitor()`가 거른다 — 4층(안전 구간)에서 던져도 보이지 않는 수위가 맞지 않는다.
func _splash_on_janitor() -> void:
	var janitor := _janitor()
	if janitor != null \
			and janitor.global_position.distance_to(global_position) <= SPLASH_RADIUS:
		janitor.call("blind", BLIND_SECONDS)
		return

	var game_state := get_tree().get_first_node_in_group("game_state")
	if game_state != null:
		game_state.call("request_notice", "잉크통이 바닥에 터졌다. 빗나갔다.")
