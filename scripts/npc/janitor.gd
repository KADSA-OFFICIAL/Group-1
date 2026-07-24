extends CharacterBody2D

## 수위아저씨 NPC.
## 기본 동작은 추적: 플레이어가 같은 층에 있으면 시야(LOS)가 트일 때 직진 추격,
## 벽에 가리면 복도 웨이포인트 그래프를 BFS 최단 경로로 타고 접근한다.
## 층이 어긋나면(혹시 모를 가드) 웨이포인트 무작위 순찰로 폴백.
## 활성/비활성과 스폰 위치는 floor_manager가 sync_floor로 제어한다.

@export var patrol_speed: float = 110.0
@export var chase_speed: float = 220.0

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
const STUCK_SECONDS := 0.6      # 목표에 가까워지지 않는 상태가 이만큼 이어지면 막힌 것으로 본다
const REPATH_SECONDS := 0.3     # 추적 경로 재계산 주기
const CONTACT_DISTANCE := 30.0  # 이 안까지 붙으면 멈춰 마주본다(페널티는 후속 이슈)
const WALL_MASK := 1            # LOS 레이캐스트 대상(벽·바리케이드)
const BODY_CLEARANCE := 15.0    # 몸통 반폭(캡슐 18×30의 최대 반경) — 지날 수 있는 틈인지 판정
const UNSTICK_SECONDS := 0.35   # 벽에 걸렸을 때 벽을 타고 도는 시간

var player: CharacterBody2D = null
var my_floor: int = -1
var player_floor: int = -1

# 순찰(폴백) 상태
var target_waypoint: String = "main_mid"
var previous_waypoint: String = ""

# 추적 상태: 비어 있으면 직진 추격, 아니면 따라갈 웨이포인트 이름 목록
var chase_path: Array[String] = []
var path_locked: bool = false   # 우회 확정 — 다음 웨이포인트에 닿기 전엔 직진 단축 금지
var repath_timer: float = 0.0
var unstick_time: float = 0.0
var unstick_direction: Vector2 = Vector2.ZERO

var stuck_time: float = 0.0
var last_goal_distance: float = INF

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
	path_locked = false
	repath_timer = 0.0
	unstick_time = 0.0
	_reset_progress()


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
		unstick_time = 0.0
		_reset_progress()
		return

	# 벽에 걸린 직후에는 잠깐 벽을 타고 돌아 몸을 빼낸다(경로 판단은 그 뒤에).
	if unstick_time > 0.0:
		unstick_time -= delta
		velocity = unstick_direction * chase_speed
		move_and_slide()
		body.rotation = unstick_direction.angle() - Vector2.UP.angle()
		return

	repath_timer -= delta
	if repath_timer <= 0.0:
		repath_timer = REPATH_SECONDS
		_update_chase_path()

	var goal: Vector2 = player.position
	if not chase_path.is_empty():
		goal = WAYPOINTS[chase_path[0]]
		if position.distance_to(goal) <= ARRIVE_DISTANCE:
			chase_path.pop_front()
			path_locked = false  # 우회 한 구간을 소화 — 다시 직진 단축을 검토할 수 있다
			_reset_progress()
			return
	_step_toward(goal, chase_speed, delta)

	# 벽 모서리·문 틈에 걸려 목표에 가까워지지 못하면 그래프로 우회하고 몸을 빼낸다.
	# 플레이어를 바로 앞에 두고 몸이 부딪혀 멈춘 것은 스턱으로 치지 않는다.
	if stuck_time >= STUCK_SECONDS and to_player > CONTACT_DISTANCE * 2.0:
		chase_path = _build_chase_path()
		path_locked = true
		repath_timer = REPATH_SECONDS
		_begin_unstick(goal)
		_reset_progress()


func _update_chase_path() -> void:
	# 우회를 확정했으면 다음 웨이포인트에 닿기 전까지 직진 단축으로 되돌리지 않는다.
	# (없으면 모서리 옆에서 직진↔우회가 0.3초마다 왕복하며 계속 끼인다)
	if path_locked and not chase_path.is_empty():
		return

	if _clear_line(position, player.position):
		if not chase_path.is_empty():
			chase_path.clear()
			_reset_progress()
		return

	var previous_goal: String = "" if chase_path.is_empty() else chase_path[0]
	chase_path = _build_chase_path()
	# 이미 지나친(또는 안 거쳐도 보이는) 앞 노드는 건너뛰어 되돌아가는 걸음을 없앤다.
	while chase_path.size() >= 2 and _clear_line(position, WAYPOINTS[chase_path[1]]):
		chase_path.pop_front()
	if chase_path.is_empty() or chase_path[0] != previous_goal:
		_reset_progress()


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


## 두 점 사이를 "몸통이" 지날 수 있는지 확인(자신·플레이어 몸은 제외).
## 중심선 한 발만 쏘면 두께가 0이라 벽 모서리를 스치는 경로도 뚫린 것으로 보고돼
## 직진 추격에 들어갔다가 몸이 끼인다. 진행 방향 수직으로 몸통 반폭만큼 벌린
## 평행선까지 검사해 실제로 통과 가능한 폭인지 본다.
func _clear_line(from: Vector2, to: Vector2) -> bool:
	if not _clear_ray(from, to):
		return false
	var side := from.direction_to(to).orthogonal() * BODY_CLEARANCE
	return _clear_ray(from + side, to + side) and _clear_ray(from - side, to - side)


func _clear_ray(from: Vector2, to: Vector2) -> bool:
	var exclude: Array[RID] = [get_rid()]
	if player != null:
		exclude.append(player.get_rid())
	var query := PhysicsRayQueryParameters2D.create(from, to, WALL_MASK, exclude)
	query.hit_from_inside = true  # 벽에 붙어 시작한 평행선이 그 벽을 놓치지 않게
	var hit := get_world_2d().direct_space_state.intersect_ray(query)
	return hit.is_empty()


## 마지막 충돌면의 접선 중 목표에 가까워지는 쪽으로 잠깐 벽을 타고 돈다.
func _begin_unstick(goal: Vector2) -> void:
	var collision := get_last_slide_collision()
	if collision == null:
		return
	var tangent := collision.get_normal().orthogonal()
	if position.direction_to(goal).dot(tangent) < 0.0:
		tangent = -tangent
	unstick_direction = tangent
	unstick_time = UNSTICK_SECONDS


func _reset_progress() -> void:
	stuck_time = 0.0
	last_goal_distance = INF


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
	_reset_progress()


func _turn_around() -> void:
	if previous_waypoint != "" and previous_waypoint != target_waypoint:
		var swap := target_waypoint
		target_waypoint = previous_waypoint
		previous_waypoint = swap
	_reset_progress()


# ── 공통 이동 ────────────────────────────────────────────────────

func _step_toward(target: Vector2, move_speed: float, delta: float) -> void:
	var direction := position.direction_to(target)
	velocity = direction * move_speed
	move_and_slide()
	body.rotation = direction.angle() - Vector2.UP.angle()

	# 이동량이 아니라 "목표까지 가까워졌는지"로 막힘을 판정한다. 벽에 비스듬히 끼면
	# move_and_slide가 벽을 따라 옆으로 밀어내므로 이동량 기준은 계속 "움직이는 중"이 된다.
	var goal_distance := position.distance_to(target)
	if goal_distance > last_goal_distance - move_speed * delta * 0.25:
		stuck_time += delta
	else:
		stuck_time = 0.0
	last_goal_distance = goal_distance
