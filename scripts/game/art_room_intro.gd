extends Node

## 미술실 도입부 장면(#409, #465에서 3막으로 재작성).
##
## **타이머로 부르지 않는다.** `docs/story.md`가 "많이 알수록 위험하고, 많이
## 알수록 엔딩이 달라진다"고 적어 둔 규칙을 도입부에서 몸으로 가르치는 자리다 —
## 시간이 흘러서 오면 플레이어의 행동과 무관하지만, **조사가 부르면** 자기 손으로
## 위험을 불러온 것이 된다.
##
## 다만 아무것도 안 뒤지고 나가려는 플레이어도 이 장면을 봐야 한다 — 준비실의
## 소지품 봉투와 날짜 벽이 이야기의 훅이다(#407에서 송하람 학생증을 걷어낸 뒤로는
## 그 둘이 유일한 훅이다). 그래서 **국어책을 집는 것**도 방아쇠다.
##
## ## 3막 (#465)
##
##   1. **숨어라** — 문 밖 발소리, 문 클로즈업, 수위 한마디. 조작이 풀리고
##      시스템이 캐비넷을 가리킨다. `HIDE_SECONDS` 안에 못 숨으면 죽는다.
##   2. **자백** — 수위가 **실제로 들어와** 캐비넷 앞까지 오고, 딸 이야기에서
##      자기가 한 일로 넘어간다. 이 동안에는 캐비넷에서 못 나온다.
##   3. **지금밖에 없어** — 수위가 열쇠를 가지러 내려가고 `GRACE_SECONDS`가 돈다.
##
## 예전에는 **수위가 방에 들어오지 않았다.** 그런데 대사가 "시우 그림은 그대로고"라
## 문 밖에서 방 안을 아는 셈이었고, 무엇보다 도입부가 숨기를 가르치지 않았다 —
## 이 게임의 두 축(숨기·도망) 중 하나를 3층 추격전에서야 처음 쓰게 됐다.

## 몇 개를 조사하면 오는가.
const CLUES_TO_TRIGGER := 2
## 조사하면 수위를 부르는 단서. 국어책은 따로 센다(백스톱).
## #407에서 송하람 학생증(`HaramCard`)이 빠져 **셋 중 둘**이 됐다.
const CLUE_NODES := ["SiwooPainting", "Belongings", "DateWall"]
const BACKSTOP_NODE := "KoreanBook"

## 1막 — 숨을 시간. 시작 지점(300,700)에서 캐비넷(76,450)까지 전속력 1.5초 거리라
## 넉넉하다. 짧게 주면 "어디 숨지?"를 읽는 사이에 죽는다.
const HIDE_SECONDS := 14.0
## 이만큼 남았을 때 한 번 더 민다.
const HIDE_WARN_AT := 6.0

## 3막 — 수위가 돌아오기까지. 미술실 시작 지점에서 준비실 창문까지 **격자 거리
## 1780px, 전속력 5.6초**로 실측했다(#409). 3배 남짓 두어 길을 헤매도 닿게 한다 —
## 되돌릴 수 없는 실패라 인색하면 억울해진다.
const GRACE_SECONDS := 20.0
const WARN_AT := 8.0

## 클로즈업 카메라. 문을 화면에 담되 조금 위를 본다 — 문에 정확히 맞추면
## 카메라 한계(y 1000)에 잘려 문이 화면 맨 아래에 붙는다.
const LOOK_ABOVE := 70.0
const CLOSEUP_ZOOM := 2.0
const CAM_IN_SECONDS := 0.7
const CAM_HOLD_SECONDS := 0.35
const CAM_OUT_SECONDS := 0.6

## 수위가 한 칸 걷는 속도(px/초). 순찰 속도(130)보다 느리다 — 쫓는 것이 아니라
## 둘러보는 걸음이다.
const WALK_SPEED := 78.0
## 걸음마다 발소리를 내는 간격(초).
const STEP_SOUND_EVERY := 0.55
## 캐비넷 표시를 이만큼 키워 눈에 띄게 한다(1막).
const MARK_PULSE_SCALE := 1.9
const MARK_PULSE_TIME := 0.45

## 스프라이트 시트 행 = 바라보는 쪽(janitor_sheet.png, hframes 3 / vframes 4).
const ROW_DOWN := 0
const ROW_LEFT := 1
const ROW_RIGHT := 2
const ROW_UP := 3

## 문 위치(클로즈업이 바라볼 곳)와 문틈 빛. 생성기가 채운다.
@export var door_position: Vector2 = Vector2.ZERO
@export var door_glow_path: NodePath
## 장면이 끝난 뒤 문을 조사하면 나올 말. 그 전에는 "국어책부터 챙기자"다.
@export_multiline var door_after_message: String = ""
@export var door_path: NodePath
## 도입부 연출용 수위(#465) — 순찰체가 아니라 정해진 길을 걷는 그림이다.
@export var janitor_path: NodePath
## 숨을 자리와 그 표시. 1막에서 가리킨다.
@export var cabinet_path: NodePath
@export var cabinet_mark_path: NodePath
## 준비실 창문(`floor_link.gd`). 여기로 내려가기 시작하면 유예를 끊는다(#472).
@export var escape_path: NodePath
## 수위 동선. 첫 점이 출발(문 밖), 마지막 점이 말하는 자리다. 생성기가 채운다.
@export var janitor_walk: PackedVector2Array = PackedVector2Array()

var _seen: Dictionary = {}
var _fired: bool = false
## 1막 유예. 0보다 크면 "숨어야 하는 중"이다.
var _hide_left: float = -1.0
var _hide_warned: bool = false
## 3막 유예.
var _grace: float = -1.0
var _warned: bool = false
## 2막이 도는 중 — 캐비넷에서 못 나온다.
var _scene_locked: bool = false
var _step_clock: float = 0.0


func _ready() -> void:
	set_process(false)
	var root := get_parent()
	for name in CLUE_NODES + [BACKSTOP_NODE]:
		var node: Node = root.get_node_or_null(name)
		if node != null and node.has_signal("interacted"):
			node.interacted.connect(_on_investigated.bind(name))

	var escape: Node = get_node_or_null(escape_path)
	if escape != null and escape.has_signal("travel_started"):
		escape.travel_started.connect(_on_escaped)


## 창문으로 내려가기 시작했다 — 유예를 끊는다.
##
## **씬이 해제되기를 기다리면 안 된다.** #468에서 창문에 컷신이 붙은 뒤로는
## `floor_link.gd`가 `travel_to()` 전에 컷신(약 18초)을 끝까지 기다리고, 그동안
## 4층 씬은 살아 있어 여기 `_process`가 계속 돈다 — 유예(20초)가 컷신 도중에
## 다 돌아 **창문에 제때 닿아도 게임 오버가 났다**(#472).
##
## 1막(숨을 유예)도 함께 끊는다. 숨기 전에 창문으로 나가는 것도 나간 것이다.
func _on_escaped() -> void:
	_hide_left = -1.0
	_grace = -1.0
	set_process(false)


func _on_investigated(_player: Node, name: String) -> void:
	if _fired:
		return
	_seen[name] = true
	if name == BACKSTOP_NODE or _clue_count() >= CLUES_TO_TRIGGER:
		_fired = true
		_act1_warning()


func _clue_count() -> int:
	var n := 0
	for c in CLUE_NODES:
		if _seen.has(c):
			n += 1
	return n


# ── 1막 — 숨어라 ────────────────────────────────────────────────────

func _act1_warning() -> void:
	var gs := get_tree().get_first_node_in_group("game_state")
	var player := get_tree().get_first_node_in_group("player")
	_freeze(player, true)

	Sfx.play(&"janitor_step")
	_say(gs, "", "복도에서 발소리가 들린다. 열쇠 꾸러미가 부딪히는 소리.")
	await _wait(1.1)

	await _camera_to_door(player)
	_glow(1.0, 0.5)
	Sfx.play(&"keys")
	await _wait(0.5)
	_say(gs, "수위", "…이 문 왜 열려 있어.")
	await _wait(2.2)

	await _camera_back(player)
	_freeze(player, false)

	# 문 문구를 바꾼다 — 이제 안 나가는 이유가 "캄캄해서"가 아니다.
	var door: Node = get_node_or_null(door_path)
	if door != null and not door_after_message.is_empty():
		door.set("message", door_after_message)

	_say(gs, "이설", "(들어온다. 지금 나가면 마주쳐.)", "fear")
	await _wait(2.0)
	# **어디에 숨어야 하는지 말해 준다.** 숨기를 처음 쓰는 자리라 아는 척하면 안 된다.
	_say(gs, "", "왼쪽 벽에 캐비넷이 있다. 저기라면 몸이 들어간다. — [E] 숨기")
	_pulse_mark()

	_hide_left = HIDE_SECONDS
	_hide_warned = false
	set_process(true)


## 캐비넷 표시를 한 번 부풀렸다 되돌린다. 문구만으로는 어두운 방에서 못 찾는다.
func _pulse_mark() -> void:
	var mark := get_node_or_null(cabinet_mark_path) as Node2D
	if mark == null:
		return
	var base: Vector2 = mark.scale
	var tween := create_tween().set_loops(3)
	tween.tween_property(mark, "scale", base * MARK_PULSE_SCALE,
		MARK_PULSE_TIME).set_trans(Tween.TRANS_SINE)
	tween.tween_property(mark, "scale", base,
		MARK_PULSE_TIME).set_trans(Tween.TRANS_SINE)


func _process(delta: float) -> void:
	if _hide_left > 0.0:
		_tick_hide(delta)
		return
	if _grace > 0.0:
		_tick_grace(delta)


func _tick_hide(delta: float) -> void:
	var player := get_tree().get_first_node_in_group("player")
	if player != null and player.get("is_hiding") == true:
		_hide_left = -1.0
		set_process(false)
		_act2_confession()
		return

	_hide_left -= delta
	if not _hide_warned and _hide_left <= HIDE_WARN_AT:
		_hide_warned = true
		Sfx.play(&"janitor_step")
		_say(get_tree().get_first_node_in_group("game_state"), "",
			"문고리가 돌아간다.")
	if _hide_left <= 0.0:
		_hide_left = -1.0
		set_process(false)
		_caught("…거기 누구야.")


# ── 2막 — 자백 ──────────────────────────────────────────────────────

## 수위가 실제로 들어와 캐비넷 앞까지 오고, 자기가 한 일을 말한다.
##
## **캐비넷 앞까지 오는 것이 연출이 아니라 제약이다.** `WallFade` 마스크가
## 플레이어에게서 389px 밖을 완전히 검게 칠하므로, 시우 그림 앞(캐비넷에서
## 800px)에 세우면 숨은 이설에게 아무것도 안 보인다.
func _act2_confession() -> void:
	var gs := get_tree().get_first_node_in_group("game_state")
	var player := get_tree().get_first_node_in_group("player")
	_scene_locked = true
	_freeze(player, true)          # 장면 도중 E로 캐비넷에서 튀어나오지 못하게

	var jan := get_node_or_null(janitor_path) as Node2D
	Sfx.play(&"door_open")
	_glow(1.0, 0.3)
	if jan != null and janitor_walk.size() >= 2:
		jan.position = janitor_walk[0]
		jan.visible = true
		for i in range(1, janitor_walk.size()):
			await _walk_to(jan, janitor_walk[i])
	await _wait(0.4)

	_say(gs, "수위", "…또 열어 놨네.")
	await _wait(2.2)
	_face(jan, ROW_LEFT)
	_say(gs, "수위", "시우야. 니 그림은 아직 여기 있다.")
	await _wait(2.6)
	_say(gs, "수위", "아빠가 다 치워 줬어. 니 반 애들.")
	await _wait(2.6)
	_say(gs, "수위", "하나씩. 울면서 빌더라.")
	await _wait(2.6)
	_say(gs, "수위", "니가 빌 때는 아무도 안 들어줬는데 말이야.")
	await _wait(2.8)
	_say(gs, "", "숨소리를 죽인다. 캐비넷 문틈으로 다 들린다.")
	await _wait(2.4)
	_say(gs, "수위", "이건 심판이야. 죄 있는 애들만.")
	await _wait(2.8)

	# 나간다.
	_say(gs, "수위", "…문부터 잠가야겠다. 열쇠 가져와서.")
	await _wait(2.0)
	if jan != null and janitor_walk.size() >= 2:
		for i in range(janitor_walk.size() - 2, -1, -1):
			await _walk_to(jan, janitor_walk[i])
		jan.visible = false
	Sfx.play(&"janitor_step")
	_say(gs, "", "발소리가 멀어진다. 계단 쪽이다.")
	_glow(0.0, 0.8)
	await _wait(1.6)

	_scene_locked = false
	_freeze(player, false)
	_act3_grace(gs)


## 한 지점까지 걸어간다. 속도가 일정해야 발소리와 어긋나지 않으므로
## 거리에 비례한 시간을 준다.
func _walk_to(jan: Node2D, target: Vector2) -> void:
	var from: Vector2 = jan.position
	var delta := target - from
	var seconds: float = max(0.05, delta.length() / WALK_SPEED)
	_face(jan, _row_for(delta))

	var tween := create_tween()
	tween.tween_property(jan, "position", target, seconds).set_trans(Tween.TRANS_LINEAR)
	# 걷는 동안 발소리. 트윈과 나란히 돌린다.
	_step_clock = 0.0
	while tween.is_running():
		await get_tree().process_frame
		_step_clock += get_process_delta_time()
		if _step_clock >= STEP_SOUND_EVERY:
			_step_clock = 0.0
			Sfx.play(&"janitor_step")


func _row_for(delta: Vector2) -> int:
	if absf(delta.x) > absf(delta.y):
		return ROW_RIGHT if delta.x > 0.0 else ROW_LEFT
	return ROW_DOWN if delta.y > 0.0 else ROW_UP


## 바라보는 쪽을 바꾼다. 가운데 칸(1)이 서 있는 자세다.
func _face(jan: Node2D, row: int) -> void:
	if jan == null:
		return
	var body := jan.get_node_or_null("IntroJanitorBody") as Sprite2D
	if body == null:
		return
	body.frame = row * body.hframes + 1


# ── 3막 — 지금밖에 없어 ─────────────────────────────────────────────

func _act3_grace(gs) -> void:
	_say(gs, "이설", "(지금밖에 없어.)", "fear")
	_grace = GRACE_SECONDS
	_warned = false
	set_process(true)


func _tick_grace(delta: float) -> void:
	_grace -= delta
	if not _warned and _grace <= WARN_AT:
		_warned = true
		Sfx.play(&"janitor_step")
		_say(get_tree().get_first_node_in_group("game_state"), "",
			"발소리가 되돌아온다. 아까보다 가깝다.")
	if _grace <= 0.0:
		_grace = -1.0
		set_process(false)
		_caught("…아직 여기 있었네.")


## 유예를 넘겼다.
func _caught(line: String) -> void:
	var gs := get_tree().get_first_node_in_group("game_state")
	if gs == null:
		return
	Sfx.play(&"caught")
	_say(gs, "수위", line)
	gs.call("trigger_game_over", "artroom")


# ── 도구 ────────────────────────────────────────────────────────────

func _say(gs, speaker: String, text: String, emotion: String = "") -> void:
	if gs == null:
		return
	if speaker.is_empty():
		gs.call("request_notice", text)
	else:
		gs.call("request_speech", speaker, text, emotion)


func _wait(seconds: float) -> void:
	await get_tree().create_timer(seconds).timeout


## 조작을 멈춘다. **게임 전체를 멈추면(`get_tree().paused`) 카메라 트윈도 멈춘다** —
## 플레이어 노드만 세운다(`floor_manager`의 게임 오버 처리와 같은 방식).
##
## 숨은 동안에도 이걸 건다(2막). `player_controller`가 `_unhandled_input`에서
## E를 받아 캐비넷을 나가므로, 입력을 안 끊으면 자백 도중에 걸어 나올 수 있다.
func _freeze(player: Node, on: bool) -> void:
	if player == null:
		return
	if on:
		player.set("velocity", Vector2.ZERO)
	player.set_physics_process(not on)
	player.set_process_unhandled_input(not on)


func _camera(player: Node) -> Camera2D:
	if player == null:
		return null
	return player.get_node_or_null("Camera2D") as Camera2D


## 카메라를 문으로. `offset`을 움직인다 — 카메라가 플레이어의 자식이라
## 위치를 직접 옮길 수 없고, `offset`은 한계(`limit_*`)도 그대로 지킨다.
func _camera_to_door(player: Node) -> void:
	var cam := _camera(player)
	if cam == null:
		return
	var look := door_position - Vector2(0.0, LOOK_ABOVE)
	var tween := create_tween().set_parallel(true)
	tween.tween_property(cam, "offset", look - player.global_position,
		CAM_IN_SECONDS).set_trans(Tween.TRANS_SINE)
	tween.tween_property(cam, "zoom", Vector2(CLOSEUP_ZOOM, CLOSEUP_ZOOM),
		CAM_IN_SECONDS).set_trans(Tween.TRANS_SINE)
	await tween.finished
	await _wait(CAM_HOLD_SECONDS)


func _camera_back(player: Node) -> void:
	var cam := _camera(player)
	if cam == null:
		return
	var tween := create_tween().set_parallel(true)
	tween.tween_property(cam, "offset", Vector2.ZERO,
		CAM_OUT_SECONDS).set_trans(Tween.TRANS_SINE)
	tween.tween_property(cam, "zoom", Vector2(1.25, 1.25),
		CAM_OUT_SECONDS).set_trans(Tween.TRANS_SINE)
	await tween.finished


## 문틈으로 새는 빛. 폴리곤 하나를 알파로 켰다 끈다 — 문 바깥에 광원을 두면
## 문짝 차단체(`LO_ArtRoomDoorCollision`)에 막혀 아무것도 안 보인다.
func _glow(alpha: float, seconds: float) -> void:
	var node := get_node_or_null(door_glow_path)
	if node == null:
		return
	create_tween().tween_property(node, "modulate:a", alpha, seconds)
