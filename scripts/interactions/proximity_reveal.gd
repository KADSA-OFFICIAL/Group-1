extends Area2D

## 가까이 가면 화면 왼쪽 위에 클로즈업을 띄운다(#451) — E를 누르지 않는다.
##
## 맵 위 그림은 위에서 내려다본 것이라 **무엇인지까지는 말하지 못한다.** 2층
## 창고의 머리가 그렇다: 위에서 보면 검은 덩어리와 피지만, 정면 그림에는
## 눈구멍에 열쇠가 박힌 것이 보인다. 같은 물건의 두 그림을 자리로 나눠 쓴다.
##
## **조사(`interactable.gd`)를 대신하지 않는다.** E는 그대로 문구를 띄우고
## 아이템을 준다 — 이쪽은 다가서기만 해도 보이는 것이다.

## 왼쪽 위에 띄울 그림.
@export var portrait: Texture2D
## 그림 아래 한 줄. 비우면 안 쓴다.
@export var caption: String = ""
## 들어섰을 때 **한 번만** 나오는 대사. 화자가 비면 지문으로 나간다.
@export var line_speaker: String = ""
@export_multiline var line_text: String = ""

var _said: bool = false
var _inside: int = 0


func _ready() -> void:
	body_entered.connect(_on_entered)
	body_exited.connect(_on_exited)


## **임자가 사라져도 클로즈업을 내려야 한다.** 2층 머리는 접촉 획득이라
## (`pickup_item.gd`) 열쇠를 집는 순간 `queue_free()`된다 — 이 노드가 자식이라
## 같이 죽고 `body_exited`가 영영 안 와서 그림이 화면에 붙박인다.
## 층을 옮길 때도 씬째 해제되므로 같은 처리가 맞다.
func _exit_tree() -> void:
	if _inside <= 0:
		return
	_inside = 0
	_hide()


## 플레이어인가. **`collision_mask = 1`은 벽·집기 StaticBody2D도 잡는다** —
## 그냥 세면 씬을 여는 순간 켜진 채가 된다(#234·#292와 같은 함정).
## 움직이는 몸만 세고 수위는 뺀다.
func _is_player(body: Node2D) -> bool:
	return body is CharacterBody2D and not body.is_in_group("janitor")


func _on_entered(body: Node2D) -> void:
	if not _is_player(body):
		return
	_inside += 1
	if _inside != 1:
		return
	var hud := get_tree().get_first_node_in_group("hud")
	if hud != null and hud.has_method("show_close_up"):
		hud.call("show_close_up", portrait, caption)
	if not _said and not line_text.is_empty():
		_said = true
		var gs := get_tree().get_first_node_in_group("game_state")
		if gs != null:
			if line_speaker.is_empty():
				gs.call("request_notice", line_text)
			else:
				gs.call("request_speech", line_speaker, line_text, "")


func _on_exited(body: Node2D) -> void:
	if not _is_player(body):
		return
	_inside = maxi(0, _inside - 1)
	if _inside > 0:
		return
	_hide()


func _hide() -> void:
	var tree := get_tree()
	if tree == null:
		return
	var hud := tree.get_first_node_in_group("hud")
	if hud != null and hud.has_method("hide_close_up"):
		hud.call("hide_close_up")
