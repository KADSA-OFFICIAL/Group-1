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
	# 0은 층이 아니라 **탈출 뒤 걸어 나가는 바깥 구간**이다(#356). 계단이 없고,
	# 현관에서 한 방향으로만 들어온다.
	0: "res://scenes/background/school_yard.tscn",
	1: "res://scenes/background/school_floor_1.tscn",
	2: "res://scenes/background/school_floor_2.tscn",
	3: "res://scenes/background/school_floor_3.tscn",
	4: "res://scenes/background/school_floor_4.tscn",
}
const MIN_FLOOR := 1
## 계단으로 오갈 수 있는 위 경계. **4층이 아니라 3층이다**(#406) — 4층은
## 도입부 전용이라 계단이 없고, 창문으로 내려가면 다시 올라올 수 없다.
## 4로 두면 3층 계단에서 위로 올라갈 때 빈 `STAIRS[4]`를 인덱싱해 죽는다.
const MAX_FLOOR := 3
const START_FLOOR := 4
## 수위가 순찰하지 않는 층. 4층에서는 순찰 대신 **스크립트로 등장**한다(#404).
const JANITOR_FREE_FLOOR := 4
## 도입부에서 조작이 시작되는 자리 — 미술실 문 안쪽.
## `gen_floors.py`의 `INTRO_ARRIVE`와 같아야 한다.
const INTRO_ARRIVE := Vector2(300, 700)
## 운동장(#356). 계단 대신 현관 문이 데려오고, 정문이 엔딩으로 보낸다.
const YARD_FLOOR := 0
const YARD_LABEL := "운동장"
## 운동장 등장 지점 — 현관 바로 앞. `gen_floors.py`의 `YARD_ARRIVE`와 같아야 한다.
const YARD_ARRIVE := Vector2(1700, 380)

## 층별 카메라 한계. 운동장은 3400x1500이라 층(3400x2500)과 다르다 —
## `player.tscn`에 박아 두면 운동장에서 빈 아래쪽이 보인다.
const FLOOR_BOUNDS := {
	0: Rect2(0, 0, 3400, 1700),
	1: Rect2(0, 0, 3400, 1500),   # 현관 로비 층(#498) — 북쪽 봉인 공백을 없앴다
	4: Rect2(0, 0, 1800, 1000),   # 도입부(#405) — 두 방뿐이라 훨씬 작다
}
const DEFAULT_BOUNDS := Rect2(0, 0, 3400, 2500)

## 밖은 안보다 밝다. "손전등만이 광원"(#74)은 **실내** 규칙이다 — 네 개 층을
## 기어 내려온 끝에 시야가 트이는 것이 이 구간의 연출이다.
const INDOOR_DARKNESS := Color(0, 0, 0, 1)
const YARD_DARKNESS := Color(0.30, 0.31, 0.36, 1)
## 시야 마스크 배율. 2 = 반경 1024px(389px에서 완전히 검다).
const INDOOR_FADE_SCALE := 2.0
const YARD_FADE_SCALE := 5.0

## **층마다 다르게 두는 예외**(#498). 1층은 현관 로비 층이라 다른 층보다 밝다 —
## 네 층을 기어 내려온 끝이라는 감각이 0층(운동장)에만 있었고, 그 사이에
## "밖에 가까워진다"는 단계가 없었다. 값은 완전 검정(다른 층)과 운동장(0.30)
## 사이다. 밝음의 **출처**는 현관 빛(`gen_floors`의 `EntranceLight`)이고
## 이 표는 그 빛이 닿지 않는 데까지 층 전체를 조금 들어 올린다.
const FLOOR_DARKNESS := {
	1: Color(0.16, 0.16, 0.20, 1),
}
## 시야 마스크도 같이 넓힌다 — 2.6이면 완전 암전이 389 → 506px이다.
## 손전등 반경(333px)보다 여전히 넓어서 "손전등으로 길을 찾는다"는 규칙(#74)은
## 그대로다. 로비가 넓어(970x680) 2.0이면 방 안에서도 반대쪽 벽이 안 보였다.
const FLOOR_FADE_SCALE := {
	1: 2.6,
}

# 층별 계단실 사각형. 인덱스 0 = 위쪽(좌측) 계단, 1 = 하단 중앙 계단.
# 1층은 도면상 계단이 한 곳뿐이라 목록 길이가 1이다.
const STAIR_A := Rect2(300, 720, 440, 280)
const STAIR_B := Rect2(1450, 2120, 440, 320)
## 계단실이 **아예 없는** 자리(#398). `STAIRS`의 사각형은 남긴다 — 위층에서
## 내려올 때 `_arrive_on`이 쓰는 도착 지점의 기준이라, 빼면 인덱스가 밀려
## 엉뚱한 계단 앞으로 순간이동한다. 층 전환 판정에서만 건너뛴다.
const NO_STAIRWELL := {2: [1]}

const STAIRS := {
	0: [],   # 운동장 — 계단 없음(#356)
	# 현관 로비 층(#498) — 하단 방 띠(800~1480) 왼쪽. `gen_floors.FLOOR1["stair"]`와
	# 같은 자리여야 한다(`verify_stairs`가 대조). **위가 복도여야 한다** —
	# `_arrive_on`이 사각형 위쪽에서 도착 지점을 잡는다.
	1: [Rect2(220, 800, 440, 320)],
	2: [STAIR_A, STAIR_B],
	3: [STAIR_A, STAIR_B],
	4: [],   # 도입부 — 계단 없음. 창문으로 3층에 내려간다(#405)
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
@onready var hud: CanvasLayer = $HUD
@onready var darkness: CanvasModulate = $Darkness
@onready var fade_mask: Sprite2D = $WallFade/Mask

const FADE_IN_SECONDS := 1.5
const FLOOR_FADE_OUT_SECONDS := 0.25
const FLOOR_FADE_IN_SECONDS := 0.35
const START_HINT := "4층 미술실. 국어책만 챙겨서 나가면 된다."

# 붙잡힌 순간을 잠깐 보여준 뒤 실패 화면으로 넘어간다(수위가 마주보는 연출).
const GAME_OVER_SCENE := "res://scenes/ui/game_over.tscn"
const GAME_OVER_FADE_SECONDS := 1.2
## 붙잡힘 대사가 다 찍힌 뒤 페이드를 시작하기까지 두는 시간(#199).
const GAME_OVER_LINE_HOLD := 0.5

var game_over_active: bool = false


## 현관 문(#356)이 층 전환을 부르려면 이름이 아니라 그룹으로 찾아야 한다 —
## 상호작용 노드는 층 씬 안에 있어서 조립 씬 루트까지의 경로를 알 수 없다.
func _enter_tree() -> void:
	add_to_group("floor_manager")


func _ready() -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null:
		game_state.connect("game_over", _on_game_over)

	_update_floor_label()
	_apply_environment(current_floor)
	Sfx.start_music()
	janitor.sync_floor(_janitor_active(current_floor), current_floor, player, $Background)
	fade_rect.color.a = 1.0
	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 0.0, FADE_IN_SECONDS)
	tween.tween_callback(_show_start_hint)


func _show_start_hint() -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null:
		game_state.call("request_notice", START_HINT)


## 붙잡힘 → 조작 정지 → 마지막 대사를 다 보여준 뒤 실패 화면.
## game_state가 중복 발동을 막지만, 층 전환 페이드와 겹치면 트윈이 서로 알파를
## 다투므로 여기서도 가드한다.
func _on_game_over(reason: String) -> void:
	if game_over_active:
		return
	game_over_active = true
	changing_floor = true   # 계단 트리거 검사 정지
	Sfx.stop_music()

	# 플레이어는 이동(_physics_process)과 E 상호작용(_unhandled_input)을 모두 끊고,
	# 수위는 붙잡은 자리에 그대로 세워 둔다.
	player.velocity = Vector2.ZERO
	player.set_physics_process(false)
	player.set_process_unhandled_input(false)
	janitor.set_physics_process(false)

	GameOverScreen.pending_reason = reason

	# 수위의 마지막 대사가 자막에 다 찍힐 때까지 기다린다 — 페이드를 바로 걸면
	# 문장이 절반쯤 나온 채로 화면이 어두워진다(#199). 이미 다 찍혔으면
	# await_subtitle()이 곧바로 돌아오고 아래 유예만 적용된다.
	if hud.has_method("await_subtitle"):
		await hud.await_subtitle()
	await get_tree().create_timer(GAME_OVER_LINE_HOLD).timeout

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, GAME_OVER_FADE_SECONDS)
	tween.tween_callback(func() -> void:
		get_tree().change_scene_to_file(GAME_OVER_SCENE))


func _physics_process(_delta: float) -> void:
	if changing_floor:
		return

	var pos := player.position
	var stairs: Array = STAIRS.get(current_floor, [])
	if stairs.is_empty():
		return   # 운동장(#356) — 계단이 없다
	var walled: Array = NO_STAIRWELL.get(current_floor, [])

	for i in stairs.size():
		if i in walled:
			continue   # 계단실이 없는 자리(#398) — 실체로 메워져 닿을 수도 없다
		var r: Rect2 = stairs[i]
		if current_floor < MAX_FLOOR and _stair_zone(r, true).has_point(pos):
			_change_floor(current_floor + 1, _arrive_on(current_floor + 1, i, true))
			return
		if current_floor > MIN_FLOOR and _stair_zone(r, false).has_point(pos):
			_change_floor(current_floor - 1, _arrive_on(current_floor - 1, i, false))
			return


## 층별 기본 등장 지점. `travel_to()`가 등장 지점 없이 불렸을 때 쓴다.
const DEFAULT_ARRIVES := {
	0: YARD_ARRIVE,
	1: Vector2(381, 772),
	2: Vector2(579, 692),
	3: Vector2(579, 692),
	4: INTRO_ARRIVE,
}


## 디버그용 층 이동 단축키(#507) — 릴리스 빌드에서는 동작하지 않는다.
## 숫자키 0~4로 해당 층의 기본 등장 지점으로 즉시 이동한다.
func _input(event: InputEvent) -> void:
	if not OS.is_debug_build() or changing_floor or game_over_active:
		return
	if not (event is InputEventKey and event.pressed and not event.echo):
		return

	match event.keycode:
		KEY_0, KEY_KP_0:
			travel_to(0)
		KEY_1, KEY_KP_1:
			travel_to(1)
		KEY_2, KEY_KP_2:
			travel_to(2)
		KEY_3, KEY_KP_3:
			travel_to(3)
		KEY_4, KEY_KP_4:
			travel_to(4)


## 계단이 아닌 곳에서 층을 바꾼다(#356) — 현관 문이 운동장으로 데려올 때 쓴다.
## `arrive`를 비워 두면 그 층의 기본 등장 지점으로 간다.
func travel_to(target: int, arrive: Vector2 = Vector2.INF) -> void:
	if changing_floor or not FLOOR_SCENES.has(target):
		return
	if arrive == Vector2.INF:
		arrive = DEFAULT_ARRIVES.get(target, Vector2.ZERO)
	_change_floor(target, arrive)


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
	janitor.sync_floor(_janitor_active(current_floor), current_floor, player,
		next_background)

	_apply_environment(target)

	var camera: Camera2D = player.get_node_or_null("Camera2D")
	if camera != null:
		camera.reset_smoothing()


func _update_floor_label() -> void:
	floor_label.text = YARD_LABEL if current_floor == YARD_FLOOR \
			else "%d층" % current_floor


## 수위가 이 층에서 활동하는가. 4층은 안전 구간이고, 운동장(#356)에는 아예 없다
## — 밖에서 붙잡히면 탈출이 무효가 되는데 그 자리는 이미 엔딩 판정이 끝난 뒤다.
func _janitor_active(target: int) -> bool:
	return target != JANITOR_FREE_FLOOR and target != YARD_FLOOR


## 어둠·시야·카메라 한계를 층에 맞춘다(#356).
##
## 운동장은 크기부터 다르다(3400x1500). 카메라 한계를 `player.tscn`에 박아 두면
## 씬 아래쪽 빈 공간이 보인다.
func _apply_environment(target: int) -> void:
	var outside := target == YARD_FLOOR
	if darkness != null:
		var base_dark: Color = YARD_DARKNESS if outside else INDOOR_DARKNESS
		darkness.color = FLOOR_DARKNESS.get(target, base_dark)
	if fade_mask != null:
		var base_k: float = YARD_FADE_SCALE if outside else INDOOR_FADE_SCALE
		var k: float = FLOOR_FADE_SCALE.get(target, base_k)
		fade_mask.scale = Vector2(k, k)
	var camera: Camera2D = player.get_node_or_null("Camera2D")
	if camera != null:
		var b: Rect2 = FLOOR_BOUNDS.get(target, DEFAULT_BOUNDS)
		camera.limit_left = int(b.position.x)
		camera.limit_top = int(b.position.y)
		camera.limit_right = int(b.position.x + b.size.x)
		camera.limit_bottom = int(b.position.y + b.size.y)
