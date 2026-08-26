extends Control

## 엔딩 컷신(#139) — 기획서의 3종(#353). 현관을 열고 나오면 여기로 넘어온다.
## 장면마다 자막(caption)을 바꾸고 대사를 한 글자씩 출력한다 — 표시와 진행 방식은 프롤로그(intro.gd)와
## 같은 하단 자막(scenes/ui/subtitle_dialogue.tscn)을 쓴다.
##
## **어느 엔딩인지는 `SceneTree` 메타로 받는다.** `exit_door.gd`가 현관에서 판정해
## 넣어 준다 — `GameState`는 씬 노드라 `change_scene_to_file()` 뒤에 사라진다.
## 메타가 없으면(에디터에서 이 씬을 직접 실행) 기본 엔딩으로 떨어진다.
##
## 2026-07-28에 "방과 후" 1종으로 줄였던 것을 사용자 우선순위(2026-08-22, #297)에
## 따라 되돌렸다.

@export_file("*.tscn") var title_scene_path: String = "res://scenes/ui/main_menu.tscn"

# 장면: caption과 lines([화자, 대사] 또는 [화자, 대사, 감정]). 화자가 빈 문자열이면 지문·독백으로
# 표시된다. 순서대로 재생하고 마지막에 타이틀로 돌아간다.
#
# 기본 "방과 후" — 단서를 거의 안 봤거나, 보고도 그냥 나왔을 때.
# 이설은 아무에게도 말하지 못한다. 시우가 그랬던 것처럼.
const BASIC_SCENES: Array = [
	{
		"caption": "— 학교 현관 —",
		"lines": [
			["", "현관문이 열렸다. 밤공기가 차갑게 목덜미를 스쳤다."],
			["", "이설은 뒤를 돌아보지 않고 운동장을 가로질렀다."],
			["", "등 뒤의 학교는 아무 일도 없었다는 듯 조용했다."],
		],
	},
	{
		"caption": "— 다음 날 아침, 집 —",
		"lines": [
			["", "TV가 켜져 있다."],
			["TV 아나운서", "불암고등학교에서 여섯 번째 학생의 실종 신고가 접수되었습니다—"],
			["엄마", "어제 왜 그렇게 늦었어?"],
			["이설", "…아무것도 아니야."],
			["", "이설은 밥그릇만 내려다봤다."],
		],
	},
	{
		"caption": "— 등굣길, 정문 —",
		"lines": [
			["", "정문 앞에서 수위 아저씨가 낙엽을 쓸고 있었다."],
			["수위", "어, 잘 가."],
			["", "이설은 고개를 숙이고 지나쳤다."],
			["", "말해도 아무도 안 들어줄 것 같았으니까. 시우처럼."],
			["", "— 엔딩: 방과 후 —"],
		],
	},
]

# 신고 "어른들의 일" — 교장 편지·수위 공책·대응 매뉴얼 중 하나라도 보고,
# 현관에서 "신고한다"를 고른 경우. 어른들이 덮은 일을 아이가 꺼낸다.
# 후련한 결말이 아니다 — 절차는 굴러가는데 그게 누구를 위한 절차인지는 끝내 흐리다.
const REPORT_SCENES: Array = [
	{
		"caption": "— 학교 현관 —",
		"lines": [
			["", "현관문이 열렸다. 밤공기가 차갑게 목덜미를 스쳤다."],
			["", "이설은 운동장 한가운데서 걸음을 멈췄다."],
			["", "가방 안에 접어 넣은 것들이 등을 눌렀다. 편지 한 장, 공책 몇 줄."],
			["이설", "…말 안 하면, 아무 일도 없던 게 되잖아."],
			["", "휴대폰을 꺼냈다. 화면 빛이 손을 하얗게 만들었다."],
		],
	},
	{
		"caption": "— 경찰서, 새벽 —",
		"lines": [
			["", "형광등이 지나치게 밝았다."],
			["경찰", "학생, 이거 전부 학교 안에서 찍은 거 맞아요?"],
			["이설", "네."],
			["경찰", "…10년 전 사건이랑 같이 봐야겠는데."],
			["", "옆자리에서 누군가 수화기를 들었다. 교육청, 이라는 말이 들렸다."],
			["", "이설은 그 말이 어디까지 갈지 짐작할 수 없었다."],
		],
	},
	{
		"caption": "— 사흘 뒤, 교문 앞 —",
		"lines": [
			["", "교문에 카메라가 늘어섰다. 학교 이름이 자막으로 지나갔다."],
			["TV 아나운서", "불암고등학교 실종 사건과 관련해 학교 측의 은폐 정황이—"],
			["", "정문 앞은 비어 있었다. 낙엽을 쓰는 사람은 없었다."],
			["", "누군가 물었다. 진작 말하지 그랬냐고."],
			["이설", "…말할 데가 없었어요."],
			["", "그 말은 기사에 실리지 않았다."],
			["", "— 엔딩: 어른들의 일 —"],
		],
	},
]

# 히든 "쉬는 시간" — 실종 학생 다섯을 전부 찾고 시우가 어떤 아이였는지까지 본 경우.
# 가해자로 지목된 아이들도 누군가에게는 맞고 있었다는 것을 알게 된 플레이어에게만 온다.
# 심판도 폭로도 아니고, 그냥 한 사람의 이름을 불러 주는 결말이다.
const HIDDEN_SCENES: Array = [
	{
		"caption": "— 학교 현관 —",
		"lines": [
			["", "현관문 손잡이를 잡은 채로, 이설은 뒤를 돌아봤다."],
			["", "복도 끝에 불빛 하나가 서 있었다. 손전등. 움직이지 않았다."],
			["이설", "…박시우."],
			["", "불빛이 흔들렸다."],
			["이설", "그 애 그림, 봤어요. 상담 기록도요."],
			["이설", "쉬는 시간에 혼자 있는 게 제일 무서웠다고 적혀 있었어요."],
			["수위", "……"],
			["이설", "다섯 명도 봤어요. 그 애들도 어딘가에서 혼자였어요."],
			["수위", "(낮게) 그만해."],
			["이설", "아저씨가 제일 잘 알잖아요. 아무도 안 물어봐 주는 게 어떤 건지."],
		],
	},
	{
		"caption": "— 복도 —",
		"lines": [
			["", "손전등이 바닥으로 내려갔다. 빛이 타일 위에 동그랗게 고였다."],
			["수위", "…시우가 그 말을 나한테는 안 했어."],
			["수위", "학교에서도 안 했고. 집에서도 안 했고."],
			["수위", "그래서 내가 대신 물어보고 다녔어. 32년 동안."],
			["이설", "그건 묻는 게 아니었어요."],
			["", "긴 침묵이 복도를 채웠다."],
			["수위", "…그래."],
			["", "열쇠 꾸러미가 바닥에 놓이는 소리가 났다."],
		],
	},
	{
		"caption": "— 며칠 뒤, 쉬는 시간 —",
		"lines": [
			["", "종이 울렸다. 복도가 시끄러워졌다."],
			["", "이설은 교실 뒤쪽, 늘 비어 있던 자리를 봤다."],
			["", "거기 앉은 아이에게 다가가 물었다. 별것 아닌 걸."],
			["이설", "…같이 갈래?"],
			["", "아이가 고개를 들었다. 대답까지는 오래 걸렸다."],
			["", "그래도 이설은 기다렸다."],
			["", "— 엔딩: 쉬는 시간 —"],
		],
	},
]

# 운동장 출입구로 나온 경우의 첫 장면(#393). **판정은 바뀌지 않는다** — 엔딩은
# 그대로 3종이고, 현관을 묘사하는 첫 장면만 그 루트에서 갈아 끼운다.
# 현관으로 나오지 않았는데 "현관문이 열렸다"로 시작하면 방금 한 선택이 지워진다.
const YARD_ROUTE := &"yard_exit"
const YARD_OPENINGS: Dictionary = {
	&"after_school": {
		"caption": "— 운동장 출입구 —",
		"lines": [
			["", "철문이 안쪽으로 밀렸다. 경첩이 길게 울었다."],
			["", "현관은 지나지도 않았다. 아무도 쓰지 않는 문이었다."],
			["", "이설은 어두운 운동장으로 내려섰다. 뒤는 돌아보지 않았다."],
		],
	},
	&"adults_work": {
		"caption": "— 운동장 출입구 —",
		"lines": [
			["", "철문이 안쪽으로 밀렸다. 경첩이 길게 울었다."],
			["", "이설은 어두운 운동장 한가운데서 걸음을 멈췄다."],
			["", "가방 안에 접어 넣은 것들이 등을 눌렀다. 편지 한 장, 공책 몇 줄."],
			["이설", "…말 안 하면, 아무 일도 없던 게 되잖아."],
			["", "휴대폰을 꺼냈다. 화면 빛이 손을 하얗게 만들었다."],
		],
	},
	&"break_time": {
		"caption": "— 운동장 출입구 —",
		"lines": [
			["", "철문 손잡이를 잡은 채로, 이설은 뒤를 돌아봤다."],
			["", "통로 끝, 복도 쪽에 불빛 하나가 서 있었다. 손전등. 움직이지 않았다."],
			["이설", "…박시우."],
			["", "불빛이 흔들렸다."],
			["이설", "그 애 그림, 봤어요. 상담 기록도요."],
			["이설", "쉬는 시간에 혼자 있는 게 제일 무서웠다고 적혀 있었어요."],
			["수위", "……"],
			["이설", "다섯 명도 봤어요. 그 애들도 어딘가에서 혼자였어요."],
			["수위", "(낮게) 그만해."],
			["이설", "아저씨가 제일 잘 알잖아요. 아무도 안 물어봐 주는 게 어떤 건지."],
		],
	},
}

## 메타 값 -> 장면 묶음. `game_state.gd`의 ENDING_* 상수와 같은 문자열이다.
const ENDINGS: Dictionary = {
	&"after_school": BASIC_SCENES,
	&"adults_work": REPORT_SCENES,
	&"break_time": HIDDEN_SCENES,
}
## 메타가 없을 때 떨어질 곳(에디터에서 이 씬만 실행할 때).
const DEFAULT_KIND := &"after_school"

const SCENE_FADE_SECONDS := 0.6
const SCENE_FADE_IN_SECONDS := 1.4

@onready var scene_caption: Label = $SceneCaption
@onready var dialogue: SubtitleDialogue = $Dialogue
@onready var fade_rect: ColorRect = $FadeRect

## 이번 판에 재생할 장면 묶음. _ready에서 메타를 보고 고른다.
var scenes: Array = BASIC_SCENES
var scene_index: int = 0
var line_index: int = -1
var transitioning: bool = false
var finished: bool = false


func _ready() -> void:
	var kind: StringName = DEFAULT_KIND
	if get_tree().has_meta("ending_kind"):
		kind = StringName(get_tree().get_meta("ending_kind"))
		get_tree().remove_meta("ending_kind")   # 타이틀로 돌아간 뒤 남지 않게
	scenes = ENDINGS.get(kind, BASIC_SCENES)
	_apply_route(kind)
	_append_score()

	fade_rect.color.a = 1.0
	dialogue.apply_font(scene_caption)
	_apply_scene()

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 0.0, SCENE_FADE_SECONDS)
	tween.tween_callback(_next_line)


func _unhandled_input(event: InputEvent) -> void:
	if transitioning or finished:
		return
	if not (event.is_action_pressed("interact") or event.is_action_pressed("ui_accept")):
		return

	# 타이핑 중이면 먼저 남은 글자를 즉시 전부 표시하고, 아니면 다음 줄로
	if not dialogue.skip_typing():
		_next_line()

	get_viewport().set_input_as_handled()


## 나온 문에 맞춰 첫 장면을 갈아 끼운다(#393).
##
## **원본 상수를 건드리지 않는다** — `const`가 담은 Array는 참조라, 그냥 0번을
## 바꾸면 같은 프로세스에서 다음 판까지 운동장 출입구 판으로 남는다(#353에서
## 점수 줄이 쌓이던 것과 같은 함정이다).
##
## 메타가 없으면(현관으로 나왔거나 에디터에서 이 씬만 실행) 그대로 둔다.
func _apply_route(kind: StringName) -> void:
	if not get_tree().has_meta("exit_route"):
		return
	var route := StringName(get_tree().get_meta("exit_route"))
	get_tree().remove_meta("exit_route")   # 타이틀로 돌아간 뒤 남지 않게
	if route != YARD_ROUTE or not YARD_OPENINGS.has(kind):
		return
	var copy: Array = scenes.duplicate(true)
	copy[0] = YARD_OPENINGS[kind]
	scenes = copy


## 마지막에 "알아낸 것 N / M"을 한 줄 붙인다(#353).
##
## 엔딩이 셋뿐이라 그 사이가 안 보인다 — 열 개를 본 플레이어와 두 개를 본
## 플레이어가 같은 "방과 후"를 받으면 단서를 읽은 값이 어디에도 안 남는다.
##
## **원본 상수를 건드리지 않는다.** `const`가 담은 Array는 참조라 그냥 append하면
## 다음 판까지 줄이 쌓인다(같은 프로세스에서 두 번 클리어하면 두 줄이 된다).
func _append_score() -> void:
	if not get_tree().has_meta("clue_score"):
		return
	var score: Array = get_tree().get_meta("clue_score")
	get_tree().remove_meta("clue_score")
	if score.size() < 2:
		return
	var copy: Array = scenes.duplicate(true)
	var last: Dictionary = copy[copy.size() - 1]
	last["lines"] = (last["lines"] as Array).duplicate()
	(last["lines"] as Array).append(["", "알아낸 것 %d / %d" % [score[0], score[1]]])
	scenes = copy


func _apply_scene() -> void:
	scene_caption.text = scenes[scene_index]["caption"]
	dialogue.clear()


func _next_line() -> void:
	line_index += 1
	var lines: Array = scenes[scene_index]["lines"]

	if line_index >= lines.size():
		_next_scene()
		return

	var line: Array = lines[line_index]
	var emotion: String = line[2] if line.size() > 2 else ""
	dialogue.show_line(line[0], line[1], emotion)


func _next_scene() -> void:
	if scene_index + 1 >= scenes.size():
		_finish()
		return

	transitioning = true

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, SCENE_FADE_SECONDS)
	tween.tween_callback(func() -> void:
		scene_index += 1
		line_index = -1
		_apply_scene())
	tween.tween_property(fade_rect, "color:a", 0.0, SCENE_FADE_IN_SECONDS)
	tween.tween_callback(func() -> void:
		transitioning = false
		_next_line())


func _finish() -> void:
	if finished:
		return
	finished = true

	var tween := create_tween()
	tween.tween_property(fade_rect, "color:a", 1.0, SCENE_FADE_SECONDS)
	tween.tween_callback(func() -> void:
		get_tree().change_scene_to_file(title_scene_path))
