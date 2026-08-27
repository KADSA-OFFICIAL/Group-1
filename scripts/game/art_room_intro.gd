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
## 국어책을 아직 안 챙긴 런의 유예 (#477).
##
## **책 없이 3막에 들어오는 것이 정상 경로다** — 수위를 부르는 방아쇠가 둘인데
## (#409) 그중 "단서 두 개 조사"는 책과 무관하다. 그런데 창문은 책을 요구하므로
## 그 런은 캐비넷 → 책 → 창문을 다 돌아야 한다.
##
## 격자 BFS로 실측했다(`verify_floor_reach`의 격자, 전속력 320px/s):
##
## | 경로 | 거리 | 전속력 |
## |---|---|---|
## | 캐비넷 → 창문 (책 든 런) | 1800px | 5.62초 |
## | 캐비넷 → 책 → 창문 (책 없는 런) | 2400px | 7.50초 |
##
## 20초가 5.62초의 3.6배이므로 같은 여유를 7.50초에 주면 27초다. 같은 20초를
## 주면 더 먼 길을 같은 시간에 뛰어야 했다 — 되돌릴 수 없는 실패라 인색하면 억울해진다.
const GRACE_SECONDS_NO_BOOK := 27.0
const WARN_AT := 8.0

## 클로즈업 카메라. 문을 화면에 담되 조금 위를 본다 — 문에 정확히 맞추면
## 카메라 한계(y 1000)에 잘려 문이 화면 맨 아래에 붙는다.
const LOOK_ABOVE := 70.0
const CLOSEUP_ZOOM := 2.0
const CAM_IN_SECONDS := 0.7
const CAM_HOLD_SECONDS := 0.35
const CAM_OUT_SECONDS := 0.6

## 들어올 때 걷는 속도(px/초). 순찰 속도(130)보다 느리다 — 쫓는 것이 아니라
## 둘러보는 걸음이다.
const WALK_SPEED := 115.0
## 나갈 때(#471). **열쇠를 가지러 가는 길이라 느릴 이유가 없다.** 78로 들고 날
## 때 왕복 16초가 걸렸는데, 그동안 플레이어는 캐비넷에 갇혀 아무것도 못 한다.
const EXIT_SPEED := 150.0
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
## 국어책과 그 표시 (#477). 아직 안 챙긴 런에서 가리킨다 — 창문이 요구하는 물건이
## 그것이고, 전에는 그 사실을 창문 앞에 서고 나서야 알 수 있었다.
@export var book_path: NodePath
@export var book_mark_path: NodePath
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
	_clear_waypoint()


func _on_investigated(_player: Node, name: String) -> void:
	if _fired:
		# 3막 도중에 국어책을 챙겼다 — 가리키던 표시를 걷는다 (#477).
		# 남겨 두면 이미 가방에 있는 것을 계속 가리켜 "아직 덜 됐다"로 읽힌다.
		if name == BACKSTOP_NODE and _grace > 0.0:
			_seen[name] = true
			_clear_waypoint()
			_say(get_tree().get_first_node_in_group("game_state"), "이설",
				"(챙겼어. 창문으로.)", "fear")
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
	_say(gs, "", "복도에서 발소리. 열쇠 꾸러미가 부딪힌다.")
	await _wait(1.1)

	await _camera_to_door(player)
	_glow(1.0, 0.5)
	Sfx.play(&"keys")
	await _wait(1.4)

	await _camera_back(player)
	_freeze(player, false)

	# 문 문구를 바꾼다 — 이제 안 나가는 이유가 "캄캄해서"가 아니다.
	var door: Node = get_node_or_null(door_path)
	if door != null and not door_after_message.is_empty():
		door.set("message", door_after_message)

	_say(gs, "이설", "(들어온다. 왼쪽 벽 캐비넷에 숨어야 해.)", "fear")
	_pulse_mark(cabinet_mark_path)
	_point_at(cabinet_path, "숨을 곳")

	# 국어책을 아직 안 챙겼으면 **지금** 말한다 (#477). 나가는 유일한 길인 창문이
	# 그 책을 요구하는데, 전에는 그 말을 창문 앞에 서고 나서야 들었다 — 그때는
	# 3막 유예가 거의 다 돌아 있어 되돌릴 수 없었다.
	#
	# 화면 표시(`_point_at`)는 캐비넷이 쓴다 — 지금은 숨는 것이 먼저이고, 표시가
	# 하나뿐이라 둘을 같이 가리키면 어디로 갈지가 흐려진다. 책은 월드 표시만 부풀린다.
	if _missing_book():
		_say(gs, "이설", "(국어책… 아직 책상 위야. 숨고 나서 챙기자.)", "fear")
		_pulse_mark(book_mark_path)

	_hide_left = HIDE_SECONDS
	_hide_warned = false
	set_process(true)


## 월드의 한 곳을 **화면에** 가리킨다(#478). 월드 표시(`_pulse_mark`)만으로는
## 부족하다 — 그 자리가 화면 밖일 수 있고, 화면 안이어도 `WallFade` 마스크가
## 389px 밖을 검게 칠해 어둠 속에서 부푼다.
##
## **표시는 하나뿐이다.** 1막은 숨을 곳, 3막은(책이 없으면) 국어책을 가리킨다 —
## 둘을 같이 가리킬 수 없으니 그 순간에 가야 할 곳 하나만 가리킨다 (#477).
func _point_at(target_path: NodePath, label: String) -> void:
	var hud := get_tree().get_first_node_in_group("hud")
	var target := get_node_or_null(target_path) as Node2D
	if hud == null or target == null or not hud.has_method("show_waypoint"):
		return
	hud.call("show_waypoint", target.global_position, label)


func _clear_waypoint() -> void:
	var hud := get_tree().get_first_node_in_group("hud")
	if hud != null and hud.has_method("hide_waypoint"):
		hud.call("hide_waypoint")


## 창문이 요구하는 물건을 아직 안 챙겼는가 (#477).
##
## **요구 조건을 여기 다시 적지 않고 창문 노드에서 읽는다** — 같은 값을 두 곳에
## 적어 두면 한쪽만 고쳐져 안내와 실제 관문이 어긋난다. 관문이 없어지면(빈 문자열)
## 아무 말도 하지 않는다.
func _missing_book() -> bool:
	var escape: Node = get_node_or_null(escape_path)
	if escape == null:
		return false
	var need = escape.get("required_item_id")
	if need == null or str(need).is_empty():
		return false
	var gs := get_tree().get_first_node_in_group("game_state")
	if gs == null or not gs.has_method("has_item"):
		return false
	return not gs.call("has_item", str(need))


## 표시 하나를 부풀렸다 되돌린다. 문구만으로는 어두운 방에서 못 찾는다.
func _pulse_mark(mark_path: NodePath) -> void:
	var mark := get_node_or_null(mark_path) as Node2D
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
		_clear_waypoint()
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
		_clear_waypoint()
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
	# **1막 안내 대사가 다 뜬 뒤에 입을 연다.** 캐비넷으로 곧장 달려간
	# 플레이어는 그것이 아직 대기열에 남은 채로 여기 도착한다(#471).
	await _drain()

	# **걸음과 대사를 겹친다.** 다 걸어온 뒤에 말하게 하면 들어오는 5초가
	# 통째로 침묵이다 — 걸으면서 딸 이야기를 시작하는 편이 자연스럽기도 하다.
	# 줄마다 대기 시간을 손으로 잡지는 않는다: 잡으면 실제 표시 시간과 어긋나
	# 장면이 대사를 앞지르거나(수위가 자백 도중 걸어 나감) 다 뜬 뒤 빈 화면을
	# 보게 된다(#471에서 둘 다 겪었다). 속도는 HUD 대기열(#454)이 잡는다.
	for line in [
			# 문을 열고 들어서며 하는 말이다 — 1막에서 여기로 옮겼다(#478).
			["수위", "…이 문 왜 열려 있어.", ""],
			["수위", "시우야. 니 그림은 아직 여기 있다.", ""],
			["수위", "니 반 애들, 아빠가 하나씩 치웠어. 울면서 빌더라.", ""],
			["수위", "니가 빌 때는 아무도 안 들어줬는데. 심판이야, 죄 있는 애들만.",
				"suspicion"]]:
		_say(gs, line[0], line[1], line[2])

	if jan != null and janitor_walk.size() >= 2:
		jan.position = janitor_walk[0]
		jan.visible = true
		for i in range(1, janitor_walk.size()):
			await _walk_to(jan, janitor_walk[i])
	_face(jan, ROW_LEFT)

	# 다 말하기 전에 나가면 안 된다.
	await _drain()

	# 나간다. **말과 걸음도 겹친다** — 말이 다 뜨기를 기다렸다 걷게 하면 그
	# 사이가 빈 화면이고, 말하면서 몸을 돌려 나가는 것이 자연스럽다.
	_say(gs, "수위", "…열쇠 가져와서 잠가야겠다.")
	if jan != null and janitor_walk.size() >= 2:
		for i in range(janitor_walk.size() - 2, -1, -1):
			await _walk_to(jan, janitor_walk[i], EXIT_SPEED)
		jan.visible = false
	Sfx.play(&"janitor_step")
	_glow(0.0, 0.8)
	# **이 줄이 다 뜬 뒤에 유예를 켠다.** 안 기다리면 "지금밖에 없어"가 덮고,
	# 20초 유예가 아직 읽는 중에 흐르기 시작한다(#471).
	await _drain()

	_scene_locked = false
	_freeze(player, false)
	_act3_grace(gs)


## 한 지점까지 걸어간다. 속도가 일정해야 발소리와 어긋나지 않으므로
## 거리에 비례한 시간을 준다.
func _walk_to(jan: Node2D, target: Vector2, speed: float = WALK_SPEED) -> void:
	var from: Vector2 = jan.position
	var delta := target - from
	var seconds: float = max(0.05, delta.length() / speed)
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
	# 책이 없으면 **다시** 알린다 (#477). 1막에서 한 번 말했지만 그 사이에
	# 자백 28초가 지나갔고, 그동안 플레이어는 캐비넷에 갇혀 아무것도 못 했다.
	# 여기서는 표시도 책으로 옮긴다 — 숨을 곳은 이미 다 쓴 안내다.
	if _missing_book():
		_grace = GRACE_SECONDS_NO_BOOK
		_say(gs, "이설", "(국어책부터. 그거 가지러 온 거야.)", "fear")
		_point_at(book_path, "국어책")
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
		_clear_waypoint()
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


## 자막 대기열이 빌 때까지 기다린다 — 장면이 대사를 앞지르지 않게(#471).
func _drain() -> void:
	var hud := get_tree().get_first_node_in_group("hud")
	if hud != null and hud.has_method("await_speech_drained"):
		await hud.call("await_speech_drained")


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
