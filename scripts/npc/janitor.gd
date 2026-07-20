extends CharacterBody2D

## 수위아저씨 NPC.
## 기본 동작은 추적: 플레이어가 같은 층에 있으면 시야(LOS)가 트일 때 직진 추격,
## 벽에 가리면 복도 웨이포인트 그래프를 BFS 최단 경로로 타고 접근한다.
## 층이 어긋나면(혹시 모를 가드) 웨이포인트 무작위 순찰로 폴백.
## 활성/비활성과 스폰 위치는 floor_manager가 sync_floor로 제어한다.

@export var patrol_speed: float = 110.0
@export var chase_speed: float = 260.0

# 복도 웨이포인트 — 전 층 공통 좌표(방·계단실·외벽 충돌 rect와 겹치지 않음).
# stair_top_*: 좌상단 계단실 위 복도, main_*: 메인 복도(y=940), lower_*: 아래 복도(y=1360)
const WAYPOINTS := {
	"stair_top_w": Vector2(170, 670),
	"stair_top_e": Vector2(620, 670),
	"main_w": Vector2(620, 940),
	"main_mid": Vector2(1325, 940),
	"main_e": Vector2(2600, 940),
	"lower_mid": Vector2(1325, 1360),
	"lower_w": Vector2(170, 1360),
	"lower_e": Vector2(2600, 1360),
}
const NEIGHBORS := {
	"stair_top_w": ["stair_top_e"],
	"stair_top_e": ["stair_top_w", "main_w"],
	"main_w": ["stair_top_e", "main_mid"],
	"main_mid": ["main_w", "main_e", "lower_mid"],
	"main_e": ["main_mid"],
	"lower_mid": ["main_mid", "lower_w", "lower_e"],
	"lower_w": ["lower_mid"],
	"lower_e": ["lower_mid"],
}
const ARRIVE_DISTANCE := 6.0
const STUCK_SECONDS := 1.2
const REPATH_SECONDS := 0.3     # 추적 경로 재계산 주기
const CONTACT_DISTANCE := 30.0  # 이 안까지 붙으면 멈춰 마주본다(페널티는 후속 이슈)
const WALL_MASK := 1            # LOS 레이캐스트 대상(벽·바리케이드)

var player: CharacterBody2D = null
var my_floor: int = -1
var player_floor: int = -1

# 순찰(폴백) 상태
var target_waypoint: String = "main_mid"
var previous_waypoint: String = ""

# 추적 상태: 비어 있으면 직진 추격, 아니면 따라갈 웨이포인트 이름 목록
var chase_path: Array[String] = []
var repath_timer: float = 0.0

var stuck_time: float = 0.0
var last_position: Vector2 = Vector2.ZERO

@onready var body: Polygon2D = $Body
@onready var collision_shape: CollisionShape2D = $CollisionShape2D


func _ready() -> void:
	_apply_active(false)


## floor_manager가 층 전환마다 호출한다. active=true면 player_position에서
## 가장 먼 웨이포인트에 스폰해 추적을 시작한다(층 진입 시 화면 밖 등장 보장).
func sync_floor(active: bool, floor_number: int, player_node: CharacterBody2D) -> void:
	player = player_node
	player_floor = floor_number
	if active:
		my_floor = floor_number
	_apply_active(active)


func _apply_active(active: bool) -> void:
	visible = active
	set_physics_process(active)
	collision_shape.set_deferred("disabled", not active)
	if active and player != null:
		_spawn_away_from(player.position)


func _spawn_away_from(player_position: Vector2) -> void:
	var best: String = target_waypoint
	var best_distance := -1.0
	for waypoint_name in WAYPOINTS:
		var distance: float = WAYPOINTS[waypoint_name].distance_to(player_position)
		if distance > best_distance:
			best_distance = distance
			best = waypoint_name
	position = WAYPOINTS[best]
	previous_waypoint = best
	target_waypoint = NEIGHBORS[best].pick_random()
	chase_path.clear()
	repath_timer = 0.0
	stuck_time = 0.0
	last_position = position


func _physics_process(delta: float) -> void:
	if _is_chasing():
		_move_chase(delta)
	else:
		_move_patrol(delta)


## 혹시 모를 어긋남 대비: 플레이어가 수위와 같은 층에 있을 때만 추적한다.
func _is_chasing() -> bool:
	return player != null and player_floor == my_floor


# ── 추적 ─────────────────────────────────────────────────────────

func _move_chase(delta: float) -> void:
	var to_player := position.distance_to(player.position)

	if to_player <= CONTACT_DISTANCE:
		velocity = Vector2.ZERO
		body.rotation = position.direction_to(player.position).angle() - Vector2.UP.angle()
		stuck_time = 0.0
		last_position = position
		return

	repath_timer -= delta
	if repath_timer <= 0.0:
		repath_timer = REPATH_SECONDS
		_update_chase_path()

	if chase_path.is_empty():
		_step_toward(player.position, chase_speed, delta)
	else:
		var next_point: Vector2 = WAYPOINTS[chase_path[0]]
		if position.distance_to(next_point) <= ARRIVE_DISTANCE:
			chase_path.pop_front()
			return
		_step_toward(next_point, chase_speed, delta)

	# 벽 모서리·문 틈에 걸려 제자리면 그래프로 복귀해 경로를 다시 짠다.
	# 플레이어를 바로 앞에 두고 몸이 부딪혀 멈춘 것은 스턱으로 치지 않는다.
	if stuck_time >= STUCK_SECONDS and to_player > CONTACT_DISTANCE * 2.0:
		chase_path = _build_chase_path()
		repath_timer = REPATH_SECONDS * 3.0
		stuck_time = 0.0


func _update_chase_path() -> void:
	if _clear_line(position, player.position):
		chase_path.clear()
		return
	chase_path = _build_chase_path()
	# 이미 지나친(또는 안 거쳐도 보이는) 앞 노드는 건너뛰어 되돌아가는 걸음을 없앤다.
	while chase_path.size() >= 2 and _clear_line(position, WAYPOINTS[chase_path[1]]):
		chase_path.pop_front()


func _build_chase_path() -> Array[String]:
	return _bfs_path(_nearest_waypoint(position), _nearest_waypoint(player.position))


## point에서 보이는(벽에 안 가리는) 가장 가까운 웨이포인트. 없으면 그냥 가장 가까운 것.
func _nearest_waypoint(point: Vector2) -> String:
	var best := ""
	var best_distance := INF
	var best_visible := ""
	var best_visible_distance := INF
	for waypoint_name in WAYPOINTS:
		var distance: float = point.distance_to(WAYPOINTS[waypoint_name])
		if distance < best_distance:
			best_distance = distance
			best = waypoint_name
		if distance < best_visible_distance and _clear_line(point, WAYPOINTS[waypoint_name]):
			best_visible_distance = distance
			best_visible = waypoint_name
	return best_visible if best_visible != "" else best


func _bfs_path(from: String, to: String) -> Array[String]:
	var came_from := {from: ""}
	var queue: Array[String] = [from]
	while not queue.is_empty():
		var current: String = queue.pop_front()
		if current == to:
			break
		for neighbor in NEIGHBORS[current]:
			if not came_from.has(neighbor):
				came_from[neighbor] = current
				queue.append(neighbor)

	var path: Array[String] = []
	var step: String = to
	while step != "":
		path.push_front(step)
		step = came_from.get(step, "")
	return path


## 두 점 사이에 벽이 없는지 레이캐스트로 확인(자신·플레이어 몸은 제외).
func _clear_line(from: Vector2, to: Vector2) -> bool:
	var query := PhysicsRayQueryParameters2D.create(from, to, WALL_MASK, [get_rid(), player.get_rid()])
	var hit := get_world_2d().direct_space_state.intersect_ray(query)
	return hit.is_empty()


# ── 순찰 (층이 어긋났을 때의 폴백) ───────────────────────────────

func _move_patrol(delta: float) -> void:
	var target: Vector2 = WAYPOINTS[target_waypoint]

	if position.distance_to(target) <= ARRIVE_DISTANCE:
		_pick_next_waypoint()
		return

	_step_toward(target, patrol_speed, delta)

	if stuck_time >= STUCK_SECONDS:
		_turn_around()


func _pick_next_waypoint() -> void:
	var options: Array = NEIGHBORS[target_waypoint].duplicate()
	if options.size() > 1:
		options.erase(previous_waypoint)
	previous_waypoint = target_waypoint
	target_waypoint = options.pick_random()
	stuck_time = 0.0


func _turn_around() -> void:
	if previous_waypoint != "" and previous_waypoint != target_waypoint:
		var swap := target_waypoint
		target_waypoint = previous_waypoint
		previous_waypoint = swap
	stuck_time = 0.0


# ── 공통 이동 ────────────────────────────────────────────────────

func _step_toward(target: Vector2, move_speed: float, delta: float) -> void:
	var direction := position.direction_to(target)
	velocity = direction * move_speed
	move_and_slide()
	body.rotation = direction.angle() - Vector2.UP.angle()

	if position.distance_to(last_position) < move_speed * delta * 0.25:
		stuck_time += delta
	else:
		stuck_time = 0.0
	last_position = position
