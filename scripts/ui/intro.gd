extends Control

## 게임 시작 전 도입 내레이션. 줄마다 페이드 인 → 유지 → 페이드 아웃.
## interact(E)/ui_accept(Enter)로 다음 줄로 스킵할 수 있다.

@export_file("*.tscn") var next_scene_path: String = "res://scenes/main/main.tscn"

const LINES: Array[String] = [
	"밤 10시 30분.",
	"집으로 가던 이설은 국어 교과서를 미술실에 두고 온 것을 깨달았다.",
	"내일은 수행평가 날. 어쩔 수 없이 어두운 학교로 되돌아왔다.",
	"5층 미술실, 교과서를 집어 든 순간 — 쿵. 멀리서 현관문이 닫히는 소리가 들렸다.",
	"창밖의 가로등이 하나씩 꺼져 간다. …여기서 나가야 한다.",
]
const FADE_SECONDS := 0.6
const HOLD_SECONDS := 2.0

@onready var line_label: Label = $LineLabel

var line_index: int = -1
var line_tween: Tween
var finished: bool = false


func _ready() -> void:
	line_label.modulate.a = 0.0
	_next_line()


func _next_line() -> void:
	line_index += 1
	if line_index >= LINES.size():
		_finish()
		return

	line_label.text = LINES[line_index]
	line_tween = create_tween()
	line_tween.tween_property(line_label, "modulate:a", 1.0, FADE_SECONDS)
	line_tween.tween_interval(HOLD_SECONDS)
	line_tween.tween_property(line_label, "modulate:a", 0.0, FADE_SECONDS)
	line_tween.tween_callback(_next_line)


func _unhandled_input(event: InputEvent) -> void:
	if not (event.is_action_pressed("interact") or event.is_action_pressed("ui_accept")):
		return

	if line_tween != null:
		line_tween.kill()
	line_label.modulate.a = 0.0
	_next_line()


func _finish() -> void:
	if finished:
		return
	finished = true
	get_tree().change_scene_to_file(next_scene_path)
