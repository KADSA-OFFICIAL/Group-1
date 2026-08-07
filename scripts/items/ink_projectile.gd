extends Node2D

## 던진 잉크통(#169). 바라보는 방향으로 날아가다 벽에 맞거나 사거리를 다하면
## 그 자리에서 터지고, 터진 지점 반경 안의 수위 눈을 잠시 멀게 한다.
##
## 물리 바디를 쓰지 않고 프레임마다 레이캐스트로 벽을 확인한다. Area2D로 하면
## 층 씬의 상호작용 존(collision_layer 2)과 섞이고, RigidBody2D는 이 게임에
## 물리 상호작용이 하나도 없는데 혼자 튀는 물체가 된다.
##
## 플레이어(player_controller.gd)가 던질 때 launch()로 방향을 넣어 준다.

const SPEED := 560.0
const MAX_RANGE := 540.0        # 수위 인지 거리(320)보다 넉넉히 — 보고 나서 던질 여유
const SPLASH_RADIUS := 120.0
const BLIND_SECONDS := 5.0      # 플레이어 속도 320 기준 약 1600px 도주 거리
const SPLASH_SECONDS := 0.8     # 터진 자국이 보이는 시간
const WALL_MASK := 1            # 벽·바리케이드(janitor.gd와 같은 레이어)
const WALL_BACKOFF := 10.0      # 벽에 박혀 그려지지 않게 접점에서 물러나는 거리

@onready var can: Polygon2D = $Can
@onready var splash: Polygon2D = $Splash

var direction: Vector2 = Vector2.RIGHT
var travelled: float = 0.0
var landed: bool = false


func _ready() -> void:
	splash.visible = false


## 플레이어가 던지는 순간 호출한다. 방향이 0이면 아래로 던진다(가만히 서서
## 던질 때 facing_direction이 비어 있는 경우 대비).
func launch(from: Vector2, throw_direction: Vector2) -> void:
	position = from
	direction = throw_direction.normalized() if throw_direction != Vector2.ZERO \
		else Vector2.DOWN


func _physics_process(delta: float) -> void:
	if landed:
		return

	var step := SPEED * delta
	var next_position := position + direction * step

	var query := PhysicsRayQueryParameters2D.create(
		position, next_position, WALL_MASK, [])
	var hit := get_world_2d().direct_space_state.intersect_ray(query)
	if not hit.is_empty():
		_land(hit["position"] - direction * WALL_BACKOFF)
		return

	position = next_position
	can.rotation += TAU * delta   # 굴러가는 느낌
	travelled += step
	if travelled >= MAX_RANGE:
		_land(position)


func _land(at: Vector2) -> void:
	landed = true
	position = at
	can.visible = false
	splash.visible = true

	_splash_on_janitor()

	var tween := create_tween()
	tween.tween_property(splash, "modulate:a", 0.0, SPLASH_SECONDS)
	tween.tween_callback(queue_free)


## 터진 지점 근처의 수위를 멀게 한다. 수위는 활동하지 않는 층에서 숨겨져 있으므로
## visible로 거른다 — 4층(안전 구간)에서 던져도 보이지 않는 수위가 맞지 않는다.
func _splash_on_janitor() -> void:
	var game_state := get_tree().get_first_node_in_group("game_state")
	var janitor := get_tree().get_first_node_in_group("janitor") as Node2D

	if janitor != null and janitor.visible \
			and janitor.position.distance_to(position) <= SPLASH_RADIUS:
		janitor.call("blind", BLIND_SECONDS)
		return

	if game_state != null:
		game_state.call("request_notice", "잉크통이 바닥에 터졌다. 빗나갔다.")
