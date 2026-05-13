extends CharacterBody2D

@export var speed: float = 160.0

@onready var body: Polygon2D = $Body
@onready var interaction_area: Area2D = $InteractionArea

var facing_direction: Vector2 = Vector2.DOWN


func _physics_process(_delta: float) -> void:
	var direction := Input.get_vector("move_left", "move_right", "move_up", "move_down")

	if direction != Vector2.ZERO:
		facing_direction = direction.normalized()
		body.rotation = facing_direction.angle() - Vector2.UP.angle()

	velocity = direction * speed
	move_and_slide()

	interaction_area.position = facing_direction * 22.0


func _unhandled_input(event: InputEvent) -> void:
	if not event.is_action_pressed("interact"):
		return

	for area in interaction_area.get_overlapping_areas():
		if area.has_method("interact"):
			area.call("interact", self)
			get_viewport().set_input_as_handled()
			return
