extends Node

## 전역 효과음(#9). autoload로 둔다 — 타이틀 → 본편 → 엔딩/게임오버로 씬이
## 통째로 바뀌어도 살아 있어야 하고, 씬 전환 직전에 울린 소리가 끊기면 안 된다.
##
## 여기는 화면 어디서 나든 상관없는 소리만 맡는다. 위치가 정보인 소리(수위
## 발소리·열쇠)는 그 노드에 붙인 AudioStreamPlayer2D가 낸다 — janitor.tscn 참조.
##
## 소리 파일은 tools/gen_sfx.py가 합성한다. 톤을 바꾸려면 그 스크립트를 고치고
## 다시 돌린다.

const SFX_DIR := "res://assets/audio/"

## 소리별 음량(dB). 합성 단계에서도 크기를 맞췄지만, 실제로 섞어 보면
## 스팅어가 조사음을 잡아먹는 식의 불균형이 남는다 — 최종 조정은 여기서 한다.
const VOLUMES := {
	"investigate": -6.0,
	"pickup": -4.0,
	"door_locked": -5.0,
	"door_open": -6.0,
	"hide_in": -5.0,
	"hide_out": -5.0,
	"stairs": -7.0,
	"ink_throw": -4.0,
	"ink_splash": -2.0,
	"spotted": -1.0,
	"caught": 0.0,
	"escape": -2.0,
	"ui_click": -8.0,
}

## 동시 발음 수. 이보다 많이 겹치면 가장 오래된 것을 끊는다. 조사·획득이
## 연달아 눌릴 때 플레이어를 매번 새로 만들지 않으려고 미리 잡아 둔다.
const VOICES := 8

var _streams: Dictionary = {}
var _players: Array[AudioStreamPlayer] = []
var _next_voice: int = 0


func _ready() -> void:
	# autoload는 씬 트리 전환의 영향을 받지 않지만, 일시정지에도 멈추지 않게 둔다.
	process_mode = Node.PROCESS_MODE_ALWAYS

	for i in VOICES:
		var player := AudioStreamPlayer.new()
		player.bus = &"Master"
		add_child(player)
		_players.append(player)


## 효과음 재생. 없는 id를 넘기면 조용히 무시한다 — 소리 하나 빠졌다고
## 게임이 죽으면 안 된다.
func play(id: StringName) -> void:
	var stream := _stream_for(id)
	if stream == null:
		return

	var player := _players[_next_voice]
	_next_voice = (_next_voice + 1) % _players.size()

	player.stream = stream
	player.volume_db = VOLUMES.get(String(id), -4.0)
	player.play()


## 파일은 처음 쓸 때 한 번만 읽고 캐시한다. 실패해도 캐시에 null을 넣어
## 매 프레임 디스크를 두드리지 않게 한다.
func _stream_for(id: StringName) -> AudioStream:
	var key := String(id)
	if _streams.has(key):
		return _streams[key]

	var path := SFX_DIR + key + ".wav"
	var stream: AudioStream = null
	if ResourceLoader.exists(path):
		stream = load(path) as AudioStream
	else:
		push_warning("효과음 없음: %s (tools/gen_sfx.py를 돌렸는가?)" % path)

	_streams[key] = stream
	return stream
