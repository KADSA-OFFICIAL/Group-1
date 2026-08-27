extends Area2D

## 계단이 아닌 곳에서 다른 층으로 넘어간다(#406) — 지금은 미술실 준비실 창문뿐이다.
##
## **`exit_door.gd`를 쓰지 않는 이유**: 저쪽은 탈출구라 엔딩 판정을 하고
## (`ending_kind`·`clue_score`를 `SceneTree` 메타에 싣고) 음악을 끄고 탈출음을
## 낸다. 도입부에서 3층으로 내려가는 것은 탈출이 아니라 **진행**이다.
##
## 층 전환은 `floor_manager.travel_to()`(#356)가 한다. 계단 트리거와 같은
## 페이드를 타므로 화면 전환이 계단과 똑같이 보인다.

## 이 아이템이 있어야 넘어갈 수 있다. 비우면 조건 없이 열린다.
@export var required_item_id: String = ""
@export_multiline var locked_message: String = "아직 갈 수 없다."
@export var prompt_text: String = "내려가기"
## 넘어가기 직전에 한 줄 띄운다. 층이 바뀌어도 HUD는 그대로라 알림이 살아남는다.
@export_multiline var message: String = ""
## 도착할 층. 음수면 아무것도 하지 않는다.
@export var target_floor: int = -1
## 도착 지점. `Vector2.INF`면 그 층의 기본 자리로 간다.
@export var arrive_at: Vector2 = Vector2.INF
## 겹쳤을 때 누가 이기는가(#301). 진행에 필요한 것이라 잠긴 문과 같은 20이다.
@export var interact_priority: int = 20

## ── 내려가는 컷신(#468) ────────────────────────────────────────────
## 비우면 컷신 없이 바로 넘어간다(계단과 같다).
##
## **왜 여기서, 페이드 전에 하는가.** 층 전환 페이드의 까만 화면 위에 대사를
## 흘릴 수 없다 — `main.tscn`에서 `HUD`와 `UI`가 둘 다 CanvasLayer **layer 3**인데
## `UI`가 뒤에 선언돼 위로 오므로, `FadeRect`가 알파 1이 되면 자막이 그 아래로
## 들어간다. 컷신 전용 씬도 못 쓴다 — `GameState`가 `main.tscn` 안에 있어서
## 씬을 떠났다 돌아오면 진행 상태가 초기화된다.
##
## 그래서 `art_room_intro.gd`의 문 클로즈업과 같은 방식을 쓴다.
@export var cutscene_speaker: String = ""
@export var cutscene_lines: PackedStringArray = PackedStringArray()
@export var cutscene_emotions: PackedStringArray = PackedStringArray()
## 컷신 동안 카메라가 바라볼 곳. `Vector2.INF`면 이 노드 자리를 본다.
@export var cutscene_look_at: Vector2 = Vector2.INF
@export var cutscene_zoom: float = 1.9
## 이설이 창틀 앞까지 걸어가는 데 걸리는 시간(초).
@export var cutscene_step_seconds: float = 0.9
## 대사 한 줄에 주는 시간. HUD 대기열(#454)이 줄 사이를 알아서 벌리므로
## 여기서는 **전체가 끝날 때까지** 기다릴 시간만 잡는다.
@export var cutscene_line_seconds: float = 2.6
## 창밖으로 사라지는 데 걸리는 시간(초).
@export var cutscene_vanish_seconds: float = 0.8

## 되돌릴 수 없는 행동이라 두 번 돌지 않게 한다.
var _played: bool = false


func interact(_player: Node) -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null and not required_item_id.is_empty() \
			and not game_state.call("has_item", required_item_id):
		game_state.call("request_notice", locked_message)
		Sfx.play(&"door_locked")
		return

	if target_floor < 0:
		return

	# 층 관리자는 조립 씬 루트에 있고 이 노드는 층 씬 안에 있다 — 경로를 알 수
	# 없으므로 그룹으로 찾는다(`exit_door.gd`와 같은 방식).
	var manager := get_tree().get_first_node_in_group("floor_manager")
	if manager == null or not manager.has_method("travel_to"):
		return

	if not cutscene_lines.is_empty():
		if _played:
			return
		_played = true
		await _play_cutscene(game_state)

	if game_state != null and not message.is_empty():
		game_state.call("request_notice", message)
	Sfx.play(&"stairs")
	manager.call("travel_to", target_floor, arrive_at)


## 창틀을 넘는 장면. 조작을 멈추고, 카메라를 창문에 붙이고, 이설을 창틀까지
## 걸린 뒤 창밖으로 사라지게 한다. 끝나면 부른 쪽이 층을 넘긴다.
func _play_cutscene(game_state) -> void:
	var player := get_tree().get_first_node_in_group("player") as Node2D
	var look: Vector2 = global_position if cutscene_look_at == Vector2.INF else cutscene_look_at

	# **플레이어 노드만 세운다.** `get_tree().paused`를 쓰면 아래 트윈도 같이 멈춘다
	# (`art_room_intro.gd`와 같은 이유).
	var cam: Camera2D = null
	if player != null:
		player.set("velocity", Vector2.ZERO)
		player.set_physics_process(false)
		player.set_process_unhandled_input(false)
		cam = player.get_node_or_null("Camera2D") as Camera2D

	if cam != null:
		var into := create_tween().set_parallel(true)
		into.tween_property(cam, "offset", look - player.global_position, 0.6) 			.set_trans(Tween.TRANS_SINE)
		into.tween_property(cam, "zoom", Vector2(cutscene_zoom, cutscene_zoom), 0.6) 			.set_trans(Tween.TRANS_SINE)
		await into.finished

	# 창틀 앞까지 걸어간다.
	if player != null:
		var step := create_tween()
		step.tween_property(player, "global_position", look,
			cutscene_step_seconds).set_trans(Tween.TRANS_SINE)
		await step.finished

	# 대사. 순서와 간격은 HUD 자막 대기열이 맡는다(#454).
	if game_state != null:
		for i in cutscene_lines.size():
			var emotion := cutscene_emotions[i] if i < cutscene_emotions.size() else ""
			if cutscene_speaker.is_empty():
				game_state.call("request_notice", cutscene_lines[i])
			else:
				game_state.call("request_speech", cutscene_speaker,
					cutscene_lines[i], emotion)

	# 창밖으로 사라진다. 그림은 `Visuals`(CanvasLayer 2)에 있어 부모를 흐려도
	# 안 따라오므로 그쪽을 직접 흐린다.
	var visuals := player.get_node_or_null("Visuals") as CanvasLayer if player != null else null
	if visuals != null:
		var body := visuals.get_node_or_null("Anchor") as CanvasItem
		if body != null:
			await create_tween().tween_property(body, "modulate:a", 0.0,
				cutscene_vanish_seconds).finished

	# 대사가 다 흐를 때까지 기다린 뒤 넘긴다.
	await get_tree().create_timer(
		cutscene_line_seconds * float(cutscene_lines.size())).timeout

	# 카메라와 그림을 되돌려 둔다 — 다음 층에 그대로 들고 간다.
	if cam != null:
		cam.offset = Vector2.ZERO
		cam.zoom = Vector2(1.25, 1.25)
	if visuals != null:
		var body2 := visuals.get_node_or_null("Anchor") as CanvasItem
		if body2 != null:
			body2.modulate.a = 1.0
	if player != null:
		player.set_physics_process(true)
		player.set_process_unhandled_input(true)
