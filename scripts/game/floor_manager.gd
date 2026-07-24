extends Node2D

## 계단 반쪽(위층/아래층)을 끝까지 걸어가면 층을 전환한다.
## 전제: 계단실 위치·분할 좌표가 전 층 동일(수직 정렬).
## 왼쪽 반 = 위층(N+1), 오른쪽 반 = 아래층(N-1).

const FLOOR_SCENES := {
	1: "res://scenes/background/school_floor_1.tscn",
	2: "res://scenes/background/school_floor_2.tscn",
	3: "res://scenes/background/school_floor_3.tscn",
	4: "res://scenes/background/school_floor_4.tscn",
	5: "res://scenes/background/school_floor_5.tscn",
}
const MIN_FLOOR := 1
const MAX_FLOOR := 5
const START_FLOOR := 5
const JANITOR_FREE_FLOOR := 5  # 수위아저씨가 나타나지 않는 층

# 전환 트리거 존: 각 계단실 반쪽의 안쪽 끝 (인덱스 0=좌상단 계단, 1=중앙 하단 계단)
const UP_ZONES := [Rect2(136, 930, 196, 54), Rect2(1196, 1610, 166, 54)]
const DOWN_ZONES := [Rect2(348, 930, 196, 54), Rect2(1378, 1610, 166, 54)]
# 도착 지점: 계단실 입구 바로 앞 복도 (입구가 잠겨 있어도 갇히지 않도록 계단실 밖)
# 올라가면 입구 오른쪽 앞, 내려가면 입구 왼쪽 앞에서 등장
const ARRIVE_AFTER_UP := [Vector2(399, 692), Vector2(1429, 1372)]
const ARRIVE_AFTER_DOWN := [Vector2(281, 692), Vector2(1311, 1372)]

var current_floor: int = START_FLOOR
var changing_floor: bool = false

@onready var player: CharacterBody2D = $Player
@onready var janitor: CharacterBody2D = $Janitor
@onready var floor_label: Label = $UI/FloorLabel
@onready var fade_rect: ColorRect = $UI/FadeRect

const FADE_IN_SECONDS := 1.5
const FLOOR_FADE_OUT_SECONDS := 0.25
const FLOOR_FADE_IN_SECONDS := 0.35
const START_HINT := "문은 잠겨서 열리지 않는다. …아래쪽 창문으로 나가는 게 좋겠어."


func _ready() -> void:
	_update_floor_label()
	janitor.sync_floor(current_floor != JANITOR_FREE_FLOOR, current_floor, player)
	fade_rect.color.a = 1.0
	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 0.0, FADE_IN_SECONDS)
	tween.tween_callback(_show_start_hint)


func _show_start_hint() -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null:
		game_state.call("request_notice", START_HINT)


func _physics_process(_delta: float) -> void:
	if changing_floor:
		return

	var pos := player.position

	for i in UP_ZONES.size():
		if UP_ZONES[i].has_point(pos) and current_floor < MAX_FLOOR:
			_change_floor(current_floor + 1, ARRIVE_AFTER_UP[i])
			return

	for i in DOWN_ZONES.size():
		if DOWN_ZONES[i].has_point(pos) and current_floor > MIN_FLOOR:
			_change_floor(current_floor - 1, ARRIVE_AFTER_DOWN[i])
			return


func _change_floor(target: int, arrive: Vector2) -> void:
	changing_floor = true

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
	janitor.sync_floor(current_floor != JANITOR_FREE_FLOOR, current_floor, player)

	var camera: Camera2D = player.get_node_or_null("Camera2D")
	if camera != null:
		camera.reset_smoothing()


func _update_floor_label() -> void:
	floor_label.text = "%d층" % current_floor
