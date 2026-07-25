extends CharacterBody2D

## 수위아저씨 NPC.
## 경로탐색은 격자 A*(AStarGrid2D). 층 로드 시 벽 충돌 도형을 몸통 크기만큼
## 부풀려 격자에 표시하므로 문·방 안까지 경로가 나온다(복도 웨이포인트로는
## 문을 지나는 경로를 표현할 수 없어 방 안 플레이어를 추적하지 못했다).
## 추적: 몸통이 지나갈 직선이 트이면 직진, 아니면 A* 경로를 따라간다.
## 층이 어긋나면(혹시 모를 가드) 무작위 지점 순찰로 폴백.
## 활성/비활성·격자 재생성은 floor_manager가 sync_floor로 제어한다.

@export var patrol_speed: float = 110.0
@export var chase_speed: float = 220.0

const ARRIVE_DISTANCE := 6.0
const STUCK_SECONDS := 0.6      # 가려던 방향으로 못 나아간 시간이 이만큼이면 막힌 것
const PROGRESS_RATIO := 0.3     # 기대 전진량의 이 비율 미만이면 나아가지 못한 것으로 본다
const REPATH_SECONDS := 0.3     # 경로 재계산 주기
const CONTACT_DISTANCE := 30.0  # 이 안까지 붙으면 멈춰 마주본다(페널티는 후속 이슈)
const WALL_MASK := 1            # LOS 레이캐스트 대상(벽·바리케이드)

# 콜리전 캡슐(18×30)은 회전하지 않으므로 반폭이 축마다 다르다.
const BODY_HALF_WIDTH := 9.0
const BODY_HALF_HEIGHT := 15.0
# 벽에 밀착하면 몸통 반폭 위치가 벽면과 정확히 겹쳐 판정이 부동소수점에 좌우된다.
# 평행선을 1px 안쪽으로 넣어 "붙어서 걷는 것"이 막힘으로 뒤집히지 않게 한다.
const BODY_PROBE_MARGIN := 1.0

# 격자: 층 씬은 모두 2800×1800.
const CELL := 25.0
const GRID_WIDTH := 112
const GRID_HEIGHT := 72
const PATH_LOOKAHEAD := 12      # 경로 다듬기에서 앞쪽 몇 지점까지 시야를 볼지
const FAR_SPAWN_RATIO := 0.6    # 스폰 후보: 플레이어에게서 최대 거리의 이 비율 이상인 칸

var player: CharacterBody2D = null
var my_floor: int = -1
var player_floor: int = -1

# F3 디버그 오버레이 — 이 환경에 Godot이 없어 실행 관찰을 사용자가 대신 해야 한다.
# 이상 동작이 보일 때 켜서 "직진인가 경로추적인가 / LOS가 막혔다고 보는가"를 확인한다.
var debug_draw: bool = false

var astar_grid := AStarGrid2D.new()
var grid_ready: bool = false
var walkable_cells: Array[Vector2i] = []

var path_points: PackedVector2Array = PackedVector2Array()
var patrol_target: Vector2 = Vector2.ZERO
var repath_timer: float = 0.0
var stuck_time: float = 0.0

@onready var body: Polygon2D = $Body
@onready var collision_shape: CollisionShape2D = $CollisionShape2D


func _ready() -> void:
	_apply_active(false)


## floor_manager가 층 전환마다 호출한다. active=true면 층 씬의 벽으로 격자를
## 다시 만들고, 플레이어에게서 먼 지점에 스폰한다(층 진입 시 화면 밖 등장 보장).
func sync_floor(active: bool, floor_number: int, player_node: CharacterBody2D,
		floor_root: Node) -> void:
	player = player_node
	player_floor = floor_number
	if active:
		my_floor = floor_number
		if floor_root != null:
			_rebuild_grid(floor_root)
	_apply_active(active)


func _apply_active(active: bool) -> void:
	visible = active
	set_physics_process(active)
	collision_shape.set_deferred("disabled", not active)
	if active and player != null:
		_spawn_away_from(player.position)


# ── 격자 ─────────────────────────────────────────────────────────

func _rebuild_grid(floor_root: Node) -> void:
	astar_grid.clear()
	astar_grid.region = Rect2i(0, 0, GRID_WIDTH, GRID_HEIGHT)
	astar_grid.cell_size = Vector2(CELL, CELL)
	astar_grid.offset = Vector2(CELL, CELL) * 0.5   # 경로 지점이 칸 중심에 오게
	astar_grid.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	astar_grid.update()

	var blockers: Array[Rect2] = []
	_collect_blockers(floor_root, blockers)
	for rect in blockers:
		# 몸통이 들어갈 수 없는 칸을 막는다 = 벽을 몸통 반폭만큼 부풀리고
		# 칸 중심이 그 안에 들어가면 통행 불가.
		var grown := rect.grow_individual(BODY_HALF_WIDTH, BODY_HALF_HEIGHT,
			BODY_HALF_WIDTH, BODY_HALF_HEIGHT)
		var min_cell := _cell_of(grown.position)
		var max_cell := _cell_of(grown.end)
		for cell_x in range(maxi(min_cell.x, 0), mini(max_cell.x, GRID_WIDTH - 1) + 1):
			for cell_y in range(maxi(min_cell.y, 0), mini(max_cell.y, GRID_HEIGHT - 1) + 1):
				var cell := Vector2i(cell_x, cell_y)
				if grown.has_point(_cell_center(cell)):
					astar_grid.set_point_solid(cell, true)

	walkable_cells.clear()
	for cell_x in GRID_WIDTH:
		for cell_y in GRID_HEIGHT:
			var cell := Vector2i(cell_x, cell_y)
			if not astar_grid.is_point_solid(cell):
				walkable_cells.append(cell)
	grid_ready = not walkable_cells.is_empty()


## 층 씬에서 StaticBody2D 하위 충돌 도형만 모은다(Area2D 상호작용 존은 제외).
func _collect_blockers(node: Node, out: Array[Rect2]) -> void:
	for child in node.get_children():
		if child.get_parent() is StaticBody2D:
			if child is CollisionPolygon2D:
				var polygon := (child as CollisionPolygon2D).polygon
				if polygon.size() > 0:
					var node_2d := child as Node2D
					var rect := Rect2(node_2d.to_global(polygon[0]), Vector2.ZERO)
					for i in range(1, polygon.size()):
						rect = rect.expand(node_2d.to_global(polygon[i]))
					out.append(rect)
			elif child is CollisionShape2D:
				var shape := (child as CollisionShape2D).shape
				if shape is RectangleShape2D:
					var half: Vector2 = (shape as RectangleShape2D).size * 0.5
					out.append(Rect2((child as Node2D).global_position - half, half * 2.0))
		_collect_blockers(child, out)


func _cell_of(point: Vector2) -> Vector2i:
	return Vector2i(floori(point.x / CELL), floori(point.y / CELL))


func _cell_center(cell: Vector2i) -> Vector2:
	return Vector2(cell.x * CELL + CELL * 0.5, cell.y * CELL + CELL * 0.5)


## 격자 밖이거나 벽 안인 지점은 가장 가까운 통행 가능 칸으로 보정한다.
## (플레이어가 벽에 붙어 있으면 그 칸이 막힌 것으로 표시돼 A*가 실패한다)
func _nearest_free_cell(point: Vector2) -> Vector2i:
	var cell := _cell_of(point)
	cell.x = clampi(cell.x, 0, GRID_WIDTH - 1)
	cell.y = clampi(cell.y, 0, GRID_HEIGHT - 1)
	if not astar_grid.is_point_solid(cell):
		return cell

	for radius in range(1, 8):
		var best := Vector2i(-1, -1)
		var best_distance := INF
		for offset_x in range(-radius, radius + 1):
			for offset_y in range(-radius, radius + 1):
				if absi(offset_x) != radius and absi(offset_y) != radius:
					continue   # 테두리만 검사
				var probe := Vector2i(cell.x + offset_x, cell.y + offset_y)
				if probe.x < 0 or probe.y < 0 \
						or probe.x >= GRID_WIDTH or probe.y >= GRID_HEIGHT:
					continue
				if astar_grid.is_point_solid(probe):
					continue
				var distance := _cell_center(probe).distance_squared_to(point)
				if distance < best_distance:
					best_distance = distance
					best = probe
		if best.x >= 0:
			return best
	return cell


func _spawn_away_from(player_position: Vector2) -> void:
	if not grid_ready:
		return

	var max_distance := 0.0
	for cell in walkable_cells:
		max_distance = maxf(max_distance, _cell_center(cell).distance_to(player_position))

	# 가장 먼 한 칸만 쓰면 매번 같은 구석에서 나온다 — 충분히 먼 칸 중 무작위.
	var candidates: Array[Vector2i] = []
	for cell in walkable_cells:
		if _cell_center(cell).distance_to(player_position) >= max_distance * FAR_SPAWN_RATIO:
			candidates.append(cell)
	if candidates.is_empty():
		return

	position = _cell_center(candidates.pick_random())
	path_points = PackedVector2Array()
	patrol_target = position
	repath_timer = 0.0
	stuck_time = 0.0


# ── 이동 ─────────────────────────────────────────────────────────

func _physics_process(delta: float) -> void:
	if _is_chasing():
		_move_chase(delta)
	else:
		_move_patrol(delta)

	if debug_draw:
		queue_redraw()


## 혹시 모를 어긋남 대비: 플레이어가 수위와 같은 층에 있을 때만 추적한다.
## 은신 중(#6)이면 발각되지 않아 순찰로 돌아간다.
func _is_chasing() -> bool:
	if player == null or player_floor != my_floor:
		return false
	return player.get("hidden") != true


func _move_chase(delta: float) -> void:
	if position.distance_to(player.position) <= CONTACT_DISTANCE:
		velocity = Vector2.ZERO
		body.rotation = position.direction_to(player.position).angle() - Vector2.UP.angle()
		stuck_time = 0.0
		return

	repath_timer -= delta
	# 막혔으면 억제 타이머 없이 즉시 다시 계산한다. 예전 direct_block_time은
	# 막힌 동안 갱신이 반복되며 "플레이어가 보이면 직진" 검사를 영구 억제해,
	# 플레이어가 앞에 있어도 벽으로 계속 밀는 livelock을 만들었다.
	if repath_timer <= 0.0 or stuck_time >= STUCK_SECONDS:
		repath_timer = REPATH_SECONDS
		stuck_time = 0.0
		_update_chase_path()

	_step_toward(_next_point(player.position), chase_speed, delta)


func _update_chase_path() -> void:
	if not grid_ready:
		path_points = PackedVector2Array()
		return
	if _clear_line(position, player.position):
		path_points = PackedVector2Array()   # 몸통이 지나갈 직선이 있으면 직진
		return
	path_points = astar_grid.get_point_path(
		_nearest_free_cell(position), _nearest_free_cell(player.position))


func _move_patrol(delta: float) -> void:
	if not grid_ready:
		return

	repath_timer -= delta
	if path_points.is_empty() or stuck_time >= STUCK_SECONDS \
			or position.distance_to(patrol_target) <= ARRIVE_DISTANCE:
		stuck_time = 0.0
		repath_timer = REPATH_SECONDS
		_pick_patrol_target()

	_step_toward(_next_point(patrol_target), patrol_speed, delta)


func _pick_patrol_target() -> void:
	patrol_target = _cell_center(walkable_cells.pick_random())
	path_points = astar_grid.get_point_path(
		_nearest_free_cell(position), _nearest_free_cell(patrol_target))


## 경로 다듬기: 시야가 트인 가장 먼 지점으로 건너뛴다(격자 계단 현상 완화).
## 지나친 지점은 버린다. 경로가 없으면 fallback으로 직진.
func _next_point(fallback: Vector2) -> Vector2:
	if path_points.is_empty():
		return fallback

	var limit := mini(path_points.size(), PATH_LOOKAHEAD)
	var index := 0
	for i in range(limit - 1, -1, -1):
		if _clear_line(position, path_points[i]):
			index = i
			break

	while index > 0 and path_points.size() > 1:
		path_points.remove_at(0)
		index -= 1
	if path_points.size() > 1 and position.distance_to(path_points[0]) <= ARRIVE_DISTANCE:
		path_points.remove_at(0)
	return path_points[0]


func _step_toward(target: Vector2, move_speed: float, delta: float) -> void:
	var direction := position.direction_to(target)
	if direction == Vector2.ZERO:
		velocity = Vector2.ZERO
		return

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


# ── 시야 판정 ────────────────────────────────────────────────────

## 두 점 사이를 "몸통이" 지날 수 있는지 확인(자신·플레이어 몸은 제외).
## 중심선 한 발만 쏘면 두께가 0이라 벽 모서리를 스치는 경로도 뚫린 것으로 보고돼
## 직진에 들어갔다가 몸이 끼인다. 진행 방향 수직으로 몸통 반폭만큼 벌린
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

## project.godot에 입력 액션을 추가하지 않으려고 키코드를 직접 본다
## (사용자 미커밋 변경이 있는 파일이라 건드리지 않는다).
func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo \
			and event.keycode == KEY_F3:
		debug_draw = not debug_draw
		queue_redraw()


func _draw() -> void:
	if not debug_draw:
		return

	var mode := "직진"
	if not _is_chasing():
		mode = "순찰"
	elif not path_points.is_empty():
		mode = "경로(%d)" % path_points.size()

	# A* 경로 — 첫 선분은 자기 위치(로컬 원점)에서
	var previous := Vector2.ZERO
	for i in path_points.size():
		var point := to_local(path_points[i])
		draw_circle(point, 4.0, Color(0.3, 0.9, 1.0, 0.8))
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

	draw_string(ThemeDB.fallback_font, Vector2(-40, -34),
		"%s  stuck %.2f  grid %s" % [mode, stuck_time, "OK" if grid_ready else "X"],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1, 1, 0.6, 1))
