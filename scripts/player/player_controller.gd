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
## 60x72 스프라이트(중앙 정렬)의 발끝을 충돌 캡슐 바닥(y=13)에 맞추는 오프셋.
## 캔버스 높이를 바꾸면 (발끝 y 14) - (높이/2)로 다시 계산할 것.
const SPRITE_OFFSET_Y := -22.0
## 달리기 포즈가 한 장뿐이라 1px 위아래로 흔들어 걸음을 만든다.
const BOB_INTERVAL := 0.14
const BOB_HEIGHT := 1.0

## 잉크통 던지기(#169). 손에서 조금 앞에 놓고 던져야 벽에 붙어 있을 때
## 자기 발밑에서 터지지 않는다.
const INK_ITEM_ID := "ink_can"
const INK_PROJECTILE := preload("res://scenes/items/ink_projectile.tscn")
const INK_SPAWN_OFFSET := 24.0

## 시각 노드는 벽 위에 그려야 해서(#250) layer 1 CanvasLayer(Visuals) 안에 있고,
## 위치는 _process에서 본체에 맞춘다. 충돌·조명·카메라는 layer 0에 그대로 둔다 —
## 손전등이 바닥·집기를 비추려면 같은 캔버스에 있어야 한다.
@onready var visuals: Node2D = $Visuals/Anchor
@onready var body: Sprite2D = $Visuals/Anchor/Body
@onready var interaction_area: Area2D = $InteractionArea
@onready var interact_prompt: Label = $Visuals/Anchor/InteractPrompt
@onready var player_light: PointLight2D = $PlayerLight

## `interact_priority`가 없는 상호작용의 기본값(#301).
const DEFAULT_INTERACT_PRIORITY := 5

var facing_direction: Vector2 = Vector2.DOWN
var is_hiding: bool = false
var _light_energy: float = 1.0
## 위아래로만 움직일 땐 직전 좌우를 유지한다(스프라이트가 제자리에서 뒤집히지 않게).
var _facing_right: bool = true
var _bob_time: float = 0.0


func _ready() -> void:
	# 상호작용 표시(#301)가 거리를 재려고 찾는다. 플레이어는 조립 씬(main)
	# 소속이라 층 씬에서 이름으로는 못 찾는다.
	add_to_group("player")
	_light_energy = player_light.energy
	visuals.global_position = global_position


## 벽 시각(WallGlow, layer 1)은 layer 0보다 앞에 그려져 z_index로는 뒤집을 수 없다.
## 그래서 시각만 같은 layer 1로 올리고, 여기서 본체 위치를 따라가게 한다.
## follow_viewport CanvasLayer 안이라 global_position이 곧 월드 좌표다
## (벽 페이드 마스크 wall_fade_mask.gd가 쓰는 방식과 같다).
func _process(_delta: float) -> void:
	visuals.global_position = global_position


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


## 겹친 상호작용 중 하나를 고른다 — **우선순위가 먼저, 같으면 가까운 쪽**(#301).
##
## 예전에는 겹친 것 중 첫 번째를 돌려줬는데, 그 순서가 노드 선언 순이라
## 사실상 임의였다. 조사 대상을 늘리면 잡동사니가 단서를 가로챈다 — #274에서
## 창가 조사를 방마다 하나로 제한한 것도 같은 이유였다.
func _find_interactable() -> Area2D:
	var best: Area2D = null
	var best_prio := -1
	var best_dist := INF
	for area in interaction_area.get_overlapping_areas():
		if not area.has_method("interact"):
			continue
		var prio := DEFAULT_INTERACT_PRIORITY
		var value = area.get("interact_priority")
		if value is int:
			prio = value
		var dist := global_position.distance_squared_to(area.global_position)
		if prio > best_prio or (prio == best_prio and dist < best_dist):
			best = area
			best_prio = prio
			best_dist = dist
	return best


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
