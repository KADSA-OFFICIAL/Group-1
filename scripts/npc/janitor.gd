extends CharacterBody2D

## 수위아저씨 NPC.
## 기본 동작은 추적: 플레이어가 같은 층에 있으면 몸통이 지나갈 수 있는 직선이 트일 때
## 직진 추격, 막히면 복도 웨이포인트 그래프를 타고 접근한다.
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
const STUCK_SECONDS := 0.6           # 가려던 방향으로 못 나아간 시간이 이만큼이면 막힌 것
const PROGRESS_RATIO := 0.3          # 기대 전진량의 이 비율 미만이면 나아가지 못한 것으로 본다
const REPATH_SECONDS := 0.3          # 추적 경로 재계산 주기
const DIRECT_BLOCK_SECONDS := 1.0    # 막힌 뒤 직진 추격을 억제하는 시간(상한 있는 우회 유지)
const CONTACT_DISTANCE := 30.0       # 이 안까지 붙으면 멈춰 마주본다(페널티는 후속 이슈)
const WALL_MASK := 1                 # LOS 레이캐스트 대상(벽·바리케이드)
# 콜리전 캡슐(18×30)은 회전하지 않으므로 반폭이 축마다 다르다.
const BODY_HALF_WIDTH := 9.0
const BODY_HALF_HEIGHT := 15.0
# 벽에 밀착하면 몸통 반폭 위치가 벽면과 정확히 겹쳐 판정이 부동소수점에 좌우된다.
# 평행선을 1px 안쪽으로 넣어 "붙어서 걷는 것"이 막힘으로 뒤집히지 않게 한다.
const BODY_PROBE_MARGIN := 1.0

var player: CharacterBody2D = null
var my_floor: int = -1
var player_floor: int = -1

# F3 디버그 오버레이 — 이 환경에 Godot이 없어 실행 관찰을 사용자가 대신 해야 한다.
# 이상 동작이 보일 때 켜서 "직진인가 우회인가 / LOS가 막혔다고 보는가"를 확인한다.
var debug_draw: bool = false

# 순찰(폴백) 상태
var target_waypoint: String = "main_mid"
var previous_waypoint: String = ""

# 추적 상태: 비어 있으면 직진 추격, 아니면 따라갈 웨이포인트 이름 목록
var chase_path: Array[String] = []
var repath_timer: float = 0.0
var direct_block_time: float = 0.0
var stuck_time: float = 0.0

# 웨이포인트 그래프는 트리(8노드·7간선)라 두 지점 사이 경로가 유일 — 한 번만 계산해 둔다.
var path_cache := {}

@onready var body: Polygon2D = $Body
@onready var collision_shape: CollisionShape2D = $CollisionShape2D


func _ready() -> void:
	_build_path_cache()
	_apply_active(false)


func _build_path_cache() -> void:
	for from in WAYPOINTS:
		for to in WAYPOINTS:
			path_cache["%s>%s" % [from, to]] = _bfs_path(from, to)


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
	direct_block_time = 0.0
	stuck_time = 0.0


func _physics_process(delta: float) -> void:
	if _is_chasing():
		_move_chase(delta)
	else:
		_move_patrol(delta)

	if debug_draw:
		queue_redraw()


## project.godot에 입력 액션을 추가하지 않으려고 키코드를 직접 본다
## (사용자 미커밋 변경이 있는 파일이라 건드리지 않는다).
func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo \
			and event.keycode == KEY_F3:
		debug_draw = not debug_draw
		queue_redraw()


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
		return

	direct_block_time = maxf(direct_block_time - delta, 0.0)

	repath_timer -= delta
	if repath_timer <= 0.0:
		repath_timer = REPATH_SECONDS
		_update_chase_path()

	var goal: Vector2 = player.position
	if not chase_path.is_empty():
		goal = WAYPOINTS[chase_path[0]]
		if position.distance_to(goal) <= ARRIVE_DISTANCE:
			chase_path.pop_front()
			stuck_time = 0.0
			return
	_step_toward(goal, chase_speed, delta)

	# 몸이 실제로 막혀 나아가지 못할 때만 우회로 돌린다. 플레이어가 더 빨라 거리가
	# 벌어지는 것은 막힘이 아니다(전진량으로 판정하므로 여기 걸리지 않는다).
	# 플레이어 몸에 부딪혀 멈춘 것도 스턱으로 치지 않는다.
	if stuck_time >= STUCK_SECONDS and to_player > CONTACT_DISTANCE * 2.0:
		direct_block_time = DIRECT_BLOCK_SECONDS
		chase_path = _build_chase_path()
		repath_timer = REPATH_SECONDS
		stuck_time = 0.0


func _update_chase_path() -> void:
	# 몸통이 지나갈 수 있는 직선이면 그대로 직진. 방금 막힌 직후에는 잠시 억제한다
	# (상한이 있어 예전처럼 등 뒤 웨이포인트까지 무제한 커밋하지 않는다).
	if direct_block_time <= 0.0 and _clear_line(position, player.position):
		chase_path.clear()
		return

	var previous_goal: String = "" if chase_path.is_empty() else chase_path[0]
	chase_path = _build_chase_path()
	if chase_path.is_empty() or chase_path[0] != previous_goal:
		stuck_time = 0.0


## 총 이동거리(자신→시작 노드 + 그래프 + 끝 노드→플레이어)가 가장 짧은 경로를 고른다.
## 시작 노드를 단순히 "가장 가까운 것"으로 잡으면 등 뒤 노드를 골라 반대로 걸어간다.
func _build_chase_path() -> Array[String]:
	var starts := _reachable_waypoints(position)
	var ends := _reachable_waypoints(player.position)
	var best: Array[String] = []
	var best_cost := INF
	for start in starts:
		var to_start: float = position.distance_to(WAYPOINTS[start])
		for end in ends:
			var path: Array[String] = path_cache["%s>%s" % [start, end]]
			var cost: float = to_start + _path_length(path) \
				+ WAYPOINTS[end].distance_to(player.position)
			if cost < best_cost:
				best_cost = cost
				best = path
	return best.duplicate()


func _path_length(path: Array[String]) -> float:
	var total := 0.0
	for i in range(1, path.size()):
		total += WAYPOINTS[path[i - 1]].distance_to(WAYPOINTS[path[i]])
	return total


## point에서 몸통이 곧장 갈 수 있는 웨이포인트들. 하나도 없으면 가장 가까운 것 하나.
func _reachable_waypoints(point: Vector2) -> Array[String]:
	var reachable: Array[String] = []
	var nearest := ""
	var nearest_distance := INF
	for waypoint_name in WAYPOINTS:
		var distance: float = point.distance_to(WAYPOINTS[waypoint_name])
		if distance < nearest_distance:
			nearest_distance = distance
			nearest = waypoint_name
		if _clear_line(point, WAYPOINTS[waypoint_name]):
			reachable.append(waypoint_name)
	if reachable.is_empty():
		reachable.append(nearest)
	return reachable


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
	var side := _side_offset(from.direction_to(to))
	return _clear_ray(from + side, to + side) and _clear_ray(from - side, to - side)


## 진행 방향에 수직인 몸통 반폭. 캡슐이 회전하지 않으므로 가로 이동일 때는
## 상하 반폭(15), 세로 이동일 때는 좌우 반폭(9)이 필요하다.
func _side_offset(direction: Vector2) -> Vector2:
	var perpendicular := direction.orthogonal()
	var extent := absf(perpendicular.x) * BODY_HALF_WIDTH \
		+ absf(perpendicular.y) * BODY_HALF_HEIGHT - BODY_PROBE_MARGIN
	return perpendicular * maxf(extent, 0.0)


func _clear_ray(from: Vector2, to: Vector2) -> bool:
	var exclude: Array[RID] = [get_rid()]
	if player != null:
		exclude.append(player.get_rid())
	# hit_from_inside은 끄고 둔다(기본값). 벽에 붙어 걸으면 평행선의 시작점이 벽
	# 안에 들어가는데, 그걸 히트로 세면 앞이 열려 있어도 "막힘"이 되어 헛우회한다.
	var query := PhysicsRayQueryParameters2D.create(from, to, WALL_MASK, exclude)
	var hit := get_world_2d().direct_space_state.intersect_ray(query)
	return hit.is_empty()


# ── 디버그 오버레이 (F3) ─────────────────────────────────────────

func _draw() -> void:
	if not debug_draw:
		return

	var font := ThemeDB.fallback_font
	var mode := "직진"
	if not _is_chasing():
		mode = "순찰"
	elif not chase_path.is_empty():
		mode = "우회(%d)" % chase_path.size()

	# 우회 경로 — 첫 선분은 자기 위치(로컬 원점)에서 첫 웨이포인트로
	var previous := Vector2.ZERO
	for i in chase_path.size():
		var point := to_local(WAYPOINTS[chase_path[i]])
		draw_circle(point, 7.0, Color(0.3, 0.9, 1.0, 0.8))
		draw_line(previous, point, Color(0.3, 0.9, 1.0, 0.6), 2.0)
		previous = point

	if player != null:
		# 플레이어까지 LOS 프로브 3발 — 통과=초록 / 차단=빨강
		var target := player.position
		var side := _side_offset(position.direction_to(target))
		for offset in [Vector2.ZERO, side, -side]:
			var from: Vector2 = position + offset
			var to: Vector2 = target + offset
			var color := Color(0.2, 1.0, 0.3, 0.7) if _clear_ray(from, to) \
				else Color(1.0, 0.25, 0.2, 0.7)
			draw_line(to_local(from), to_local(to), color, 1.5)

	draw_string(font, Vector2(-40, -34), "%s  stuck %.2f  block %.2f"
		% [mode, stuck_time, direct_block_time], HORIZONTAL_ALIGNMENT_LEFT, -1, 13,
		Color(1, 1, 0.6, 1))


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
	var before := position
	velocity = direction * move_speed
	move_and_slide()
	body.rotation = direction.angle() - Vector2.UP.angle()

	# 막힘은 "가려던 방향으로 실제로 나아간 양"으로 판정한다.
	# 이동량 크기로 보면 벽을 따라 옆으로 밀려나는 것도 전진으로 세고,
	# 목표까지의 거리로 보면 더 빠른 플레이어가 달아나는 것까지 막힘으로 센다.
	var advance := (position - before).dot(direction)
	if advance < move_speed * delta * PROGRESS_RATIO:
		stuck_time += delta
	else:
		stuck_time = 0.0
