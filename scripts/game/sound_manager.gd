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
## 전체가 크다는 확인을 받아 서로의 균형은 두고 일괄 6dB(진폭 절반) 내렸다(#196).
const VOLUMES := {
	"investigate": -12.0,
	"pickup": -10.0,
	"door_locked": -11.0,
	"door_open": -12.0,
	"hide_in": -11.0,
	"hide_out": -11.0,
	"stairs": -13.0,
	"ink_throw": -10.0,
	"ink_splash": -8.0,
	"spotted": -7.0,
	"caught": -6.0,
	"escape": -8.0,
	"ui_click": -14.0,
}

## 같은 소리의 변형(#611). 하나를 고정 간격으로 되풀이하면 메트로놈처럼
## 들린다 — 수위 발소리가 "뽁뽁뽁뽁"이던 이유의 절반이다. play()와 variant()가
## 이 중 하나를 고르되 바로 앞에 쓴 것은 피한다. 파일은 gen_sfx.py가 굽는다.
const VARIANTS := {
	"janitor_step": ["janitor_step", "janitor_step_2", "janitor_step_3", "janitor_step_4"],
}
## 변형이 있는 소리는 재생할 때마다 음높이도 이 비율 안에서 흔든다.
const VARIANT_PITCH_JITTER := 0.05

## 동시 발음 수. 이보다 많이 겹치면 가장 오래된 것을 끊는다. 조사·획득이
## 연달아 눌릴 때 플레이어를 매번 새로 만들지 않으려고 미리 잡아 둔다.
const VOICES := 8

# ── 지속음 (#176) ────────────────────────────────────────────────
const AMBIENCE_DB := -16.0
const CHASE_DB := -10.0
const MUSIC_SILENT_DB := -50.0     # 사실상 무음. 0 볼륨 대신 dB로 재운다.
const MUSIC_FADE := 1.1
## 추격이 풀려도 이만큼은 음악을 유지한다. janitor의 lose_sight_seconds(1.5)보다
## 길어야 모퉁이에서 시야가 끊겼다 붙을 때 음악이 깜빡이지 않는다.
const CHASE_RELEASE_DELAY := 2.5
## 추격 중 앰비언트는 끄지 않고 낮춘다 — 완전히 끊으면 추격이 끝날 때
## 정적이 튀어나와 오히려 어색하다.
const AMBIENCE_DUCK_DB := -30.0

# ── 테마 (#606) ──────────────────────────────────────────────────
## 타이틀·프롤로그 음악. 본편 앰비언트와 겹치지 않는 구간이라 따로 둔다 —
## start_music/stop_music은 추격 상태까지 얽혀 있어 거기 끼우면 안 된다.
## 프롤로그는 자막만 흐르는 장면이라 타이틀보다 한 단 낮다(실측 RMS가
## 타이틀 0.138 / 프롤로그 0.088 / 앰비언트 0.158이라 그만큼 올려 맞췄다).
const THEME_DB := {
	"title": -13.0,
	"prologue": -11.0,
}
## 타이틀 → 프롤로그 크로스페이드. 시작 버튼의 페이드(0.8초)와 인트로 첫
## 페이드인(0.5초)이 이어지는 동안 바뀌도록 그보다 조금 길게 잡았다.
const THEME_FADE := 1.6

var _streams: Dictionary = {}
var _players: Array[AudioStreamPlayer] = []
var _next_voice: int = 0
var _last_variant: Dictionary = {}

var _ambience: AudioStreamPlayer = null
var _chase: AudioStreamPlayer = null
var _music_on: bool = false
var _chase_active: bool = false     # 지금 음악이 추격 상태인가
var _chase_wanted: bool = false     # 수위가 쫓고 있는가(매 프레임 갱신)
var _chase_release: float = 0.0
## 플레이어마다 진행 중인 음량 트윈. 같은 volume_db를 두 트윈이 다투면 튄다.
var _tweens: Dictionary = {}

## 테마 플레이어 둘을 번갈아 쓴다 — 하나가 사라지는 동안 다른 하나가 들어온다.
var _theme_players: Array[AudioStreamPlayer] = []
var _theme_index: int = 0
var _theme_id: StringName = &""


func _ready() -> void:
	# autoload는 씬 트리 전환의 영향을 받지 않지만, 일시정지에도 멈추지 않게 둔다.
	process_mode = Node.PROCESS_MODE_ALWAYS

	for i in VOICES:
		var player := AudioStreamPlayer.new()
		player.bus = &"Master"
		add_child(player)
		_players.append(player)

	_ambience = _make_loop_player(&"ambience")
	_chase = _make_loop_player(&"chase")
	for i in 2:
		_theme_players.append(_make_loop_player(&""))


## 루프 재생용 플레이어. 루프 지점은 .import가 아니라 여기서 정한다 —
## .import는 에디터가 만드는 파일이라 커밋에 빠질 수 있고, 그러면 한 바퀴
## 돌고 조용해진다.
func _make_loop_player(id: StringName) -> AudioStreamPlayer:
	var player := AudioStreamPlayer.new()
	player.bus = &"Master"
	player.volume_db = MUSIC_SILENT_DB
	add_child(player)

	# 테마 플레이어는 곡을 재생할 때 정하므로 빈 id로 만든다.
	if id != &"":
		player.stream = _loop_stream(id)
	return player


func _loop_stream(id: StringName) -> AudioStream:
	var stream := _stream_for(id)
	if stream is AudioStreamWAV:
		var wav := stream as AudioStreamWAV
		wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
		wav.loop_begin = 0
		# 샘플 수. 포맷(비트수·채널)에 기대지 않으려고 길이×샘플레이트로 센다.
		wav.loop_end = int(wav.get_length() * wav.mix_rate)
	return stream


## 효과음 재생. 없는 id를 넘기면 조용히 무시한다 — 소리 하나 빠졌다고
## 게임이 죽으면 안 된다.
func play(id: StringName) -> void:
	var stream := variant(id)
	if stream == null:
		return

	var player := _free_voice()
	player.stream = stream
	player.volume_db = VOLUMES.get(String(id), -10.0)
	# 보이스를 돌려 쓰므로 변형이 없는 소리는 음높이를 되돌려 놓아야 한다.
	player.pitch_scale = variant_pitch() if VARIANTS.has(String(id)) else 1.0
	player.play()


## id의 변형 중 하나. 변형이 없으면 그 소리 자체다. 위치가 있는 소리(수위의
## StepSound)도 이걸 거쳐 같은 변형을 쓴다.
func variant(id: StringName) -> AudioStream:
	var names: Array = VARIANTS.get(String(id), [])
	if names.is_empty():
		return _stream_for(id)
	if names.size() == 1:
		return _stream_for(StringName(names[0]))
	var last: int = _last_variant.get(id, -1)
	var pick := randi() % names.size()
	if pick == last:
		pick = (pick + 1 + randi() % (names.size() - 1)) % names.size()
	_last_variant[id] = pick
	return _stream_for(StringName(names[pick]))


func variant_pitch() -> float:
	return randf_range(1.0 - VARIANT_PITCH_JITTER, 1.0 + VARIANT_PITCH_JITTER)


## 놀고 있는 보이스를 먼저 쓴다. 재생 중인 플레이어에 stream을 갈아 끼우면
## 그 자리에서 파형이 잘려 딸깍 소리가 나기 때문이다. 여덟 개가 전부 울리는
## 중이면 그때만 순번이 돌아온 것을 끊는다.
func _free_voice() -> AudioStreamPlayer:
	for offset in _players.size():
		var index := (_next_voice + offset) % _players.size()
		if not _players[index].playing:
			_next_voice = (index + 1) % _players.size()
			return _players[index]

	var oldest := _players[_next_voice]
	_next_voice = (_next_voice + 1) % _players.size()
	return oldest


# ── 앰비언트·추격 BGM (#176) ─────────────────────────────────────

## 본편 진입 시 호출한다(floor_manager). 타이틀·엔딩에서는 울리지 않는다.
func start_music() -> void:
	# 프롤로그 테마가 남아 있으면 걷는다. 인트로가 스스로 끄지만, 건너뛰기나
	# 게임오버 재시도처럼 그 경로를 안 지나는 진입도 있다.
	stop_theme()
	if _music_on:
		return
	_music_on = true
	_chase_active = false
	_chase_wanted = false
	_chase_release = 0.0

	if _ambience != null:
		_ambience.play()
		_fade(_ambience, AMBIENCE_DB)
	if _chase != null:
		# 계속 돌려 두고 음량으로만 여닫는다 — 추격 시작마다 처음부터 나면
		# 짧은 루프가 반복이라는 게 티난다.
		# _fade를 먼저 부르는 것은 stop_music이 걸어 둔 정지 트윈을 걷어내기
		# 위해서다. 게임오버 직후 1.1초 안에 재시도하면 그 트윈이 살아 있어
		# 방금 시작한 음악을 멈춰 버린다.
		_fade(_chase, MUSIC_SILENT_DB)
		_chase.volume_db = MUSIC_SILENT_DB
		_chase.play()


func stop_music() -> void:
	if not _music_on:
		return
	_music_on = false
	_chase_wanted = false
	_chase_active = false

	for player in [_ambience, _chase]:
		if player == null:
			continue
		var tween := _fade(player, MUSIC_SILENT_DB)
		if tween != null:
			tween.tween_callback(player.stop)


## 수위가 쫓고 있는지 매 프레임 알려 준다(janitor). 해제는 바로 반영하지 않고
## CHASE_RELEASE_DELAY만큼 미룬다 — 시야가 끊겼다 붙을 때마다 음악이 켜졌다
## 꺼지면 추격 자체보다 그게 더 거슬린다.
func set_chasing(active: bool) -> void:
	_chase_wanted = active
	if active:
		_chase_release = CHASE_RELEASE_DELAY


func _process(delta: float) -> void:
	if not _music_on:
		return

	if not _chase_wanted:
		_chase_release = maxf(_chase_release - delta, 0.0)

	var should_chase := _chase_wanted or _chase_release > 0.0
	if should_chase == _chase_active:
		return

	_chase_active = should_chase
	_fade(_chase, CHASE_DB if should_chase else MUSIC_SILENT_DB)
	_fade(_ambience, AMBIENCE_DUCK_DB if should_chase else AMBIENCE_DB)


# ── 타이틀·프롤로그 테마 (#606) ──────────────────────────────────

## 테마를 튼다. 다른 테마가 울리고 있으면 크로스페이드한다. 같은 곡을 다시
## 부르면 아무것도 안 한다 — 처음부터 다시 나면 끊긴 것처럼 들린다.
func play_theme(id: StringName) -> void:
	if id == _theme_id:
		return
	var stream := _loop_stream(id)
	if stream == null:
		return

	_release_theme(_theme_players[_theme_index])
	_theme_index = (_theme_index + 1) % _theme_players.size()
	_theme_id = id

	var player := _theme_players[_theme_index]
	# 이 플레이어가 직전 크로스페이드에서 아직 사라지는 중일 수 있다. 그 정지
	# 트윈을 걷어내지 않으면 방금 튼 곡을 멈춰 버린다.
	_kill_fade(player)
	player.stop()
	player.stream = stream
	player.volume_db = MUSIC_SILENT_DB
	player.play()
	_fade(player, THEME_DB.get(String(id), -12.0), THEME_FADE)


func stop_theme() -> void:
	if _theme_id == &"":
		return
	_theme_id = &""
	_release_theme(_theme_players[_theme_index])


func _release_theme(player: AudioStreamPlayer) -> void:
	if not player.playing:
		return
	var tween := _fade(player, MUSIC_SILENT_DB, THEME_FADE)
	tween.tween_callback(player.stop)


## 진행 중이던 페이드는 버리고 새로 건다. 두 트윈이 같은 volume_db를 두고
## 다투면 음량이 튄다.
func _fade(player: AudioStreamPlayer, target_db: float,
		seconds: float = MUSIC_FADE) -> Tween:
	if player == null:
		return null

	_kill_fade(player)
	var tween := create_tween()
	tween.tween_property(player, "volume_db", target_db, seconds)
	_tweens[player] = tween
	return tween


func _kill_fade(player: AudioStreamPlayer) -> void:
	var previous: Tween = _tweens.get(player, null)
	if previous != null and previous.is_valid():
		previous.kill()


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
