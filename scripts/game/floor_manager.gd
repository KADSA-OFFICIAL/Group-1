extends Node2D

## 계단 반쪽(위층/아래층)을 끝까지 걸어가면 층을 전환한다.
## 왼쪽 반 = 위층(N+1), 오른쪽 반 = 아래층(N-1).
##
## 계단실 좌표는 더 이상 전 층 동일이 아니다(#159 손도면 개편) — 1층은 계단이
## 한 곳뿐이고 위치도 다르다. 그래서 층별 계단실 사각형 STAIRS를 두고,
## 트리거 존·도착 지점을 사각형에서 계산한다. 값은 tools/gen_floors.py의
## STAIR_A / STAIR_B / FLOOR1["stair"]와 일치해야 하며,
## tools/verify_stairs.py가 씬과 대조해 어긋나면 실패한다.

const FLOOR_SCENES := {
	1: "res://scenes/background/school_floor_1.tscn",
	2: "res://scenes/background/school_floor_2.tscn",
	3: "res://scenes/background/school_floor_3.tscn",
	4: "res://scenes/background/school_floor_4.tscn",
	5: "res://scenes/background/school_floor_5.tscn",
}
const MIN_FLOOR := 1
const MAX_FLOOR := 4  # 5층은 프롤로그 전용 — 본편에서 올라가지 않는다
const START_FLOOR := 4
# 시작 층은 안전 구간 — 기획서상 수위는 3층부터 활동한다.
const JANITOR_FREE_FLOOR := 4

# 층별 계단실 사각형. 인덱스 0 = 위쪽(좌측) 계단, 1 = 하단 중앙 계단.
# 1층은 도면상 계단이 한 곳뿐이라 목록 길이가 1이다.
const STAIR_A := Rect2(300, 720, 440, 280)
const STAIR_B := Rect2(1450, 2120, 440, 320)
const STAIRS := {
	1: [Rect2(220, 2120, 440, 320)],
	2: [STAIR_A, STAIR_B],
	3: [STAIR_A, STAIR_B],
	4: [STAIR_A, STAIR_B],
	5: [STAIR_A, STAIR_B],
}

const WALL_T := 16.0     # 계단실 벽 두께
const RAIL_HALF := 8.0   # 가운데 분할 난간 반두께
const ZONE_H := 54.0     # 트리거 존 높이(계단 안쪽 끝)
const ARRIVE_DY := 28.0  # 도착 지점: 입구 바로 앞 복도(계단실 밖)
const ARRIVE_DX := 59.0  # 올라오면 입구 오른쪽, 내려오면 왼쪽으로 비켜 등장


func _stair_zone(r: Rect2, up: bool) -> Rect2:
	var mid := r.position.x + r.size.x / 2.0
	var y_end := r.position.y + r.size.y - WALL_T
	if up:
		var x0 := r.position.x + WALL_T
		return Rect2(x0, y_end - ZONE_H, (mid - RAIL_HALF) - x0, ZONE_H)
	var x1 := r.position.x + r.size.x - WALL_T
	return Rect2(mid + RAIL_HALF, y_end - ZONE_H, x1 - (mid + RAIL_HALF), ZONE_H)


## 도착 지점은 "목표 층"의 계단실 기준으로 잡는다. 층마다 계단 수가 달라
## (1층은 1곳) 인덱스가 없으면 마지막 계단으로 떨어진다.
func _arrive_on(target: int, index: int, up: bool) -> Vector2:
	var list: Array = STAIRS[target]
	var r: Rect2 = list[min(index, list.size() - 1)]
	var mid := r.position.x + r.size.x / 2.0
	return Vector2(mid + (ARRIVE_DX if up else -ARRIVE_DX), r.position.y - ARRIVE_DY)

var current_floor: int = START_FLOOR
var changing_floor: bool = false

@onready var player: CharacterBody2D = $Player
@onready var janitor: CharacterBody2D = $Janitor
@onready var floor_label: Label = $UI/FloorLabel
@onready var fade_rect: ColorRect = $UI/FadeRect

const FADE_IN_SECONDS := 1.5
const FLOOR_FADE_OUT_SECONDS := 0.25
const FLOOR_FADE_IN_SECONDS := 0.35
const START_HINT := "4층 복도. 계단으로 내려가야 한다. 이 층 어딘가에 계단 열쇠가 있을 것이다."

# 붙잡힌 순간을 잠깐 보여준 뒤 실패 화면으로 넘어간다(수위가 마주보는 연출).
const GAME_OVER_SCENE := "res://scenes/ui/game_over.tscn"
const GAME_OVER_FADE_SECONDS := 1.2

var game_over_active: bool = false


func _ready() -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null:
		game_state.connect("game_over", _on_game_over)

	_update_floor_label()
	janitor.sync_floor(current_floor != JANITOR_FREE_FLOOR, current_floor, player, $Background)
	fade_rect.color.a = 1.0
	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 0.0, FADE_IN_SECONDS)
	tween.tween_callback(_show_start_hint)


func _show_start_hint() -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null:
		game_state.call("request_notice", START_HINT)


## 붙잡힘 → 조작 정지 후 실패 화면. game_state가 중복 발동을 막지만,
## 층 전환 페이드와 겹치면 트윈이 서로 알파를 다투므로 여기서도 가드한다.
func _on_game_over(reason: String) -> void:
	if game_over_active:
		return
	game_over_active = true
	changing_floor = true   # 계단 트리거 검사 정지

	# 플레이어는 이동(_physics_process)과 E 상호작용(_unhandled_input)을 모두 끊고,
	# 수위는 붙잡은 자리에 그대로 세워 둔다.
	player.velocity = Vector2.ZERO
	player.set_physics_process(false)
	player.set_process_unhandled_input(false)
	janitor.set_physics_process(false)

	GameOverScreen.pending_reason = reason

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, GAME_OVER_FADE_SECONDS)
	tween.tween_callback(func() -> void:
		get_tree().change_scene_to_file(GAME_OVER_SCENE))


func _physics_process(_delta: float) -> void:
	if changing_floor:
		return

	var pos := player.position
	var stairs: Array = STAIRS[current_floor]

	for i in stairs.size():
		var r: Rect2 = stairs[i]
		if current_floor < MAX_FLOOR and _stair_zone(r, true).has_point(pos):
			_change_floor(current_floor + 1, _arrive_on(current_floor + 1, i, true))
			return
		if current_floor > MIN_FLOOR and _stair_zone(r, false).has_point(pos):
			_change_floor(current_floor - 1, _arrive_on(current_floor - 1, i, false))
			return


func _change_floor(target: int, arrive: Vector2) -> void:
	changing_floor = true

	Sfx.play(&"stairs")

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, FLOOR_FADE_OUT_SECONDS)
	tween.tween_callback(_swap_floor.bind(target, arrive))
	tween.tween_property(fade_rect, "color:a", 0.0, FLOOR_FADE_IN_SECONDS)
	tween.tween_callback(func() -> void:
		changing_floor = false)


func _swap_floor(target: int, arrive: Vector2) -> void:
	var old_background: Node = $Background
	var next_background: Node2D = load(FLOOR_SCENES[target]).instantiate()
	var background_index := old_background.get_index()

	old_background.name = "BackgroundOld"
	next_background.name = "Background"
	add_child(next_background)
	move_child(next_background, background_index)
	old_background.queue_free()

	player.position = arrive
	current_floor = target
	_update_floor_label()
	# 새 층 씬의 벽으로 수위 경로탐색 격자를 다시 만든다(위에서 add_child 완료됨)
	janitor.sync_floor(current_floor != JANITOR_FREE_FLOOR, current_floor, player,
		next_background)

	var camera: Camera2D = player.get_node_or_null("Camera2D")
	if camera != null:
		camera.reset_smoothing()


func _update_floor_label() -> void:
	floor_label.text = "%d층" % current_floor
