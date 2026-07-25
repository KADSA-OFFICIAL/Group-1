extends CharacterBody2D

@export var speed: float = 320.0

## 은신(#6): 숨은 동안 이동이 잠기고 수위아저씨가 발각하지 않는다.
## 빛을 완전히 끄면 수위가 지나가는지 볼 수 없어 나올 시점을 판단할 근거가
## 사라진다. 발각 판정은 빛과 무관하므로 끄지 않고 어둡게만 낮춘다.
const HIDDEN_LIGHT_ENERGY := 0.5
const HIDDEN_PROMPT := "나오기"

@onready var body: Polygon2D = $Body
@onready var interaction_area: Area2D = $InteractionArea
@onready var interact_prompt: Label = $InteractPrompt
@onready var player_light: PointLight2D = $PlayerLight

var facing_direction: Vector2 = Vector2.DOWN
var hidden: bool = false
var _light_energy: float = 1.0


func _ready() -> void:
	_light_energy = player_light.energy


## 은신처(hiding_spot.gd)가 숨길 때, 플레이어가 E로 나올 때 호출된다.
func set_hidden(value: bool) -> void:
	if hidden == value:
		return

	hidden = value
	velocity = Vector2.ZERO
	body.visible = not hidden
	player_light.energy = HIDDEN_LIGHT_ENERGY if hidden else _light_energy


func _physics_process(_delta: float) -> void:
	if hidden:
		# 숨은 자리에 고정. 프롬프트만 갱신해 "나오기" 안내를 유지한다.
		velocity = Vector2.ZERO
		_update_interact_prompt()
		return

	var direction := Input.get_vector("move_left", "move_right", "move_up", "move_down")

	if direction != Vector2.ZERO:
		facing_direction = direction.normalized()
		body.rotation = facing_direction.angle() - Vector2.UP.angle()

	velocity = direction * speed
	move_and_slide()

	interaction_area.position = facing_direction * 22.0
	_update_interact_prompt()


func _unhandled_input(event: InputEvent) -> void:
	if not event.is_action_pressed("interact"):
		return

	# 숨은 동안 E는 항상 "나오기". 상호작용 영역이 은신처에서 어긋나 있어도
	# 나올 수 있어야 한다(갇힘 방지).
	if hidden:
		set_hidden(false)
		get_viewport().set_input_as_handled()
		return

	var target := _find_interactable()
	if target != null:
		target.call("interact", self)
		get_viewport().set_input_as_handled()


func _find_interactable() -> Area2D:
	for area in interaction_area.get_overlapping_areas():
		if area.has_method("interact"):
			return area
	return null


func _update_interact_prompt() -> void:
	if hidden:
		interact_prompt.text = "[E] " + HIDDEN_PROMPT
		interact_prompt.visible = true
		return

	var target := _find_interactable()

	if target == null:
		interact_prompt.visible = false
		return

	var action_text := "상호작용"
	var custom_text = target.get("prompt_text")
	if custom_text is String and not custom_text.is_empty():
		action_text = custom_text

	interact_prompt.text = "[E] " + action_text
	interact_prompt.visible = true
