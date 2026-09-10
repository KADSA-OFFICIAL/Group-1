extends Sprite2D

## 벽 페이드 마스크 (#117)
## 가운데가 투명하고 바깥이 검은 방사형 그라디언트를 플레이어 위치에 따라다니게 해,
## 일정 거리 밖의 벽(WallGlow 레이어)과 원경을 어둠으로 가린다. 벽 가시성을 손전등
## 시야 반경과 하나로 묶어, 어둠 속에서도 "가까운 벽만" 보이게 한다.
## WallFade(follow_viewport CanvasLayer, layer 1)의 자식으로, 벽 레이어 위·HUD 아래에 그려진다.

@onready var _player: Node2D = get_node_or_null("../../Player")

func _process(_delta: float) -> void:
	if _player == null:
		return
	# 몸이 아니라 **그림과 같은 자리**를 따라간다(#597). 몸은 physics tick(60Hz)마다
	# 계단처럼 움직이는데 카메라는 그린 프레임마다 매끈하게 따라가므로, 몸을 따라가면
	# 60Hz 초과 모니터에서 시야 원만 인물과 따로 떨린다.
	var at: Vector2 = _player.global_position
	if _player.has_method("visual_position"):
		at = _player.call("visual_position")
	global_position = at
