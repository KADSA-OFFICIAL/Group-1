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

	# 장면이 끝나면 조작이 돌아오고 카메라가 제자리로 와야 한다
	var player: Node = main.get_node_or_null("Player")
	var cam := player.get_node_or_null("Camera2D") as Camera2D if player != null else null
	var waited := 0.0
	while player != null and not player.is_physics_processing() and waited < 20.0:
		await _wait(TICK)
		waited += TICK
	if player != null and not player.is_physics_processing():
		_fault("도입부: 장면이 끝났는데 조작이 안 돌아온다(20초 대기)")
	elif cam != null:
		if not cam.offset.is_equal_approx(Vector2.ZERO):
			_fault("도입부: 클로즈업 뒤 카메라 offset이 안 돌아왔다 (%s)" % cam.offset)
		if not cam.zoom.is_equal_approx(Vector2(1.25, 1.25)):
			_fault("도입부: 클로즈업 뒤 카메라 zoom이 안 돌아왔다 (%s)" % cam.zoom)
		_ok("도입부 카메라 복귀")

	# 유예가 시작됐는가
	if float(intro.get("_grace")) <= 0.0:
		_fault("도입부: 장면이 끝났는데 유예 타이머가 안 돈다")
	else:
		_ok("도입부 유예 시작")

	main.free()
	await process_frame
