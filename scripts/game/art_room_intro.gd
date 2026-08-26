extends Node

## 미술실 도입부 장면(#409) — 단서를 두 개 조사하면 수위가 문 밖에 선다.
##
## **타이머로 부르지 않는다.** `docs/story.md`가 "많이 알수록 위험하고, 많이
## 알수록 엔딩이 달라진다"고 적어 둔 규칙을 도입부에서 몸으로 가르치는 자리다 —
## 시간이 흘러서 오면 플레이어의 행동과 무관하지만, **조사가 부르면** 자기 손으로
## 위험을 불러온 것이 된다.
##
## 다만 아무것도 안 뒤지고 나가려는 플레이어도 이 장면을 봐야 한다(송하람 학생증이
## 이야기의 훅이다). 그래서 **국어책을 집는 것**도 방아쇠다 — 그걸 챙긴 순간이
## 곧 나가려는 순간이다.
##
## **수위는 방에 들어오지 않는다.** 문 밖에서 말하고 열쇠를 가지러 간다. 그래서
## 4층 씬에 복도도 수위 스프라이트도 없고, 보여 줄 것은 문과 문틈 빛뿐이다.

## 몇 개를 조사하면 오는가.
const CLUES_TO_TRIGGER := 2
## 수위가 돌아오기까지. 미술실 시작 지점에서 준비실 창문까지 **격자 거리 1780px,
## 전속력 5.6초**로 실측했다(#409). 3배 남짓 두어 길을 헤매도 닿게 한다 —
## 되돌릴 수 없는 실패라 인색하면 억울해진다.
const GRACE_SECONDS := 20.0
## 이만큼 남았을 때 한 번 알린다. 남은 초를 숫자로 보여 주지는 않는다.
const WARN_AT := 8.0

## 클로즈업 카메라. 문을 화면에 담되 조금 위를 본다 — 문에 정확히 맞추면
## 카메라 한계(y 1000)에 잘려 문이 화면 맨 아래에 붙는다.
const LOOK_ABOVE := 70.0
const CLOSEUP_ZOOM := 2.0
const CAM_IN_SECONDS := 0.7
const CAM_HOLD_SECONDS := 0.35
const CAM_OUT_SECONDS := 0.6

## 조사하면 수위를 부르는 단서. 국어책은 따로 센다(백스톱).
const CLUE_NODES := ["SiwooPainting", "HaramCard", "Belongings", "DateWall"]
const BACKSTOP_NODE := "KoreanBook"

## 문 위치(클로즈업이 바라볼 곳)와 문틈 빛. 생성기가 채운다.
@export var door_position: Vector2 = Vector2.ZERO
@export var door_glow_path: NodePath
## 장면이 끝난 뒤 문을 조사하면 나올 말. 그 전에는 "국어책부터 챙기자"다.
@export_multiline var door_after_message: String = ""
@export var door_path: NodePath

var _seen: Dictionary = {}
var _fired: bool = false
var _grace: float = -1.0
var _warned: bool = false


func _ready() -> void:
	set_process(false)
	var root := get_parent()
	for name in CLUE_NODES + [BACKSTOP_NODE]:
		var node: Node = root.get_node_or_null(name)
		if node != null and node.has_signal("interacted"):
			node.interacted.connect(_on_investigated.bind(name))


func _on_investigated(_player: Node, name: String) -> void:
	if _fired:
		return
	_seen[name] = true
	if name == BACKSTOP_NODE or _clue_count() >= CLUES_TO_TRIGGER:
		_fired = true
		_play_scene()


func _clue_count() -> int:
	var n := 0
	for c in CLUE_NODES:
		if _seen.has(c):
			n += 1
	return n


## 문 밖의 수위. 조작을 멈추고 카메라를 문으로 붙였다가 되돌린다.
func _play_scene() -> void:
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

	_say(gs, "수위", "이 문 왜 열려 있어?")
	await _wait(2.0)
	_say(gs, "수위", "…시우 그림은 그대로고.")
	await _wait(2.0)
	_say(gs, "수위", "열쇠 가져와서 잠가야겠네.")
	await _wait(2.0)

	Sfx.play(&"janitor_step")
	_say(gs, "", "발소리가 멀어진다. 계단 쪽이다.")
	_glow(0.0, 0.8)
	await _wait(1.2)

	await _camera_back(player)
	_freeze(player, false)

	# 문 문구를 바꾼다 — 이제 안 나가는 이유가 "캄캄해서"가 아니다.
	var door: Node = get_node_or_null(door_path)
	if door != null and not door_after_message.is_empty():
		door.set("message", door_after_message)

	_say(gs, "이설", "(지금밖에 없어.)", "fear")
	_grace = GRACE_SECONDS
	_warned = false
	set_process(true)


func _process(delta: float) -> void:
	if _grace < 0.0:
		return
	_grace -= delta
	if not _warned and _grace <= WARN_AT:
		_warned = true
		Sfx.play(&"janitor_step")
		var gs := get_tree().get_first_node_in_group("game_state")
		_say(gs, "", "발소리가 되돌아온다. 아까보다 가깝다.")
	if _grace <= 0.0:
		_grace = -1.0
		set_process(false)
		_caught()


## 유예를 넘겼다. 수위가 문을 열고 들어온다.
func _caught() -> void:
	var gs := get_tree().get_first_node_in_group("game_state")
	if gs == null:
		return
	Sfx.play(&"caught")
	_say(gs, "수위", "…거기 누구야.")
	gs.call("trigger_game_over", "artroom")


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
