extends SceneTree

## 런타임 스모크 테스트(#240) — 씬을 **트리에 붙이고 프레임을 돌려** 본다.
##
## `ci_load_scenes.gd`는 `load()` + `instantiate()`만 한다. 트리에 안 넣으므로
## **`_ready`가 돌지 않고**, `@onready` 경로·시그널 연결·트윈이 통째로 검사에서
## 빠진다. 그 빈틈으로 버그가 `main`까지 머지된 적이 있다(#225 → #234).
##
##   1. 미닫이문 시각이 레이어 0에 있어 `WallGlow`에 가려 아예 안 보였다.
##   2. 문 존의 `collision_mask = 1`에 벽·집기·자기 문짝이 걸려 **모든 문이
##      씬을 여는 순간 영구히 열린 채**였다.
##
## 둘 다 정적 검사로는 못 잡고 프레임이 한 번만 돌면 바로 드러난다. 같은 유형을
## 임시 스크립트로 열 번 넘게 잡았으니(#225·#231·#234·#301·#343·#353·#356·
## #359·#405·#406·#409) 상설로 둔다.
##
##     godot --headless --script res://tools/ci_smoke_scenes.gd

## 미닫이문이 있는 층. **4층은 뺀다** — 도입부라 미술실 문이 미닫이가 아니라
## 고정 패널(`ArtDoorPanel`)이다(#405). 4층은 `_check_artroom_intro()`가 따로 본다.
const DOOR_FLOORS := [1, 2, 3]
const MAIN := "res://scenes/main/main.tscn"
const INTRO := "res://scenes/ui/intro.tscn"
## 문을 열고 닫는 데 주는 시간. `sliding_door.gd`의 `open_time`보다 넉넉해야 한다.
const DOOR_SETTLE := 0.6
## 프레임을 돌리는 사이 한 번에 기다릴 시간.
const TICK := 0.05
## `WallFade` 마스크가 완전히 검어지는 거리(main.tscn의 Mask, scale 2 기준 389px).
## 이 밖에 있는 수위는 숨은 이설에게 **안 보인다**(#465).
const FADE_RADIUS := 389.0

var _fail: Array[String] = []
var _checked := 0


func _initialize() -> void:
	_run()


func _fault(msg: String) -> void:
	_fail.append(msg)
	push_error("스모크: " + msg)


func _ok(_msg: String) -> void:
	_checked += 1


func _run() -> void:
	await process_frame
	for fl in DOOR_FLOORS:
		await _check_floor(fl)
	await _check_intro()
	await _check_artroom_intro()

	print("")
	if _fail.is_empty():
		print("스모크 테스트: 검사 %d건, 실패 0건" % _checked)
		quit(0)
		return
	print("스모크 테스트: 검사 %d건, **실패 %d건**" % [_checked, _fail.size()])
	for f in _fail:
		print("  ✗ " + f)
	quit(1)


func _wait(seconds: float) -> void:
	await create_timer(seconds).timeout


## 조건이 참이 될 때까지 기다린다. 참이 됐으면 true, 시간을 넘기면 false.
func _until(cond: Callable, seconds: float) -> bool:
	var waited := 0.0
	while waited < seconds:
		if bool(cond.call()):
			return true
		await _wait(TICK)
		waited += TICK
	return bool(cond.call())


## 층 씬을 붙이고 미닫이문 전부를 열고 닫아 본다.
func _check_floor(fl: int) -> void:
	var path := "res://scenes/background/school_floor_%d.tscn" % fl
	var packed: PackedScene = load(path)
	if packed == null:
		_fault("floor%d: 씬을 못 읽었다" % fl)
		return
	var node: Node2D = packed.instantiate()
	root.add_child(node)
	await process_frame
	await process_frame

	var doors: Array[Node] = []
	for child in node.get_children():
		if String(child.name).begins_with("SlideDoor_"):
			doors.append(child)
	if doors.is_empty():
		_fault("floor%d: 미닫이문이 하나도 없다" % fl)
		node.free()
		return

	# ── 처음 상태 ──────────────────────────────────────────
	# **저절로 열려 있으면 안 된다**(#234). 문 존이 벽·집기를 몸으로 세면
	# 씬을 여는 순간 전부 열린 채가 된다.
	var opened_by_itself := 0
	for d in doors:
		var panel := d.get_node_or_null("SDPanel") as StaticBody2D
		if panel == null:
			_fault("floor%d %s: SDPanel이 없다" % [fl, d.name])
			continue
		if not panel.position.is_equal_approx(Vector2.ZERO):
			opened_by_itself += 1
		var shape := _polygon_of(panel)
		if shape == null:
			_fault("floor%d %s: 문짝 충돌(CollisionPolygon2D)이 없다" % [fl, d.name])
		elif shape.disabled:
			_fault("floor%d %s: 처음부터 충돌이 꺼져 있다" % [fl, d.name])
		if d.get_node_or_null(d.get("leaf_visual")) == null:
			_fault("floor%d %s: 문짝 시각(leaf_visual)을 못 찾는다" % [fl, d.name])
	if opened_by_itself > 0:
		_fault("floor%d: 문 %d개가 **저절로 열렸다**(#234와 같은 함정)"
			% [fl, opened_by_itself])
	_ok("floor%d 문 %d개 초기 상태" % [fl, doors.size()])

	# ── 열고 닫기 ──────────────────────────────────────────
	var sample: Node = doors[0]
	var panel0 := sample.get_node_or_null("SDPanel") as StaticBody2D
	var leaf0 := sample.get_node_or_null(sample.get("leaf_visual")) as Node2D
	if panel0 != null and leaf0 != null:
		var want := Vector2(float(sample.get("travel")), float(sample.get("travel_y")))
		sample.call("interact", null)
		await _wait(DOOR_SETTLE)
		if not panel0.position.is_equal_approx(want):
			_fault("floor%d %s: 열었는데 문짝 몸이 안 움직였다 (%s != %s)"
				% [fl, sample.name, panel0.position, want])
		if not leaf0.position.is_equal_approx(want):
			_fault("floor%d %s: 열었는데 문짝 **시각**이 안 따라왔다 (%s != %s)"
				% [fl, sample.name, leaf0.position, want])
		var sh := _polygon_of(panel0)
		if sh != null and not sh.disabled:
			_fault("floor%d %s: 열었는데 충돌이 켜져 있다" % [fl, sample.name])

		sample.call("interact", null)
		await _wait(DOOR_SETTLE)
		if not panel0.position.is_equal_approx(Vector2.ZERO):
			_fault("floor%d %s: 닫았는데 제자리로 안 왔다" % [fl, sample.name])
		if sh != null and sh.disabled:
			_fault("floor%d %s: 닫았는데 충돌이 꺼져 있다" % [fl, sample.name])
		_ok("floor%d %s 여닫기" % [fl, sample.name])

	node.free()
	await process_frame


func _polygon_of(body: Node) -> CollisionPolygon2D:
	for c in body.get_children():
		if c is CollisionPolygon2D:
			return c as CollisionPolygon2D
	return null


## 프롤로그 — 건너뛰기 버튼이 살아 있는가(#231).
func _check_intro() -> void:
	var packed: PackedScene = load(INTRO)
	if packed == null:
		_fault("intro: 씬을 못 읽었다")
		return
	var node: Node = packed.instantiate()
	root.add_child(node)
	await process_frame
	await process_frame

	var skip := node.get_node_or_null("SkipButton") as Button
	if skip == null:
		_fault("intro: SkipButton이 없다")
	else:
		if skip.pressed.get_connections().is_empty():
			_fault("intro: SkipButton의 pressed가 아무 데도 연결돼 있지 않다")
		# 포커스를 받으면 스페이스·엔터가 대사 넘기기 대신 버튼을 누른다.
		if skip.focus_mode != Control.FOCUS_NONE:
			_fault("intro: SkipButton의 focus_mode가 FOCUS_NONE이 아니다")
		_ok("intro SkipButton")
	node.free()
	await process_frame


## 미술실 도입부(#409) — 단서 두 개를 조사하면 수위가 오는가.
##
## 조립 씬(`main.tscn`)째로 띄운다. 장면 진행자가 층 씬 안에 있고 플레이어·
## GameState·HUD를 전부 필요로 하기 때문이다.
func _check_artroom_intro() -> void:
	var packed: PackedScene = load(MAIN)
	if packed == null:
		_fault("main: 씬을 못 읽었다")
		return
	var main: Node = packed.instantiate()
	root.add_child(main)
	for i in 8:
		await process_frame
	await _wait(0.4)

	var bg: Node = main.get_node_or_null("Background")
	var intro: Node = bg.get_node_or_null("ArtRoomIntro") if bg != null else null
	if intro == null:
		_fault("main: 4층 ArtRoomIntro를 못 찾았다")
		main.free()
		return

	# 창문·문·단서가 다 붙어 있는가
	for want in ["PrepWindowEscape", "ArtRoomDoor", "KoreanBook", "SiwooPainting",
			"Belongings", "DateWall", "HideArtCabinet"]:
		if bg.get_node_or_null(want) == null:
			_fault("main: 4층에 %s가 없다" % want)
	_ok("4층 도입부 노드")

	# 창문 컷신(#468) — 생성기가 대사를 안 실으면 계단처럼 지나가 버린다.
	var win: Node = bg.get_node_or_null("PrepWindowEscape")
	if win != null:
		var cl: PackedStringArray = win.get("cutscene_lines")
		if cl.is_empty():
			_fault("창문: 내려가는 컷신 대사가 비어 있다")
		elif not String(win.get("cutscene_speaker")) == "이설":
			_fault("창문: 컷신 화자가 이설이 아니다 (%s)" % win.get("cutscene_speaker"))
		else:
			_ok("창문 컷신 대사 %d줄" % cl.size())

	# 단서 하나로는 안 오고
	bg.get_node("SiwooPainting").call("interact", null)
	await _wait(0.2)
	if bool(intro.get("_fired")):
		_fault("도입부: 단서 하나만 조사했는데 수위가 왔다")
	# 둘이면 온다
	bg.get_node("Belongings").call("interact", null)
	await _wait(0.2)
	if not bool(intro.get("_fired")):
		_fault("도입부: 단서 둘을 조사했는데 수위가 오지 않는다")
	else:
		_ok("도입부 발동 조건")

	var player: Node = main.get_node_or_null("Player")
	var cam := player.get_node_or_null("Camera2D") as Camera2D if player != null else null

	# ── 1막: 조작이 돌아오고 숨을 유예가 돈다(#465) ─────────────────
	if not await _until(func() -> bool:
			return player != null and player.is_physics_processing(), 20.0):
		_fault("도입부 1막: 장면이 끝났는데 조작이 안 돌아온다(20초 대기)")
	elif cam != null:
		if not cam.offset.is_equal_approx(Vector2.ZERO):
			_fault("도입부 1막: 클로즈업 뒤 카메라 offset이 안 돌아왔다 (%s)" % cam.offset)
		if not cam.zoom.is_equal_approx(Vector2(1.25, 1.25)):
			_fault("도입부 1막: 클로즈업 뒤 카메라 zoom이 안 돌아왔다 (%s)" % cam.zoom)
		_ok("도입부 1막 카메라 복귀")
	if not await _until(func() -> bool:
			return float(intro.get("_hide_left")) > 0.0, 10.0):
		_fault("도입부 1막: 숨을 유예가 안 돈다(10초 대기)")
	else:
		_ok("도입부 1막 숨을 유예")

	# 숨을 곳을 화면에 가리키는가(#478) — 월드 표시만으로는 어둠에 묻힌다.
	var wp: Control = main.get_node_or_null("HUD/Root/Waypoint")
	if wp == null:
		_fault("도입부 1막: HUD에 Waypoint가 없다")
	elif not await _until(func() -> bool: return wp.visible, 10.0):
		_fault("도입부 1막: 숨을 곳 화면 표시가 안 뜬다(10초 대기)")
	else:
		_ok("도입부 1막 숨을 곳 화면 표시")

	# ── 2막: 숨으면 수위가 실제로 들어온다 ────────────────────────
	var jan := bg.get_node_or_null("IntroJanitor") as Node2D
	if jan == null:
		_fault("도입부: IntroJanitor가 없다")
	elif jan.visible:
		_fault("도입부: 숨기 전인데 수위가 벌써 보인다")
	bg.get_node("HideArtCabinet").call("interact", player)
	if player.get("is_hiding") != true:
		_fault("도입부 2막: 캐비넷에 숨지 못했다")
	if not await _until(func() -> bool: return bool(intro.get("_scene_locked")), 5.0):
		_fault("도입부 2막: 숨었는데 자백 장면이 시작되지 않는다")
	else:
		_ok("도입부 2막 시작")
	if wp != null and not await _until(func() -> bool: return not wp.visible, 5.0):
		_fault("도입부 2막: 숨었는데 숨을 곳 표시가 안 사라진다")
	elif wp != null:
		_ok("도입부 2막 표시 사라짐")
	if jan != null and not await _until(func() -> bool: return jan.visible, 20.0):
		_fault("도입부 2막: 수위가 안 보인다(20초 대기)")
	# 장면 도중에는 캐비넷에서 못 나온다
	if player.is_processing_unhandled_input():
		_fault("도입부 2막: 장면 도중인데 입력이 살아 있다(캐비넷에서 나갈 수 있다)")
	else:
		_ok("도입부 2막 입력 잠금")
	# 캐비넷 앞까지 오는가 — WallFade 마스크가 389px 밖을 검게 칠한다
	var cabinet := bg.get_node("HideArtCabinet") as Node2D
	if jan != null and not await _until(func() -> bool:
			return jan.position.distance_to(cabinet.position) <= FADE_RADIUS, 30.0):
		_fault("도입부 2막: 수위가 캐비넷 %dpx 안까지 안 온다 (가장 가까웠던 곳 %.0fpx)"
			% [FADE_RADIUS, jan.position.distance_to(cabinet.position)])
	else:
		_ok("도입부 2막 수위가 캐비넷 앞까지")

	# ── 3막: 수위가 나가고 유예가 돈다 ────────────────────────────
	if not await _until(func() -> bool: return float(intro.get("_grace")) > 0.0, 60.0):
		_fault("도입부 3막: 자백이 끝났는데 유예 타이머가 안 돈다(60초 대기)")
	else:
		_ok("도입부 3막 유예 시작")
	# **여기서 붙잡아 둔다** — 유예는 매 프레임 줄어들어 아래 검사까지 가면 값이 달라진다.
	var grace_at_start := float(intro.get("_grace"))
	if jan != null and jan.visible:
		_fault("도입부 3막: 수위가 나갔는데 아직 보인다")
	if not player.is_processing_unhandled_input():
		_fault("도입부 3막: 장면이 끝났는데 입력이 안 돌아왔다")
	else:
		_ok("도입부 3막 조작 복귀")

	# ── 책 없이 3막에 들어온 런(#477) ─────────────────────────────
	# **이 스모크가 곧 그 런이다** — 국어책을 안 챙기고 단서 둘로 수위를 불렀다.
	# 정상 경로인데(방아쇠 둘 중 하나가 책과 무관하다) 전에는 창문이 거절하고
	# 유예가 다 돌아 그대로 죽었다. 안내도 창문 앞 말고는 없었다.
	var gs: Node = get_first_node_in_group("game_state")
	var need := String(win.get("required_item_id")) if win != null else ""
	var consts: Dictionary = intro.get_script().get_script_constant_map()
	var grace_base: float = float(consts.get("GRACE_SECONDS", 20.0))
	var grace_long: float = float(consts.get("GRACE_SECONDS_NO_BOOK", grace_base))
	if gs == null or need.is_empty():
		_fault("도입부 3막: game_state(%s) 또는 창문 요구 아이템(%s)을 못 찾았다"
			% [gs, need])
	elif bool(gs.call("has_item", need)):
		_fault("도입부 3막: 스모크가 %s를 이미 들고 있어 책 없는 경로를 못 본다" % need)
	else:
		# 유예가 길어진다 — 캐비넷에서 책을 거쳐 창문까지가 더 멀다.
		if grace_at_start <= grace_base + 1.0:
			_fault("도입부 3막: 책이 없는데 유예가 안 늘었다 (%.1f초, 기본 %.1f초)"
				% [grace_at_start, grace_base])
		elif grace_at_start > grace_long + 0.5:
			_fault("도입부 3막: 유예가 상수보다 길다 (%.1f초 > %.1f초)"
				% [grace_at_start, grace_long])
		else:
			_ok("도입부 3막 책 없는 런의 유예 %.1f초" % grace_at_start)
		# 국어책을 화면에서 가리킨다 — 2막에서 한 번 걷힌 표시가 다시 뜬다.
		if wp == null:
			_fault("도입부 3막: HUD에 Waypoint가 없다")
		elif not await _until(func() -> bool: return wp.visible, 5.0):
			_fault("도입부 3막: 책이 없는데 국어책 표시가 안 뜬다(5초 대기)")
		else:
			_ok("도입부 3막 국어책 화면 표시")
		# 챙기면 표시가 걷힌다 — 가방에 있는 것을 계속 가리키면 안 된다.
		bg.get_node("KoreanBook").call("interact", player)
		await process_frame
		if not bool(gs.call("has_item", need)):
			_fault("도입부 3막: 국어책을 조사했는데 가방에 안 들어왔다")
		elif wp != null and not await _until(func() -> bool: return not wp.visible, 5.0):
			_fault("도입부 3막: 국어책을 챙겼는데 표시가 안 사라진다")
		else:
			_ok("도입부 3막 국어책 챙긴 뒤 표시 정리")

	# ── 창문으로 내려가기 시작하면 유예가 끊긴다(#472) ─────────────
	# 컷신(#468)이 도는 18초 동안에도 4층 씬은 살아 있어 유예(20초)가 계속 돌았고,
	# 창문에 제때 닿아도 컷신 도중에 게임 오버가 났다.
	if win != null and not win.has_signal("travel_started"):
		_fault("창문: 하강 시작을 알리는 travel_started 신호가 없다")
	elif win != null:
		win.emit_signal("travel_started")
		await process_frame
		if float(intro.get("_grace")) > 0.0:
			_fault("도입부: 창문으로 내려가기 시작했는데 유예가 계속 돈다 (%.1f초)"
				% intro.get("_grace"))
		elif intro.is_processing():
			_fault("도입부: 창문으로 내려가기 시작했는데 타이머가 안 꺼졌다")
		else:
			_ok("창문 하강 시 유예 정지")

	main.free()
	await process_frame
