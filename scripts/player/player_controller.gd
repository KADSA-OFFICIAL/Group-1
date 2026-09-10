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
## **위로 걸을 때는 뒷모습, 아래로 걸을 때는 정면 두 장을 번갈아 쓴다**(#519·#551).
## 사용자가 방향마다 걷기 두 포즈를 그려서, 수위처럼(janitor.gd의 ROW_*) 방향에 따라
## 그림이 갈린다. 좌우는 측면 12프레임이다.
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
## 뒷모습 달리기 네 장(#519에서 두 장, #585에서 네 장). **한 장이 반 걸음**이다 —
## 네 장이 두 걸음이라 한 프레임이 `WALK_STEP_PX / 2`만큼 유지되고, 걸음 박자(초당
## 2걸음)는 측면과 같다. 좌우 반전은 하지 않는다(등을 보이는 그림이다).
##
## **3·4번은 1·2번을 좌우로 뒤집어 구운 것이다**(#585). 원본 시트의 뒤 절반이 미러가
## 아니라 복제라, 그대로 두 장만 쓰면 한쪽 다리만 까딱거린다. 뒤집어 만들면 다리
## 교대가 정의상 정확하다. 그림 자체가 뒤집혀 있으므로 여기서 flip_h를 걸면 안 된다.
const BACK_TEXTURES := [
	preload("res://assets/sprites/player_back_1.png"),
	preload("res://assets/sprites/player_back_2.png"),
	preload("res://assets/sprites/player_back_3.png"),
	preload("res://assets/sprites/player_back_4.png"),
]
## 정면 달리기 네 장(#551에서 두 장, #585에서 네 장). 뒷모습과 완전히 같은 규약이다
## — 한 장이 반 걸음이고, 3·4번이 1·2번의 좌우 반전이라 여기서 flip_h를 걸지 않는다.
## 대기 포즈(`IDLE_TEXTURE`)도 정면이지만 그쪽은 두 발을 모으고 서 있어 걷는 것으로
## 보이지 않는다 — 아래로 걸을 때 그것을 쓰면 미끄러져 내려가는 것처럼 보인다.
const FRONT_TEXTURES := [
	preload("res://assets/sprites/player_front_1.png"),
	preload("res://assets/sprites/player_front_2.png"),
	preload("res://assets/sprites/player_front_3.png"),
	preload("res://assets/sprites/player_front_4.png"),
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
## 옆모습 사이클에서 **몇 장 걸러 쓸지**(#555). 1이면 열두 장 전부다.
##
## `WALK_STEP_PX`를 또 올려서 대응하지 않은 이유: 그 상수는 **좌우와 상하가 함께
## 쓴다.** 좌우는 12장이 두 걸음(한 장 = WALK_STRIDE 26.7px)이고 위아래는 두 장이
## 두 걸음(한 장 = WALK_STEP_PX 160px)이라, 걸음 박자는 2.0/초로 같은데 **이미지
## 전환은 좌우가 12장/초, 위아래가 2장/초로 6배 차이**다. 좌우로 걸을 때만 어색하다는
## 보고(#387·#519에 이어 세 번째)의 원인이 그 격차다. `WALK_STEP_PX`를 올리면
## 격차는 그대로인 채 위아래가 함께 느려져 두 장짜리 그림이 눈에 띄게 끊긴다.
##
## 2면 여섯 장(1·3·5·7·9·11번)만 화면에 나와 **초당 6장**이 되고, 한 바퀴는 여전히
## 320px이라 **걸음 박자 2.0/초는 그대로**다. 열두 장이 전부 이어지는 손그림이라
## 한 장 건너뛴 것도 그대로 이어진다. 되돌리려면 1로 두면 된다.
const SIDE_FRAME_STEP := 2

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

## ── 고정 시간 간격 보간(#597) ──────────────────────────────────
## 60Hz를 넘는 모니터에서 **이설만** 두두둑 떨리던 원인은 표본 시점이 둘로
## 갈려 있던 것이다. 몸은 `_physics_process`(60Hz)에서 한 tick에 5.33px씩
## 계단처럼 나아가는데, 카메라는 `position_smoothing_enabled`이고
## `process_callback`이 기본값(idle)이라 **그린 프레임마다** 매끈하게 따라간다.
## 화면에 보이는 이설의 자리는 `몸(계단) - 카메라(직선)`이라 톱니가 되고,
## 배경은 정적이라 카메라와 정확히 같이 움직여 매끈하므로 **인물만** 떨린다.
## 그 톱니가 잔상처럼 겹쳐 보이는 것이다. 모사 실측(화면 좌표, zoom 1.25 x
## 창 배율 1.6): 60Hz 0.01px / 144Hz **9.48px** / 165Hz 9.45px / 240Hz 7.88px.
## 60Hz에서 멀쩡했던 것은 tick과 프레임이 1:1이라 두 표본이 같은 시점이어서다.
##
## 그래서 **그림만** 직전 tick과 이번 tick 사이를
## `Engine.get_physics_interpolation_fraction()`으로 보간한다. 몸·충돌·상호작용
## 존·수위 판정은 그대로 60Hz다 — 판정을 건드리지 않는다. 대가는 그림이 최대
## 한 tick(16.7ms) 뒤에 오는 것으로, 고정 시간 간격 보간의 표준적인 맞바꿈이다.
##
## **엔진 전역 보간(`physics/common/physics_interpolation`)을 켜지 않는다.**
## 이 프로젝트는 시각 노드를 `Visuals` CanvasLayer로 떼어 `_process`에서 손으로
## 위치를 맞추는 구조(#250)라, 전역 보간은 `_process`에서 변형을 쓰는 노드와
## 싸운다. 필요한 노드만 손으로 보간한다.
##
## 한 tick에 갈 수 있는 거리를 넘으면 **보간하지 않고 붙인다** — 층 전환·체크포인트
## 재시작은 위치를 통째로 옮기므로(`floor_manager`의 `player.position = arrive`)
## 그대로 보간하면 한 프레임 동안 그림이 맵을 가로질러 흐른다. 걸어서는 한 tick에
## 5.33px 이상 갈 수 없으니 64px은 넉넉한 문턱이다.
const INTERP_SNAP_PX := 64.0
var _interp_prev: Vector2 = Vector2.ZERO
var _interp_curr: Vector2 = Vector2.ZERO


func _ready() -> void:
	# 상호작용 표시(#301)가 거리를 재려고 찾는다. 플레이어는 조립 씬(main)
	# 소속이라 층 씬에서 이름으로는 못 찾는다.
	add_to_group("player")
	_light_energy = player_light.energy
	_reset_interpolation()
	visuals.global_position = global_position


## 벽 시각(WallGlow, layer 1)은 layer 0보다 앞에 그려져 z_index로는 뒤집을 수 없다.
## 그래서 시각만 같은 layer 1로 올리고, 여기서 본체 위치를 따라가게 한다.
## follow_viewport CanvasLayer 안이라 global_position이 곧 월드 좌표다
## (벽 페이드 마스크 wall_fade_mask.gd가 쓰는 방식과 같다).
func _process(_delta: float) -> void:
	var at := visual_position()
	visuals.global_position = at
	# 손전등도 같은 시점을 봐야 한다(#597). 몸에 붙여 두면 그림은 매끈한데 빛과
	# 그림자 경계만 60Hz로 떨려서 오히려 눈에 띈다. 충돌·상호작용 존은 몸에 그대로
	# 둔다 — 여기서 옮기는 것은 보이는 것뿐이다.
	player_light.position = at - global_position


## 이번에 그릴 프레임에서 이설이 있어야 할 자리(#597). 직전 tick과 이번 tick 사이를
## 프레임이 놓인 만큼 보간한다. 어둠 마스크(wall_fade_mask.gd)도 이 값을 따라간다 —
## 몸을 따라가면 그림은 매끈한데 시야 원만 떨린다.
func visual_position() -> Vector2:
	# 컷신은 `set_physics_process(false)`로 조작을 끊고 `scripted_step()`이 매 프레임
	# 직접 옮긴다(#594) — 보간할 tick이 없으므로 그대로 베낀다.
	if not is_physics_processing():
		return global_position
	return _interp_prev.lerp(_interp_curr,
		clampf(Engine.get_physics_interpolation_fraction(), 0.0, 1.0))


func _reset_interpolation() -> void:
	_interp_prev = global_position
	_interp_curr = global_position


## 이번 tick이 끝난 자리를 적는다. `_physics_process`의 모든 갈래 끝에서 부른다 —
## 숨은 동안에도 적어야 나올 때 직전 자리에서 흐르지 않는다.
func _record_interpolation() -> void:
	_interp_prev = _interp_curr
	_interp_curr = global_position
	if _interp_prev.distance_squared_to(_interp_curr) > INTERP_SNAP_PX * INTERP_SNAP_PX:
		_interp_prev = _interp_curr


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
		_record_interpolation()
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
	_record_interpolation()


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

	# 위로 걸으면 뒷모습(#519), 아래로 걸으면 정면(#551). 대각선은 세로 성분이 더 큰
	# 쪽만 세로 그림으로 본다 — 정확한 대각선(|x| == |y|)은 측면이다. 두 방향이 같은
	# 계산을 쓰는 이유는 그림 규약이 같아서다(한 장이 한 걸음, 반전 없음).
	if absf(facing_direction.y) > absf(facing_direction.x):
		var pair: Array = BACK_TEXTURES if facing_direction.y < 0.0 else FRONT_TEXTURES
		# 한 바퀴(두 걸음)가 측면과 같은 2 x WALK_STEP_PX가 되도록 나눈다 — 장수가
		# 둘에서 넷으로 늘어도(#585) 걸음 박자는 그대로다.
		var step := int(_walk_distance / (2.0 * WALK_STEP_PX / pair.size())) % pair.size()
		body.texture = pair[step]
		body.flip_h = false
		return

	# **한 장 걸러 쓴다**(#555). 열두 장을 전부 쓰면 이미지가 초당 12장 바뀌는데
	# 위아래는 초당 2장이라, 걸음 박자가 2.0으로 같은데도 좌우만 화면이 6배 바쁘다.
	# 표본을 성기게 뜨는 것이지 사이클을 줄이는 것이 아니다 — 한 바퀴는 여전히
	# 12 x WALK_STRIDE = 320px 이고 걸음 박자도 그대로다.
	var slot := int(_walk_distance / (WALK_STRIDE * float(SIDE_FRAME_STEP)))
	var frame := (slot * SIDE_FRAME_STEP) % WALK_TEXTURES.size()
	body.texture = WALK_TEXTURES[frame]
	body.flip_h = not _facing_right


## ── 연출용 이동(#594) ────────────────────────────────────────────
## 컷신은 조작을 끊으려고 `set_physics_process(false)`를 거는데, 걷기 프레임을
## 정하는 `_update_sprite()`가 **그 안에서만** 불린다 — 그래서 컷신이
## `global_position`을 직접 옮기면 이설이 대기 포즈로 미끄러졌다(창문 하강 #468).
##
## 컷신이 매 프레임 `scripted_step()`을 부르면 그 자리에서 프레임이 넘어간다.
## 애니메이션 거리를 **인자로 받는 이유**는 연출 구간이 짧기 때문이다 — 창틀까지는
## 한 걸음(`WALK_STEP_PX` 160px)도 안 되므로 실제 이동 거리로 굴리면 그림이 한 장도
## 안 바뀐다. 부르는 쪽이 `speed * delta`를 넘겨 평소 걸음 박자로 굴린다.


## 조작을 끊고 연출용 이동에 들어간다. 머리 위 프롬프트도 감춘다 — 물리 처리가
## 꺼지면 마지막 상태로 붙박여서 컷신 내내 `[E] …`가 떠 있었다.
func begin_scripted_motion() -> void:
	velocity = Vector2.ZERO
	set_physics_process(false)
	set_process_unhandled_input(false)
	interact_prompt.visible = false


## 연출이 이설을 `to`로 옮기고 걷기 그림을 `anim_px`만큼 굴린다.
## `facing`이 0이면 직전 방향을 유지한다(제자리에서 몸이 돌지 않게).
func scripted_step(to: Vector2, facing: Vector2, anim_px: float) -> void:
	if facing != Vector2.ZERO:
		facing_direction = facing.normalized()
		if not is_zero_approx(facing.x):
			_facing_right = facing.x > 0.0
	global_position = to
	visuals.global_position = to
	# 연출이 프레임마다 옮기므로 보간 자리도 같이 당긴다 — 안 그러면 조작이
	# 돌아오는 순간 직전 tick 자리가 컷신 시작 지점이라 그림이 되돌아갔다 온다.
	_reset_interpolation()
	_update_sprite(anim_px > 0.0, anim_px)


## 대기 포즈로 되돌리고 조작을 돌려준다.
func end_scripted_motion() -> void:
	_update_sprite(false, 0.0)
	set_physics_process(true)
	set_process_unhandled_input(true)


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
