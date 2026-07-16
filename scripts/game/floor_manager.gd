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
const START_FLOOR := 3

# 전환 트리거 존: 각 계단실 반쪽의 안쪽 끝 (인덱스 0=좌상단 계단, 1=중앙 하단 계단)
const UP_ZONES := [Rect2(136, 930, 196, 54), Rect2(1196, 1610, 166, 54)]
const DOWN_ZONES := [Rect2(348, 930, 196, 54), Rect2(1378, 1610, 166, 54)]
# 도착 지점: 들어간 반쪽과 같은 반쪽의 입구 (트리거 존 밖)
# 위층 이동 = 왼쪽 반 입구, 아래층 이동 = 오른쪽 반 입구
const ARRIVE_AFTER_UP := [Vector2(234, 760), Vector2(1279, 1445)]
const ARRIVE_AFTER_DOWN := [Vector2(446, 760), Vector2(1461, 1445)]

var current_floor: int = START_FLOOR

@onready var player: CharacterBody2D = $Player


func _physics_process(_delta: float) -> void:
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

	var camera: Camera2D = player.get_node_or_null("Camera2D")
	if camera != null:
		camera.reset_smoothing()
