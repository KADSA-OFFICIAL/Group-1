extends CharacterBody2D

@export var speed: float = 320.0

## 은신(#6): 숨은 동안 이동이 잠기고 수위아저씨가 발각하지 않는다.
## 빛을 완전히 끄면 수위가 지나가는지 볼 수 없어 나올 시점을 판단할 근거가
## 사라진다. 발각 판정은 빛과 무관하므로 끄지 않고 어둡게만 낮춘다.
const HIDDEN_LIGHT_ENERGY := 0.5
const HIDDEN_PROMPT := "나오기"

## 스프라이트(#210): 서 있을 땐 정면 대기 포즈, 움직이면 걷기 사이클.
## 걷기 그림은 열두 장 모두 오른쪽을 보고 있어 왼쪽으로 갈 때만 뒤집는다.
## tools/gen_player_sprites.py가 원본 아트에서 만든다.
##
## **위로 걸을 때는 뒷모습 두 장을 번갈아 쓴다**(#519). 사용자가 뒷모습 걷기 두 포즈를
## 그려서, 수위처럼(janitor.gd의 ROW_*) 방향에 따라 그림이 갈린다. **아래로 걸을 때는
## 아직 측면 그림이다** — 정면 걷기 원본이 없다.
const IDLE_TEXTURE := preload("res://assets/sprites/player_idle.png")
## 걷기 **12프레임**(#384). 사용자가 걷기 사이클 전체(두 걸음, 2행×6열 시트)를
## 직접 그렸다 — 프레임마다 다른 실제 포즈이므로 수위(#375)처럼 반복되는 "기본
## 프레임"을 끼우는 인덱스 표가 필요 없다. `player_walk_1 → 2 → … → 12 → (루프) 1`을
## 그대로 순서대로 돈다. 1~6이 한 걸음, 7~12가 반대쪽 다리의 같은 걸음이다(발끝이
## 캔버스 바닥에서 거의 안 움직이는 접지 프레임의 오프셋이 1번과 7번에서 정확히
## 같다 — 대칭 확인됨).
##
## #365→#368→#372→#375→#378→#381까지는 프레임이 3~4장뿐이라 어떤 조합도 매끄럽게
## 안 읽혔다. 코드 합성(#372·#375)도 세 번 다 "다리 윤곽이 거칠다"로 끝났다 — 프레임
## 수 자체가 부족했던 것이지 포즈 선택의 문제가 아니었다.
const WALK_TEXTURES := [
	preload("res://assets/sprites/player_walk_1.png"),
	preload("res://assets/sprites/player_walk_2.png"),
	preload("res://assets/sprites/player_walk_3.png"),
	preload("res://assets/sprites/player_walk_4.png"),
	preload("res://assets/sprites/player_walk_5.png"),
	preload("res://assets/sprites/player_walk_6.png"),
	preload("res://assets/sprites/player_walk_7.png"),
	preload("res://assets/sprites/player_walk_8.png"),
	preload("res://assets/sprites/player_walk_9.png"),
	preload("res://assets/sprites/player_walk_10.png"),
	preload("res://assets/sprites/player_walk_11.png"),
	preload("res://assets/sprites/player_walk_12.png"),
]
## 뒷모습 걷기 두 장(#519). **한 장이 한 걸음**이다 — 측면은 6프레임이 한 걸음이지만
## 이쪽은 두 장이 두 걸음이라, 한 프레임이 `WALK_STEP_PX`만큼 유지된다. 그래서 걸음
## 박자(초당 2걸음)가 측면과 같다. 좌우 반전은 하지 않는다(등을 보이는 그림이다).
const BACK_TEXTURES := [
	preload("res://assets/sprites/player_back_1.png"),
	preload("res://assets/sprites/player_back_2.png"),
]
const SPRITE_OFFSET_Y := -24.0
## 한 걸음(6프레임)의 물리적 거리 — 정확히는 "12프레임 걷기 사이클이 화면에서
## 얼마나 자주 넘어가는가"를 정하는 다이얼이다.
##
## #375(4프레임, 2프레임/걸음)에서는 이 값이 수위와 같은 52(인물 키의 0.72배)여야
## 했다 — 프레임이 3~4장뿐이라 한 프레임이 표시되는 거리가 너무 길면(다리가 닿을 수
## 없는 거리를 나아가면) 발이 화면에 미끄러지는 게 눈에 띄었다. #384로 12장(실제
## 손그림, 6프레임/걸음)으로 늘리면서 그 52를 그대로 물려받았더니 **같은 이동
## 거리에 이미지가 3배 더 자주 바뀌어** 화면이 바빠 보였다(#387).
##
## 이제는 그 "다리 길이만큼만 나아가야 한다"는 제약이 약하다 — 프레임 밀도(px당
## 프레임 수)가 12/104 ≈ 0.115로 #375의 사고 사례(4/136 ≈ 0.029)보다 4배 촘촘하고,
## 열두 장 전부 실제로 이어지는 손그림이라 프레임 사이 포즈가 항상 매끄럽게
## 연결된다 — 그래서 104(#375 기준의 2배, 전환 빈도는 절반)로 올려도 미끄러지는
## 느낌 없이 그냥 차분해진다. 이동 속도(`speed`)는 그대로다 — 이 상수는 순수하게
## "다리 애니메이션이 얼마나 자주 넘어가는가"만 조절한다.
## **104에서 다시 올렸다**(#519). 104면 초당 프레임이 320 ÷ (104/6) = 18.5장이고
## 초당 걸음이 3.1인데, 도트 걷기 사이클은 8~12장/초가 보통이고 3.1걸음/초는 걷기가
## 아니라 종종걸음이다(사용자 보고: "너무 빨리 전환된다"). 160이면 **12.0장/초,
## 2.0걸음/초** — 사람이 걷는 박자다. 이 상수는 이동 속도(`speed` 320)와 무관하게
## "애니메이션이 얼마나 자주 넘어가는가"만 정한다.
const WALK_STEP_PX := 160.0
## 한 프레임이 유지되는 이동 거리. 시간이 아니라 거리로 재야 벽에 스쳐 느려질 때
## 발이 미끄러지지 않는다(수위 #310과 같은 규약). 12프레임이 두 걸음이므로 한 걸음은
## 6프레임 — WALK_STEP_PX를 6으로 나눈다.
const WALK_STRIDE := WALK_STEP_PX / 6.0

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
## 이번 판에서 걸은 거리. WALK_STRIDE로 나눈 몫을 WALK_TEXTURES.size()로 나눈
## 나머지가 걷기 프레임 번호다.
var _walk_distance: float = 0.0


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


func _physics_process(_delta: float) -> void:
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

	velocity = direction * speed
	var before := global_position
	move_and_slide()
	# 프레임을 넘길 거리는 입력이 아니라 **실제로 나아간 거리**로 센다 — 벽에
	# 붙어 밀고 있을 때 제자리에서 발만 젓지 않게.
	_update_sprite(direction != Vector2.ZERO, global_position.distance_to(before))

	interaction_area.position = facing_direction * 22.0
	_update_interact_prompt()


## 대기/걷기 포즈 전환. 사람 그림이라 이동 각도로 회전시키면 안 된다
## (예전 삼각형 도형은 회전으로 방향을 나타냈다).
func _update_sprite(moving: bool, moved: float) -> void:
	body.offset = Vector2(0.0, SPRITE_OFFSET_Y)

	if not moving:
		# 멈추면 정면 대기 포즈. 걸음을 처음으로 되돌려야 다시 걸을 때 늘 같은
		# 발부터 나간다(수위 _advance_sprite와 같은 이유).
		_walk_distance = 0.0
		body.texture = IDLE_TEXTURE
		# 대기 포즈는 정면이라 좌우가 없다.
		body.flip_h = false
		return

	# 벽을 밀고 있으면 moved가 0이라 프레임이 그 자리에 멈춘다 — 대기 포즈로
	# 돌아가면 방향키를 누른 채 정면을 보는 것처럼 보인다.
	_walk_distance += moved

	# 위로 걸으면 뒷모습(#519). 대각선은 세로 성분이 더 큰 쪽만 뒷모습으로 본다 —
	# 정확한 대각선(|x| == |y|)은 측면이다. 아래로 걸을 때는 정면 걷기 원본이
	# 없어 지금처럼 측면을 쓴다.
	if facing_direction.y < 0.0 and absf(facing_direction.y) > absf(facing_direction.x):
		var back := int(_walk_distance / WALK_STEP_PX) % BACK_TEXTURES.size()
		body.texture = BACK_TEXTURES[back]
		body.flip_h = false
		return

	var frame := int(_walk_distance / WALK_STRIDE) % WALK_TEXTURES.size()
	body.texture = WALK_TEXTURES[frame]
	body.flip_h = not _facing_right


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
