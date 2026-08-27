extends CanvasLayer

## 자막이 다 찍힌 뒤 더 남겨 두는 시간(초). 실제 표시 시간은 타이핑 시간 + 이 값이라,
## 긴 조사 서술도 끝까지 읽을 수 있다(#193).
@export var notice_seconds: float = 3.0
## 뒤에 대기 중인 줄이 있을 때 주는 짧은 읽는 시간(초).
@export var queued_notice_seconds: float = 1.4

## 인벤토리 슬롯에 조작 키를 덧붙일 아이템(#169).
const USABLE_ITEM_KEYS := {
	"ink_can": "[Q] 던지기",
}

@onready var objective_label: Label = $Root/TopLeft/Margin/TextRows/ObjectiveLabel
@onready var inventory_label: Label = $Root/TopLeft/Margin/TextRows/InventoryLabel
## 하단 알림은 프롤로그·엔딩과 같은 자막 표시를 쓴다(#193).
@onready var subtitle: SubtitleDialogue = $Root/Subtitle
@onready var inventory_panel: PanelContainer = $Root/InventoryPanel
@onready var close_up: PanelContainer = $Root/CloseUp
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
		var limit = game_state.get("max_items")
		if limit != null:
			max_items = limit

	set_inventory([])
	subtitle.clear()
	inventory_panel.visible = false


func _unhandled_input(event: InputEvent) -> void:
	if not event.is_action_pressed("inventory"):
		return

	inventory_panel.visible = not inventory_panel.visible
	get_viewport().set_input_as_handled()


func set_objective(text: String) -> void:
	objective_label.text = text


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


## 지금 찍히는 중인 자막이 끝날 때까지 기다린다. 이미 끝났으면 바로 돌아온다.
## 붙잡힘 연출이 대사를 자르지 않도록 floor_manager가 쓴다(#199).
func await_subtitle() -> void:
	if is_instance_valid(subtitle) and subtitle.typing:
		await subtitle.typing_finished


func _show_subtitle(speaker: String, text: String, emotion: String) -> void:
	_speech_queue.append([speaker, text, emotion])
	if _draining:
		return

	_draining = true
	while not _speech_queue.is_empty() and is_instance_valid(subtitle):
		var line: Array = _speech_queue.pop_front()
		subtitle.show_line(line[0], line[1], line[2])

		# 컷신과 달리 본편에는 넘기는 입력이 없다 — 다 찍힐 때까지 기다린 뒤
		# 읽는 시간을 준다. 뒤에 줄이 더 있으면 짧게 준다: 한 사람이 이어서
		# 말하는데 매 줄 3초씩 쉬면 대화가 아니라 안내문이 된다.
		var hold := notice_seconds if _speech_queue.is_empty() else queued_notice_seconds
		await get_tree().create_timer(subtitle.last_typing_seconds + hold).timeout

	# 기다리는 사이 씬이 바뀌었을 수 있다(체포·탈출).
	if is_instance_valid(subtitle):
		subtitle.clear()
	_draining = false


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


func hide_close_up() -> void:
	close_up.visible = false
