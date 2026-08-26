extends Node

signal inventory_changed(items: Array[String])
signal notice_requested(message: String)
## 화자가 있는 대사(#193). 지문인 notice_requested와 나뉘어 있어야 HUD가
## 프롤로그와 같은 두 가지 자막 배치 중 하나를 고를 수 있다.
signal speech_requested(speaker: String, message: String, emotion: String)
signal game_over(reason: String)

@export var starting_items: Array[String] = []
## 시작 시 미리 세워 둘 플래그. 뒤쪽 층을 바로 확인할 때(예: stairs_f4_unlocked) 에디터에서 채워 쓴다.
@export var starting_flags: Array[String] = []
@export var max_items: int = 5

var items: Array[String] = []
# 세션 내 진행 상태(문 개방, 아이템 획득 등)를 문자열 플래그로 기록
var flags: Array[String] = []

# 런이 끝났는지(붙잡힘 등). 끝난 뒤 들어오는 중복 신호를 여기서 흡수한다.
var _is_finished: bool = false


func _enter_tree() -> void:
	add_to_group("game_state")


func _ready() -> void:
	items = starting_items.duplicate()
	flags = starting_flags.duplicate()
	inventory_changed.emit(items)


func has_item(item_id: String) -> bool:
	return item_id.is_empty() or item_id in items


func add_item(item_id: String) -> bool:
	if item_id.is_empty() or item_id in items:
		return true

	if items.size() >= max_items:
		return false

	items.append(item_id)
	inventory_changed.emit(items)
	return true


func remove_item(item_id: String) -> void:
	if item_id in items:
		items.erase(item_id)
		inventory_changed.emit(items)


func set_flag(flag: String) -> void:
	if not flag.is_empty() and flag not in flags:
		flags.append(flag)


func has_flag(flag: String) -> bool:
	return flag in flags


func request_notice(message: String) -> void:
	if message.is_empty():
		return

	notice_requested.emit(message)


## 화자 이름이 붙는 대사를 띄운다. emotion은 subtitle_dialogue.gd의 EMOTIONS 키.
func request_speech(speaker: String, message: String, emotion: String = "") -> void:
	if message.is_empty():
		return

	speech_requested.emit(speaker, message, emotion)


## 런이 실패로 끝났음을 알린다(붙잡힘 등). 접촉 판정은 매 프레임 들어오므로
## _is_finished로 첫 호출만 통과시킨다 — 호출자가 따로 가드할 필요가 없다.
func trigger_game_over(reason: String = "") -> void:
	if _is_finished:
		return

	_is_finished = true
	game_over.emit(reason)


func is_finished() -> bool:
	return _is_finished


## ── 엔딩 판정(#353) ───────────────────────────────────────────────
##
## 엔딩 종류. `exit_door.gd`가 `SceneTree` 메타로 넘기고 `ending.gd`가 읽는다.
const ENDING_BASIC := &"after_school"     # 방과 후 — 기본 탈출
const ENDING_REPORT := &"adults_work"     # 어른들의 일 — 신고
const ENDING_HIDDEN := &"break_time"      # 쉬는 시간 — 히든
## `SceneTree`에 엔딩 종류를 담을 때 쓰는 키.
const ENDING_META := &"ending_kind"

## 실종 학생의 흔적. 다섯 → 넷(#407) → **셋**(#413) — 힌트를 지운 만큼 조건도
## 줄인다. **송하람(#407)·백승호(#413)는 없다** — 그 둘의 단서를 전부 없앴으므로
## `found_songharam`·`found_baekseungho`를 얻을 방법이 없다. 남겨 두면 히든 엔딩이
## 영구히 닫힌다.
const MISSING_FLAGS := [
	"found_imnayeon", "found_jominhyuk", "found_kangyujin"]
## 시우가 어떤 아이였는지 알려 주는 것.
const SIWOO_FLAGS := [
	"read_siwoo_counseling", "read_siwoo_painting", "read_janitor_notebook"]
## 학교가 덮었다는 증거. 하나라도 있으면 현관에서 신고 선택지가 뜬다.
const COVERUP_FLAGS := [
	"read_principal_letter", "read_janitor_notebook", "read_crisis_manual"]


## 히든 엔딩 조건인가 — 실종 학생 셋을 **전부** 찾고 시우의 이야기를 **전부** 봤는가.
##
## 기획서(`docs/story.md` 7장)의 "5명 흔적 + 상담 기록 + 공책 + 시우 그림"인데,
## 하람(#407)·백승호(#413) 단서를 없앤 뒤로 찾을 수 있는 실종 학생이 **셋**이다.
## 그림 **재조사** 기믹은 2026-07-28에 걷어냈으므로 그림 플래그 보유로 대신한다.
func has_full_truth() -> bool:
	for f in MISSING_FLAGS + SIWOO_FLAGS:
		if f not in flags:
			return false
	return true


## 신고 선택지를 띄울 만큼 어른 쪽 은폐를 봤는가.
func saw_coverup() -> bool:
	for f in COVERUP_FLAGS:
		if f in flags:
			return true
	return false


## 현관에서 어떤 엔딩으로 갈 것인가(#353).
##
## `reported`는 신고 선택지에서 "신고한다"를 골랐는지다. 히든이 신고보다
## **우선**한다 — 전부 아는 플레이어에게 신고 여부를 다시 묻는 것은 의미가 없다.
func ending_kind(reported: bool) -> StringName:
	if has_full_truth():
		return ENDING_HIDDEN
	if reported and saw_coverup():
		return ENDING_REPORT
	return ENDING_BASIC


## 본 단서 수 / 전체. 엔딩 컷신 끝에 보여 준다.
func clue_score() -> Array:
	var all: Array = MISSING_FLAGS + SIWOO_FLAGS + COVERUP_FLAGS + [
		"read_siwoo_past", "read_taeho_note", "read_report_flyer",
		"read_janitor_warning", "saw_photo_wall", "saw_student_cards",
		"saw_shower_marks", "opened_key_cabinet",
		# 미술실 도입부(#405) — 목록에 안 넣어서 "알아낸 것 N"에 안 세어졌다.
		"saw_belongings", "saw_dates"]
	var uniq: Array = []
	for f in all:
		if f not in uniq:
			uniq.append(f)
	var got := 0
	for f in uniq:
		if f in flags:
			got += 1
	return [got, uniq.size()]
