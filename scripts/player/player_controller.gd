extends CharacterBody2D

@export var speed: float = 320.0

## 은신(#6): 숨은 동안 이동이 잠기고 수위아저씨가 발각하지 않는다.
## 빛을 완전히 끄면 수위가 지나가는지 볼 수 없어 나올 시점을 판단할 근거가
## 사라진다. 발각 판정은 빛과 무관하므로 끄지 않고 어둡게만 낮춘다.
const HIDDEN_LIGHT_ENERGY := 0.5
const HIDDEN_PROMPT := "나오기"

## 스프라이트(#210): 서 있을 땐 정면 대기 포즈, 움직이면 달리기 포즈.
## 달리기 그림은 오른쪽을 보고 있어 왼쪽으로 갈 때만 뒤집는다.
## 두 장 모두 tools/gen_player_sprites.py가 원본 아트에서 만든다.
const IDLE_TEXTURE := preload("res://assets/sprites/player_idle.png")
const RUN_TEXTURE := preload("res://assets/sprites/player_run.png")
## 40x48 스프라이트(중앙 정렬)의 발끝을 충돌 캡슐 바닥(y=13)에 맞추는 오프셋.
const SPRITE_OFFSET_Y := -10.0
## 달리기 포즈가 한 장뿐이라 1px 위아래로 흔들어 걸음을 만든다.
const BOB_INTERVAL := 0.14
const BOB_HEIGHT := 1.0

## 잉크통 던지기(#169). 손에서 조금 앞에 놓고 던져야 벽에 붙어 있을 때
## 자기 발밑에서 터지지 않는다.
const INK_ITEM_ID := "ink_can"
const INK_PROJECTILE := preload("res://scenes/items/ink_projectile.tscn")
const INK_SPAWN_OFFSET := 24.0

@onready var body: Sprite2D = $Body
@onready var interaction_area: Area2D = $InteractionArea
@onready var interact_prompt: Label = $InteractPrompt
@onready var player_light: PointLight2D = $PlayerLight

var facing_direction: Vector2 = Vector2.DOWN
var is_hiding: bool = false
var _light_energy: float = 1.0
## 위아래로만 움직일 땐 직전 좌우를 유지한다(스프라이트가 제자리에서 뒤집히지 않게).
var _facing_right: bool = true
var _bob_time: float = 0.0


func _ready() -> void:
	_light_energy = player_light.energy


## 은신처(hiding_spot.gd)가 숨길 때, 플레이어가 E로 나올 때 호출된다.
func set_hiding(value: bool) -> void:
	if is_hiding == value:
		return

	is_hiding = value
	velocity = Vector2.ZERO
	body.visible = not is_hiding
	player_light.energy = HIDDEN_LIGHT_ENERGY if is_hiding else _light_energy


func _physics_process(delta: float) -> void:
	if is_hiding:
		# 숨은 자리에 고정. 프롬프트만 갱신해 "나오기" 안내를 유지한다.
		velocity = Vector2.ZERO
		_update_interact_prompt()
		return

	var direction := Input.get_vector("move_left", "move_right", "move_up", "move_down")

	if direction != Vector2.ZERO:
		facing_direction = direction.normalized()
		if not is_zero_approx(direction.x):
			_facing_right = direction.x > 0.0

	_update_sprite(direction != Vector2.ZERO, delta)

	velocity = direction * speed
	move_and_slide()

	interaction_area.position = facing_direction * 22.0
	_update_interact_prompt()


## 대기/달리기 포즈 전환. 사람 그림이라 이동 각도로 회전시키면 안 된다
## (예전 삼각형 도형은 회전으로 방향을 나타냈다).
func _update_sprite(moving: bool, delta: float) -> void:
	body.texture = RUN_TEXTURE if moving else IDLE_TEXTURE
	# 대기 포즈는 정면이라 좌우가 없다 — 달릴 때만 뒤집는다.
	body.flip_h = moving and not _facing_right

	var bob := 0.0
	if moving:
		_bob_time += delta
		if fmod(_bob_time, BOB_INTERVAL * 2.0) < BOB_INTERVAL:
			bob = BOB_HEIGHT
	else:
		_bob_time = 0.0
	body.offset = Vector2(0.0, SPRITE_OFFSET_Y - bob)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("throw_ink"):
		if _throw_ink():
			get_viewport().set_input_as_handled()
		return

	if not event.is_action_pressed("interact"):
		return

	# 숨은 동안 E는 항상 "나오기". 상호작용 영역이 은신처에서 어긋나 있어도
	# 나올 수 있어야 한다(갇힘 방지).
	if is_hiding:
		set_hiding(false)
		Sfx.play(&"hide_out")
		get_viewport().set_input_as_handled()
		return

	var target := _find_interactable()
	if target != null:
		# 입력 소비를 interact()보다 먼저 한다. 현관(exit_door)처럼 상호작용 안에서
		# 씬을 바꾸는 경우 호출 뒤에는 이 노드가 트리에서 빠져 get_viewport()가
		# null이 되고 "Cannot call method 'set_input_as_handled' on a null value"로
		# 죽는다(#159 F5에서 발견).
		get_viewport().set_input_as_handled()
		target.call("interact", self)


## 잉크통을 바라보는 방향으로 던진다(#169). 던졌으면 true.
## 없는데 눌렀을 때 알림을 띄우면 Q를 누를 때마다 하단이 도배되므로 조용히 무시한다.
func _throw_ink() -> bool:
	if is_hiding:
		return false

	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state == null or not game_state.call("has_item", INK_ITEM_ID):
		return false

	game_state.call("remove_item", INK_ITEM_ID)

	var projectile := INK_PROJECTILE.instantiate()
	# 층 씬이 아니라 조립 씬(main)에 붙인다 — 층 씬은 층을 옮길 때 통째로
	# 교체되므로 거기 붙이면 전환 중에 같이 사라진다.
	get_parent().add_child(projectile)
	projectile.call("launch",
		position + facing_direction * INK_SPAWN_OFFSET, facing_direction)

	game_state.call("request_notice", "잉크통을 던졌다.")
	Sfx.play(&"ink_throw")
	return true


func _find_interactable() -> Area2D:
	for area in interaction_area.get_overlapping_areas():
		if area.has_method("interact"):
			return area
	return null


func _update_interact_prompt() -> void:
	if is_hiding:
		interact_prompt.text = "[E] " + HIDDEN_PROMPT
		interact_prompt.visible = true
		return

	var target := _find_interactable()

	if target == null:
		interact_prompt.visible = false
		return

	var action_text := "상호작용"
	var custom_text = target.get("prompt_text")
	if custom_text is String and not custom_text.is_empty():
		action_text = custom_text

	interact_prompt.text = "[E] " + action_text
	interact_prompt.visible = true
