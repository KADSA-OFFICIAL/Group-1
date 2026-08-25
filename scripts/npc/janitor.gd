extends CharacterBody2D

## 수위아저씨 NPC.
## 경로탐색은 격자 A*(AStarGrid2D). 층 로드 시 벽 충돌 도형을 몸통 크기만큼
## 부풀려 격자에 표시하므로 문·방 안까지 경로가 나온다(복도 웨이포인트로는
## 문을 지나는 경로를 표현할 수 없어 방 안 플레이어를 추적하지 못했다).
## 추적: 몸통이 지나갈 직선이 트이면 직진, 아니면 A* 경로를 따라간다.
## 활성/비활성·격자 재생성은 floor_manager가 sync_floor로 제어한다.
##
## 순찰(#141): 무작위 배회가 아니라 층 씬의 문(Door_*)을 이어 만든 고정 루트를
## 돌고, 문 앞에 서면 잠시 멈춰 방을 확인한다. 기획서 5장 "정해진 순찰 루트를
## 돌며 가끔 각 방을 확인한다"에 맞춘 것이다. 문을 하나도 못 찾은 층에서는
## 예전의 무작위 복도 배회로 폴백한다.
## 플레이어는 발소리·열쇠 소리·혼잣말(하단 알림)로 수위의 위치를 가늠한다 —
## 벽 너머는 보이지 않으므로 소리가 유일한 단서다.
## 수위가 도는 층은 floor_manager의 JANITOR_FREE_FLOOR로 정한다(4층은 안전 구간).

# 플레이어는 320. 추격 속도는 220 → 240 → 250으로 올려 왔고, 250 시점의 기록은
# "260부터는 직선 도주로 못 벗어난다"였다. #202에서 플레이어와 동일한 320까지
# 올려 본 뒤 290으로 정착했다 — 초당 30px씩만 벌어져서 직선 도주로 뿌리치려면
# 5초 넘게 달려야 하고, 실질적인 회피 수단은 시야 차단(모퉁이)과 은신(#6)이 된다.
# 압박을 조절하려면 이 값만 움직이면 된다(250=여유, 320=직선 도주 무효).
@export var patrol_speed: float = 130.0
## 추격 속도. 플레이어(320)보다 **눈에 띄게 느려야** 도망칠 수 있다(#341).
##
## 290이던 것을 낮췄다. 차이가 30px/s(9%)뿐이라 곧은 복도에서도 4초에 123px
## 밖에 못 벌렸는데, 시야가 320px이라 시야를 끊으려면 7초 넘게 직선으로
## 달려야 했다 — 모퉁이 하나만 돌면 도로 붙었다. 수위는 A*로 최단 경로를 타고
## 플레이어는 손으로 조종하며 집기에 부딪히므로 실제 격차는 더 작다.
## 240이면 초당 80px씩 벌어져 3초 안팎이면 시야가 끊긴다.
@export var chase_speed: float = 240.0
## 숨는 것을 본 뒤 그 자리로 걸어가는 속도(#298). 뛰지 않는다 — 이미 어디
## 들어갔는지 아니까 서두를 이유가 없고, 천천히 다가오는 편이 더 무섭다.
@export var search_speed: float = 175.0
# 플레이어가 수위를 알아볼 수 있는 거리. 플레이어 PointLight2D가 512×512 방사
# 그라디언트(텍스처 반경 256) × texture_scale 1.3 ≈ 333px까지 비춘다.
# 카메라(zoom 1.25, 1600×900)의 가시 반경은 360px이라 이 범위는 항상 화면 안이다.
@export var sight_range: float = 320.0
# 시야에 들어온 뒤 추적을 시작하기까지의 유예 — 플레이어에게 반응 시간을 준다.
@export var reveal_delay: float = 1.0
# 시야를 잃은 뒤에도 추적을 유지하는 시간. 0이면 모퉁이를 도는 순간 태세를 풀어
# 돌진하다 갑자기 산책하는 모습이 된다.
@export var lose_sight_seconds: float = 1.5

const ARRIVE_DISTANCE := 6.0
const STUCK_SECONDS := 0.6      # 가려던 방향으로 못 나아간 시간이 이만큼이면 막힌 것
const PROGRESS_RATIO := 0.3     # 기대 전진량의 이 비율 미만이면 나아가지 못한 것으로 본다
const REPATH_SECONDS := 0.3     # 경로 재계산 주기
const CONTACT_DISTANCE := 30.0  # 이 안까지 붙으면 멈춰 마주보고 붙잡는다(#4)
const WALL_MASK := 1            # LOS 레이캐스트 대상(벽·바리케이드)

# 콜리전 캡슐(18×30)은 회전하지 않으므로 반폭이 축마다 다르다.
const BODY_HALF_WIDTH := 9.0
const BODY_HALF_HEIGHT := 15.0
# 벽에 밀착하면 몸통 반폭 위치가 벽면과 정확히 겹쳐 판정이 부동소수점에 좌우된다.
# 평행선을 1px 안쪽으로 넣어 "붙어서 걷는 것"이 막힘으로 뒤집히지 않게 한다.
const BODY_PROBE_MARGIN := 1.0

# 격자: 층 씬 크기에서 매번 계산한다. 예전엔 2800×1800 고정이라 맵이 커지자
# (#159로 3400×2500) 격자가 왼쪽 위만 덮어 바깥 구역이 통째로 경로탐색에서
# 빠졌다 — 1층 현관·수위실 띠(y 2120~2480)가 격자 밖이었다.
const CELL := 25.0
const NEIGHBORS := [Vector2i.LEFT, Vector2i.RIGHT, Vector2i.UP, Vector2i.DOWN]
const GRID_FALLBACK := Vector2i(136, 100)
const PATH_LOOKAHEAD := 12      # 경로 다듬기에서 앞쪽 몇 지점까지 시야를 볼지
const FAR_SPAWN_RATIO := 0.6    # 스폰 후보: 플레이어에게서 최대 거리의 이 비율 이상인 칸

# ── 순찰 루트 (#141) ─────────────────────────────────────────────
# 문 앞 대기 지점은 문에서 복도 쪽으로 이만큼 물러난 곳. 문틀에 붙여 세우면
# 몸통이 벽에 끼어 도착 판정이 나지 않는다(몸통 반높이 15 + 벽 반두께 8 여유).
const DOOR_APPROACH := 46.0
const ROUTE_ARRIVE := 16.0      # 문 앞 도착 판정. 순찰은 정밀할 필요가 없어 넉넉히 잡는다

# ── 은신 수색 (#298) ─────────────────────────────────────────────
const SEARCH_SECONDS := 14.0        # 이 안에 못 닿으면 포기한다(길이 막힌 경우 대비)
const SEARCH_OPEN_DISTANCE := 46.0  # 이만큼 다가가면 은신처를 연다
const INSPECT_SECONDS := 1.8    # 문 앞에 멈춰 방을 확인하는 시간

# ── 순찰 중 방 진입 (#321) ───────────────────────────────────────
# #313에서 순찰을 복도로 한정한 뒤로 **방 안이 완전 안전지대**가 됐다. 수위가
# 방에 들어오는 것은 직접 봤을 때(추격)와 숨는 것을 봤을 때(수색, #298)뿐인데
# 둘 다 '이미 들킨 뒤'다. 들키지만 않으면 방에서 무한정 뒤질 수 있었다.
const SWEEP_CHANCE := 32        # 문 확인이 끝났을 때 방에 들어가 볼 확률(%)
const SWEEP_DEPTH := 130.0      # 문에서 방 안쪽으로 들어가는 깊이
const SWEEP_LOOK_SECONDS := 1.5 # 방 안에 서서 둘러보는 시간
const SWEEP_LIMIT := 8.0        # 들어가고 나오는 데 쓸 수 있는 총 시간
const SWEEP_LINES := [
	"…안에 누구 있나.",
	"문이 열려 있었나?",
	"불 끄고 가랬는데.",
	"…아무도 없네.",
]

# ── 소리 단서 (#141) ─────────────────────────────────────────────
# 하단 알림으로 존재감을 전한다. 화면 밖·벽 너머의 수위를 플레이어가 감지할
# 유일한 수단이다. 알림은 서로를 덮어쓰므로(hud.gd의 notice_token) 쿨다운을
# 넉넉히 줘서 단서 조사 안내 문구를 밀어내지 않게 한다.
const EARSHOT := 720.0          # 열쇠 소리·혼잣말이 들리는 거리
const FOOTSTEP_RANGE := 420.0   # 이 안이면 발소리로 더 급하게 알린다
const MUTTER_COOLDOWN := 15.0
const SOUND_COOLDOWN := 9.0

# 잉크를 뒤집어쓴 동안 몸에 덧씌우는 색. 왜 멈춰 있는지 한눈에 보이게 한다(#169).
# Polygon2D 시절에는 색을 통째로 갈아 끼웠지만 스프라이트는 그림이 있으므로
# modulate로 어둡게 죽인다 — 잉크를 뒤집어썼다는 것이 그림 위에 얹혀 보인다.
const BLIND_MODULATE := Color(0.34, 0.34, 0.5, 1.0)

# ── 스프라이트 (#310) ────────────────────────────────────────────
# assets/sprites/janitor_sheet.png = 3열 x 4행. 열이 걸음 프레임, 행이 방향.
# 사람 그림이라 이동 각도로 회전시키지 않는다(플레이어 #210과 같은 규약) —
# 방향은 행을 바꿔서 나타낸다.
const ROW_DOWN := 0
const ROW_LEFT := 1
const ROW_RIGHT := 2
const ROW_UP := 3
## 걸음 순환은 [기본, 왼발, 기본, 오른발]. 기본 프레임을 사이에 끼워야
## 두 걸음 사이에 몸이 지나가는 순간이 생긴다.
const WALK_CYCLE := [0, 1, 0, 2]
## 한 프레임이 유지되는 이동 거리. 시간이 아니라 거리로 재야 순찰(130)과
## 추격(290)에서 따로 맞추지 않아도 발이 미끄러지지 않는다.
const WALK_STRIDE := 26.0
## 뒷모습은 원본 그림이 한 장뿐이라(#310) 세 열이 모두 같다 — 위로 걸을
## 때만 1px 위아래로 흔들어 걸음을 만든다(플레이어의 BOB과 같은 방법).
const UP_BOB_STRIDE := 20.0
const SPRITE_OFFSET_Y := -24.0   # 발끝을 충돌 캡슐 바닥(y=15)에 맞추는 값

# ── 발소리·열쇠 소리 (#9) ────────────────────────────────────────
# 하단 알림 텍스트(위 EARSHOT/FOOTSTEP_RANGE)는 그대로 두고 소리를 더한다.
# 소리는 AudioStreamPlayer2D의 거리 감쇠로 위치를 알려 주고, 텍스트는 소리를
# 못 듣는 상황에서도 단서가 남게 한다.
const STEP_INTERVAL_PATROL := 0.52   # 느릿느릿(기획서 5장)
const STEP_INTERVAL_CHASE := 0.30
const STEPS_PER_JINGLE := 4          # 몇 걸음마다 열쇠꾸러미가 찰랑이는가
const MOVING_SPEED_EPSILON := 10.0   # 이보다 느리면 멈춘 것으로 본다

# 자막에 붙는 화자 이름. 프롤로그(intro.gd)의 표기와 같아야 한다.
const SPEAKER_NAME := "수위"

# ── 대사·소리 단서 (#330) ────────────────────────────────────────
# 상황마다 문장이 하나씩이라 한 판에 같은 말을 수십 번 들었다(발소리 단서는
# 9초 쿨다운마다 뜬다). 상황별로 풀을 두고 **바로 앞에 쓴 것을 피해서** 고른다
# — 3~5개짜리에서 pick_random()만 쓰면 같은 말이 두 번 연달아 나오기 쉽다.
#
# 소리 단서는 **지문 톤**(무엇이 들리는지)이고 수위 대사는 **말투**다. 박종태는
# 딸을 잃고 스스로 심판을 집행하는 인물이라 히스테릭하지 않고 담담해야 한다.
const MUTTERS := [
	"…오늘도 아무도 없지.",
	"시우야, 아빠 순찰 중이야.",
	"다 끝나면 올라갈게.",
	"불은 다 껐고… 창문도 봤고.",
	"요즘 애들은 문을 안 닫아.",
	"이 시간엔 아무도 없어야 하는데.",
]

## 발소리(420px 안). 지문이다 — 수위가 하는 말이 아니라 들리는 소리다.
const FOOTSTEP_LINES := [
	"발소리. 복도 저쪽에서. 느릿느릿.",
	"뚜벅. 뚜벅. 일정한 간격으로.",
	"바닥이 삐걱인다. 누가 걷고 있다.",
	"발소리가 멎었다가, 다시 이어진다.",
	"복도 어딘가에서 신발 끄는 소리.",
]

## 열쇠 소리(720px 안).
const KEY_LINES := [
	"— 찰랑. 열쇠꾸러미 소리. 가까워지고 있다.",
	"쇠끼리 부딪는 소리가 났다.",
	"찰그랑. 허리춤에서 나는 소리다.",
	"열쇠 소리가 한 번, 그리고 조용해졌다.",
]

## 문 확인(지문).
const DOOR_CHECK_LINES := [
	"문이 열리는 소리. 수위가 방을 확인하고 있다.",
	"손잡이 돌아가는 소리가 들린다.",
	"문틈으로 불빛이 훑고 지나간다.",
	"문이 닫혔다. 다음 문으로 가는 소리.",
]

## 발각.
const SPOT_LINES := [
	"…누구야?",
	"거기 서.",
	"학생이지. 봤어.",
	"이 시간에 뭐 하는 거야.",
]

## 은신처 수색 시작.
const SEARCH_LINES := [
	"거기 들어갔지.",
	"봤어. 나와.",
	"숨는다고 없어지나.",
]

## 은신처를 열었는데 비었을 때.
const SEARCH_EMPTY_LINES := [
	"…없네. 잘못 봤나.",
	"여기가 아니었나.",
	"눈이 침침해졌어.",
]

## 수색을 포기할 때.
const SEARCH_GIVEUP_LINES := [
	"…어디 갔어.",
	"멀리는 못 갔을 텐데.",
	"문 다 잠가 놨는데 어디로.",
]

## 붙잡았을 때.
const CATCH_LINES := [
	"학생이네. 나와. 같이 수위실로 가자.",
	"잡았다. 이리 와.",
	"왜 여기 있어. 부모님 연락처 대.",
]

## 잉크를 맞았을 때(#169).
const BLIND_LINES := [
	"으윽— 뭐야, 뭐야 이거!",
	"눈이— 이게 뭐야!",
	"뭘 던진 거야, 이 자식이!",
]

## 잉크가 풀렸을 때(지문).
const BLIND_END_LINES := [
	"수위가 눈을 문지르며 다시 걷기 시작한다.",
	"소매로 얼굴을 훔치고는 고개를 든다.",
	"한참 눈을 깜빡이더니 다시 움직인다.",
]

var player: CharacterBody2D = null
var my_floor: int = -1
var player_floor: int = -1

# F3 디버그 오버레이 — 이 환경에 Godot이 없어 실행 관찰을 사용자가 대신 해야 한다.
# 이상 동작이 보일 때 켜서 "직진인가 경로추적인가 / LOS가 막혔다고 보는가"를 확인한다.
var debug_draw: bool = false

var astar_grid := AStarGrid2D.new()
## 복도만 통행 가능한 격자. 순찰·배회는 이걸로 길을 찾아 방·계단실에 들어가지
## 않는다(#313). 추격·수색은 astar_grid를 쓴다 — 방에 숨은 플레이어를 쫓아야 한다.
var patrol_grid := AStarGrid2D.new()
var grid_size: Vector2i = GRID_FALLBACK
var grid_ready: bool = false
var walkable_cells: Array[Vector2i] = []
var corridor_cells: Array[Vector2i] = []   # 순찰은 복도만 돈다(방·계단실 폴리곤 외부)
var corridor_lookup: Dictionary = {}       # Vector2i -> true. 복도 칸 조회
## 순찰 루트에서 걸어서 닿는 복도 칸. 스폰·배회 후보를 여기서만 뽑는다 —
## 계단실처럼 닫힌 공간에서 등장하면 나올 길이 없어 갇힌다(#313).
var patrol_cells: Array[Vector2i] = []
var patrol_lookup: Dictionary = {}         # Vector2i -> true. 복도망 칸 조회

# 플레이어 시야에 연속으로 노출된 시간. reveal_delay를 넘기면 추적이 시작된다.
var seen_time: float = 0.0
# 이번 프레임에 보이는가. 소리 단서가 같은 판정을 또 쓰기 때문에 레이캐스트를
# 프레임당 한 번만 쏘도록 _update_awareness의 결과를 남겨 둔다.
var seen_now: bool = false
# 추적 유지 잔여 시간. 보이는 동안 계속 갱신되고, 시야를 잃으면 줄어든다.
var chase_hold: float = 0.0

var path_points: PackedVector2Array = PackedVector2Array()
var patrol_target: Vector2 = Vector2.ZERO
var repath_timer: float = 0.0
var stuck_time: float = 0.0

# 순찰 루트: route[i] = 문 앞 대기 지점, route_doors[i] = 그 문의 중심(확인할 때
# 바라보는 방향). 두 배열은 항상 같은 길이다.
var route: Array[Vector2] = []
var route_doors: Array[Vector2] = []
var route_index: int = 0
var route_step: int = 1        # 왕복 방향(+1 정방향 / -1 역방향)
var inspect_timer: float = 0.0

# 순찰 중 방 진입(#321). 0=안 함 / 1=들어가는 중 / 2=둘러보는 중 / 3=나오는 중
var sweep_phase: int = 0
var sweep_point: Vector2 = Vector2.ZERO   # 방 안 목표
var sweep_exit: Vector2 = Vector2.ZERO    # 되돌아 나올 문 앞 대기 지점
var sweep_timer: float = 0.0
var sweep_look: float = 0.0

var mutter_cooldown: float = 0.0
var sound_cooldown: float = 0.0
# 발각 대사는 추적이 시작될 때 한 번만. 시야가 끊겼다 붙을 때마다 다시 외치면
# 알림이 도배된다.
var announced_chase: bool = false
var announced_catch: bool = false

# 숨는 것을 본 자리와 남은 수색 시간(#298). 0보다 크면 순찰 대신 이리로 간다.
var search_point: Vector2 = Vector2.ZERO
var search_timer: float = 0.0
var announced_search: bool = false
# 직전 프레임의 은신 여부. **숨는 순간**을 잡으려면 전이를 봐야 한다.
var _player_hidden: bool = false

var _game_state: Node = null
## 풀마다 마지막에 쓴 문장. 연속 반복만 막는다(#330).
var _last_line: Dictionary = {}

# 잉크를 뒤집어써 앞을 못 보는 남은 시간(#169). 0보다 크면 추적·순찰·접촉
# 판정이 전부 멈춘다.
var blind_timer: float = 0.0
var _body_modulate: Color = Color.WHITE

## 마지막으로 향한 방향(#310). 멈춰도 그대로 두어야 서 있는 동안 보던 쪽을
## 계속 본다 — velocity로 매 프레임 다시 구하면 멈추는 순간 정면으로 돌아간다.
var _facing: Vector2 = Vector2.DOWN
## 걸음 프레임을 고르는 누적 이동 거리.
var _walk_distance: float = 0.0

var step_timer: float = 0.0
var step_count: int = 0

@onready var body: Sprite2D = $Body
@onready var collision_shape: CollisionShape2D = $CollisionShape2D
@onready var step_sound: AudioStreamPlayer2D = $StepSound
@onready var key_sound: AudioStreamPlayer2D = $KeySound
@onready var door_sound: AudioStreamPlayer2D = $DoorSound


func _enter_tree() -> void:
	# 잉크통(#169)이 터진 자리에서 수위를 찾을 때 쓴다.
	add_to_group("janitor")


func _ready() -> void:
	_body_modulate = body.modulate
	_apply_active(false)


## floor_manager가 층 전환마다 호출한다. active=true면 층 씬의 벽으로 격자를
## 다시 만들고, 플레이어에게서 먼 지점에 스폰한다(층 진입 시 화면 밖 등장 보장).
func sync_floor(active: bool, floor_number: int, player_node: CharacterBody2D,
		floor_root: Node) -> void:
	player = player_node
	player_floor = floor_number
	if active:
		my_floor = floor_number
		if floor_root != null:
			_rebuild_grid(floor_root)
	_apply_active(active)


func _apply_active(active: bool) -> void:
	visible = active
	set_physics_process(active)
	collision_shape.set_deferred("disabled", not active)
	# 층을 벗어나면 대사·소리 상태를 초기화한다. 그러지 않으면 다음 층에 내려간
	# 직후 쿨다운이 남아 첫 접근을 소리로 알리지 못한다.
	inspect_timer = 0.0
	mutter_cooldown = 0.0
	sound_cooldown = 0.0
	announced_chase = false
	announced_catch = false
	# 수색도 층을 넘기지 않는다(#298) — 3층에서 본 은신처를 2층에서 열러 갈 수 없다.
	search_timer = 0.0
	announced_search = false
	_player_hidden = false
	# 방 진입(#321)도 층을 넘기지 않는다 — 3층에서 들어가던 방을 2층에서 이어
	# 나올 수 없다.
	_end_sweep(false)
	# 스턴(#169)도 층을 넘기지 않는다 — 3층에서 맞고 2층으로 내려가면 그 층의
	# 수위는 멀쩡해야 한다(같은 노드를 층마다 재사용한다).
	blind_timer = 0.0
	body.modulate = _body_modulate
	# 층을 옮기면 방향·걸음도 처음으로. 스폰 직후 이전 층에서 걷던 프레임이
	# 남아 있으면 서 있는데 다리가 벌어져 있다.
	_facing = Vector2.DOWN
	_walk_distance = 0.0
	_update_sprite()
	Sfx.set_chasing(false)
	if active and player != null:
		_spawn_away_from(player.position)


# ── 격자 ─────────────────────────────────────────────────────────

func _rebuild_grid(floor_root: Node) -> void:
	grid_size = _grid_size_for(floor_root)
	astar_grid.clear()
	astar_grid.region = Rect2i(0, 0, grid_size.x, grid_size.y)
	astar_grid.cell_size = Vector2(CELL, CELL)
	astar_grid.offset = Vector2(CELL, CELL) * 0.5   # 경로 지점이 칸 중심에 오게
	astar_grid.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
	astar_grid.update()

	var blockers: Array[Rect2] = []
	_collect_blockers(floor_root, blockers)
	for rect in blockers:
		# 몸통이 들어갈 수 없는 칸을 막는다 = 벽을 몸통 반폭만큼 부풀리고
		# 칸 중심이 그 안에 들어가면 통행 불가.
		var grown := rect.grow_individual(BODY_HALF_WIDTH, BODY_HALF_HEIGHT,
			BODY_HALF_WIDTH, BODY_HALF_HEIGHT)
		var min_cell := _cell_of(grown.position)
		var max_cell := _cell_of(grown.end)
		for cell_x in range(maxi(min_cell.x, 0), mini(max_cell.x, grid_size.x - 1) + 1):
			for cell_y in range(maxi(min_cell.y, 0), mini(max_cell.y, grid_size.y - 1) + 1):
				var cell := Vector2i(cell_x, cell_y)
				if grown.has_point(_cell_center(cell)):
					astar_grid.set_point_solid(cell, true)

	walkable_cells.clear()
	for cell_x in grid_size.x:
		for cell_y in grid_size.y:
			var cell := Vector2i(cell_x, cell_y)
			if not astar_grid.is_point_solid(cell):
				walkable_cells.append(cell)

	# 순찰용 복도 칸: 방·계단실 폴리곤 안에 들어가는 칸을 뺀다.
	var indoor: Array[Rect2] = []
	_collect_indoor_rects(floor_root, indoor)
	corridor_cells.clear()
	corridor_lookup.clear()
	for cell in walkable_cells:
		var center := _cell_center(cell)
		var inside := false
		for rect in indoor:
			if rect.has_point(center):
				inside = true
				break
		if not inside:
			corridor_cells.append(cell)
			corridor_lookup[cell] = true
	if corridor_cells.is_empty():
		corridor_cells = walkable_cells.duplicate()
		for cell in corridor_cells:
			corridor_lookup[cell] = true

	_build_patrol_grid()
	_build_route(floor_root)
	_collect_patrol_cells()
	_prune_route_to_reachable()

	# 경로탐색과 순찰 목표가 모두 준비된 뒤에 사용 가능으로 표시한다.
	grid_ready = not walkable_cells.is_empty()


## 복도 밖(방·계단실)을 통행 불가로 막은 순찰 전용 격자.
## 벽 정보는 astar_grid와 같아야 하므로 설정값을 그대로 복사한다.
func _build_patrol_grid() -> void:
	patrol_grid.clear()
	patrol_grid.region = astar_grid.region
	patrol_grid.cell_size = astar_grid.cell_size
	patrol_grid.offset = astar_grid.offset
	patrol_grid.diagonal_mode = astar_grid.diagonal_mode
	patrol_grid.update()

	for cell_x in grid_size.x:
		for cell_y in grid_size.y:
			var cell := Vector2i(cell_x, cell_y)
			if not corridor_lookup.has(cell):
				patrol_grid.set_point_solid(cell, true)


## 층의 복도망 = 복도 칸의 **가장 큰 연결 성분**. 스폰·배회 후보는 여기서만 뽑는다.
## 계단실처럼 배리어로 둘러싸인 자투리 복도 칸은 자동으로 빠진다 — 갇히는 자리를
## 이름으로 예외 처리하지 않아도 기하가 바뀌면 따라온다(#313).
func _collect_patrol_cells() -> void:
	patrol_cells.clear()
	patrol_lookup.clear()
	if corridor_cells.is_empty():
		return

	var seen: Dictionary = {}
	var best: Array[Vector2i] = []
	for start in corridor_cells:
		if seen.has(start):
			continue
		var component: Array[Vector2i] = []
		var queue: Array[Vector2i] = [start]
		seen[start] = true
		while not queue.is_empty():
			var cell: Vector2i = queue.pop_back()
			component.append(cell)
			for step in NEIGHBORS:
				var probe: Vector2i = cell + step
				if seen.has(probe) or not corridor_lookup.has(probe):
					continue
				seen[probe] = true
				queue.append(probe)
		if component.size() > best.size():
			best = component

	patrol_cells = best
	for cell in patrol_cells:
		patrol_lookup[cell] = true


## 복도망에서 닿지 않는 문 앞 지점은 루트에서 뺀다. 남겨 두면 순찰이 그 문으로
## 가려다 막혀 STUCK_SECONDS를 버리고 넘어가는 멈칫거림이 생긴다.
func _prune_route_to_reachable() -> void:
	if patrol_lookup.is_empty() or route.is_empty():
		return

	var kept: Array[Vector2] = []
	var kept_doors: Array[Vector2] = []
	for i in route.size():
		if patrol_lookup.has(_cell_of(route[i])):
			kept.append(route[i])
			kept_doors.append(route_doors[i])
	if kept.is_empty():
		return   # 전부 빠지는 층이면 기존 루트를 그대로 둔다(배회보다는 낫다)

	route = kept
	route_doors = kept_doors
	route_index = 0
	route_step = 1


## 층 씬의 문에서 고정 순찰 루트를 만든다(#141).
## 문 시각 노드는 WallGlow/Doors/Door_<방이름>(#318 — 복도에서 문이 보이도록
## 어둠 영향이 없는 WallGlow로 옮겼다), 대응하는 방 폴리곤은 Rooms/<방이름>이다
## (tools/gen_floors.py가 이 규약으로 생성한다).
## 순서는 씬 순서의 첫 문에서 시작하는 최근접 이웃 — 씬 순서가 고정이라
## 층마다 항상 같은 루트가 나온다("정해진 순찰 루트").
func _build_route(floor_root: Node) -> void:
	route.clear()
	route_doors.clear()
	route_index = 0
	route_step = 1

	var visuals := floor_root.get_node_or_null("WallGlow/Doors")
	var rooms := floor_root.get_node_or_null("Rooms")
	if visuals == null or rooms == null:
		return

	var stops: Array[Vector2] = []
	var doors: Array[Vector2] = []
	for child in visuals.get_children():
		if not String(child.name).begins_with("Door_"):
			continue
		var door_polygon := child as Polygon2D
		if door_polygon == null or door_polygon.polygon.size() == 0:
			continue
		var room := rooms.get_node_or_null(String(child.name).trim_prefix("Door_")) as Polygon2D
		if room == null or room.polygon.size() == 0:
			continue

		var door_rect := _polygon_rect(door_polygon)
		var door_center := door_rect.position + door_rect.size * 0.5
		var stop := door_center + _outward(door_rect, _polygon_rect(room)) * DOOR_APPROACH
		# 봉인된 방·건물 밖으로 밀려난 문은 대기 지점이 벽 안에 들어간다 — 건너뛴다.
		if not _is_free_point(stop):
			continue
		# 대기 지점은 복도여야 한다 — 방 안이면 순찰이 실내로 들어간다(#313).
		if not corridor_lookup.is_empty() and not corridor_lookup.has(_cell_of(stop)):
			continue
		stops.append(stop)
		doors.append(door_center)

	if stops.is_empty():
		return

	# 최근접 이웃으로 이어 붙인다. 씬 순서 그대로 돌면 맵을 가로질러 왔다 갔다
	# 하는 루트가 나와 순찰로 보이지 않는다.
	var remaining: Array[int] = []
	for i in stops.size():
		remaining.append(i)

	var current: int = remaining[0]
	remaining.remove_at(0)
	route.append(stops[current])
	route_doors.append(doors[current])
	while not remaining.is_empty():
		var best_slot := 0
		var best_distance := INF
		for slot in remaining.size():
			var distance: float = stops[remaining[slot]].distance_squared_to(stops[current])
			if distance < best_distance:
				best_distance = distance
				best_slot = slot
		current = remaining[best_slot]
		remaining.remove_at(best_slot)
		route.append(stops[current])
		route_doors.append(doors[current])


## 문이 붙은 벽면의 바깥 방향(복도 쪽). 문은 방 경계에 놓인 납작한 사각형이라
## 긴 변의 축이 벽면의 축이고, 짧은 축의 부호가 방 중심 반대편을 가리킨다.
func _outward(door_rect: Rect2, room_rect: Rect2) -> Vector2:
	var door_center := door_rect.position + door_rect.size * 0.5
	var room_center := room_rect.position + room_rect.size * 0.5
	if door_rect.size.x >= door_rect.size.y:
		return Vector2(0.0, 1.0 if door_center.y >= room_center.y else -1.0)
	return Vector2(1.0 if door_center.x >= room_center.x else -1.0, 0.0)


## 격자 안이고 몸통이 들어갈 수 있는 지점인가(_nearest_free_cell과 달리 보정하지
## 않는다 — 대기 지점은 "거기 설 수 있는가"가 그대로 조건이다).
func _is_free_point(point: Vector2) -> bool:
	var cell := _cell_of(point)
	if cell.x < 0 or cell.y < 0 or cell.x >= grid_size.x or cell.y >= grid_size.y:
		return false
	return not astar_grid.is_point_solid(cell)


## Polygon2D의 점들을 감싸는 전역 좌표 사각형.
## 문(WallGlow/Doors 아래)과 방(Rooms 아래)은 부모가 다르지만, CanvasLayer는
## CanvasItem이 아니라 to_global 체인에 끼지 않고 층 씬 루트도 원점에 있어
## 둘 다 맵 좌표로 나온다.
func _polygon_rect(node: Polygon2D) -> Rect2:
	var polygon := node.polygon
	var rect := Rect2(node.to_global(polygon[0]), Vector2.ZERO)
	for i in range(1, polygon.size()):
		rect = rect.expand(node.to_global(polygon[i]))
	return rect


## 층 씬의 Floor 폴리곤에서 맵 크기를 읽어 격자 칸 수를 정한다.
func _grid_size_for(floor_root: Node) -> Vector2i:
	var floor_node := floor_root.get_node_or_null("Floor") as Polygon2D
	if floor_node == null or floor_node.polygon.size() == 0:
		return GRID_FALLBACK
	var extent := Vector2.ZERO
	for point in floor_node.polygon:
		extent = extent.max(floor_node.to_global(point))
	return Vector2i(int(ceil(extent.x / CELL)), int(ceil(extent.y / CELL)))


## 순찰에서 제외할 실내 영역 — 방(Rooms)과 계단실(Stairwells)이다.
## **계단실을 빼면 안 된다**(#313): 계단실 바닥은 Rooms에 없어서 복도로 분류됐고,
## 잠긴 계단은 StairWalls + StairLocks 배리어로 둘러싸인 닫힌 상자라 거기서
## 스폰된 수위가 층 내내 갇혀 있었다.
func _collect_indoor_rects(floor_root: Node, out: Array[Rect2]) -> void:
	for parent_name in ["Rooms", "Stairwells"]:
		var parent := floor_root.get_node_or_null(parent_name)
		if parent == null:
			continue
		for child in parent.get_children():
			if child is Polygon2D:
				if (child as Polygon2D).polygon.size() == 0:
					continue
				out.append(_polygon_rect(child as Polygon2D))


## 층 씬에서 StaticBody2D 하위 충돌 도형만 모은다(Area2D 상호작용 존은 제외).
func _collect_blockers(node: Node, out: Array[Rect2]) -> void:
	for child in node.get_children():
		# SDPanel* = 미닫이 교실문. 수위가 다가가면 열리므로 격자에서는 늘
		# 열린 것으로 둔다. 막힌 것으로 세면 순찰 루트가 교실 앞에서 끊긴다
		# (tools/verify_janitor_route.py도 같은 이름 규칙을 쓴다).
		var body := child.get_parent() as Node
		var is_door := body != null and body.name.begins_with("SDPanel")
		if child.get_parent() is StaticBody2D and not is_door:
			if child is CollisionPolygon2D:
				var polygon := (child as CollisionPolygon2D).polygon
				if polygon.size() > 0:
					var node_2d := child as Node2D
					var rect := Rect2(node_2d.to_global(polygon[0]), Vector2.ZERO)
					for i in range(1, polygon.size()):
						rect = rect.expand(node_2d.to_global(polygon[i]))
					out.append(rect)
			elif child is CollisionShape2D:
				var shape := (child as CollisionShape2D).shape
				if shape is RectangleShape2D:
					var half: Vector2 = (shape as RectangleShape2D).size * 0.5
					out.append(Rect2((child as Node2D).global_position - half, half * 2.0))
		_collect_blockers(child, out)


func _cell_of(point: Vector2) -> Vector2i:
	return Vector2i(floori(point.x / CELL), floori(point.y / CELL))


func _cell_center(cell: Vector2i) -> Vector2:
	return Vector2(cell.x * CELL + CELL * 0.5, cell.y * CELL + CELL * 0.5)


## 격자 밖이거나 벽 안인 지점은 가장 가까운 통행 가능 칸으로 보정한다.
## (플레이어가 벽에 붙어 있으면 그 칸이 막힌 것으로 표시돼 A*가 실패한다)
func _nearest_free_cell(point: Vector2) -> Vector2i:
	return _nearest_cell(point, false)


## 같은 보정을 복도 칸으로 한정해서 한다(순찰 목표·스폰 기준점).
func _nearest_corridor_cell(point: Vector2) -> Vector2i:
	return _nearest_cell(point, true)


func _cell_allowed(cell: Vector2i, corridor_only: bool) -> bool:
	if corridor_only:
		return corridor_lookup.has(cell)
	return not astar_grid.is_point_solid(cell)


func _nearest_cell(point: Vector2, corridor_only: bool) -> Vector2i:
	var cell := _cell_of(point)
	cell.x = clampi(cell.x, 0, grid_size.x - 1)
	cell.y = clampi(cell.y, 0, grid_size.y - 1)
	if _cell_allowed(cell, corridor_only):
		return cell

	for radius in range(1, 8):
		var best := Vector2i(-1, -1)
		var best_distance := INF
		for offset_x in range(-radius, radius + 1):
			for offset_y in range(-radius, radius + 1):
				if absi(offset_x) != radius and absi(offset_y) != radius:
					continue   # 테두리만 검사
				var probe := Vector2i(cell.x + offset_x, cell.y + offset_y)
				if probe.x < 0 or probe.y < 0 \
						or probe.x >= grid_size.x or probe.y >= grid_size.y:
					continue
				if not _cell_allowed(probe, corridor_only):
					continue
				var distance := _cell_center(probe).distance_squared_to(point)
				if distance < best_distance:
					best_distance = distance
					best = probe
		if best.x >= 0:
			return best
	return cell


func _spawn_away_from(player_position: Vector2) -> void:
	if not grid_ready:
		return

	# 순찰이 기본 상태이므로 복도에서 등장한다. 루트에서 걸어서 닿는 칸만 쓴다 —
	# 계단실 같은 닫힌 복도 칸에서 나오면 그 층 내내 갇힌다(#313).
	var pool: Array[Vector2i] = patrol_cells if not patrol_cells.is_empty() else corridor_cells
	var max_distance := 0.0
	for cell in pool:
		max_distance = maxf(max_distance, _cell_center(cell).distance_to(player_position))

	# 가장 먼 한 칸만 쓰면 매번 같은 구석에서 나온다 — 충분히 먼 칸 중 무작위.
	var candidates: Array[Vector2i] = []
	for cell in pool:
		if _cell_center(cell).distance_to(player_position) >= max_distance * FAR_SPAWN_RATIO:
			candidates.append(cell)
	if candidates.is_empty():
		return

	position = _cell_center(candidates.pick_random())
	path_points = PackedVector2Array()
	patrol_target = position
	repath_timer = 0.0
	stuck_time = 0.0
	seen_time = 0.0
	chase_hold = 0.0
	_snap_route_to_position()


## 스폰 지점에서 가장 가까운 문부터 루트를 시작한다. 항상 route[0]부터 돌면
## 층에 진입할 때마다 맵 반대편으로 먼저 걸어가는 모습이 된다.
func _snap_route_to_position() -> void:
	inspect_timer = 0.0
	if route.is_empty():
		return

	var best := 0
	var best_distance := INF
	for i in route.size():
		var distance := route[i].distance_squared_to(position)
		if distance < best_distance:
			best_distance = distance
			best = i
	route_index = best
	route_step = 1
	patrol_target = route[route_index]


# ── 이동 ─────────────────────────────────────────────────────────

func _physics_process(delta: float) -> void:
	if blind_timer > 0.0:
		Sfx.set_chasing(false)
		_hold_blinded(delta)
		return

	_update_awareness(delta)

	mutter_cooldown = maxf(mutter_cooldown - delta, 0.0)
	sound_cooldown = maxf(sound_cooldown - delta, 0.0)

	var chasing := _is_chasing()
	if chasing:
		# 직접 보이면 수색·방 진입보다 추격이 먼저다.
		search_timer = 0.0
		if sweep_phase > 0:
			_end_sweep(false)
		if not announced_chase:
			announced_chase = true
			_say_line(_pick(SPOT_LINES))
			Sfx.play(&"spotted")
		_move_chase(delta)
	elif search_timer > 0.0:
		announced_chase = false
		_move_search(delta)
	else:
		announced_chase = false
		_update_sound_cues()
		_move_patrol(delta)

	# 수색도 쫓기는 상황이다 — 걸어올 뿐 위치를 알고 오는 것이라 긴장은
	# 추격과 같아야 한다. 음악과 발소리를 추격과 같이 취급한다.
	var hunting := chasing or search_timer > 0.0
	_update_footsteps(delta, hunting)
	_advance_sprite(delta)
	Sfx.set_chasing(hunting)

	if debug_draw:
		queue_redraw()


## 걸을 때만 발소리를 낸다. 방 확인·스턴처럼 멈춰 있을 때는 조용해야
## 플레이어가 "지금 어디 서 있구나"를 소리로 읽을 수 있다.
func _update_footsteps(delta: float, chasing: bool) -> void:
	if velocity.length() < MOVING_SPEED_EPSILON:
		# 멈추면 다음 걸음이 바로 나도록 타이머를 채워 둔다.
		step_timer = STEP_INTERVAL_PATROL
		return

	step_timer -= delta
	if step_timer > 0.0:
		return

	step_timer = STEP_INTERVAL_CHASE if chasing else STEP_INTERVAL_PATROL
	step_sound.play()

	step_count += 1
	if step_count % STEPS_PER_JINGLE == 0:
		key_sound.play()


# ── 잉크통 스턴 (#169) ───────────────────────────────────────────

## 잉크를 뒤집어썼다. 추적을 끊고 제자리에 세운다.
## ink_projectile.gd가 터진 자리에서 호출한다.
func blind(seconds: float) -> void:
	# 겹쳐 맞아도 시간이 누적되지는 않는다 — 잉크통은 하나뿐이라 실제로는
	# 일어나지 않지만, 더 긴 쪽을 남기는 편이 예측하기 쉽다.
	blind_timer = maxf(blind_timer, seconds)

	seen_time = 0.0
	chase_hold = 0.0
	seen_now = false
	inspect_timer = 0.0
	path_points = PackedVector2Array()
	velocity = Vector2.ZERO
	announced_chase = false
	body.modulate = BLIND_MODULATE

	_say_line(_pick(BLIND_LINES))


## 스턴 동안은 제자리에 선다. move_and_slide를 계속 부르는 것은 플레이어가
## 밀고 들어와도 겹쳐 서지 않게 하려는 것이다. 발각·접촉 판정은 아예 돌지
## 않으므로 이 사이에 옆을 지나가도 붙잡히지 않는다.
func _hold_blinded(delta: float) -> void:
	velocity = Vector2.ZERO
	move_and_slide()
	_advance_sprite(delta)

	blind_timer -= delta
	if blind_timer <= 0.0:
		blind_timer = 0.0
		body.modulate = _body_modulate
		repath_timer = 0.0
		_say(_pick(BLIND_END_LINES))

	if debug_draw:
		queue_redraw()


## 발각 상태 갱신. 추적 여부는 chase_hold 하나로 결정된다.
func _update_awareness(delta: float) -> void:
	var hidden: bool = player != null and player.get("is_hiding") == true

	# **숨는 그 순간**에 보고 있었는지로 가른다(#298). 숨은 뒤에도
	# player.position은 은신처에 남아 _can_be_seen()이 계속 참일 수 있으므로,
	# 전이 프레임에서 직전 상태(chase_hold/seen_now)를 봐야 한다.
	if hidden and not _player_hidden and (chase_hold > 0.0 or seen_now):
		search_point = player.position
		search_timer = SEARCH_SECONDS
		announced_search = false
		path_points = PackedVector2Array()
		repath_timer = 0.0
		stuck_time = 0.0
	_player_hidden = hidden

	# 은신(#6)은 추적을 즉시 끊는다. 여기에 유지 시간을 주면 캐비넷에 숨은
	# 직후에도 수위가 들이닥쳐 접촉 판정(#4)으로 붙잡히므로 은신이 무의미해진다.
	# 봤을 때의 처리는 위 수색이 맡는다 — 그래서 이 즉시 해제를 남겨 둔다.
	if hidden:
		seen_time = 0.0
		chase_hold = 0.0
		seen_now = false
		return

	seen_now = _can_be_seen()
	if seen_now:
		seen_time += delta
		# 이미 추적 중이면 재확인에 유예를 다시 요구하지 않는다 — 유예는 최초
		# 발각에만 적용된다. 그러지 않으면 시야를 끊었다 다시 보일 때마다
		# 추적이 잠깐 풀렸다 붙는 깜빡임이 생긴다.
		if seen_time >= reveal_delay or chase_hold > 0.0:
			chase_hold = lose_sight_seconds
	else:
		seen_time = 0.0
		chase_hold = maxf(chase_hold - delta, 0.0)


## 플레이어가 수위를 실제로 볼 수 있는가.
## 어두운 학교라 손전등이 닿는 거리(sight_range) 안이어야 하고, 벽에 가리면 안 된다.
## 손전등은 원형이라 시야각은 없다 — 방향은 보지 않는다.
## 여기서 쓰는 것은 중심선 레이 1발이다. _clear_line(몸통 통과 가능성)은 이동용이고,
## "보이는지"와는 다른 문제다.
## 혹시 모를 어긋남 대비로 같은 층 조건은 유지한다.
func _can_be_seen() -> bool:
	if player == null or player_floor != my_floor:
		return false
	if position.distance_to(player.position) > sight_range:
		return false
	return _clear_ray(position, player.position)


## 최초 발각은 시야에 reveal_delay만큼 연속 노출돼야 하고, 그 뒤 시야를 잃어도
## lose_sight_seconds 동안은 추적을 유지한다(모퉁이에서 갑자기 태세를 푸는 것 방지).
func _is_chasing() -> bool:
	return chase_hold > 0.0


func _move_chase(delta: float) -> void:
	if position.distance_to(player.position) <= CONTACT_DISTANCE:
		velocity = Vector2.ZERO
		_face(position.direction_to(player.position))
		stuck_time = 0.0
		_catch_player()
		return

	repath_timer -= delta
	# 막혔으면 억제 타이머 없이 즉시 다시 계산한다. 예전 direct_block_time은
	# 막힌 동안 갱신이 반복되며 "플레이어가 보이면 직진" 검사를 영구 억제해,
	# 플레이어가 앞에 있어도 벽으로 계속 밀는 livelock을 만들었다.
	if repath_timer <= 0.0 or stuck_time >= STUCK_SECONDS:
		repath_timer = REPATH_SECONDS
		stuck_time = 0.0
		_update_chase_path()

	_step_toward(_next_point(player.position), chase_speed, delta)

## 숨는 것을 본 자리로 걸어가 은신처를 연다(#298).
##
## 예전에는 은신이 **무조건** 추적을 끊었다(#6). 숨는 순간 보고 있었는지
## 안 보고 있었는지를 구분하지 않아서, 눈앞에서 캐비닛에 들어가도 수위가
## 아무 일 없었다는 듯 순찰로 돌아갔다.
##
## 목표가 고정이라 추격보다 경로를 자주 다시 계산할 일이 없다. 대신 **길이
## 막히면 포기해야 한다** — 안 그러면 그 자리에 멈춰 순찰이 죽는다.
func _move_search(delta: float) -> void:
	search_timer -= delta
	if not announced_search:
		announced_search = true
		_say_line(_pick(SEARCH_LINES))

	if position.distance_to(search_point) <= SEARCH_OPEN_DISTANCE:
		_open_hiding_spot()
		return
	if search_timer <= 0.0 or stuck_time >= STUCK_SECONDS:
		_give_up_search()
		return

	repath_timer -= delta
	if repath_timer <= 0.0:
		repath_timer = REPATH_SECONDS
		if grid_ready and not _clear_line(position, search_point):
			path_points = astar_grid.get_point_path(
				_nearest_free_cell(position), _nearest_free_cell(search_point))
		else:
			path_points = PackedVector2Array()

	_step_toward(_next_point(search_point), search_speed, delta)


## 은신처 앞에 닿았다 — 연다. 안에 있으면 끌어내 붙잡는다.
func _open_hiding_spot() -> void:
	search_timer = 0.0
	velocity = Vector2.ZERO
	path_points = PackedVector2Array()
	door_sound.play()
	var inside: bool = (player != null and player.get("is_hiding") == true
			and player.position.distance_to(search_point) <= SEARCH_OPEN_DISTANCE)
	if not inside:
		_say_line(_pick(SEARCH_EMPTY_LINES))
		return
	# 숨은 채로 게임 오버 화면이 뜨면 앞뒤가 안 맞는다 — 먼저 끌어낸다.
	player.call("set_hiding", false)
	_catch_player()


## 시간이 다 됐거나 길이 막혔다 — 순찰로 돌아간다.
func _give_up_search() -> void:
	search_timer = 0.0
	stuck_time = 0.0
	repath_timer = 0.0
	path_points = PackedVector2Array()
	_say_line(_pick(SEARCH_GIVEUP_LINES))


## 붙잡힘 통보. 접촉 상태가 유지되는 동안 매 프레임 불리지만
## game_state가 첫 호출만 통과시키므로 여기서 따로 가드하지 않는다.
func _catch_player() -> void:
	if not announced_catch:
		announced_catch = true
		_say_line(_pick(CATCH_LINES))
		Sfx.play(&"caught")

	var game_state = get_tree().get_first_node_in_group("game_state")
	if game_state != null:
		game_state.call("trigger_game_over", "caught")


func _update_chase_path() -> void:
	if not grid_ready:
		path_points = PackedVector2Array()
		return
	if _clear_line(position, player.position):
		path_points = PackedVector2Array()   # 몸통이 지나갈 직선이 있으면 직진
		return
	path_points = astar_grid.get_point_path(
		_nearest_free_cell(position), _nearest_free_cell(player.position))


func _move_patrol(delta: float) -> void:
	if not grid_ready:
		return

	if route.is_empty():
		_move_wander(delta)   # 문을 못 찾은 층 폴백(#141 이전 동작)
		return

	if sweep_phase > 0:
		_move_sweep(delta)
		return

	if inspect_timer > 0.0:
		_hold_at_door(delta)
		return

	if position.distance_to(patrol_target) <= ROUTE_ARRIVE:
		_begin_inspection()
		return

	# 문 앞까지 못 가는 경우(가구 배치·봉인 등으로 길이 막힘)엔 그 문을 포기하고
	# 다음 문으로 넘어간다. 붙잡고 있으면 순찰이 그 자리에서 멈춘다.
	if stuck_time >= STUCK_SECONDS:
		stuck_time = 0.0
		_advance_route()
		return

	repath_timer -= delta
	if repath_timer <= 0.0:
		repath_timer = REPATH_SECONDS
		path_points = _corridor_path(patrol_target)

	_step_toward(_next_point(patrol_target), patrol_speed, delta)


## 복도만 지나는 경로(#313). 방·계단실 안에 서 있으면(추격이 방 안에서 끝난
## 경우) 먼저 전체 격자로 가장 가까운 복도 칸까지 나온 뒤 복도 격자로 넘어간다.
func _corridor_path(target: Vector2) -> PackedVector2Array:
	var here := _cell_of(position)
	if not corridor_lookup.has(here):
		# 목표를 다음 문이 아니라 **가장 가까운 복도 칸**으로 둔다 — 그러지 않으면
		# 실내를 가로질러 문까지 걸어간다. 복도에 나오면 아래 분기로 넘어간다.
		return astar_grid.get_point_path(_nearest_free_cell(position),
			_nearest_corridor_cell(position))
	return patrol_grid.get_point_path(here, _nearest_corridor_cell(target))


## 문 앞에 도착 — 멈춰서 방 안을 확인한다.
func _begin_inspection() -> void:
	inspect_timer = INSPECT_SECONDS
	velocity = Vector2.ZERO
	path_points = PackedVector2Array()
	stuck_time = 0.0
	door_sound.play()
	_notice_inspection()


## 확인하는 동안은 제자리에서 문 쪽을 바라본다. move_and_slide를 계속 부르는
## 것은 플레이어가 밀고 들어와도 겹쳐 서지 않게 하려는 것이다.
func _hold_at_door(delta: float) -> void:
	velocity = Vector2.ZERO
	move_and_slide()

	var facing := position.direction_to(route_doors[route_index])
	if facing != Vector2.ZERO:
		_face(facing)

	inspect_timer -= delta
	if inspect_timer > 0.0:
		return
	# 문만 보고 지나가면 방 안이 안전지대가 된다(#321). 가끔 들어가 본다.
	if _try_begin_sweep():
		return
	_advance_route()

## 문 확인이 끝났다 — 방에 들어가 볼까. 들어가기로 했으면 true.
##
## 순찰은 `patrol_grid`(복도 전용)를 쓰므로 방 안으로 가는 경로가 없다.
## 진입·복귀만 `astar_grid`(전체)로 찾는다.
func _try_begin_sweep() -> bool:
	if not grid_ready or route.is_empty() or route_index >= route_doors.size():
		return false
	if randi() % 100 >= SWEEP_CHANCE:
		return false

	var stop := route[route_index]
	var door := route_doors[route_index]
	var inward := stop.direction_to(door)
	if inward == Vector2.ZERO:
		return false

	# 문 너머가 복도면(관통 문) 들어갈 방이 없다.
	var want := door + inward * SWEEP_DEPTH
	var cell := _nearest_free_cell(want)
	if corridor_lookup.has(cell):
		return false

	var path := astar_grid.get_point_path(_nearest_free_cell(position), cell)
	if path.size() < 2:
		return false

	sweep_point = path[path.size() - 1]
	sweep_exit = stop
	sweep_phase = 1
	sweep_timer = SWEEP_LIMIT
	sweep_look = 0.0
	stuck_time = 0.0
	repath_timer = REPATH_SECONDS
	path_points = path
	inspect_timer = 0.0
	door_sound.play()
	return true


## 방에 들어가 둘러보고 나온다(#321).
##
## 시간이 다 되거나 길이 막히면 **나오는 단계로 넘긴다** — 그 자리에서 끝내도
## `_corridor_path()`가 복도까지 데려다 주긴 하지만(#313), 들어간 길로 걸어
## 나오는 편이 보기에 자연스럽다.
func _move_sweep(delta: float) -> void:
	sweep_timer -= delta
	var give_up: bool = sweep_timer <= 0.0 or stuck_time >= STUCK_SECONDS

	if sweep_phase == 2:
		velocity = Vector2.ZERO
		move_and_slide()
		sweep_look -= delta
		if sweep_look <= 0.0 or give_up:
			sweep_phase = 3
			path_points = PackedVector2Array()
			repath_timer = 0.0
			stuck_time = 0.0
		return

	var target: Vector2 = sweep_point if sweep_phase == 1 else sweep_exit
	if position.distance_to(target) <= ROUTE_ARRIVE:
		if sweep_phase == 1:
			sweep_phase = 2
			sweep_look = SWEEP_LOOK_SECONDS
			velocity = Vector2.ZERO
			path_points = PackedVector2Array()
			_say_line(_pick(SWEEP_LINES))
		else:
			_end_sweep(true)
		return

	if give_up:
		if sweep_phase == 1:
			sweep_phase = 3
			sweep_timer = SWEEP_LIMIT * 0.5
			path_points = PackedVector2Array()
			repath_timer = 0.0
			stuck_time = 0.0
			return
		_end_sweep(true)   # 나오다가도 막히면 순찰에 맡긴다(#313이 데려다 준다)
		return

	repath_timer -= delta
	if repath_timer <= 0.0:
		repath_timer = REPATH_SECONDS
		path_points = astar_grid.get_point_path(
			_nearest_free_cell(position), _nearest_free_cell(target))
	_step_toward(_next_point(target), patrol_speed, delta)


## 방 진입을 끝낸다. `advance`가 참이면 순찰을 다음 문으로 넘긴다.
func _end_sweep(advance: bool) -> void:
	sweep_phase = 0
	sweep_timer = 0.0
	sweep_look = 0.0
	stuck_time = 0.0
	path_points = PackedVector2Array()
	repath_timer = 0.0
	if advance:
		_advance_route()


## 다음 문으로. 순환이 아니라 왕복이다 — 끝 문에서 첫 문으로 돌아가는 순환
## 루트는 맵을 가로지르는 긴 구간을 만든다(1층에서 3000px, 23초를 아무 방도
## 안 들르고 걷는다). 끝에 닿으면 방향을 뒤집어 왔던 복도를 되짚는다.
func _advance_route() -> void:
	inspect_timer = 0.0
	if route.is_empty():
		return

	if route_index + route_step < 0 or route_index + route_step >= route.size():
		route_step = -route_step
	route_index = clampi(route_index + route_step, 0, route.size() - 1)
	patrol_target = route[route_index]
	path_points = PackedVector2Array()
	repath_timer = 0.0


## 문 정보를 못 얻은 층에서의 예전 순찰 — 무작위 복도 지점을 오간다.
func _move_wander(delta: float) -> void:
	repath_timer -= delta
	if path_points.is_empty() or stuck_time >= STUCK_SECONDS \
			or position.distance_to(patrol_target) <= ARRIVE_DISTANCE:
		stuck_time = 0.0
		repath_timer = REPATH_SECONDS
		var pool: Array[Vector2i] = patrol_cells if not patrol_cells.is_empty() else corridor_cells
		patrol_target = _cell_center(pool.pick_random())
		path_points = _corridor_path(patrol_target)

	_step_toward(_next_point(patrol_target), patrol_speed, delta)


# ── 소리 단서·혼잣말 (#141) ──────────────────────────────────────

## 같은 문장을 연달아 쓰지 않고 고른다(#330).
##
## `pick_random()`만 쓰면 3~5개짜리 풀에서 같은 말이 두 번 이어 나오는 일이
## 잦다 — 한 판에 수십 번 뜨는 소리 단서에서 특히 눈에 띈다. 풀마다 마지막에
## 쓴 것을 기억해 그것만 피한다(완전한 비반복은 아니고, 연속만 막는다).
func _pick(pool: Array) -> String:
	if pool.is_empty():
		return ""
	var key := str(pool[0])
	var last: String = _last_line.get(key, "")
	var text: String = pool.pick_random()
	if pool.size() > 1 and text == last:
		text = pool[(pool.find(text) + 1) % pool.size()]
	_last_line[key] = text
	return text


func _say(text: String) -> void:
	if _refresh_game_state():
		_game_state.call("request_notice", text)


## 수위가 입으로 내는 말. 지문(_say)과 달리 화자 이름이 붙은 자막으로 나간다(#193) —
## 프롤로그에서 수위 대사가 나오는 모양과 같아야 한다.
func _say_line(text: String) -> void:
	if _refresh_game_state():
		_game_state.call("request_speech", SPEAKER_NAME, text, "")


func _refresh_game_state() -> bool:
	if _game_state == null or not is_instance_valid(_game_state):
		_game_state = get_tree().get_first_node_in_group("game_state")
	return _game_state != null


## 같은 층에 있다는 것을 소리로 알린다. 이미 보이는 중이면 알리지 않는다 —
## 화면에 있는 것을 글로 또 말할 필요가 없고, 소리 단서는 벽 너머에서 의미가 있다.
func _update_sound_cues() -> void:
	if player == null or sound_cooldown > 0.0 or seen_now:
		return

	var distance := position.distance_to(player.position)
	if distance <= FOOTSTEP_RANGE:
		sound_cooldown = SOUND_COOLDOWN
		_say(_pick(FOOTSTEP_LINES))
	elif distance <= EARSHOT:
		sound_cooldown = SOUND_COOLDOWN
		_say(_pick(KEY_LINES))


## 방을 확인할 때의 연출. 들리는 거리 안에서만 나온다.
## 혼잣말이 쿨다운이면 문 여는 소리로 대신해, 가까이 있는데 아무 기척도 없는
## 구간이 생기지 않게 한다.
func _notice_inspection() -> void:
	if player == null or position.distance_to(player.position) > EARSHOT:
		return

	if mutter_cooldown <= 0.0:
		mutter_cooldown = MUTTER_COOLDOWN
		_say_line(_pick(MUTTERS))
	elif sound_cooldown <= 0.0:
		sound_cooldown = SOUND_COOLDOWN
		_say(_pick(DOOR_CHECK_LINES))


## 경로 다듬기: 시야가 트인 가장 먼 지점으로 건너뛴다(격자 계단 현상 완화).
## 지나친 지점은 버린다. 경로가 없으면 fallback으로 직진.
func _next_point(fallback: Vector2) -> Vector2:
	if path_points.is_empty():
		return fallback

	var limit := mini(path_points.size(), PATH_LOOKAHEAD)
	var index := 0
	for i in range(limit - 1, -1, -1):
		if _clear_line(position, path_points[i]):
			index = i
			break

	while index > 0 and path_points.size() > 1:
		path_points.remove_at(0)
		index -= 1
	if path_points.size() > 1 and position.distance_to(path_points[0]) <= ARRIVE_DISTANCE:
		path_points.remove_at(0)
	return path_points[0]


func _step_toward(target: Vector2, move_speed: float, delta: float) -> void:
	var direction := position.direction_to(target)
	if direction == Vector2.ZERO:
		velocity = Vector2.ZERO
		return

	var before := position
	velocity = direction * move_speed
	move_and_slide()
	_face(direction)

	# 막힘은 "가려던 방향으로 실제로 나아간 양"으로 판정한다.
	# 이동량 크기로 보면 벽을 따라 옆으로 밀려나는 것도 전진으로 세고,
	# 목표까지의 거리로 보면 더 빠른 플레이어가 달아나는 것까지 막힘으로 센다.
	var advance := (position - before).dot(direction)
	if advance < move_speed * delta * PROGRESS_RATIO:
		stuck_time += delta
	else:
		stuck_time = 0.0


# ── 스프라이트 (#310) ────────────────────────────────────────────

## 바라보는 방향을 기억한다. 멈춰도 지우지 않는 것은, 문 앞에서 방을 확인하는
## 동안이나 붙잡는 순간에 계속 그쪽을 보고 있어야 하기 때문이다.
func _face(direction: Vector2) -> void:
	if direction != Vector2.ZERO:
		_facing = direction


## 걸음 프레임을 이동 거리로 굴린다. 시간으로 굴리면 순찰(130)과 추격(290)에서
## 발이 미끄러지므로, 실제로 나아간 거리를 세어 WALK_STRIDE마다 한 칸 넘긴다.
func _advance_sprite(delta: float) -> void:
	var speed := velocity.length()
	if speed < MOVING_SPEED_EPSILON:
		# 멈추면 걸음을 처음으로 되돌린다 — 늘 같은 발부터 나가야 문 앞에 섰다
		# 다시 걸을 때 다리가 튀지 않는다.
		_walk_distance = 0.0
	else:
		_walk_distance += speed * delta
	_update_sprite()


## 방향은 시트의 행, 걸음은 열. 가로가 세로보다 크면 옆모습을 쓴다 — 대각선
## 이동에서 정면·뒷모습이 깜빡이지 않게 한쪽으로 확실히 기울인다.
func _update_sprite() -> void:
	var row := ROW_DOWN
	if absf(_facing.x) > absf(_facing.y):
		row = ROW_RIGHT if _facing.x > 0.0 else ROW_LEFT
	elif _facing.y < 0.0:
		row = ROW_UP

	var step := int(_walk_distance / WALK_STRIDE)
	body.frame = row * body.hframes + int(WALK_CYCLE[step % WALK_CYCLE.size()])

	# 뒷모습은 원본이 한 장뿐이라 세 열이 같은 그림이다 — 프레임만 굴리면 멈춰
	# 선 채 미끄러지는 것처럼 보이므로 위로 걸을 때만 1px 흔든다.
	var bob := 0.0
	if row == ROW_UP and _walk_distance > 0.0 \
			and int(_walk_distance / UP_BOB_STRIDE) % 2 == 1:
		bob = 1.0
	body.offset = Vector2(0.0, SPRITE_OFFSET_Y - bob)


# ── 시야 판정 ────────────────────────────────────────────────────

## 두 점 사이를 "몸통이" 지날 수 있는지 확인(자신·플레이어 몸은 제외).
## 중심선 한 발만 쏘면 두께가 0이라 벽 모서리를 스치는 경로도 뚫린 것으로 보고돼
## 직진에 들어갔다가 몸이 끼인다. 진행 방향 수직으로 몸통 반폭만큼 벌린
## 평행선까지 검사해 실제로 통과 가능한 폭인지 본다.
func _clear_line(from: Vector2, to: Vector2) -> bool:
	if not _clear_ray(from, to):
		return false
	var side := _side_offset(from.direction_to(to))
	return _clear_ray(from + side, to + side) and _clear_ray(from - side, to - side)


## 진행 방향에 수직인 몸통 반폭. 캡슐이 회전하지 않으므로 가로 이동일 때는
## 상하 반폭(15), 세로 이동일 때는 좌우 반폭(9)이 필요하다.
func _side_offset(direction: Vector2) -> Vector2:
	var perpendicular := direction.orthogonal()
	var extent := absf(perpendicular.x) * BODY_HALF_WIDTH \
		+ absf(perpendicular.y) * BODY_HALF_HEIGHT - BODY_PROBE_MARGIN
	return perpendicular * maxf(extent, 0.0)


func _clear_ray(from: Vector2, to: Vector2) -> bool:
	var exclude: Array[RID] = [get_rid()]
	if player != null:
		exclude.append(player.get_rid())
	# hit_from_inside은 끄고 둔다(기본값). 벽에 붙어 걸으면 평행선의 시작점이 벽
	# 안에 들어가는데, 그걸 히트로 세면 앞이 열려 있어도 "막힘"이 되어 헛우회한다.
	var query := PhysicsRayQueryParameters2D.create(from, to, WALL_MASK, exclude)
	var hit := get_world_2d().direct_space_state.intersect_ray(query)
	return hit.is_empty()


# ── 디버그 오버레이 (F3) ─────────────────────────────────────────

## project.godot에 입력 액션을 추가하지 않으려고 키코드를 직접 본다
## (사용자 미커밋 변경이 있는 파일이라 건드리지 않는다).
func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo \
			and event.keycode == KEY_F3:
		debug_draw = not debug_draw
		queue_redraw()


func _draw() -> void:
	if not debug_draw:
		return

	var mode := "직진"
	if blind_timer > 0.0:
		mode = "실명 %.1f" % blind_timer
	elif not _is_chasing():
		# 보이는 중이면 발각까지 남은 시간을, 아니면 순찰임을 보여준다.
		if seen_time > 0.0:
			mode = "발각까지 %.2f" % maxf(reveal_delay - seen_time, 0.0)
		elif inspect_timer > 0.0:
			mode = "방 확인 %.1f" % inspect_timer
		elif route.is_empty():
			mode = "배회"
		else:
			mode = "순찰 %d/%d" % [route_index + 1, route.size()]
	else:
		if not path_points.is_empty():
			mode = "경로(%d)" % path_points.size()
		# 시야를 잃고 유지 시간으로 쫓는 중이면 남은 시간을 덧붙인다.
		if not _can_be_seen():
			mode += " 유지%.2f" % chase_hold

	# 순찰 루트 — 다음 목표는 채운 원, 나머지 문 앞 지점은 테두리만
	for i in route.size():
		var stop := to_local(route[i])
		if i == route_index:
			draw_circle(stop, 7.0, Color(1.0, 0.6, 0.2, 0.85))
		else:
			draw_arc(stop, 5.0, 0.0, TAU, 12, Color(1.0, 0.6, 0.2, 0.35), 1.5)

	# A* 경로 — 첫 선분은 자기 위치(로컬 원점)에서
	var previous := Vector2.ZERO
	for i in path_points.size():
		var point := to_local(path_points[i])
		draw_circle(point, 4.0, Color(0.3, 0.9, 1.0, 0.8))
		draw_line(previous, point, Color(0.3, 0.9, 1.0, 0.6), 2.0)
		previous = point

	# 플레이어가 알아볼 수 있는 거리 — 이 안이고 벽에 안 가리면 발각이 누적된다
	draw_arc(Vector2.ZERO, sight_range, 0.0, TAU, 48, Color(1, 1, 0.5, 0.18), 1.0)

	if player != null:
		# 플레이어까지 LOS 프로브 3발 — 통과=초록 / 차단=빨강
		var target := player.position
		var side := _side_offset(position.direction_to(target))
		for offset in [Vector2.ZERO, side, -side]:
			var from: Vector2 = position + offset
			var to: Vector2 = target + offset
			var color := Color(0.2, 1.0, 0.3, 0.7) if _clear_ray(from, to) \
				else Color(1.0, 0.25, 0.2, 0.7)
			draw_line(to_local(from), to_local(to), color, 1.5)

	draw_string(ThemeDB.fallback_font, Vector2(-40, -34),
		"%s  보임 %s  stuck %.2f  grid %s"
			% [mode, "O" if _can_be_seen() else "X", stuck_time,
				"OK" if grid_ready else "X"],
		HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(1, 1, 0.6, 1))
