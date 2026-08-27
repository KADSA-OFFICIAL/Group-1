extends Area2D

## 플레이어가 닿으면 자동으로 줍는 아이템.
## pickup_id를 지정하면 획득 상태가 게임 상태에 기록되어 씬을 다시 로드해도 재생성되지 않는다.

@export var item_id: String = ""
@export_multiline var message: String = "아이템을 주웠다."
@export var pickup_id: String = ""
## 주울 때 곁들여 세우는 플래그(#459). 물건을 얻는 것과 **무엇을 알게 되는가**는
## 다르다 — 2층 머리는 계단 열쇠를 주면서 조민혁을 찾은 것으로도 쳐 준다.
@export var grants_flag: String = ""
## 주운 뒤에도 **그림을 그 자리에 남길지**(#459). 기본은 지금까지대로 사라진다.
##
## 켜면 획득 판정만 끄고 노드는 남는다. 2층 머리가 그렇다: 문구가 "열쇠를 뽑아
## 냈다"인데 시신까지 증발하면 말과 화면이 어긋나고, 되돌아온 플레이어에게
## 창고가 아무 일 없던 방이 된다.
@export var keep_after_pickup: bool = false


func _ready() -> void:
	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null and not pickup_id.is_empty() and game_state.call("has_flag", pickup_id):
		# 이미 주웠다 — 남기기로 한 것은 그림만 두고 획득만 끈다.
		if keep_after_pickup:
			_disable_pickup()
			return
		queue_free()
		return

	body_entered.connect(_on_body_entered)


## 획득 판정을 끈다. **자식 Area2D는 건드리지 않는다** — 근접 클로즈업
## (`proximity_reveal.gd`)은 제 몫의 플래그로 따로 판단한다.
func _disable_pickup() -> void:
	# 신호 처리 도중에는 바로 못 끈다 — 물리 서버가 이 Area를 순회하는 중이다.
	set_deferred("monitoring", false)
	for c in get_children():
		if c is CollisionShape2D:
			(c as CollisionShape2D).set_deferred("disabled", true)


func _on_body_entered(body: Node) -> void:
	if not body is CharacterBody2D:
		return

	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null:
		if not item_id.is_empty() and not game_state.call("add_item", item_id):
			game_state.call("request_notice", "가방이 가득 차서 주울 수 없다.")
			Sfx.play(&"door_locked")
			return
		if not pickup_id.is_empty():
			game_state.call("set_flag", pickup_id)
		if not grants_flag.is_empty():
			game_state.call("set_flag", grants_flag)
		game_state.call("request_notice", message)
		Sfx.play(&"pickup")

	if keep_after_pickup:
		_disable_pickup()
		return
	queue_free()
