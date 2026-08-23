extends Area2D
## 방 창문 달빛(#274)을 **볼 수 있을 때만** 켠다(#292).
##
## Godot 2D에는 시야 판정이 없다 — 광원이 켜져 있으면 그 자리가 화면에 그려지고,
## 플레이어가 복도에 있든 방 안에 있든 똑같이 보인다. 달빛을 늘 켜 뒀더니
## **닫힌 문 너머 교실 내부가 다 보였다.** 벽 차단체(`LO_`)와 문짝 차단체(#256)는
## 빛이 방 **밖으로 새는 것**만 막는다 — 방 안이 화면에 그려지는 것은 못 막는다.
##
## 두 가지로 켠다.
##   * **문이 열려 있다** — `sliding_door.gd`가 `hold()`/`release()`로 알린다.
##   * **플레이어가 방 안에 있다** — 이 Area2D가 직접 감지한다.
## 문만 보면 들어와서 문을 닫았을 때 캄캄해지고, 방만 보면 열린 문으로
## 들여다볼 때 달빛이 안 보인다. 둘 다 있어야 앞뒤가 맞는다.
##
## **안 보이는 Area2D도 몸을 감지한다** — `visible`은 그리기만 끄고 물리는
## 그대로다. 그래서 광원 묶음 자체를 Area2D로 두고 `visible`로 껐다 켠다.

## 문이 열어 둔 횟수. 한 방에 문이 여럿일 수 있어 셈으로 둔다.
var _holders: int = 0
## 방 안에 있는 플레이어 수(0 또는 1).
var _inside: int = 0


func _ready() -> void:
	visible = false
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)


## 문이 열렸다. sliding_door.gd가 부른다.
func hold() -> void:
	_holders += 1
	_apply()


## 문이 닫혔다.
func release() -> void:
	_holders = maxi(0, _holders - 1)
	_apply()


## 방 안에 있는 것이 **플레이어**인가.
##
## `collision_mask = 1`은 벽(`RoomWalls`)·집기(`PropBodies`)·문짝(`SDPanel`)
## StaticBody2D까지 전부 잡는다. 그것들이 방 안에 있으므로 그냥 세면 방이
## 늘 켜져 있다 — #234에서 미닫이문이 영구 개방됐던 것과 같은 함정이다.
## 움직이는 몸(CharacterBody2D)만 센다.
##
## 수위는 뺀다. 그가 들어왔다고 방이 밝아지면 안 보이는 곳에 있는 위치가
## 새어 나간다. 수위가 문을 열고 들어가면 문 쪽 조건으로 어차피 켜진다.
func _is_player(body: Node2D) -> bool:
	return body is CharacterBody2D and not body.is_in_group("janitor")


func _on_body_entered(body: Node2D) -> void:
	if not _is_player(body):
		return
	_inside += 1
	_apply()


func _on_body_exited(body: Node2D) -> void:
	if not _is_player(body):
		return
	_inside = maxi(0, _inside - 1)
	_apply()


func _apply() -> void:
	visible = _holders > 0 or _inside > 0
