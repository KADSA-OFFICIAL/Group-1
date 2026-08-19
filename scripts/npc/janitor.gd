extends CharacterBody2D

## 수위아저씨 NPC.
## 경로탐색은 격자 A*(AStarGrid2D). 층 로드 시 벽 충돌 도형을 몸통 크기만큼
## 부풀려 격자에 표시하므로 문·방 안까지 경로가 나온다(복도 웨이포인트로는
## 문을 지나는 경로를 표현할 수 없어 방 안 플레이어를 추적하지 못했다).
## 추적: 몸통이 지나갈 직선이 트이면 직진, 아니면 A* 경로를 따라간다.
## 활성/비활성·격자 재생성은 floor_manager가 sync_floor로 제어한다.
##
## 순찰(#141): 무작위 배회가 아니라 층 씬의 문(Door_*)을 이어 만든 고정 루트를
## 돌고, 문 앞에 서면 잠시 멈춰 방을 확인한다. 기획서 5장 "정해진 순찰 루트를
## 돌며 가끔 각 방을 확인한다"에 맞춘 것이다. 문을 하나도 못 찾은 층에서는
## 예전의 무작위 복도 배회로 폴백한다.
## 플레이어는 발소리·열쇠 소리·혼잣말(하단 알림)로 수위의 위치를 가늠한다 —
## 벽 너머는 보이지 않으므로 소리가 유일한 단서다.
## 수위가 도는 층은 floor_manager의 JANITOR_FREE_FLOOR로 정한다(4층은 안전 구간).

# 플레이어는 320. 추격은 그보다 확실히 느려야 도망칠 여지가 남는다.
# #115에서 260이 너무 빨라 220으로 낮췄고, 새 맵이 넓어져(#159) 압박이
# 약해진 만큼 그 사이로 올렸다(220 → 240 → 250, 추격 = 플레이어의 78%).
# 여기가 사실상 상한이다 — 260부터는 직선 도주로 못 벗어나 #115처럼 된다.
@export var patrol_speed: float = 130.0
@export var chase_speed: float = 250.0
# 플레이어가 수위를 알아볼 수 있는 거리. 플레이어 PointLight2D가 512×512 방사
# 그라디언트(텍스처 반경 256) × texture_scale 1.3 ≈ 333px까지 비춘다.
# 카메라(zoom 1.25, 1600×900)의 가시 반경은 360px이라 이 범위는 항상 화면 안이다.
@export var sight_range: float = 320.0
# 시야에 들어온 뒤 추적을 시작하기까지의 유예 — 플레이어에게 반응 시간을 준다.
@export var reveal_delay: float = 1.0
# 시야를 잃은 뒤에도 추적을 유지하는 시간. 0이면 모퉁이를 도는 순간 태세를 풀어
# 돌진하다 갑자기 산책하는 모습이 된다.
@export var lose_sight_seconds: float = 1.5

const ARRIVE_DISTANCE := 6.0
const STUCK_SECONDS := 0.6      # 가려던 방향으로 못 나아간 시간이 이만큼이면 막힌 것
const PROGRESS_RATIO := 0.3     # 기대 전진량의 이 비율 미만이면 나아가지 못한 것으로 본다
const REPATH_SECONDS := 0.3     # 경로 재계산 주기
const CONTACT_DISTANCE := 30.0  # 이 안까지 붙으면 멈춰 마주보고 붙잡는다(#4)
const WALL_MASK := 1            # LOS 레이캐스트 대상(벽·바리케이드)

# 콜리전 캡슐(18×30)은 회전하지 않으므로 반폭이 축마다 다르다.
const BODY_HALF_WIDTH := 9.0
const BODY_HALF_HEIGHT := 15.0
# 벽에 밀착하면 몸통 반폭 위치가 벽면과 정확히 겹쳐 판정이 부동소수점에 좌우된다.
# 평행선을 1px 안쪽으로 넣어 "붙어서 걷는 것"이 막힘으로 뒤집히지 않게 한다.
const BODY_PROBE_MARGIN := 1.0

# 격자: 층 씬 크기에서 매번 계산한다. 예전엔 2800×1800 고정이라 맵이 커지자
# (#159로 3400×2500) 격자가 왼쪽 위만 덮어 바깥 구역이 통째로 경로탐색에서
# 빠졌다 — 1층 현관·수위실 띠(y 2120~2480)가 격자 밖이었다.
const CELL := 25.0
const GRID_FALLBACK := Vector2i(136, 100)
const PATH_LOOKAHEAD := 12      # 경로 다듬기에서 앞쪽 몇 지점까지 시야를 볼지
const FAR_SPAWN_RATIO := 0.6    # 스폰 후보: 플레이어에게서 최대 거리의 이 비율 이상인 칸

# ── 순찰 루트 (#141) ─────────────────────────────────────────────
# 문 앞 대기 지점은 문에서 복도 쪽으로 이만큼 물러난 곳. 문틀에 붙여 세우면
# 몸통이 벽에 끼어 도착 판정이 나지 않는다(몸통 반높이 15 + 벽 반두께 8 여유).
const DOOR_APPROACH := 46.0
const ROUTE_ARRIVE := 16.0      # 문 앞 도착 판정. 순찰은 정밀할 필요가 없어 넉넉히 잡는다
const INSPECT_SECONDS := 1.8    # 문 앞에 멈춰 방을 확인하는 시간

# ── 소리 단서 (#141) ─────────────────────────────────────────────
# 하단 알림으로 존재감을 전한다. 화면 밖·벽 너머의 수위를 플레이어가 감지할
# 유일한 수단이다. 알림은 서로를 덮어쓰므로(hud.gd의 notice_token) 쿨다운을
# 넉넉히 줘서 단서 조사 안내 문구를 밀어내지 않게 한다.
const EARSHOT := 720.0          # 열쇠 소리·혼잣말이 들리는 거리
const FOOTSTEP_RANGE := 420.0   # 이 안이면 발소리로 더 급하게 알린다
const MUTTER_COOLDOWN := 15.0
const SOUND_COOLDOWN := 9.0

# 잉크를 뒤집어쓴 동안의 몸 색. 왜 멈춰 있는지 한눈에 보이게 한다(#169).
const BLIND_BODY_COLOR := Color(0.2, 0.2, 0.3, 1.0)

# ── 발소리·열쇠 소리 (#9) ────────────────────────────────────────
# 하단 알림 텍스트(위 EARSHOT/FOOTSTEP_RANGE)는 그대로 두고 소리를 더한다.
# 소리는 AudioStreamPlayer2D의 거리 감쇠로 위치를 알려 주고, 텍스트는 소리를
# 못 듣는 상황에서도 단서가 남게 한다.
const STEP_INTERVAL_PATROL := 0.52   # 느릿느릿(기획서 5장)
const STEP_INTERVAL_CHASE := 0.30
const STEPS_PER_JINGLE := 4          # 몇 걸음마다 열쇠꾸러미가 찰랑이는가
const MOVING_SPEED_EPSILON := 10.0   # 이보다 느리면 멈춘 것으로 본다

# 자막에 붙는 화자 이름. 프롤로그(intro.gd)의 표기와 같아야 한다.
const SPEAKER_NAME := "수위"

const MUTTERS := [
	"…오늘도 아무도 없지.",
	"시우야, 아빠 순찰 중이야.",
	"다 끝나면 올라갈게.",
]

var player: CharacterBody2D = null
var my_floor: int = -1
var player_floor: int = -1

# F3 디버그 오버레이 — 이 환경에 Godot이 없어 실행 관찰을 사용자가 대신 해야 한다.
# 이상 동작이 보일 때 켜서 "직진인가 경로추적인가 / LOS가 막혔다고 보는가"를 확인한다.
var debug_draw: bool = false

var astar_grid := AStarGrid2D.new()
var grid_size: Vector2i = GRID_FALLBACK
var grid_ready: bool = false
var walkable_cells: Array[Vector2i] = []
var corridor_cells: Array[Vector2i] = []   # 순찰은 복도만 돈다(방 폴리곤 외부)

# 플레이어 시야에 연속으로 노출된 시간. reveal_delay를 넘기면 추적이 시작된다.
var seen_time: float = 0.0
# 이번 프레임에 보이는가. 소리 단서가 같은 판정을 또 쓰기 때문에 레이캐스트를
# 프레임당 한 번만 쏘도록 _update_awareness의 결과를 남겨 둔다.
var seen_now: bool = false
# 추적 유지 잔여 시간. 보이는 동안 계속 갱신되고, 시야를 잃으면 줄어든다.
var chase_hold: float = 0.0

var path_points: PackedVector2Array = PackedVector2Array()
var patrol_target: Vector2 = Vector2.ZERO
var repath_timer: float = 0.0
var stuck_time: float = 0.0

# 순찰 루트: route[i] = 문 앞 대기 지점, route_doors[i] = 그 문의 중심(확인할 때
# 바라보는 방향). 두 배열은 항상 같은 길이다.
var route: Array[Vector2] = []
var route_doors: Array[Vector2] = []
var route_index: int = 0
var route_step: int = 1        # 왕복 방향(+1 정방향 / -1 역방향)
var inspect_timer: float = 0.0

var mutter_cooldown: float = 0.0
var sound_cooldown: float = 0.0
# 발각 대사는 추적이 시작될 때 한 번만. 시야가 끊겼다 붙을 때마다 다시 외치면
# 알림이 도배된다.
var announced_chase: bool = false
var announced_catch: bool = false

var _game_state: Node = null

# 잉크를 뒤집어써 앞을 못 보는 남은 시간(#169). 0보다 크면 추적·순찰·접촉
# 판정이 전부 멈춘다.
var blind_timer: float = 0.0
var _body_color: Color = Color.WHITE

var step_timer: float = 0.0
var step_count: int = 0

@onready var body: Polygon2D = $Body
@onready var collision_shape: CollisionShape2D = $CollisionShape2D
@onready var step_sound: AudioStreamPlayer2D = $StepSound
@onready var key_sound: AudioStreamPlayer2D = $KeySound
@onready var door_sound: AudioStreamPlayer2D = $DoorSound


func _enter_tree() -> void:
	# 잉크통(#169)이 터진 자리에서 수위를 찾을 때 쓴다.
	add_to_group("janitor")


func _ready() -> void:
	_body_color = body.color
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
	# 층을 벗어나면 대사·소리 상태를 초기화한다. 그러지 않으면 다음 층에 내려간
	# 직후 쿨다운이 남아 첫 접근을 소리로 알리지 못한다.
	inspect_timer = 0.0
	mutter_cooldown = 0.0
	sound_cooldown = 0.0
	announced_chase = false
	announced_catch = false
	# 스턴(#169)도 층을 넘기지 않는다 — 3층에서 맞고 2층으로 내려가면 그 층의
	# 수위는 멀쩡해야 한다(같은 노드를 층마다 재사용한다).
	blind_timer = 0.0
	body.color = _body_color
	Sfx.set_chasing(false)
	if active and player != null:
		_spawn_away_from(player.position)


# ── 격자 ─────────────────────────────────────────────────────────

func _rebuild_grid(floor_root: Node) -> void:
	grid_size = _grid_size_for(floor_root)
	astar_grid.clear()
	astar_grid.region = Rect2i(0, 0, grid_size.x, grid_size.y)
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
		for cell_x in range(maxi(min_cell.x, 0), mini(max_cell.x, grid_size.x - 1) + 1):
			for cell_y in range(maxi(min_cell.y, 0), mini(max_cell.y, grid_size.y - 1) + 1):
				var cell := Vector2i(cell_x, cell_y)
				if grown.has_point(_cell_center(cell)):
					astar_grid.set_point_solid(cell, true)

	walkable_cells.clear()
	for cell_x in grid_size.x:
		for cell_y in grid_size.y:
			var cell := Vector2i(cell_x, cell_y)
			if not astar_grid.is_point_solid(cell):
				walkable_cells.append(cell)

	# 순찰용 복도 칸: 방 폴리곤 안에 들어가는 칸을 뺀다.
	var rooms: Array[Rect2] = []
	_collect_room_rects(floor_root, rooms)
	corridor_cells.clear()
	for cell in walkable_cells:
		var center := _cell_center(cell)
		var in_room := false
		for room in rooms:
			if room.has_point(center):
				in_room = true
				break
		if not in_room:
			corridor_cells.append(cell)
	if corridor_cells.is_empty():
		corridor_cells = walkable_cells.duplicate()

	_build_route(floor_root)

	# 경로탐색과 순찰 목표가 모두 준비된 뒤에 사용 가능으로 표시한다.
	grid_ready = not walkable_cells.is_empty()


## 층 씬의 문에서 고정 순찰 루트를 만든다(#141).
## 문 시각 노드는 WallGlow/RoomWallVisuals/Door_<방이름>, 대응하는 방 폴리곤은
## Rooms/<방이름>이다(tools/gen_floors.py가 이 규약으로 생성한다).
## 순서는 씬 순서의 첫 문에서 시작하는 최근접 이웃 — 씬 순서가 고정이라
## 층마다 항상 같은 루트가 나온다("정해진 순찰 루트").
func _build_route(floor_root: Node) -> void:
	route.clear()
	route_doors.clear()
	route_index = 0
	route_step = 1

	var visuals := floor_root.get_node_or_null("WallGlow/RoomWallVisuals")
	var rooms := floor_root.get_node_or_null("Rooms")
	if visuals == null or rooms == null:
		return

	var stops: Array[Vector2] = []
	var doors: Array[Vector2] = []
	for child in visuals.get_children():
		if not String(child.name).begins_with("Door_"):
			continue
		var door_polygon := child as Polygon2D
		if door_polygon == null or door_polygon.polygon.size() == 0:
			continue
		var room := rooms.get_node_or_null(String(child.name).trim_prefix("Door_")) as Polygon2D
		if room == null or room.polygon.size() == 0:
			continue

		var door_rect := _polygon_rect(door_polygon)
		var door_center := door_rect.position + door_rect.size * 0.5
		var stop := door_center + _outward(door_rect, _polygon_rect(room)) * DOOR_APPROACH
		# 봉인된 방·건물 밖으로 밀려난 문은 대기 지점이 벽 안에 들어간다 — 건너뛴다.
		if not _is_free_point(stop):
			continue
		stops.append(stop)
		doors.append(door_center)

	if stops.is_empty():
		return

	# 최근접 이웃으로 이어 붙인다. 씬 순서 그대로 돌면 맵을 가로질러 왔다 갔다
	# 하는 루트가 나와 순찰로 보이지 않는다.
	var remaining: Array[int] = []
	for i in stops.size():
		remaining.append(i)

	var current: int = remaining[0]
	remaining.remove_at(0)
	route.append(stops[current])
	route_doors.append(doors[current])
	while not remaining.is_empty():
		var best_slot := 0
		var best_distance := INF
		for slot in remaining.size():
			var distance: float = stops[remaining[slot]].distance_squared_to(stops[current])
			if distance < best_distance:
				best_distance = distance
				best_slot = slot
		current = remaining[best_slot]
		remaining.remove_at(best_slot)
		route.append(stops[current])
		route_doors.append(doors[current])


## 문이 붙은 벽면의 바깥 방향(복도 쪽). 문은 방 경계에 놓인 납작한 사각형이라
## 긴 변의 축이 벽면의 축이고, 짧은 축의 부호가 방 중심 반대편을 가리킨다.
func _outward(door_rect: Rect2, room_rect: Rect2) -> Vector2:
	var door_center := door_rect.position + door_rect.size * 0.5
	var room_center := room_rect.position + room_rect.size * 0.5
	if door_rect.size.x >= door_rect.size.y:
		return Vector2(0.0, 1.0 if door_center.y >= room_center.y else -1.0)
	return Vector2(1.0 if door_center.x >= room_center.x else -1.0, 0.0)


## 격자 안이고 몸통이 들어갈 수 있는 지점인가(_nearest_free_cell과 달리 보정하지
## 않는다 — 대기 지점은 "거기 설 수 있는가"가 그대로 조건이다).
func _is_free_point(point: Vector2) -> bool:
	var cell := _cell_of(point)
	if cell.x < 0 or cell.y < 0 or cell.x >= grid_size.x or cell.y >= grid_size.y:
		return false
	return not astar_grid.is_point_solid(cell)


## Polygon2D의 점들을 감싸는 전역 좌표 사각형.
## 문(WallGlow 아래)과 방(Rooms 아래)은 부모가 다르지만, CanvasLayer는 CanvasItem이
## 아니라 to_global 체인에 끼지 않고 층 씬 루트도 원점에 있어 둘 다 맵 좌표로 나온다.
func _polygon_rect(node: Polygon2D) -> Rect2:
	var polygon := node.polygon
	var rect := Rect2(node.to_global(polygon[0]), Vector2.ZERO)
	for i in range(1, polygon.size()):
		rect = rect.expand(node.to_global(polygon[i]))
	return rect


## 층 씬의 Floor 폴리곤에서 맵 크기를 읽어 격자 칸 수를 정한다.
func _grid_size_for(floor_root: Node) -> Vector2i:
	var floor_node := floor_root.get_node_or_null("Floor") as Polygon2D
	if floor_node == null or floor_node.polygon.size() == 0:
		return GRID_FALLBACK
	var extent := Vector2.ZERO
	for point in floor_node.polygon:
		extent = extent.max(floor_node.to_global(point))
	return Vector2i(int(ceil(extent.x / CELL)), int(ceil(extent.y / CELL)))


## 층 씬의 Rooms 아래 방 폴리곤 영역(순찰에서 제외할 실내)을 모은다.
func _collect_room_rects(floor_root: Node, out: Array[Rect2]) -> void:
	var rooms := floor_root.get_node_or_null("Rooms")
	if rooms == null:
		return
	for child in rooms.get_children():
		if child is Polygon2D:
			if (child as Polygon2D).polygon.size() == 0:
				continue
			out.append(_polygon_rect(child as Polygon2D))


## 층 씬에서 StaticBody2D 하위 충돌 도형만 모은다(Area2D 상호작용 존은 제외).
func _collect_blockers(node: Node, out: Array[Rect2]) -> void:
	for child in node.get_children():
		# SDPanel* = 미닫이 교실문. 수위가 다가가면 열리므로 격자에서는 늘
		# 열린 것으로 둔다. 막힌 것으로 세면 순찰 루트가 교실 앞에서 끊긴다
		# (tools/verify_janitor_route.py도 같은 이름 규칙을 쓴다).
		var body := child.get_parent() as Node
		var is_door := body != null and body.name.begins_with("SDPanel")
		if child.get_parent() is StaticBody2D and not is_door:
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
	cell.x = clampi(cell.x, 0, grid_size.x - 1)
	cell.y = clampi(cell.y, 0, grid_size.y - 1)
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
						or probe.x >= grid_size.x or probe.y >= grid_size.y:
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

	# 순찰이 기본 상태이므로 복도에서 등장한다.
	var max_distance := 0.0
	for cell in corridor_cells:
		max_distance = maxf(max_distance, _cell_center(cell).distance_to(player_position))

	# 가장 먼 한 칸만 쓰면 매번 같은 구석에서 나온다 — 충분히 먼 칸 중 무작위.
	var candidates: Array[Vector2i] = []
	for cell in corridor_cells:
		if _cell_center(cell).distance_to(player_position) >= max_distance * FAR_SPAWN_RATIO:
			candidates.append(cell)
	if candidates.is_empty():
		return

	position = _cell_center(candidates.pick_random())
	path_points = PackedVector2Array()
	patrol_target = position
	repath_timer = 0.0
	stuck_time = 0.0
	seen_time = 0.0
	chase_hold = 0.0
	_snap_route_to_position()


## 스폰 지점에서 가장 가까운 문부터 루트를 시작한다. 항상 route[0]부터 돌면
## 층에 진입할 때마다 맵 반대편으로 먼저 걸어가는 모습이 된다.
func _snap_route_to_position() -> void:
	inspect_timer = 0.0
	if route.is_empty():
		return

	var best := 0
	var best_distance := INF
	for i in route.size():
		var distance := route[i].distance_squared_to(position)
		if distance < best_distance:
			best_distance = distance
			best = i
	route_index = best
	route_step = 1
	patrol_target = route[route_index]


# ── 이동 ─────────────────────────────────────────────────────────

func _physics_process(delta: float) -> void:
	if blind_timer > 0.0:
		Sfx.set_chasing(false)
		_hold_blinded(delta)
		return

	_update_awareness(delta)

	mutter_cooldown = maxf(mutter_cooldown - delta, 0.0)
	sound_cooldown = maxf(sound_cooldown - delta, 0.0)

	var chasing := _is_chasing()
	if chasing:
		if not announced_chase:
			announced_chase = true
			_say_line("…누구야?")
			Sfx.play(&"spotted")
		_move_chase(delta)
	else:
		announced_chase = false
		_update_sound_cues()
		_move_patrol(delta)

	_update_footsteps(delta, chasing)
	Sfx.set_chasing(chasing)

	if debug_draw:
		queue_redraw()


## 걸을 때만 발소리를 낸다. 방 확인·스턴처럼 멈춰 있을 때는 조용해야
## 플레이어가 "지금 어디 서 있구나"를 소리로 읽을 수 있다.
func _update_footsteps(delta: float, chasing: bool) -> void:
	if velocity.length() < MOVING_SPEED_EPSILON:
		# 멈추면 다음 걸음이 바로 나도록 타이머를 채워 둔다.
		step_timer = STEP_INTERVAL_PATROL
		return

	step_timer -= delta
	if step_timer > 0.0:
		return

	step_timer = STEP_INTERVAL_CHASE if chasing else STEP_INTERVAL_PATROL
	step_sound.play()

	step_count += 1
	if step_count % STEPS_PER_JINGLE == 0:
		key_sound.play()


# ── 잉크통 스턴 (#169) ───────────────────────────────────────────

## 잉크를 뒤집어썼다. 추적을 끊고 제자리에 세운다.
## ink_projectile.gd가 터진 자리에서 호출한다.
func blind(seconds: float) -> void:
	# 겹쳐 맞아도 시간이 누적되지는 않는다 — 잉크통은 하나뿐이라 실제로는
	# 일어나지 않지만, 더 긴 쪽을 남기는 편이 예측하기 쉽다.
	blind_timer = maxf(blind_timer, seconds)

	seen_time = 0.0
	chase_hold = 0.0
	seen_now = false
	inspect_timer = 0.0
	path_points = PackedVector2Array()
	velocity = Vector2.ZERO
	announced_chase = false
	body.color = BLIND_BODY_COLOR

	_say_line("으윽— 뭐야, 뭐야 이거!")


## 스턴 동안은 제자리에 선다. move_and_slide를 계속 부르는 것은 플레이어가
## 밀고 들어와도 겹쳐 서지 않게 하려는 것이다. 발각·접촉 판정은 아예 돌지
## 않으므로 이 사이에 옆을 지나가도 붙잡히지 않는다.
func _hold_blinded(delta: float) -> void:
	velocity = Vector2.ZERO
	move_and_slide()

	blind_timer -= delta
	if blind_timer <= 0.0:
		blind_timer = 0.0
		body.color = _body_color
		repath_timer = 0.0
		_say("수위가 눈을 문지르며 다시 걷기 시작한다.")

	if debug_draw:
		queue_redraw()


## 발각 상태 갱신. 추적 여부는 chase_hold 하나로 결정된다.
func _update_awareness(delta: float) -> void:
	# 은신(#6)은 즉시 추적을 끊는다. 여기에 유지 시간을 주면 캐비넷에 숨은
	# 직후에도 수위가 들이닥쳐 접촉 판정(#4)으로 붙잡히므로 은신이 무의미해진다.
	if player != null and player.get("is_hiding") == true:
		seen_time = 0.0
		chase_hold = 0.0
		seen_now = false
		return

	seen_now = _can_be_seen()
	if seen_now:
		seen_time += delta
		# 이미 추적 중이면 재확인에 유예를 다시 요구하지 않는다 — 유예는 최초
		# 발각에만 적용된다. 그러지 않으면 시야를 끊었다 다시 보일 때마다
		# 추적이 잠깐 풀렸다 붙는 깜빡임이 생긴다.
		if seen_time >= reveal_delay or chase_hold > 0.0:
			chase_hold = lose_sight_seconds
	else:
		seen_time = 0.0
		chase_hold = maxf(chase_hold - delta, 0.0)


## 플레이어가 수위를 실제로 볼 수 있는가.
## 어두운 학교라 손전등이 닿는 거리(sight_range) 안이어야 하고, 벽에 가리면 안 된다.
## 손전등은 원형이라 시야각은 없다 — 방향은 보지 않는다.
## 여기서 쓰는 것은 중심선 레이 1발이다. _clear_line(몸통 통과 가능성)은 이동용이고,
## "보이는지"와는 다른 문제다.
## 혹시 모를 어긋남 대비로 같은 층 조건은 유지한다.
func _can_be_seen() -> bool:
	if player == null or player_floor != my_floor:
		return false
	if position.distance_to(player.position) > sight_range:
		return false
	return _clear_ray(position, player.position)


## 최초 발각은 시야에 reveal_delay만큼 연속 노출돼야 하고, 그 뒤 시야를 잃어도
## lose_sight_seconds 동안은 추적을 유지한다(모퉁이에서 갑자기 태세를 푸는 것 방지).
func _is_chasing() -> bool:
	return chase_hold > 0.0


func _move_chase(delta: float) -> void:
	if position.distance_to(player.position) <= CONTACT_DISTANCE:
		velocity = Vector2.ZERO
		body.rotation = position.direction_to(player.position).angle() - Vector2.UP.angle()
		stuck_time = 0.0
		_catch_player()
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


## 붙잡힘 통보. 접촉 상태가 유지되는 동안 매 프레임 불리지만
## game_state가 첫 호출만 통과시키므로 여기서 따로 가드하지 않는다.
func _catch_player() -> void:
	if not announced_catch:
		announced_catch = true
		_say_line("학생이네. 나와. 같이 수위실로 가자.")
		Sfx.play(&"caught")

	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null:
		game_state.call("trigger_game_over", "caught")


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

	if route.is_empty():
		_move_wander(delta)   # 문을 못 찾은 층 폴백(#141 이전 동작)
		return

	if inspect_timer > 0.0:
		_hold_at_door(delta)
		return

	if position.distance_to(patrol_target) <= ROUTE_ARRIVE:
		_begin_inspection()
		return

	# 문 앞까지 못 가는 경우(가구 배치·봉인 등으로 길이 막힘)엔 그 문을 포기하고
	# 다음 문으로 넘어간다. 붙잡고 있으면 순찰이 그 자리에서 멈춘다.
	if stuck_time >= STUCK_SECONDS:
		stuck_time = 0.0
		_advance_route()
		return

	repath_timer -= delta
	if repath_timer <= 0.0:
		repath_timer = REPATH_SECONDS
		path_points = astar_grid.get_point_path(
			_nearest_free_cell(position), _nearest_free_cell(patrol_target))

	_step_toward(_next_point(patrol_target), patrol_speed, delta)


## 문 앞에 도착 — 멈춰서 방 안을 확인한다.
func _begin_inspection() -> void:
	inspect_timer = INSPECT_SECONDS
	velocity = Vector2.ZERO
	path_points = PackedVector2Array()
	stuck_time = 0.0
	door_sound.play()
	_notice_inspection()


## 확인하는 동안은 제자리에서 문 쪽을 바라본다. move_and_slide를 계속 부르는
## 것은 플레이어가 밀고 들어와도 겹쳐 서지 않게 하려는 것이다.
func _hold_at_door(delta: float) -> void:
	velocity = Vector2.ZERO
	move_and_slide()

	var facing := position.direction_to(route_doors[route_index])
	if facing != Vector2.ZERO:
		body.rotation = facing.angle() - Vector2.UP.angle()

	inspect_timer -= delta
	if inspect_timer <= 0.0:
		_advance_route()


## 다음 문으로. 순환이 아니라 왕복이다 — 끝 문에서 첫 문으로 돌아가는 순환
## 루트는 맵을 가로지르는 긴 구간을 만든다(1층에서 3000px, 23초를 아무 방도
## 안 들르고 걷는다). 끝에 닿으면 방향을 뒤집어 왔던 복도를 되짚는다.
func _advance_route() -> void:
	inspect_timer = 0.0
	if route.is_empty():
		return

	if route_index + route_step < 0 or route_index + route_step >= route.size():
		route_step = -route_step
	route_index = clampi(route_index + route_step, 0, route.size() - 1)
	patrol_target = route[route_index]
	path_points = PackedVector2Array()
	repath_timer = 0.0


## 문 정보를 못 얻은 층에서의 예전 순찰 — 무작위 복도 지점을 오간다.
func _move_wander(delta: float) -> void:
	repath_timer -= delta
	if path_points.is_empty() or stuck_time >= STUCK_SECONDS \
			or position.distance_to(patrol_target) <= ARRIVE_DISTANCE:
		stuck_time = 0.0
		repath_timer = REPATH_SECONDS
		patrol_target = _cell_center(corridor_cells.pick_random())
		path_points = astar_grid.get_point_path(
			_nearest_free_cell(position), _nearest_free_cell(patrol_target))

	_step_toward(_next_point(patrol_target), patrol_speed, delta)


# ── 소리 단서·혼잣말 (#141) ──────────────────────────────────────

func _say(text: String) -> void:
	if _refresh_game_state():
		_game_state.call("request_notice", text)


## 수위가 입으로 내는 말. 지문(_say)과 달리 화자 이름이 붙은 자막으로 나간다(#193) —
## 프롤로그에서 수위 대사가 나오는 모양과 같아야 한다.
func _say_line(text: String) -> void:
	if _refresh_game_state():
		_game_state.call("request_speech", SPEAKER_NAME, text, "")


func _refresh_game_state() -> bool:
	if _game_state == null or not is_instance_valid(_game_state):
		_game_state = get_tree().get_first_node_in_group("game_state")
	return _game_state != null


## 같은 층에 있다는 것을 소리로 알린다. 이미 보이는 중이면 알리지 않는다 —
## 화면에 있는 것을 글로 또 말할 필요가 없고, 소리 단서는 벽 너머에서 의미가 있다.
func _update_sound_cues() -> void:
	if player == null or sound_cooldown > 0.0 or seen_now:
		return

	var distance := position.distance_to(player.position)
	if distance <= FOOTSTEP_RANGE:
		sound_cooldown = SOUND_COOLDOWN
		_say("발소리. 복도 저쪽에서. 느릿느릿.")
	elif distance <= EARSHOT:
		sound_cooldown = SOUND_COOLDOWN
		_say("— 찰랑. 열쇠꾸러미 소리. 가까워지고 있다.")


## 방을 확인할 때의 연출. 들리는 거리 안에서만 나온다.
## 혼잣말이 쿨다운이면 문 여는 소리로 대신해, 가까이 있는데 아무 기척도 없는
## 구간이 생기지 않게 한다.
func _notice_inspection() -> void:
	if player == null or position.distance_to(player.position) > EARSHOT:
		return

	if mutter_cooldown <= 0.0:
		mutter_cooldown = MUTTER_COOLDOWN
		_say_line(MUTTERS.pick_random())
	elif sound_cooldown <= 0.0:
		sound_cooldown = SOUND_COOLDOWN
		_say("문이 열리는 소리. 수위가 방을 확인하고 있다.")


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
	if blind_timer > 0.0:
		mode = "실명 %.1f" % blind_timer
	elif not _is_chasing():
		# 보이는 중이면 발각까지 남은 시간을, 아니면 순찰임을 보여준다.
		if seen_time > 0.0:
			mode = "발각까지 %.2f" % maxf(reveal_delay - seen_time, 0.0)
		elif inspect_timer > 0.0:
			mode = "방 확인 %.1f" % inspect_timer
		elif route.is_empty():
			mode = "배회"
		else:
			mode = "순찰 %d/%d" % [route_index + 1, route.size()]
	else:
		if not path_points.is_empty():
			mode = "경로(%d)" % path_points.size()
		# 시야를 잃고 유지 시간으로 쫓는 중이면 남은 시간을 덧붙인다.
		if not _can_be_seen():
			mode += " 유지%.2f" % chase_hold

	# 순찰 루트 — 다음 목표는 채운 원, 나머지 문 앞 지점은 테두리만
	for i in route.size():
		var stop := to_local(route[i])
		if i == route_index:
			draw_circle(stop, 7.0, Color(1.0, 0.6, 0.2, 0.85))
		else:
			draw_arc(stop, 5.0, 0.0, TAU, 12, Color(1.0, 0.6, 0.2, 0.35), 1.5)

	# A* 경로 — 첫 선분은 자기 위치(로컬 원점)에서
	var previous := Vector2.ZERO
	for i in path_points.size():
		var point := to_local(path_points[i])
		draw_circle(point, 4.0, Color(0.3, 0.9, 1.0, 0.8))
		draw_line(previous, point, Color(0.3, 0.9, 1.0, 0.6), 2.0)
		previous = point

	# 플레이어가 알아볼 수 있는 거리 — 이 안이고 벽에 안 가리면 발각이 누적된다
	draw_arc(Vector2.ZERO, sight_range, 0.0, TAU, 48, Color(1, 1, 0.5, 0.18), 1.0)

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
		"%s  보임 %s  stuck %.2f  grid %s"
			% [mode, "O" if _can_be_seen() else "X", stuck_time,
				"OK" if grid_ready else "X"],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1, 1, 0.6, 1))
