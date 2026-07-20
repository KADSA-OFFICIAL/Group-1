extends CharacterBody2D

## 수위아저씨 순찰 NPC.
## 층 공통 복도 뼈대의 웨이포인트 그래프를 무작위로 순찰한다.
## 활성/비활성과 스폰 위치는 floor_manager가 set_active로 제어한다.

@export var speed: float = 140.0

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

var target_waypoint: String = "main_mid"
var previous_waypoint: String = ""
var stuck_time: float = 0.0
var last_position: Vector2 = Vector2.ZERO

@onready var body: Polygon2D = $Body
@onready var collision_shape: CollisionShape2D = $CollisionShape2D


func _ready() -> void:
	set_active(false)


## active=false면 숨기고 물리를 멈춘다. active=true면 player_position에서
## 가장 먼 웨이포인트에 스폰해 순찰을 시작한다(층 진입 시 화면 밖 등장 보장).
func set_active(active: bool, player_position: Vector2 = Vector2.ZERO) -> void:
	visible = active
	set_physics_process(active)
	collision_shape.set_deferred("disabled", not active)
	if active:
		_spawn_away_from(player_position)


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
	stuck_time = 0.0
	last_position = position


func _physics_process(delta: float) -> void:
	var target: Vector2 = WAYPOINTS[target_waypoint]

	if position.distance_to(target) <= ARRIVE_DISTANCE:
		_pick_next_waypoint()
		return

	var direction := position.direction_to(target)
	velocity = direction * speed
	move_and_slide()
	body.rotation = direction.angle() - Vector2.UP.angle()

	# 플레이어 등에 막혀 제자리걸음이면 왔던 길로 돌아간다.
	if position.distance_to(last_position) < speed * delta * 0.25:
		stuck_time += delta
		if stuck_time >= STUCK_SECONDS:
			_turn_around()
	else:
		stuck_time = 0.0
	last_position = position


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
