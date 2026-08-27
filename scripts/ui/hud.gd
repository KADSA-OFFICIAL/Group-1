extends CanvasLayer

## 자막이 다 찍힌 뒤 더 남겨 두는 시간(초). 실제 표시 시간은 타이핑 시간 + 이 값이라,
## 긴 조사 서술도 끝까지 읽을 수 있다(#193).
##
## **3.0에서 줄였다**(#514). 여러 줄이 연달아 들어오면 뒤 줄이 한참 뒤에 떠서
## 이미 지나간 일을 말했다 — 수위 자백 네 줄(41자 기준)이 19.7초였다(실측).
## 40자 한 줄이 타이핑 2.0초 + 이 값이라, 2.4면 마지막 줄이 4.4초는 화면에 남는다.
@export var notice_seconds: float = 2.4
## 뒤에 대기 중인 줄이 있을 때 주는 짧은 읽는 시간(초).
## 이어 말하는 중이라 짧다 — 매 줄 `notice_seconds`씩 쉬면 대화가 아니라 안내문이 된다.
@export var queued_notice_seconds: float = 1.0

## 인벤토리 슬롯에 조작 키를 덧붙일 아이템(#169).
const USABLE_ITEM_KEYS := {
	"ink_can": "[Q] 던지기",
}

@onready var objective_label: Label = $Root/TopRight/Margin/TextRows/ObjectiveLabel
@onready var inventory_label: Label = $Root/TopRight/Margin/TextRows/InventoryLabel
## 엔딩 조건 현황 레이블(#540, #545)
@onready var true_ending_label: Label = $Root/TopLeft/Margin/TextRows/TrueEndingLabel
@onready var report_ending_label: Label = $Root/TopLeft/Margin/TextRows/ReportEndingLabel
@onready var basic_ending_label: Label = $Root/TopLeft/Margin/TextRows/BasicEndingLabel
## 하단 알림은 프롤로그·엔딩과 같은 자막 표시를 쓴다(#193).
@onready var subtitle: SubtitleDialogue = $Root/Subtitle
@onready var inventory_panel: PanelContainer = $Root/InventoryPanel
@onready var close_up: PanelContainer = $Root/CloseUp
@onready var waypoint: Control = $Root/Waypoint
@onready var close_up_image: TextureRect = $Root/CloseUp/Margin/Rows/Image
@onready var close_up_caption: Label = $Root/CloseUp/Margin/Rows/Caption
@onready var inventory_title: Label = $Root/InventoryPanel/Margin/Rows/InventoryTitle
@onready var slot_labels: Array[Label] = [
	$Root/InventoryPanel/Margin/Rows/Slots/Slot1/ItemLabel,
	$Root/InventoryPanel/Margin/Rows/Slots/Slot2/ItemLabel,
	$Root/InventoryPanel/Margin/Rows/Slots/Slot3/ItemLabel,
	$Root/InventoryPanel/Margin/Rows/Slots/Slot4/ItemLabel,
	$Root/InventoryPanel/Margin/Rows/Slots/Slot5/ItemLabel,
]

## 자막 대기열(#454). 대기열이 없으면 연달아 오는 대사가 서로를 **덮는다** —
## 이설이 2층 머리를 보고 말하는 도중 수위 혼잣말이 끼어들자 그 줄이 통째로
## 사라졌다. 온 순서대로 한 줄씩, 앞 줄이 끝난 뒤에 보여 준다.
var _speech_queue: Array[Array] = []
## 지금 찍히는 중(또는 읽는 시간 중)인 줄. 중복을 버리는 데 쓴다(#505).
## 빈 배열이면 아무것도 안 뜨고 있다.
var _current: Array = []
var _draining: bool = false
var current_items: Array[String] = []
var max_items: int = 5


## 층 씬 안의 노드가 HUD를 부를 수 있게 그룹에 든다(#451). 조립 씬 루트까지의
## 경로를 층 씬에서는 알 수 없다 — `floor_manager`·`game_state`와 같은 방식이다.
func _enter_tree() -> void:
	add_to_group("hud")


func _ready() -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")

	if game_state != null:
		if game_state.has_signal("notice_requested"):
			game_state.connect("notice_requested", Callable(self, "show_notice"))
		if game_state.has_signal("speech_requested"):
			game_state.connect("speech_requested", Callable(self, "show_speech"))
		if game_state.has_signal("inventory_changed"):
			game_state.connect("inventory_changed", Callable(self, "set_inventory"))
			game_state.connect("inventory_changed", Callable(self, "_on_inventory_or_flags_changed"))
		if game_state.has_signal("clues_changed"):
			game_state.connect("clues_changed", Callable(self, "_on_inventory_or_flags_changed"))
		if game_state.has_signal("flags_changed"):
			game_state.connect("flags_changed", Callable(self, "_on_inventory_or_flags_changed"))
		var limit = game_state.get("max_items")
		if limit != null:
			max_items = limit

	set_inventory([])
	subtitle.clear()
	inventory_panel.visible = false
	_update_endings_ui()


func _on_inventory_or_flags_changed(_arg = null, _arg2 = null) -> void:
	_update_endings_ui()


func _unhandled_input(event: InputEvent) -> void:
	if not event.is_action_pressed("inventory"):
		return

	inventory_panel.visible = not inventory_panel.visible
	get_viewport().set_input_as_handled()


func set_objective(text: String) -> void:
	objective_label.text = text


func set_clues(_found: int, _total: int) -> void:
	pass


## 각 엔딩 조건 및 층별 진행도 실시간 갱신(#540, #545)
func _update_endings_ui() -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state == null:
		return

	# 1. 진엔딩 (쉬는 시간, 총 6개)
	if is_instance_valid(true_ending_label) and game_state.has_method("get_true_ending_stats"):
		var te: Dictionary = game_state.call("get_true_ending_stats")
		var f4: Array = te.by_floor.get(4, [0, 2])
		var f3: Array = te.by_floor.get(3, [0, 2])
		var f2: Array = te.by_floor.get(2, [0, 1])
		var f1: Array = te.by_floor.get(1, [0, 1])
		if te.found >= te.total:
			true_ending_label.text = "진엔딩: %d/%d (조건 달성! 현관 탈출)" % [te.found, te.total]
		else:
			true_ending_label.text = "진엔딩: %d/%d (4층:%d/%d, 3층:%d/%d, 2층:%d/%d, 1층:%d/%d)" % [
				te.found, te.total, f4[0], f4[1], f3[0], f3[1], f2[0], f2[1], f1[0], f1[1]
			]

	# 2. 엔딩 2 (어른들의 일 / 신고, 총 3개 중 1개 이상)
	if is_instance_valid(report_ending_label) and game_state.has_method("get_report_ending_stats"):
		var re: Dictionary = game_state.call("get_report_ending_stats")
		var f2: Array = re.by_floor.get(2, [0, 1])
		var f1: Array = re.by_floor.get(1, [0, 2])
		if re.found >= 1:
			report_ending_label.text = "엔딩 2: %d/%d (신고 가능! 2층:%d/%d, 1층:%d/%d)" % [
				re.found, re.total, f2[0], f2[1], f1[0], f1[1]
			]
		else:
			report_ending_label.text = "엔딩 2: %d/%d (2층:%d/%d, 1층:%d/%d) [1개+ 필요]" % [
				re.found, re.total, f2[0], f2[1], f1[0], f1[1]
			]

	# 3. 엔딩 1 (방과 후 / 기본 탈출)
	if is_instance_valid(basic_ending_label):
		var has_gate_key: bool = game_state.call("has_item", "front_gate_key") if game_state.has_method("has_item") else false
		if has_gate_key:
			basic_ending_label.text = "엔딩 1: 1층 열쇠 (보유)"
		else:
			basic_ending_label.text = "엔딩 1: 1층 열쇠"


func set_inventory(items: Array[String]) -> void:
	current_items = items.duplicate()
	_refresh_inventory_panel()

	if items.is_empty():
		inventory_label.text = "소지품: 없음"
		return

	var display_names := PackedStringArray()
	for item_id in items:
		display_names.append(_get_item_display_name(item_id))

	inventory_label.text = "소지품: " + ", ".join(display_names)


func _refresh_inventory_panel() -> void:
	inventory_title.text = "소지품 (%d/%d)" % [current_items.size(), max_items]

	# 슬롯에 아이템 이름 표시 (아이템 이미지는 추후 교체 예정)
	# 쓸 수 있는 아이템은 조작 키를 같이 적는다 — 획득 시 안내는 3초 뒤 사라지지만
	# 정작 필요한 순간은 한참 뒤라, R로 다시 확인할 수 있어야 한다(#169).
	for i in slot_labels.size():
		if i >= current_items.size():
			slot_labels[i].text = ""
			continue

		var item_id := current_items[i]
		var label := _get_item_display_name(item_id)
		if item_id in USABLE_ITEM_KEYS:
			label += "\n" + USABLE_ITEM_KEYS[item_id]
		slot_labels[i].text = label


## 지문·서술. 화자가 없으므로 프롤로그의 독백 배치로 나온다.
func show_notice(text: String) -> void:
	_show_subtitle("", text, "")


## 화자가 있는 대사(수위 등). 이름 줄이 붙고 본문이 크고 밝게 나온다.
func show_speech(speaker: String, text: String, emotion: String = "") -> void:
	_show_subtitle(speaker, text, emotion)


## **대기열이 통째로 빌 때까지** 기다린다(#471).
##
## `await_subtitle()`은 지금 찍히는 한 줄만 본다. 장면 연출(`art_room_intro.gd`)은
## 고정 시간으로 대사를 흘리는데 그 시간이 실제 표시 시간과 맞지 않으면 **장면이
## 대사를 앞질러 간다** — 수위가 자백을 다 하기도 전에 걸어 나가고, 다음 막의
## 유예가 자백이 아직 떠 있는 채로 돌기 시작했다. 막 경계에서 이걸 부른다.
func await_speech_drained() -> void:
	while _draining:
		if get_tree() == null:
			return
		await get_tree().process_frame


## 지금 찍히는 중인 자막이 끝날 때까지 기다린다. 이미 끝났으면 바로 돌아온다.
## 붙잡힘 연출이 대사를 자르지 않도록 floor_manager가 쓴다(#199).
func await_subtitle() -> void:
	if is_instance_valid(subtitle) and subtitle.typing:
		await subtitle.typing_finished


## **같은 줄이 겹치면 버린다**(#505). `interactable.gd`는 E를 누를 때마다
## `request_notice`를 부르고(되풀이 조사는 의도된 동작이다, #301) 대기열은 받은 것을
## 그대로 쌓았다 — 그래서 E를 세 번 누르면 같은 문장이 세 번 떴고, 뒤에 줄이 있으면
## 읽는 시간이 1.4초로 짧아져 깜빡이는 것처럼 보였다. 그 사이 다른 대사(수위 혼잣말·
## 발소리)가 뒤로 밀리고, 유예가 도는 구간에서는 밀린 시간이 그대로 손해다.
##
## **자막이 끝난 뒤 다시 조사하면 다시 나온다** — 지금 떠 있는 줄과 대기열만 본다.
func _show_subtitle(speaker: String, text: String, emotion: String) -> void:
	var line_now: Array = [speaker, text, emotion]
	if _same_line(_current, line_now):
		return
	for queued: Array in _speech_queue:
		if _same_line(queued, line_now):
			return
	_speech_queue.append(line_now)
	if _draining:
		return

	_draining = true
	while not _speech_queue.is_empty() and is_instance_valid(subtitle):
		var line: Array = _speech_queue.pop_front()
		_current = line
		# 뒤에 줄이 더 있으면 더 빨리 찍는다(#563) — 밀려 있는 만큼 서두른다.
		# 혼자 뜨는 대사는 평소 배속 그대로다.
		subtitle.show_line(line[0], line[1], line[2], not _speech_queue.is_empty())

		# 컷신과 달리 본편에는 넘기는 입력이 없다 — 다 찍힐 때까지 기다린 뒤
		# 읽는 시간을 준다. 뒤에 줄이 더 있으면 짧게 준다: 한 사람이 이어서
		# 말하는데 매 줄 3초씩 쉬면 대화가 아니라 안내문이 된다.
		var hold := notice_seconds if _speech_queue.is_empty() else queued_notice_seconds
		await get_tree().create_timer(subtitle.last_typing_seconds + hold).timeout

	# 기다리는 사이 씬이 바뀌었을 수 있다(체포·탈출).
	if is_instance_valid(subtitle):
		subtitle.clear()
	_current = []
	_draining = false


## 화자와 본문이 같으면 같은 줄로 본다(#505). 감정은 보지 않는다 — 같은 문장을
## 다른 감정으로 연달아 내보내는 자리가 없고, 있어도 두 번 읽힐 이유가 없다.
func _same_line(a: Array, b: Array) -> bool:
	return a.size() >= 2 and b.size() >= 2 and a[0] == b[0] and a[1] == b[1]


## 지금 자막이 떠 있는가. 연출이 대사를 앞지르지 않게 보는 곳이 쓴다.
func is_speaking() -> bool:
	return _draining


func _get_item_display_name(item_id: String) -> String:
	if item_id.begins_with("stair_key_"):
		return item_id.trim_prefix("stair_key_") + "층 계단 열쇠"

	match item_id:
		"korean_book":
			return "국어책"
		"front_gate_key":
			return "현관 열쇠"
		"ink_can":
			return "잉크통"
		_:
			return item_id


## 화면 왼쪽 위 클로즈업(#451) — 가까이 가야 보이는 것을 크게 보여 준다.
##
## 맵 위 그림은 위에서 내려다본 것이라 **무엇인지까지는 말하지 못한다.** 2층
## 창고의 머리가 그렇다 — 위에서 보면 검은 덩어리와 피지만, 정면에서는 눈구멍에
## 열쇠가 박힌 것이 보인다. 두 그림을 자리로 나눠 둘 다 쓴다.
##
## 목표·소지품 패널(`TopLeft`) **아래**에 둔다. 겹치면 목표 글이 가려진다.
func show_close_up(texture: Texture2D, caption: String = "") -> void:
	if texture == null:
		return
	close_up_image.texture = texture
	close_up_caption.text = caption
	close_up_caption.visible = not caption.is_empty()
	close_up.visible = true


## 월드의 한 곳을 화면에서 가리킨다(#478). 도입부에서 숨을 캐비넷을 알려 준다.
func show_waypoint(world_position: Vector2, text: String = "") -> void:
	if is_instance_valid(waypoint):
		waypoint.call("show_at", world_position, text)


func hide_waypoint() -> void:
	if is_instance_valid(waypoint):
		waypoint.call("clear")


func hide_close_up() -> void:
	close_up.visible = false
