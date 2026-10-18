extends CanvasLayer

## 점프스케어(#662). 수위에게 붙잡혀 마지막 대사가 다 찍힌 뒤, 게임 오버 화면으로
## 넘어가기 직전에 `floor_manager._on_game_over()`가 `play()`를 부른다.
##
## 화면이 한순간에 검게 바뀌고 수위 얼굴이 가운데서 튀어나와 화면을 넘칠 만큼
## 커지며, 흔들리고, 붉게 번쩍인다. 끝나면 얼굴만 치우고 **검은 바탕은 남긴다** —
## 게임 오버 화면이 검은 데서 페이드 인하므로 그 사이가 컷으로 이어진다.
##
## 얼굴 그림은 `tools/gen_jumpscare_sprite.py`가 수위 정면 원본에서 굽는다.
## 효과음 `jumpscare`는 `tools/gen_sfx.py`가 합성한다.
##
## **layer 5** — HUD·UI(`FadeRect`)가 3, 일시정지 메뉴가 4다. 자막(HUD)까지
## 덮어야 얼굴이 대사 글자에 가리지 않는다. 게임 오버 중에는 일시정지가
## 안 열리므로(`game_over_active`) 메뉴와 겹칠 일은 없다.

## 덮치는 시간 — 작게 시작해 화면을 넘칠 때까지.
const LUNGE_SECONDS := 0.13
## 덮친 뒤 화면에 머무는 시간. 그동안 아주 천천히 더 다가온다.
const HOLD_SECONDS := 0.85
const START_SCALE := 0.3
## 화면 높이에 맞춘 그림(KEEP_ASPECT)을 이만큼 더 키운다 — 1보다 커야 얼굴이
## 화면 테두리를 넘어 '코앞'이 된다. 눈이 그림 세로 가운데라 잘리지 않는다.
const LUNGE_SCALE := 1.22
const CREEP_SCALE := 1.36
## 흔들림 폭(px). 시간이 갈수록 줄어 끝에서 절반이 된다.
const SHAKE_PX := 28.0
## 붉은 번쩍임 — 덮치는 순간 한 번 세게, 그 뒤 짧게 두 번.
const FLASH_ALPHA := 0.6
const FLASH_TIMES := [0.0, 0.22, 0.4]
const FLASH_FADE := 0.12
## 덮치는 순간 얼굴을 원래보다 밝게 — 한두 프레임 '터지는' 느낌.
const BURST_MODULATE := Color(1.8, 1.25, 1.25)
const BURST_SECONDS := 0.08

signal finished

@onready var root: Control = $Root
@onready var face: TextureRect = $Root/Face
@onready var flash: ColorRect = $Root/Flash

var playing := false


func _ready() -> void:
	root.visible = false


## 연출 전체를 기다릴 수 있다(`await jumpscare.play()`). 끝나도 검은 바탕은 남는다.
func play() -> void:
	if playing:
		return
	playing = true
	root.visible = true
	face.visible = true
	face.position = Vector2.ZERO
	face.pivot_offset = face.size * 0.5
	face.scale = Vector2.ONE * START_SCALE
	face.modulate = BURST_MODULATE
	flash.color.a = 0.0
	Sfx.play(&"jumpscare")

	var grow := create_tween()
	grow.tween_property(face, "scale", Vector2.ONE * LUNGE_SCALE, LUNGE_SECONDS) \
		.set_trans(Tween.TRANS_EXPO).set_ease(Tween.EASE_OUT)
	grow.tween_property(face, "scale", Vector2.ONE * CREEP_SCALE, HOLD_SECONDS)

	var total := LUNGE_SECONDS + HOLD_SECONDS
	var elapsed := 0.0
	var next_flash := 0
	while elapsed < total:
		await get_tree().process_frame
		# 멈춘 트리에서는 시간을 세지 않는다(#624의 규칙 — process_frame은 멈춰도 돈다).
		if not can_process():
			continue
		elapsed += get_process_delta_time()
		if next_flash < FLASH_TIMES.size() and elapsed >= float(FLASH_TIMES[next_flash]):
			var strength := 1.0 if next_flash == 0 else 0.55
			flash.color.a = FLASH_ALPHA * strength
			create_tween().tween_property(flash, "color:a", 0.0, FLASH_FADE)
			next_flash += 1
		if elapsed >= BURST_SECONDS:
			face.modulate = Color.WHITE
		var fall := 1.0 - 0.5 * clampf(elapsed / total, 0.0, 1.0)
		face.position = Vector2(randf_range(-1.0, 1.0), randf_range(-1.0, 1.0)) * SHAKE_PX * fall

	grow.kill()
	face.visible = false
	flash.color.a = 0.0
	playing = false
	finished.emit()
