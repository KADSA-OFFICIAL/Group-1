extends Node

## 시작할 때 창을 macOS의 좌표 배율에 맞춘다(#679). autoload로 둔다 — 첫 씬이
## 뜨기 전에 한 번만 돌아야 하고, 타이틀로 돌아올 때마다 다시 돌면 플레이어가
## 늘린 창을 도로 줄인다.
##
## `window/size/viewport_width/height`(1600x900)는 Godot의 **픽셀**이다. 그런데
## macOS에서 Godot은 데스크톱 전체를 `screen_get_max_scale()`배로 잡는다 — 배율
## 2인 화면(Retina·Sidecar)이 **하나라도** 붙어 있으면 1pt가 2px이다. 그래서
## 그 화면이 아니라 **배율 1인 모니터에서도** 창이 800x450pt로 뜬다.
## 실측: 1920x1080 모니터(배율 1) + Sidecar(배율 2)에서 내보낸 앱 창이 모니터에
## 800x450pt로 떴다. 화면별 `screen_get_scale()`은 그 모니터를 1.0으로 돌려주므로
## 그것을 기준으로 삼으면 이 경우를 놓친다.
##
## Windows는 `screen_get_max_scale()`이 1이라(macOS만 구현) 아무것도 안 한다 —
## 분기를 OS 이름으로 걸지 않고 배율로 건다.
##
## 창이 커지면 렌더 해상도도 커진다(`stretch/mode = canvas_items`). 논리 화면은
## 1600x900 그대로라 HUD·카메라 좌표는 안 바뀐다.

## 쓸 수 있는 화면 영역 중 창이 차지할 최대 비율. 화면을 꽉 채우면 메뉴 막대·Dock과
## 붙어 창 테두리를 잡을 곳이 없다.
const SCREEN_FILL := 0.85


func _ready() -> void:
	# 헤드리스(CI·스모크)에는 창이 없다.
	if DisplayServer.get_name() == "headless":
		return
	# 전체 화면으로 시작하면 맞출 것이 없다.
	if DisplayServer.window_get_mode() != DisplayServer.WINDOW_MODE_WINDOWED:
		return

	var scale := DisplayServer.screen_get_max_scale()
	if scale <= 1.0:
		return

	var screen := DisplayServer.window_get_current_screen()
	var base := Vector2(
		ProjectSettings.get_setting("display/window/size/viewport_width"),
		ProjectSettings.get_setting("display/window/size/viewport_height"))
	# 사용 영역도 같은 Godot 픽셀이다(pt x 배율).
	var usable := DisplayServer.screen_get_usable_rect(screen)
	var want := base * scale
	# 화면보다 크면 16:9를 지킨 채 줄인다 — 맥북 화면(1470~1512pt)은 전부 여기 걸린다.
	var fit := minf(1.0, minf(
		usable.size.x * SCREEN_FILL / want.x,
		usable.size.y * SCREEN_FILL / want.y))
	var size := Vector2i((want * fit).floor())

	DisplayServer.window_set_size(size)
	DisplayServer.window_set_position(usable.position + (usable.size - size) / 2)
