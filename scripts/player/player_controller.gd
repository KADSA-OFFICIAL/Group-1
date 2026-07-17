extends CharacterBody2D

@export var speed: float = 320.0

@onready var body: Polygon2D = $Body
@onready var interaction_area: Area2D = $InteractionArea
@onready var interact_prompt: Label = $InteractPrompt

var facing_direction: Vector2 = Vector2.DOWN


func _physics_process(_delta: float) -> void:
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
