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

## 미닫이문이 있는 층. 4층은 도입부라 **복도** 문이 미닫이가 아니라 고정
## 패널(`ArtDoorPanel`)이지만(#405), 미술실↔준비실 연결문은 미닫이다(#591) —
## 그래서 4층도 본다. 4층 도입부 연출 자체는 `_check_artroom_intro()`가 따로 본다.
const DOOR_FLOORS := [1, 2, 3, 4]
const MAIN := "res://scenes/main/main.tscn"
const INTRO := "res://scenes/ui/intro.tscn"
const MENU := "res://scenes/ui/main_menu.tscn"
const INK := "res://scenes/items/ink_projectile.tscn"
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
	# 테마는 본편 씬보다 먼저 본다 — main.tscn을 띄우면 start_music이 테마를 걷는다.
	await _check_themes()
	_check_variants()
	await _check_player_footsteps()
	await _check_intro()
	await _check_subtitle_queue()
	await _check_artroom_intro()
	await _check_ink_throw()

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

		# 수위가 지나가면 문은 열리되 **전역 효과음은 안 난다**(#609).
		# Sfx는 위치가 없어 층 반대편에서 지나가도 바로 옆처럼 들렸다.
		await _wait(0.6)   # 위 여닫이 소리가 끝나길 기다린다
		var before := _sfx_voices_playing()
		var fake := CharacterBody2D.new()
		fake.add_to_group("janitor")
		node.add_child(fake)
		sample.call("_on_body_entered", fake)
		await process_frame
		if _sfx_voices_playing() > before:
			_fault("floor%d %s: 수위가 문에 들어오자 전역 효과음이 울렸다(#609)"
				% [fl, sample.name])
		await _wait(DOOR_SETTLE)
		if not panel0.position.is_equal_approx(want):
			_fault("floor%d %s: 수위가 들어왔는데 문이 안 열렸다" % [fl, sample.name])
		sample.call("_on_body_exited", fake)
		fake.free()
		_ok("floor%d %s 수위 통과 무음" % [fl, sample.name])

	node.free()
	await process_frame


func _sfx_voices_playing() -> int:
	var sfx: Node = root.get_node_or_null("Sfx")
	if sfx == null:
		return 0
	var count := 0
	for p in sfx.get("_players"):
		if (p as AudioStreamPlayer).playing:
			count += 1
	return count


func _polygon_of(body: Node) -> CollisionPolygon2D:
	for c in body.get_children():
		if c is CollisionPolygon2D:
			return c as CollisionPolygon2D
	return null


## 타이틀·프롤로그 테마(#606) — 화면마다 제 곡이 울리고, 바뀔 때 앞 곡이
## 사라지고, 본편(start_music)이 테마를 걷어 가는가.
func _check_themes() -> void:
	var sfx: Node = root.get_node_or_null("Sfx")
	if sfx == null:
		_fault("테마: Sfx autoload가 없다")
		return
	var fade: float = sfx.get_script().get_script_constant_map().get("THEME_FADE", 1.6)

	var menu: Node = (load(MENU) as PackedScene).instantiate()
	root.add_child(menu)
	await process_frame
	var title_player: AudioStreamPlayer = _expect_theme(sfx, &"title", "타이틀")
	menu.free()

	var intro: Node = (load(INTRO) as PackedScene).instantiate()
	root.add_child(intro)
	await process_frame
	var prologue_player: AudioStreamPlayer = _expect_theme(sfx, &"prologue", "프롤로그")
	if title_player != null and title_player == prologue_player:
		_fault("테마: 타이틀과 프롤로그가 같은 플레이어다(크로스페이드가 아니라 갈아 끼움)")
	await _wait(fade + 0.3)
	if title_player != null and title_player.playing:
		_fault("테마: 프롤로그로 넘어간 뒤에도 타이틀 곡이 멈추지 않았다")
	else:
		_ok("테마 크로스페이드 후 앞 곡 정지")
	intro.free()

	# 본편 진입 — 건너뛰기처럼 인트로가 stop_theme을 안 부른 경로도 덮는가.
	sfx.call("start_music")
	await _wait(fade + 0.3)
	if prologue_player != null and prologue_player.playing:
		_fault("테마: start_music 뒤에도 프롤로그 곡이 울린다")
	else:
		_ok("본편 진입 시 테마 정지")
	sfx.call("stop_music")
	await _wait(0.1)


## 소리 변형(#611) — 수위 발소리가 같은 파일을 연달아 쓰지 않고 넷을 고루 쓰는가.
## 이설 발소리(#621) — 걷기 그림과 같은 자로 한 걸음(WALK_STEP_PX)마다 한 번.
## `_update_sprite(moving, moved)`가 걷기 그림과 발소리를 함께 정하므로 그것을
## 직접 부른다(입력을 흉내 내면 벽·집기에 막혀 거리가 들쭉날쭉하다).
func _check_player_footsteps() -> void:
	var main: Node = (load(MAIN) as PackedScene).instantiate()
	root.add_child(main)
	for i in 4:
		await process_frame
	var player: Node = main.get_node_or_null("Player")
	if player == null:
		_fault("이설 발소리: Player가 없다")
		main.free()
		return
	var consts: Dictionary = player.get_script().get_script_constant_map()
	var step_px: float = consts.get("WALK_STEP_PX", 160.0)
	var phase: float = consts.get("FOOTSTEP_PHASE_PX", 0.0)
	# **물리 처리를 끈다**(컷신이 이설을 붙잡는 방식). 켜 두면 입력이 없는
	# _physics_process가 매 tick `_update_sprite(false, …)`로 걸은 거리를 0으로
	# 되돌려서, 프레임 사이에 tick이 끼는 느린 기계(CI)에서는 "걸음 사이" 호출이
	# 다시 첫 걸음 경계를 넘었다 — 로컬은 프레임이 빨라 tick이 안 끼어 통과했다.
	player.set_physics_process(false)
	player.call("_update_sprite", false, 0.0)

	# (움직이는가, 이번에 나아간 거리, 이 호출에서 발소리가 나야 하는가)
	var plan := [
		[true, phase * 0.5, false],          # 출발 직후 — 첫 걸음 전
		[true, phase, true],                 # 첫 걸음 경계를 넘음
		[true, 0.0, false],                  # 벽 밀기 — 이동 0
		[true, step_px * 0.5, false],        # 걸음 사이
		[true, step_px * 0.5, true],         # 둘째 걸음
		[false, 0.0, false],                 # 멈춤
		[true, phase * 0.5, false],          # 다시 출발 — 다시 첫 걸음 전부터
	]
	for row in plan:
		var before := _player_step_voices()
		player.call("_update_sprite", row[0], row[1])
		# 물리 tick을 반드시 하나 끼운다 — 기계 속도와 상관없이 CI와 같은 조건.
		await physics_frame
		await process_frame
		var rang := _player_step_voices() > before
		if rang != row[2]:
			_fault("이설 발소리: moving=%s moved=%.0f에서 %s"
				% [row[0], row[1], "소리가 났다" if rang else "소리가 안 났다"])
			main.free()
			await process_frame
			return
		# 다음 줄이 새 발소리를 셀 수 있게 지금 울리는 것을 끊는다.
		_stop_player_step_voices()
	_ok("이설 발소리 박자")
	player.set_physics_process(true)
	main.free()
	await process_frame


func _player_step_voices() -> int:
	var count := 0
	for p in root.get_node("Sfx").get("_players"):
		var player := p as AudioStreamPlayer
		if player.playing and player.stream != null \
				and player.stream.resource_path.get_file().begins_with("player_step"):
			count += 1
	return count


func _stop_player_step_voices() -> void:
	for p in root.get_node("Sfx").get("_players"):
		var player := p as AudioStreamPlayer
		if player.stream != null and player.stream.resource_path.get_file().begins_with("player_step"):
			player.stop()


func _check_variants() -> void:
	var sfx: Node = root.get_node_or_null("Sfx")
	if sfx == null:
		_fault("변형: Sfx autoload가 없다")
		return
	var seen := {}
	var previous: AudioStream = null
	for i in 40:
		var stream: AudioStream = sfx.call("variant", &"janitor_step")
		if stream == null:
			_fault("변형: janitor_step 변형을 못 읽었다")
			return
		if stream == previous:
			_fault("변형: 같은 발소리가 연달아 나왔다(%s)" % stream.resource_path)
			return
		previous = stream
		seen[stream.resource_path] = true
	if seen.size() != 4:
		_fault("변형: 발소리 변형 4개 중 %d개만 나왔다" % seen.size())
		return
	var plain: AudioStream = sfx.call("variant", &"pickup")
	if plain == null or not plain.resource_path.ends_with("pickup.wav"):
		_fault("변형: 변형이 없는 소리(pickup)가 그대로 안 나온다")
		return
	_ok("발소리 변형")


## 지금 테마가 id이고 그 곡을 실제로 틀고 있는가. 틀고 있는 플레이어를 돌려준다.
func _expect_theme(sfx: Node, id: StringName, label: String) -> AudioStreamPlayer:
	if StringName(sfx.get("_theme_id")) != id:
		_fault("테마: %s 화면인데 현재 테마가 '%s'다" % [label, sfx.get("_theme_id")])
		return null
	var players: Array = sfx.get("_theme_players")
	var player := players[int(sfx.get("_theme_index"))] as AudioStreamPlayer
	if player.stream == null or not player.stream.resource_path.ends_with("%s.wav" % id):
		_fault("테마: %s 플레이어에 %s.wav가 안 물려 있다" % [label, id])
		return null
	if not player.playing:
		_fault("테마: %s 곡이 재생 중이 아니다" % label)
		return null
	_ok("테마 %s" % label)
	return player


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
## 같은 자막이 겹쳐 나오지 않는가(#505).
##
## `interactable.gd`는 E를 누를 때마다 `request_notice`를 부르고(되풀이 조사는
## 의도된 동작이다, #301) 대기열은 받은 것을 그대로 쌓았다 — E를 세 번 누르면
## 같은 문장이 세 번 떴다. **대기열 길이로 본다**: 첫 줄은 곧바로 꺼내 찍히므로
## 같은 줄 셋을 넣으면 대기열이 비어 있어야 하고, 다른 줄 둘을 넣으면 둘이 남는다.
## 표시 횟수를 시그널로 세면 안 된다 — `request_speech`는 방출이라 한 프레임에
## 다 잡힌다(#454).
func _check_subtitle_queue() -> void:
	var packed: PackedScene = load(MAIN)
	var main: Node = packed.instantiate()
	root.add_child(main)
	for i in 8:
		await process_frame
	var gs: Node = get_first_node_in_group("game_state")
	var hud: Node = get_first_node_in_group("hud")
	if gs == null or hud == null:
		_fault("자막: game_state 또는 hud를 못 찾았다")
		main.free()
		await process_frame
		return
	if not hud.has_method("is_speaking"):
		_fault("자막: hud.is_speaking()이 없다")
	# 시작 안내(`START_HINT`)가 흐르는 중이다 — 비워진 뒤에 검사한다.
	await hud.call("await_speech_drained")
	await _wait(0.3)

	for i in 3:
		gs.call("request_notice", "스모크 중복 검사 줄.")
	await process_frame
	var queue: Array = hud.get("_speech_queue")
	if queue.size() != 0:
		_fault("자막: 같은 줄 셋을 넣었는데 대기열에 %d줄 남았다(중복)" % queue.size())
	else:
		_ok("자막 중복 억제")

	for t in ["스모크 줄 A.", "스모크 줄 B."]:
		gs.call("request_notice", t)
	await process_frame
	queue = hud.get("_speech_queue")
	if queue.size() != 2:
		_fault("자막: 서로 다른 줄 둘이 대기열에 안 들어갔다(%d줄)" % queue.size())
	else:
		_ok("자막 대기열 서로 다른 줄 유지")
	main.free()
	await process_frame


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
	var grace_base: float = float(consts.get("GRACE_SECONDS", 44.0))
	if gs == null or need.is_empty():
		_fault("도입부 3막: game_state(%s) 또는 창문 요구 아이템(%s)을 못 찾았다"
			% [gs, need])
	elif bool(gs.call("has_item", need)):
		_fault("도입부 3막: 스모크가 %s를 이미 들고 있어 책 없는 경로를 못 본다" % need)
	else:
		# **유예는 책 유무로 가르지 않는다**(#506) — 읽는 시간이 걷는 시간보다 크고,
		# 그 방향이 걷는 거리와 반대다(근거는 `GRACE_SECONDS` 주석). 상수와 같은지만 본다.
		if absf(grace_at_start - grace_base) > 1.0:
			_fault("도입부 3막: 유예가 상수와 다르다 (%.1f초, 상수 %.1f초)"
				% [grace_at_start, grace_base])
		else:
			_ok("도입부 3막 유예 %.1f초" % grace_at_start)
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

	# ── 창문 컷신에서 걷기 그림이 굴러가는지(#594) ────────────────
	# 컷신은 조작을 끊으려고 `set_physics_process(false)`를 거는데, 걷기 프레임을
	# 정하는 `_update_sprite()`가 그 안에서만 불린다 — 그래서 위치만 옮기던
	# 시절에는 이설이 **대기 포즈로 미끄러졌다**. 연출용 이동 API를 직접 굴려
	# 프레임이 실제로 넘어가는지 본다(컷신 전체를 돌리면 20초가 넘는다).
	var spr: Sprite2D = null
	var prompt: CanvasItem = null
	if player != null:
		spr = player.get_node_or_null("Visuals/Anchor/Body") as Sprite2D
		prompt = player.get_node_or_null("Visuals/Anchor/InteractPrompt") as CanvasItem
	if player == null or spr == null or not player.has_method("scripted_step"):
		_fault("컷신 걷기: 연출용 이동 API(scripted_step)나 스프라이트가 없다")
	else:
		var pmap: Dictionary = player.get_script().get_script_constant_map()
		var backs: Array = pmap.get("BACK_TEXTURES", [])
		player.call("begin_scripted_motion")
		await process_frame
		if player.is_physics_processing():
			_fault("컷신 걷기: 연출 이동에 들어갔는데 조작이 살아 있다")
		if prompt != null and prompt.visible:
			_fault("컷신 걷기: 컷신 동안 머리 위 [E] 프롬프트가 남았다")
		# 창문은 위쪽 외벽이다 — 위로 걸으면 뒷모습 네 장이 돌아야 한다.
		var from: Vector2 = player.get("global_position")
		var seen := {}
		var wrong := 0
		for i in 40:
			player.call("scripted_step", from + Vector2(0.0, -float(i) * 5.3),
				Vector2.UP, 320.0 / 60.0)
			seen[spr.texture] = true
			if not backs.has(spr.texture):
				wrong += 1
		if seen.size() < 2:
			_fault("컷신 걷기: 연출 이동인데 그림이 %d장뿐이다 — 대기 포즈로 미끄러진다"
				% seen.size())
		elif wrong > 0:
			_fault("컷신 걷기: 위로 걷는데 뒷모습이 아닌 프레임이 %d번 나왔다" % wrong)
		else:
			_ok("컷신 걷기 프레임 %d장 순환" % seen.size())
		player.call("end_scripted_motion")
		await process_frame
		if spr.texture != pmap.get("IDLE_TEXTURE"):
			_fault("컷신 걷기: 끝났는데 대기 포즈로 안 돌아왔다")
		elif not player.is_physics_processing():
			_fault("컷신 걷기: 끝났는데 조작이 안 돌아왔다")
		else:
			_ok("컷신 걷기 뒤 대기 포즈·조작 복귀")

	# ── 창문 컷신이 대사 끝에 맞춰 넘어가는지(#618) ───────────────
	# 예전에는 줄당 2.6초를 **고정으로** 기다려, 자막이 빨라진 뒤(#514·#563·#569)
	# 마지막 줄이 사라지고도 6초를 빈 화면으로 기다렸다. 반대로 짧으면 대사를
	# 자르고 페이드한다. 자막 대기열이 빈 순간과 층 전환이 시작된 순간을 잰다.
	var hud: Node = get_first_node_in_group("hud")
	if win == null or hud == null or player == null:
		_fault("창문 컷신: 창문(%s)·HUD(%s)·플레이어(%s)를 못 찾았다" % [win, hud, player])
	else:
		# 앞 단계의 자막(국어책 등)이 다 빠진 뒤에 시작해야 창문 대사만 잰다.
		await _until(func() -> bool: return not bool(hud.get("_draining")), 20.0)
		win.call("interact", player)
		var t0 := Time.get_ticks_msec()
		var drained_at := -1
		var travel_at := -1
		var draining_at_travel := false
		# 대사는 카메라 이동·창틀까지 걷기가 끝난 뒤에 나온다 — 그 전의 "빈 대기열"을
		# 끝으로 세면 안 되므로 한 번 배출이 시작된 뒤부터 본다.
		var saw_draining := false
		while Time.get_ticks_msec() - t0 < 40000:
			await process_frame
			var now := Time.get_ticks_msec()
			var draining := bool(hud.get("_draining"))
			if draining:
				saw_draining = true
			elif saw_draining and drained_at < 0:
				drained_at = now
			if bool(main.get("changing_floor")):
				travel_at = now
				draining_at_travel = bool(hud.get("_draining"))
				break
		if travel_at < 0:
			_fault("창문 컷신: 40초가 지나도 층 전환이 시작되지 않는다")
		elif draining_at_travel or drained_at < 0:
			_fault("창문 컷신: 대사가 다 나오기 전에 층을 넘긴다 (%.1f초)"
				% ((travel_at - t0) / 1000.0))
		elif travel_at - drained_at > 1000:
			_fault("창문 컷신: 대사가 끝나고 %.1f초를 빈 화면으로 기다린다"
				% ((travel_at - drained_at) / 1000.0))
		else:
			_ok("창문 컷신: 대사 끝 %.2f초 뒤 전환 (전체 %.1f초)"
				% [(travel_at - drained_at) / 1000.0, (travel_at - t0) / 1000.0])

	main.free()
	await process_frame


## 잉크통(#169)이 실제로 수위를 맞히는가(#600).
##
## **정적 검사로는 절대 못 잡는 유형이다.** 물리 레이의 의미(`hit_from_inside`가
## 기본 false라 출발점을 품은 충돌체는 보고되지 않는다)와 던지는 방향이 얽힌
## 문제라, 프레임을 돌려 실제로 던져 봐야 드러난다. 실제로 이 셋 다 게임에
## 들어간 채로 남아 있었다(#600) — 던지면 거의 늘 "빗나갔다"였다.
##
## 수위를 미리 **잉크에 멀게 해 세워 둔다**(`blind_timer = 3.0`). 그러면
## `_physics_process`가 곧바로 돌아 나가 추격·접촉 판정이 아예 안 돌므로,
## 검사 도중에 이설을 붙잡아 게임 오버 씬으로 넘어가는 일이 없다. 맞으면
## `blind()`가 `maxf`로 5초를 새로 얹으므로 4.5초를 넘는지로 가른다.
func _check_ink_throw() -> void:
	var packed: PackedScene = load(MAIN)
	if packed == null:
		_fault("잉크: main 씬을 못 읽었다")
		return
	var main: Node = packed.instantiate()
	root.add_child(main)
	for _i in 8:
		await process_frame

	# 수위는 4층(도입부)에서 활동하지 않는다(JANITOR_FREE_FLOOR) — 3층으로 내린다.
	main.call("travel_to", 3)
	if not await _until(func() -> bool:
			return not bool(main.get("changing_floor")), 6.0):
		_fault("잉크: 3층 전환이 끝나지 않는다")
		main.free()
		return

	var player := main.get_node_or_null("Player") as Node2D
	var janitor := main.get_node_or_null("Janitor") as Node2D
	if player == null or janitor == null:
		_fault("잉크: Player 또는 Janitor가 없다")
		main.free()
		return
	if not janitor.is_physics_processing():
		_fault("잉크: 3층인데 수위가 활동 상태가 아니다")
		main.free()
		return

	# ① 수위를 **등지고** 던져도 맞는다(자동 조준). 예전에는 바라보는 방향으로만
	#    날아가서, 도망치면서 던지면 캔이 수위 반대편으로 갔다.
	if await _throw_ink(main, player, janitor, 200.0, Vector2.LEFT):
		_ok("잉크 자동 조준(등지고 200px)")
	else:
		_fault("잉크: 수위를 등지고 던졌는데 안 맞았다(자동 조준)")

	# ② 코앞에서도 통과하지 않는다. 캔이 수위 충돌체 **안에서** 출발하는 거리다.
	if await _throw_ink(main, player, janitor, 28.0, Vector2.RIGHT):
		_ok("잉크 근접 피격(28px)")
	else:
		_fault("잉크: 코앞(28px)에서 던졌는데 몸을 통과했다")

	main.free()
	await process_frame


## 수위를 이설 오른쪽 `gap`px에 세우고 `facing` 방향으로 잉크통을 던진다.
## 캔은 플레이어가 던질 때와 같은 부모(조립 씬)에, 같은 스폰 거리(24px)로 낸다.
func _throw_ink(main: Node, player: Node2D, janitor: Node2D,
		gap: float, facing: Vector2) -> bool:
	janitor.set("blind_timer", 3.0)
	janitor.global_position = player.global_position + Vector2(gap, 0.0)
	await process_frame

	var packed: PackedScene = load(INK)
	if packed == null:
		_fault("잉크: 잉크통 씬을 못 읽었다")
		return false
	var can: Node2D = packed.instantiate()
	main.add_child(can)
	can.call("launch", player.global_position + facing * 24.0, facing)

	var hit := await _until(func() -> bool:
		return float(janitor.get("blind_timer")) > 4.5, 2.0)
	if is_instance_valid(can):
		can.free()
	janitor.set("blind_timer", 0.0)
	return hit
