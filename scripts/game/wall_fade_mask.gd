extends Sprite2D

## 벽 페이드 마스크 (#117)
## 가운데가 투명하고 바깥이 검은 방사형 그라디언트를 플레이어 위치에 따라다니게 해,
## 일정 거리 밖의 벽(WallGlow 레이어)과 원경을 어둠으로 가린다. 벽 가시성을 손전등
## 시야 반경과 하나로 묶어, 어둠 속에서도 "가까운 벽만" 보이게 한다.
## WallFade(follow_viewport CanvasLayer, layer 1)의 자식으로, 벽 레이어 위·HUD 아래에 그려진다.

@onready var _player: Node2D = get_node_or_null("../../Player")

func _process(_delta: float) -> void:
	if _player:
		global_position = _player.global_position
