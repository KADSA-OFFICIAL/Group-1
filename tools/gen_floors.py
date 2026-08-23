#!/usr/bin/env python3
"""손도면(#159) 기반으로 층 씬 전체를 생성한다.

기존 gen_walls.py / gen_occluders.py는 "이미 있는 씬에 벽을 끼워넣는" 도구지만,
이 도구는 아래 LAYOUT 테이블 하나로 층 씬(.tscn) 전체를 새로 만든다.

생성물: Floor, Rooms, WallGlow(Rail_*/RoomWallVisuals), Stairwells, StairWalls,
        Occluders, Labels, RoomWalls, Walls(외벽)

규약(#159):
- 벽 두께 16, 문 폭 110
- 벽은 충돌(WC_/RC_) + 시각(WV_, WallGlow 레이어) + 광원차단(LO_+Occ_) 3종 세트
- 사선 구역은 축정렬 근사가 아니라 실제 대각 폴리곤(y가 x에 따라 기울어짐)
- 막힌 공간(도면 X 표시)은 사방이 벽이고 문·라벨이 없다

P1 범위: 지오메트리만. 계단 자물쇠·열쇠·단서 오브젝트는 P3에서 얹는다.
"""
import pathlib
import re
import json

NL = chr(10)   # 노드 블록을 줄 단위로 조립할 때 쓴다

T = 16          # 벽 두께
DOOR = 110      # 문 틈 폭
W, H = 3400, 2500   # 캔버스

C_FLOOR = "Color(0.14, 0.14, 0.16, 1)"
C_ROOM = "Color(0.1, 0.11, 0.12, 1)"
# 벽은 텍스처 게인(1/TEX_MEAN)이 붙어 실제로는 이 값의 1.28배로 칠해진다.
# 0.45,0.48,0.55였을 때 화면에서 **가장 밝은 것이 벽**이라 시선을 다 가져갔다(#265).
C_WALL = "Color(0.285, 0.300, 0.335, 1)"
C_DOOR = "Color(0.45, 0.32, 0.2, 1)"
C_SLAB = "Color(0.1, 0.12, 0.13, 1)"
C_STEP = "Color(0.22, 0.24, 0.28, 1)"
C_LOCK = "Color(0.55, 0.26, 0.22, 1)"   # 잠긴 계단 배리어
C_KEY = "Color(0.85, 0.74, 0.32, 1)"    # 열쇠
C_SEAL = "Color(0.38, 0.38, 0.40, 1)"   # 영구 봉인된 계단(콘크리트)

# 방 안 집기 — 어둠(CanvasModulate)을 받는 Props 레이어라 손전등에 들어와야 보인다.
C_DESK = "Color(0.29, 0.23, 0.17, 1)"    # 나무 책상·탁자
C_METAL = "Color(0.25, 0.27, 0.31, 1)"   # 사물함·컴퓨터 책상
C_SHELF = "Color(0.23, 0.20, 0.16, 1)"   # 창고 선반
C_STALL = "Color(0.33, 0.36, 0.38, 1)"   # 화장실 칸막이 — 어두우면 바닥에 묻혀
                                         # 칸이 있는지 안 보인다(0.21이었다)
C_BENCH = "Color(0.27, 0.25, 0.21, 1)"   # 벤치·의자
C_LOCKER = "Color(0.30, 0.32, 0.37, 1)"  # 사물함
C_CHAIR = "Color(0.22, 0.18, 0.14, 1)"   # 의자
C_BOARD = "Color(0.13, 0.19, 0.16, 1)"   # 칠판(장식)
C_NOTICE = "Color(0.34, 0.29, 0.21, 1)"  # 게시판(장식)
C_CLEAN = "Color(0.19, 0.26, 0.24, 1)"   # 청소도구함
C_BIN = "Color(0.17, 0.19, 0.21, 1)"     # 쓰레기통
C_WINDOW = "Color(0.17, 0.23, 0.36, 1)"  # 창문 — 짙은 밤하늘이 비친 유리(#268)
C_MOON_LIGHT = "Color(0.54, 0.65, 0.95, 1)"  # 달빛 — 폴리곤이 아니라 광원(#274)
C_FIRE = "Color(0.44, 0.17, 0.15, 1)"    # 소화기(장식)
C_LINE = "Color(0.17, 0.19, 0.23, 1)"    # 복도 바닥 유도선(장식)
C_TRAY = "Color(0.33, 0.34, 0.36, 1)"    # 분필받이
C_FLAG = "Color(0.62, 0.60, 0.57, 1)"    # 태극기
C_TV = "Color(0.10, 0.11, 0.13, 1)"      # 벽걸이 TV
C_CLOCK = "Color(0.58, 0.57, 0.54, 1)"   # 시계
C_SPEAKER = "Color(0.20, 0.21, 0.23, 1)" # 스피커
C_CURTAIN = "Color(0.36, 0.33, 0.31, 1)" # 커튼
C_BOOK = "Color(0.45, 0.34, 0.24, 1)"    # 책·교과서(집기 위 소품)
C_PAPER = "Color(0.55, 0.54, 0.50, 1)"   # 서류
C_LEAF = "Color(0.66, 0.58, 0.44, 1)"    # 미닫이 문짝 — 문 표식(C_DOOR)보다 밝게
DOOR_LEAF_T = 10                          # 문짝 두께(벽 16 안쪽에 낀다)
WALL_FACE = 20                            # 가로 벽 아래 앞면 높이(#268, #271에서
                                          # 14->20. 낮으면 높이가 안 느껴진다)
# ── 창문 달빛(#274) ─────────────────────────────────────────────
# 세 번 다르게 그려 봤다 — 불투명한 바닥 표시(#268), 사다리꼴, 반투명
# 사다리꼴(#271). 매번 다른 이유로 빛이 아니라 바닥에 깔린 천으로 보였다.
# **그리는 방법이 아니라 도구가 틀렸다.** 폴리곤에는 빛의 성질이 없다 —
# 가장자리가 안 번지고, 아래를 덮을 뿐 밝히지 못하고, 벽에 안 막힌다.
MOON_ENERGY = 1.25   # 창 하나가 내는 밝기. 어둠은 (0.1, 0.1, 0.13)이다
MOON_SCALE = 0.72    # 512px 그라디언트에 곱한다 → 반경 약 185px
MOON_INSET = 24      # 광원을 창에서 방 안으로 들여놓는 거리
WINDOW_ZONE = (170, 52)   # 창가 조사(E) 범위

# 바닥 구역 — Floor(맵 바탕) 위, Rooms(방 바닥) 아래에 깔린다.
C_CORRIDOR = "Color(0.196, 0.160, 0.120, 1)"  # 복도 마루 — 학교 목재 바닥
C_SEAM = "Color(0.168, 0.134, 0.098, 1)"      # 마루 널 이음매
C_WAINSCOT = "Color(0.34, 0.29, 0.22, 1)"     # 걸레받이(벽 아래 나무 띠)
C_WALL_TOP = "Color(0.375, 0.392, 0.430, 1)"  # 벽 윗변 하이라이트(#271)
C_WALL_SHADOW = "Color(0.118, 0.124, 0.140, 1)"  # 앞면이 바닥에 닿는 그림자
C_FACE = "Color(0.205, 0.216, 0.242, 1)"      # 벽 앞면 — 윗면보다 어둡게 해
                                              # 세워진 면으로 읽히게 한다(#268)
C_PILASTER = "Color(0.235, 0.248, 0.278, 1)"  # 복도 기둥 — 벽보다 **어둡게**.
                                              # 밝으면 흰 기둥처럼 튄다(#265)
C_URINAL = "Color(0.32, 0.35, 0.37, 1)"       # 소변기
C_STALLDOOR = "Color(0.26, 0.29, 0.31, 1)"    # 칸막이 문(장식)
C_DRAIN = "Color(0.10, 0.11, 0.12, 1)"        # 배수구(장식)
C_DRYER = "Color(0.40, 0.42, 0.44, 1)"        # 손건조기(장식)
C_TISSUE = "Color(0.58, 0.56, 0.52, 1)"       # 휴지걸이(장식)
C_FAN = "Color(0.28, 0.30, 0.32, 1)"          # 환풍기(장식)
C_MOP = "Color(0.36, 0.30, 0.20, 1)"          # 대걸레
C_BUCKET = "Color(0.22, 0.32, 0.30, 1)"       # 양동이
C_STAIN = "Color(0.118, 0.130, 0.136, 1)"     # 바닥 물때(바닥 표시)
C_TOILET = "Color(0.60, 0.63, 0.65, 1)"       # 대변기
C_PIPE = "Color(0.225, 0.235, 0.255, 1)"      # 천장 배관(장식) — 바닥보다
                                              # 살짝만 밝게. 진하면 바닥 선이 된다

# 방 종류별 바닥. 들어간 방이 무슨 방인지 바닥만 보고도 갈리게 한다.
C_BLOCKED_FLOOR = "Color(0.072, 0.072, 0.078, 1)"   # 막힌 공간
ROOM_FLOOR = {
    "classroom": "Color(0.152, 0.124, 0.092, 1)",   # 마루
    "office":    "Color(0.140, 0.118, 0.094, 1)",   # 마루(교실보다 어둡게)
    "toilet":    "Color(0.128, 0.142, 0.148, 1)",   # 타일
    "storage":   "Color(0.092, 0.088, 0.082, 1)",   # 시멘트
    "lab":       "Color(0.100, 0.120, 0.122, 1)",
    "computer":  "Color(0.100, 0.108, 0.128, 1)",
    "entrance":  "Color(0.148, 0.126, 0.100, 1)",
    "janitor":   "Color(0.134, 0.112, 0.090, 1)",
}

# 방 종류별 부속 — 규격 사각형만으로는 실험대와 선반이 크기만 다른 상자였다.
C_SINK = "Color(0.30, 0.33, 0.35, 1)"        # 세면대·개수대
C_MIRROR = "Color(0.34, 0.40, 0.45, 1)"      # 거울(장식)
C_CABINET = "Color(0.24, 0.22, 0.19, 1)"     # 캐비닛·약품장
C_WBOARD = "Color(0.50, 0.52, 0.51, 1)"      # 화이트보드(장식)
C_MONITOR = "Color(0.09, 0.10, 0.12, 1)"     # 모니터(소품)
C_RACK = "Color(0.19, 0.20, 0.23, 1)"        # 서버랙
C_BED = "Color(0.30, 0.26, 0.24, 1)"         # 간이침상
C_MAT = "Color(0.19, 0.17, 0.15, 1)"         # 매트(소품)
C_PLANT = "Color(0.16, 0.26, 0.18, 1)"       # 화분
C_HYDRANT = "Color(0.38, 0.16, 0.15, 1)"     # 소화전 함(장식)
C_WATER = "Color(0.24, 0.30, 0.34, 1)"       # 정수기
C_KEYBOARD_WALL = "Color(0.42, 0.36, 0.22, 1)"  # 수위실 열쇠판(장식)
C_SIGN = "Color(0.30, 0.34, 0.38, 1)"
C_SOFA = "Color(0.28, 0.24, 0.26, 1)"        # 접견 소파(교무실)
C_COPIER = "Color(0.30, 0.31, 0.33, 1)"      # 복사기
C_FRIDGE = "Color(0.38, 0.39, 0.41, 1)"      # 냉장고
C_PARTITION = "Color(0.31, 0.29, 0.26, 1)"   # 마주 본 책상 사이 칸막이
C_BAG = "Color(0.30, 0.26, 0.32, 1)"         # 책가방(#289)
C_CUP = "Color(0.66, 0.65, 0.60, 1)"         # 컵·비누
C_CASE = "Color(0.44, 0.32, 0.22, 1)"        # 필통·도구함
C_CLOTHES = "Color(0.35, 0.38, 0.42, 1)"     # 체육복·담요·쿠션        # 안내판(장식)

# ── 도트 타일 텍스처 (#246, 원안 #243) ───────────────────────
# 바닥·벽·집기는 단색 면이었다. `tools/gen_tiles.py`가 구운 회색조 도트 무늬를
# 같은 폴리곤에 물려 2D 쯔꾸르류 느낌을 낸다. **지오메트리는 건드리지 않는다.**
#
# 왜 색이 아니라 무늬만 텍스처인가: 방 종류별 바닥색(#237)과 #242의 마루 톤을
# 팔레트가 계속 쥐어야 새 방에 타일을 붙일 때 색을 다시 고민하지 않는다.
# 텍스처는 color와 곱해진다.
#
# UV: Polygon2D의 uv를 비워 두면 정점 좌표가 곧 UV다. 이 폴리곤들은 전부 절대
# 좌표 + position 0이므로 **맵 전체가 하나의 타일 격자에 정렬된다**.
#
# #241/#242가 이미 격자를 그리는 면에는 **선 없는 무늬**를 준다 — 복도 마루널
# (64px)·화장실 줄눈(60px)과 타일 주기(48px)가 어긋나 격자가 겹쳐 보이기 때문이다.
# gen_tiles.py의 `LINELESS`가 그 무늬에 선이 없는지 검사한다.
TEX_DIR = "res://assets/tiles"
TEX_MEAN = 0.78     # gen_tiles.py의 MEAN과 반드시 같아야 한다

# 색 상수 -> 타일 이름. 여기 없는 색은 단색으로 남는다 — 열쇠·화살표·천장등처럼
# 표식이거나, 마루 널 이음매(C_SEAM 2px)·칸막이 문
# (C_STALLDOOR 5px)처럼 무늬가 들어갈 수 없을 만큼 얇은 것들이다.
TEX = {
    # 바닥 — #242가 격자를 그리는 면(복도·화장실)은 선 없는 무늬
    C_CORRIDOR: "floor_board",
    ROOM_FLOOR["toilet"]: "floor_matte",
    C_FLOOR: "floor_cement",
    C_ROOM: "floor_matte",
    C_BLOCKED_FLOOR: "floor_cement",
    ROOM_FLOOR["classroom"]: "floor_wood",
    ROOM_FLOOR["office"]: "floor_wood",
    ROOM_FLOOR["entrance"]: "floor_wood",
    ROOM_FLOOR["janitor"]: "floor_wood",
    ROOM_FLOOR["storage"]: "floor_cement",
    ROOM_FLOOR["lab"]: "floor_vinyl",
    ROOM_FLOOR["computer"]: "floor_panel",
    # 벽·문·계단
    C_WALL: "wall_brick",
    C_SEAL: "wall_brick",
    C_PILASTER: "wall_brick",
    C_STEP: "wall_brick",
    C_SLAB: "floor_cement",
    C_DOOR: "prop_grain",
    C_LEAF: "prop_grain",
    C_LOCK: "prop_metal",
    C_WAINSCOT: "prop_grain",
    # 나무 집기
    C_DESK: "prop_grain",
    C_SHELF: "prop_grain",
    C_BENCH: "prop_grain",
    C_CHAIR: "prop_grain",
    C_CABINET: "prop_grain",
    C_BED: "prop_grain",
    C_BOOK: "prop_grain",
    C_KEYBOARD_WALL: "prop_grain",
    # 금속 집기·설비
    C_METAL: "prop_metal",
    C_LOCKER: "prop_metal",
    C_STALL: "prop_metal",
    C_BIN: "prop_metal",
    C_RACK: "prop_metal",
    C_SINK: "prop_metal",
    C_URINAL: "prop_metal",
    C_DRAIN: "prop_metal",
    C_WATER: "prop_metal",
    C_TRAY: "prop_metal",
    C_HYDRANT: "prop_metal",
    C_FIRE: "prop_metal",
    C_CLOCK: "prop_metal",
    C_SPEAKER: "prop_metal",
    # 유리·화면 (칠판은 단색 — 반사 무늬가 얹히면 분필판이 아니라 창처럼 보였다)
    C_WINDOW: "prop_glass",
    C_MIRROR: "prop_glass",
    C_TV: "prop_glass",
    C_MONITOR: "prop_glass",
    C_WBOARD: "prop_glass",
    C_SIGN: "prop_glass",
    # 천·코르크 (화분은 단색 — 잎에 짜임이 얹히면 식물로 안 읽힌다)
    C_NOTICE: "prop_cloth",
    C_CURTAIN: "prop_cloth",
    C_FLAG: "prop_cloth",
    C_PAPER: "prop_cloth",
    C_CLEAN: "prop_cloth",
    C_MAT: "prop_cloth",
}

# 색 -> 오브젝트 그림(#259). TEX가 "이어붙는 재질"이라면 이쪽은 "경계가 있는
# 물건"이다. 여기 있는 색은 TEX보다 우선하고, 물건마다 로컬 UV가 들어가 그림
# 한 장이 그 물건에 맞춰 늘어난다 — 44x26 책상에도 상판·모서리·서랍선이 제자리에
# 온다. 재질만 쓰던 때는 월드 격자의 아무 조각이나 잘려 들어갔다.
SPRITE = {
    C_DESK: "obj_desk",
    C_CHAIR: "obj_chair",
    C_LOCKER: "obj_locker",
    C_SHELF: "obj_shelf",
    C_SINK: "obj_sink",
    C_URINAL: "obj_sink",
    C_MONITOR: "obj_screen",
    C_STALL: "obj_panel",
    C_STALLDOOR: "obj_panel",
    C_LEAF: "obj_panel",
    C_CABINET: "obj_cabinet",
    C_CLEAN: "obj_cabinet",
    C_METAL: "obj_locker",
    C_BIN: "obj_bin",
    C_BUCKET: "obj_bin",
    C_BED: "obj_bed",
    C_PLANT: "obj_plant",
    C_RACK: "obj_rack",
    C_TOILET: "obj_toilet",
    C_BENCH: "obj_shelf",
    C_SOFA: "obj_bed",
    C_COPIER: "obj_cabinet",
    C_FRIDGE: "obj_locker",
    C_PARTITION: "obj_panel",
}
SPRITE_SIZE = 32    # gen_tiles.py의 OBJ와 반드시 같아야 한다


def uv_for(polygon):
    """폴리곤 경계상자를 오브젝트 그림 한 장에 대응시키는 UV.

    UV는 텍스처 픽셀 좌표다 — 정점마다 (0,0)~(SPRITE_SIZE,SPRITE_SIZE) 안의
    자리를 준다. 그래서 44x26 책상이든 140x38 실험대든 그림 한 장이 통째로
    늘어나 들어간다(잘리지 않는다).
    """
    nums = [float(v) for v in polygon[polygon.index("(") + 1:polygon.rindex(")")].split(",")]
    xs, ys = nums[0::2], nums[1::2]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w = (x1 - x0) or 1.0
    h = (y1 - y0) or 1.0
    pts = [((x - x0) / w * SPRITE_SIZE, (y - y0) / h * SPRITE_SIZE)
           for x, y in zip(xs, ys)]
    return poly(*pts)


TEXTURES = {f"tex_{stem}": f"{TEX_DIR}/{stem}.png"
            for stem in sorted(set(TEX.values()) | set(SPRITE.values()))}

CANVAS_ITEM_ROOTS = ("WallGlow",)   # CanvasLayer 직속 = 텍스처 설정을 물려받을 부모가 없다

# texture_filter = 1(Nearest): 도트가 보간돼 뭉개지지 않게. 프로젝트 기본값은 Linear다.
# texture_repeat = 2(Enabled): UV가 폴리곤 좌표라 1을 넘어간다 — 감싸지 않으면 한 장만
#   늘어나 붙는다. 둘 다 CanvasItem 속성이라 자식이 부모에게서 물려받으므로(기본값 0 =
#   Parent) 층 씬 루트와 RoomWallVisuals에만 걸면 그 아래 폴리곤 전부에 적용된다.
TEX_FLAGS = "texture_filter = 1\ntexture_repeat = 2\n"


def shade_jitter(color, name, amount=0.06):
    """같은 종류 집기라도 조금씩 다른 색으로 칠한다(#289).

    교실 책상 스무 개가 완전히 같은 색이라 복사·붙여넣기로 보였다. 노드
    이름으로 결정론적으로 흔들어, 재생성해도 같은 물건에 같은 색이 붙는다.

    **텍스처를 고른 뒤에** 걸어야 한다 — `SPRITE`·`TEX`가 색 문자열을 키로
    쓰므로 먼저 흔들면 그림을 못 찾는다. 벽·바닥에는 걸지 않는다 — 이어붙는
    면이라 조각마다 색이 다르면 누더기가 된다.
    """
    h = 2166136261
    for ch in name:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    k = 1.0 + ((h % 2001) / 1000.0 - 1.0) * amount
    nums = [float(v) for v in color[color.index("(") + 1:color.rindex(")")].split(",")]
    out = [min(1.0, max(0.0, round(v * k, 4))) for v in nums[:3]] + nums[3:]
    return "Color(" + ", ".join(f"{v:g}" for v in out) + ")"


def tex_color(color):
    """텍스처와 곱해질 색: 원래 색 / TEX_MEAN (1.0에서 잘린다).

    텍스처를 곱하면 평균이 TEX_MEAN배 어두워진다. 어둠 + 손전등 밝기를 아슬아슬하게
    맞춰 놨으므로(#74) 그만큼 색에 게인을 줘서 평균 밝기를 텍스처 도입 전과 같게 둔다.
    """
    nums = [float(v) for v in color[color.index("(") + 1:color.rindex(")")].split(",")]
    out = [min(1.0, round(v / TEX_MEAN, 4)) for v in nums[:3]] + nums[3:]
    return "Color(" + ", ".join(f"{v:g}" for v in out) + ")"


# ── 세로 밴드 ────────────────────────────────────────────────
# 외벽은 두께 40이 경계선 위에 걸쳐 있으므로 안쪽 면이 EDGE. 방을 여기 딱 붙인다(#159 피드백).
EDGE = 20
NORTH_Y0, NORTH_Y1 = EDGE, 540       # 북쪽 교실동 — 위쪽 외벽에 밀착
MID_Y0, MID_Y1 = 720, 1000           # 중간 띠(화장실·막힌공간)
STAIR_A = (300, 720, 740, 1000)      # 좌측 계단실 — 중간 띠와 같은 높이(공백 봉인 벽과 겹치지 않게)
BRIDGE_X0, BRIDGE_X1 = 1670, 1890    # 중앙다리(유일한 남북 통로)
BRIDGE_Y0, BRIDGE_Y1 = 1000, 1400    # 위=중간 띠 아래, 아래=남쪽 복도
VOID_Y1 = 1400                       # 공백 구역(건물 밖) 하단 = 남쪽 복도 시작
SOUTH_Y0, SOUTH_Y1 = 1520, 1940      # 남쪽 특별실동(위 복도 1400~1520)
BOT_Y0, BOT_Y1 = 2120, 2480          # 하단 띠 — 아래쪽 외벽에 밀착
STAIR_B = (1450, 2120, 1890, 2440)   # 중앙 하단 계단실 (2~5층 동일)

# 북쪽 교실: 칸 수에 맞춰 폭을 자동 계산해 EDGE~W-EDGE를 꽉 채운다.
# pitch = (span+gap)/count 로 두면 마지막 칸 오른쪽 끝이 정확히 W-EDGE에 떨어진다.
# 간격은 0 — 반과 반이 벽을 맞대게 한다. 예전 32px 간격은 교실 사이에 복도로
# 열린 막다른 골목을 만들어, 실내인데 바깥처럼 보이고 수위 스폰 후보에도 들었다.
NORTH_GAP = 0

def north_x(i, count):
    span = W - 2 * EDGE
    pitch = (span + NORTH_GAP) / count
    x0 = EDGE + i * pitch
    return x0, x0 + pitch - NORTH_GAP

# 오른쪽 중간 띠는 예전에 x가 늘수록 y가 내려가는 평행사변형이었다(#159 도면).
# #265에서 일자로 폈다 — 사선 때문에 벽 장식·환풍기·줄눈·복도 사물함·유도선이
# 전부 "사선 방은 건너뛴다" 특례를 달고 있었고, 유지 비용이 모양값보다 컸다.
RIGHT_X0 = 1920


# ── 층별 방 구성 (도면 그대로) ───────────────────────────────
# north: 교실 8칸 이름 / mid_left·mid_right·south·bottom: (키, 라벨, x0, x1)
# 라벨이 None이면 막힌 공간(문 없음·라벨 없음)
LAYOUT = {
    4: {
        "north": ["1반", "2반", "3반", "3학년부", "4반", "5반", "6반", "7반", "8반"],
        "south_left": [("Dasan7", "다산7실", 20, 720), ("CreativeDept", "창의체험부", 750, 1640)],
        "south_right": [("ComputerRoom", "컴퓨터실", 1920, 2400),
                        ("Storage2", "창고", 2430, 2790),
                        ("InfoDept", "정보부실", 2820, 3380)],
        "bottom_left": [("Dasan6", "다산6실", 20, 1200)],
    },
    3: {
        "north": ["1반", "2반", "3반", "생활지도부", "2학년부", "4반", "5반", "6반", "7반"],
        "south_left": [("Class6", "6반", 20, 720), ("CareerDept", "진로진학부", 750, 1640)],
        "south_right": [("ScienceLab1", "과학실1", 1920, 2400),
                        ("Storage2", "창고", 2430, 2790),
                        ("ScienceLab2", "과학실2", 2820, 3380)],
        "bottom_left": [("CareerRoom", "진로실", 20, 1200)],
    },
    2: {
        "north": ["1반", "2반", "3반", "1학년부", "4반", "5반", "6반", "7반", "8반"],
        "south_left": [("PEStorage", "체육창고", 20, 720), ("PEDept", "체육건강부", 750, 1640)],
        "south_right": [("EduRoom", "교육실", 1920, 2400),
                        ("Storage2", "창고", 2430, 2790),
                        ("ComputerRoom", "컴퓨터실", 2820, 3380)],
        "bottom_left": [],
    },
    5: {   # 프롤로그 전용 — 같은 뼈대, 방 이름만 미술 계열
        "north": ["1반", "2반", "3반", "예술부", "4반", "5반", "6반", "7반"],
        "south_left": [("ArtRoom", "미술실", 20, 720), ("MusicPrep", "음악준비실", 750, 1640)],
        "south_right": [("AVRoom", "시청각실", 1920, 2400),
                        ("Storage2", "창고", 2430, 2790),
                        ("EmptyClass", "빈 교실", 2820, 3380)],
        "bottom_left": [("ArtStorage", "미술창고", 20, 1200)],
    },
}

# 중간 띠 공통(좌): 남/여 화장실 + 막힌 공간
MID_LEFT = [("MensRoomL", "남자 화장실", 800, 1060),
            ("WomensRoomL", "여자 화장실", 1090, 1350),
            ("BlockedL", None, 1380, 1640)]
# 중간 띠 공통(우, 사선): 창고 + 막힌 공간 + 남/여 화장실
MID_RIGHT = [("StorageR", "창고", 1920, 2280),
             ("BlockedR", None, 2310, 2790),
             ("MensRoomR", "남자 화장실", 2820, 3060),
             ("WomensRoomR", "여자 화장실", 3090, 3380)]
# 하단 띠 공통: 남/여 화장실
BOTTOM_RIGHT = [("MensRoomB", "남자 화장실", 2270, 2530),
                ("WomensRoomB", "여자 화장실", 2560, 2820)]

def close_gaps(seq, limit=200, i0=2, i1=3):
    """같은 띠에서 이웃한 방 사이의 틈을 없앤다 — 경계를 틈 한가운데로 옮긴다.

    30px 안팎의 틈은 도면상 아무것도 아닌데 복도로 열린 막다른 골목을 만들었다
    (반 사이 틈과 같은 문제). limit보다 넓은 간격은 계단 접근로처럼 통로일 수
    있으므로 그대로 둔다. 띠가 다른 방끼리는 애초에 같은 리스트에 없다.
    """
    out = [list(r) for r in seq]
    for a, b in zip(out, out[1:]):
        gap = b[i0] - a[i1]
        if 0 < gap <= limit:
            mid = round((a[i1] + b[i0]) / 2, 1)
            a[i1] = mid
            b[i0] = mid
    return [tuple(r) for r in out]


MID_LEFT = close_gaps(MID_LEFT)
MID_RIGHT = close_gaps(MID_RIGHT)
BOTTOM_RIGHT = close_gaps(BOTTOM_RIGHT)
for _spec in LAYOUT.values():
    for _band in ("south_left", "south_right", "bottom_left"):
        _spec[_band] = close_gaps(_spec[_band])


# 1층: 도면이 다르다 — 상단 교실 3칸+운동장출입구+교무실, 하단 계단(좌)·화장실·현관·수위실·창고2
FLOOR1 = {
    "rooms": [   # (키, 라벨, x0, y0, x1, y1, 문 위치)
        ("Class1", "교실1", 20, 1020, 460, 1500, "bottom"),
        ("Class2", "교실2", 490, 1020, 810, 1500, "bottom"),
        ("Class3", "교실3", 840, 1020, 1360, 1500, "bottom"),
        ("YardExit", "운동장 출입구", 1390, 1020, 1920, 1500, None),   # 닫힘
        # 하단 띠는 전부 2120~2480. 예전엔 화장실·창고만 2370이라 그 아래
        # 2370~2500에 걸어 들어갈 수 있는 빈 띠가 남았고, 방 사이 틈이 그 입구
        # 노릇을 했다(수위가 거기 스폰되면 영영 안 보인다).
        ("MensRoom1", "남자 화장실", 900, 2120, 1160, 2480, "top"),
        ("WomensRoom1", "여자 화장실", 1190, 2120, 1450, 2480, "top"),
        ("Entrance", "현관", 1600, 2120, 2000, 2480, "top"),           # 탈출구
        ("JanitorRoom", "수위실", 2100, 2120, 2560, 2480, "top"),
        ("Storage1", "창고", 2620, 2120, 2960, 2480, "top"),
        ("Storage2", "창고", 3000, 2120, 3380, 2480, "top"),
    ],
    "staff": (1950, 1020, 3380, 1500),   # 교무실(사선)
    "stair": (220, 2120, 660, 2440),     # 1층 계단 — 다른 층과 위치가 다르다
}


def _close_floor1():
    """1층은 방 목록이 한 줄로 섞여 있어 같은 y 띠끼리 묶어서 붙인다.

    교무실은 사선이라 따로 들어간다(FLOOR1["staff"]). 그 왼쪽 방을 교무실
    시작 x까지 늘려 틈을 없앤다 — 사선 방의 x0를 옮기면 slope_y 기준점이
    흔들리므로 옆방을 늘리는 쪽이 안전하다.
    """
    rows = {}
    for r in FLOOR1["rooms"]:
        rows.setdefault((r[3], r[5]), []).append(list(r))
    out = []
    for band in rows.values():
        band.sort(key=lambda r: r[2])
        for a, b in zip(band, band[1:]):
            gap = b[2] - a[4]
            if 0 < gap <= 200:
                mid = round((a[4] + b[2]) / 2, 1)
                a[4] = mid
                b[2] = mid
        out.extend(band)
    sx0, sy0, _, sy1 = FLOOR1["staff"]
    for r in out:
        if (r[3], r[5]) == (sy0, sy1) and 0 < sx0 - r[4] <= 200:
            r[4] = sx0
    FLOOR1["rooms"] = [tuple(r) for r in out]


_close_floor1()


# ── 유틸 ────────────────────────────────────────────────────
def n(v):
    return int(v) if float(v) == int(float(v)) else round(float(v), 1)


def poly(*pts):
    return "PackedVector2Array(" + ", ".join(str(n(p)) for xy in pts for p in xy) + ")"


def rect(x0, y0, x1, y1):
    return poly((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _poly_box(polygon):
    """폴리곤 문자열에서 경계상자를 되읽는다 — 집기 목록을 남기는 데 쓴다(#289)."""
    vals = [float(v) for v in
            polygon[polygon.index("(") + 1:polygon.rindex(")")].split(",")]
    xs, ys = vals[0::2], vals[1::2]
    return (min(xs), min(ys), max(xs), max(ys))


class Scene:
    """노드/서브리소스를 모아 .tscn 텍스트로 직렬화."""

    def __init__(self):
        self.subs = []      # (id, polygon)
        self.nodes = []     # 텍스트 블록
        self.rect_shapes = []
        self.rooms = {}
        self.room_meta = {}   # key -> 집기 배치에 필요한 방 형상(add_props가 읽는다)
        self.clue_pts = []    # 단서·은신처 좌표 — 집기가 덮으면 조사할 수 없다
        self.furniture = []   # add_furniture가 손으로 놓은 가구 — 절차적 집기가 피한다
        self.corridor_props = []  # 복도에 선 집기 — 복도 장식이 피한다
        self.prop_rects = []      # (이름, 경계상자, 색) — add_clutter가 훑는다(#289)
        self.overlay_rects = []   # 이미 놓인 소품 — 겹쳐 놓지 않으려고
        self.raw_subs = []    # 손으로 쓴 sub_resource 블록(달빛 그라디언트)
        self.floor_no = 0     # 창밖 묘사가 층마다 다르다

    def occ(self, oid, polygon):
        self.subs.append((oid, polygon))

    def node(self, text):
        self.nodes.append(text)

    def poly2d(self, name, parent, color, polygon, z=None):
        z_line = f"z_index = {z}\n" if z is not None else ""
        tex_line = ""
        # 오브젝트 그림이 재질보다 우선한다(#259). 물건 하나에 한 장을 맞춰 늘리려고
        # 로컬 UV를 넣는다 — 재질은 UV를 비워 월드 격자에 정렬시키는 것과 반대다.
        obj = SPRITE.get(color)
        stem = obj or TEX.get(color)
        if stem:
            tex_line = f'texture = ExtResource("tex_{stem}")\n'
            if obj:
                tex_line += f"uv = {uv_for(polygon)}\n"
            color = tex_color(color)
            if obj:
                color = shade_jitter(color, name)
            # 층 씬 루트와 RoomWallVisuals에 걸어 둔 Nearest·Repeat를 물려받는다.
            # CanvasLayer 직속 노드(계단 난간)는 물려받을 부모가 없어 직접 적는다.
            if parent in CANVAS_ITEM_ROOTS:
                tex_line = TEX_FLAGS + tex_line
        self.node(f'[node name="{name}" type="Polygon2D" parent="{parent}"]\n'
                  f'{z_line}{tex_line}color = {color}\npolygon = {polygon}\n')

    def solid(self, key, parent_body, polygon):
        """충돌 + 광원차단 한 쌍 (시각은 별도로 추가)."""
        self.node(f'[node name="{key}" type="CollisionPolygon2D" parent="{parent_body}"]\n'
                  f'polygon = {polygon}\n')
        oid = f"Occ_{key}"
        self.occ(oid, polygon)
        self.node(f'[node name="LO_{key}" type="LightOccluder2D" parent="{parent_body}"]\n'
                  f'occluder = SubResource("{oid}")\n')

    def wall(self, key, polygon, body="RoomWalls"):
        """벽 3종 세트: 충돌 WC_ + 시각 WV_(WallGlow) + 광원차단 LO_WC_.

        가로 벽에는 **앞면**(WF_)을 하나 더 낸다(#268). 위에서 내려다본 16px 띠
        하나만 그리면 두께만 있고 높이가 없어 건축 도면처럼 보인다. 아래쪽에
        면을 덧그리면 벽이 서 있는 것으로 읽힌다.

        앞면은 **시각 전용**이다 — 충돌·광원 차단체는 그대로 16px 띠에 있어서
        통행과 시야 판정이 바뀌지 않는다. 세로 벽에는 그리지 않는다(탑다운에서
        앞면이 보이는 것은 시선과 마주 보는 가로 벽뿐이다).
        """
        self.solid(f"WC_{key}", body, polygon)
        self.poly2d(f"WV_{key}", "WallGlow/RoomWallVisuals", C_WALL, polygon)
        nums = [float(v) for v in
                polygon[polygon.index("(") + 1:polygon.rindex(")")].split(",")]
        xs, ys = nums[0::2], nums[1::2]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        if w > h * 1.5:                       # 가로 벽만
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            # 3단으로 나눈다 — 윗변 하이라이트 / 앞면 / 바닥에 닿는 그림자.
            # 면 하나만 두면 밝기가 같은 띠 두 개라 여전히 납작해 보인다(#271).
            self.poly2d(f"WH_{key}", "WallGlow/RoomWallVisuals", C_WALL_TOP,
                        rect(x0, y0, x1, y0 + 3))
            self.poly2d(f"WF_{key}", "WallGlow/RoomWallVisuals", C_FACE,
                        rect(x0, y1, x1, y1 + WALL_FACE - 4))
            self.poly2d(f"WS_{key}", "WallGlow/RoomWallVisuals", C_WALL_SHADOW,
                        rect(x0, y1 + WALL_FACE - 4, x1, y1 + WALL_FACE))

    def prop(self, key, polygon, color):
        """방 안 집기: 충돌 PC_ + 시각 PV_ 한 쌍.

        벽(WC_/LO_)과 달리 광원 차단체를 달지 않는다. 책상·선반은 사람 키보다
        낮다는 설정이고, 차단체를 달면 방마다 그림자가 갈라져 조명 튜닝(#74)이
        전부 흔들린다. verify_scenes의 벽↔차단체 1:1 검사도 접두사로 구분한다.
        """
        self.node(f'[node name="PC_{key}" type="CollisionPolygon2D" parent="PropBodies"]\n'
                  f'polygon = {polygon}\n')
        self.poly2d(f"PV_{key}", "Props", color, polygon)
        self.prop_rects.append((key, _poly_box(polygon), color))

    def window_light(self, key, x, y, room):
        """창으로 드는 달빛 — 진짜 광원(#274).

        `Lights`(Node2D, 씬 루트)에 둔다. **WallGlow에 두면 안 된다** —
        CanvasLayer는 별도 캔버스라 그 안의 광원은 아래 레이어의 바닥·집기를
        못 비춘다.

        그림자를 켜야 벽(LO_)에 막혀 옆 방·복도로 새지 않는다. 광원은 화면
        밖이면 컬링되므로 층당 서른 개를 달아도 카메라(1600x900)에 드는 것은
        대여섯 개뿐이다.
        """
        self.node(NL.join([
            f'[node name="WinLight_{key}" type="PointLight2D" parent="Lights/Room_{room}"]',
            f"position = Vector2({x:.1f}, {y:.1f})",
            f"color = {C_MOON_LIGHT}",
            f"energy = {MOON_ENERGY}",
            "shadow_enabled = true",
            "shadow_filter = 1",
            "shadow_filter_smooth = 4.0",
            'texture = SubResource("GradientTexture2D_moon")',
            f"texture_scale = {MOON_SCALE}",
            ""]))
    def room_lights(self, key, x0, y0, x1, y1):
        """방 창문 달빛을 묶는 Area2D(#292). 평소에는 꺼져 있다.

        광원을 늘 켜 두면 **닫힌 문 너머 방 안이 다 보인다** — Godot 2D에는
        시야 판정이 없어서, 켜진 자리는 플레이어가 어디 있든 화면에 그려진다.
        벽·문짝 차단체는 빛이 방 밖으로 새는 것만 막는다.

        방 감지에 `CollisionPolygon2D`를 쓰면 안 된다 — `verify_props`가
        `PropBodies` 밖의 모든 폴리곤 충돌을 **벽**으로 세고
        `verify_floor_reach`가 그것을 막힌 것으로 봐서 방이 통행 불가가 된다.
        """
        sid = f"RectangleShape2D_room_{key}"
        self.rect_shapes.append((sid, f"Vector2({n(x1 - x0)}, {n(y1 - y0)})"))
        self.node(NL.join([
            f'[node name="Room_{key}" type="Area2D" parent="Lights"]',
            "collision_layer = 0",
            "collision_mask = 1",
            'script = ExtResource("7_roomlights")',
            "",
            f'[node name="Zone" type="CollisionShape2D" parent="Lights/Room_{key}"]',
            f"position = Vector2({n((x0 + x1) / 2)}, {n((y0 + y1) / 2)})",
            f'shape = SubResource("{sid}")',
            ""]))

    def window_probe(self, key, x, y, message):
        """창가 조사(E) — 방마다 하나.

        창마다 달면 층당 서른 개가 되는데, `_find_interactable`는 겹친 것 중
        **아무거나** 돌려주므로 창문이 단서를 가로챌 수 있다.
        """
        name = f"Window_{key}"
        self.node(NL.join([
            f'[node name="{name}" type="Area2D" parent="."]',
            f"position = Vector2({x:.1f}, {y:.1f})",
            "collision_layer = 2",
            "collision_mask = 0",
            'script = ExtResource("3_interactable")',
            f'message = "{message}"',
            'prompt_text = "창밖 보기"',
            "",
            f'[node name="{name}Zone" type="CollisionShape2D" parent="{name}"]',
            'shape = SubResource("RectangleShape2D_window_zone")',
            ""]))

    def wall_decor(self, key, polygon, color):
        """벽면에 붙는 장식 — WallGlow 안이라 어둠을 받지 않고 벽 위에 그려진다.

        Props(레이어 0)에 두면 CanvasLayer인 WallGlow의 벽 시각이 덮어
        아예 안 보인다(#234와 같은 함정).
        """
        self.poly2d(f"WD_{key}", "WallGlow/RoomWallVisuals", color, polygon, z=1)

    def floor_mark(self, key, polygon, color):
        """방 바닥 표시 — 방 바닥 위, 집기 아래. 가구 밑에 깔리는 것이 정상이라

        장식(PD_)으로 내면 verify_props가 집기와 겹쳤다고 잡는다. 바닥에
        그리는 것과 벽·가구에 붙는 것은 레이어가 달라야 한다.
        """
        self.poly2d(f"FM_{key}", "RoomMarks", color, polygon)

    def ground(self, key, polygon, color):
        """바닥 구역 — Rooms보다 먼저 선언되는 Ground 아래. 충돌 없음."""
        self.poly2d(f"G_{key}", "Ground", color, polygon)

    def decor(self, key, polygon, color):
        """벽에 붙는 장식 — 충돌체가 없다(칠판·게시판).

        통행에 전혀 영향을 주지 않으므로 도달성·순찰 검사가 흔들릴 걱정 없이
        복도와 교실에 정보를 더할 수 있다. PC_/PV_와 접두사를 나눠서
        verify_props가 짝 검사에서 제외한다.
        """
        self.poly2d(f"PD_{key}", "Props", color, polygon)

    def overlay(self, key, polygon, color):
        """집기 위에 놓이는 소품 — 충돌 없음(책상 위 교과서, 선반의 책).

        장식(PD_)과 접두사를 나눈다. PD_는 집기와 겹치면 안 되지만 PT_는
        겹치는 게 정상이고, 대신 어느 집기 안에 온전히 들어가야 한다.
        """
        self.poly2d(f"PT_{key}", "Props", color, polygon)
        self.overlay_rects.append(_poly_box(polygon))

    def label(self, name, text, cx, cy):
        # 주의: offset은 실수 하나여야 한다. 예전엔 f"{n(v)}.0" 이라 폭이 소수인 층에서
        # "92.4.0" 같은 깨진 값이 나왔다(#159 라벨 미표시 원인).
        # 부모는 WallGlow — 어둠(CanvasModulate) 곱연산을 받지 않아야 읽힌다(#117·#130과 동일).
        self.node(f'[node name="L_{name}" type="Label" parent="WallGlow/Labels"]\n'
                  f'offset_left = {cx - 110:.1f}\noffset_top = {cy - 16:.1f}\n'
                  f'offset_right = {cx + 110:.1f}\noffset_bottom = {cy + 16:.1f}\n'
                  f'theme_override_colors/font_color = Color(0.78, 0.81, 0.88, 1)\n'
                  f'theme_override_colors/font_outline_color = Color(0, 0, 0, 1)\n'
                  f'theme_override_constants/outline_size = 4\n'
                  f'theme_override_font_sizes/font_size = 22\n'
                  f'text = "{text}"\nhorizontal_alignment = 1\n')

    def render(self, ext):
        steps = (len(ext) + len(self.subs) + len(self.rect_shapes)
                 + len(self.raw_subs) + 1)
        out = [f"[gd_scene load_steps={steps} format=3]\n"]
        for e in ext:
            out.append(e)
        out.append("")
        for sid, size in self.rect_shapes:
            out.append(f'[sub_resource type="RectangleShape2D" id="{sid}"]\nsize = {size}\n')
        for oid, p in self.subs:
            out.append(f'[sub_resource type="OccluderPolygon2D" id="{oid}"]\npolygon = {p}\n')
        out.extend(self.raw_subs)
        out.append("")
        out.extend(self.nodes)
        return "\n".join(out)


# 창밖 묘사(#274) — 층마다 셋을 돌려 쓴다. 방 이름으로 고르므로 재생성해도
# 같은 방에 같은 대사가 붙는다.
WINDOW_LINES = {
    1: [
        '운동장이 내려다보인다. 가로등 하나만 켜져 있고 그 아래엔 아무도 없다.',
        '정문 쪽 유리다. 철문이 사슬로 감겨 있다. 안쪽에서 잠근 모양이다.',
        '화단 흙이 한 군데만 파헤쳐져 있다. 삽이 그대로 꽂혀 있다.',
    ],
    2: [
        '창틀에 먼지가 두껍게 앉았다. 손자국 하나가 안쪽에서 찍혀 있다.',
        '유리에 복도가 비친다. 뒤를 돌아봤지만 아무도 없다.',
        '빗물 자국 사이로 운동장 트랙이 보인다. 흰 선이 반쯤 지워져 있다.',
    ],
    3: [
        '운동장 구석 창고 앞에서 불빛이 하나 움직인다. 손전등 같다. 곧 꺼진다.',
        '창문이 3cm쯤 열려 있다. 바람이 들어오는데 커튼은 흔들리지 않는다.',
        '유리에 금이 가 있다. 밖에서 뭔가 부딪친 자국이다. 여기는 3층인데.',
    ],
    4: [
        '여기서는 담장 너머 도로까지 보인다. 차가 한 대도 지나가지 않는다.',
        '창문이 못으로 박혀 있다. 새 못이다. 머리에 아직 광이 남아 있다.',
        '옥상 물탱크 그림자가 운동장에 길게 누워 있다. 그 끝이 조금씩 움직인다.',
    ],
    5: [
        '옥상으로 이어지는 계단참 창이다. 유리에 손자국이 안쪽에서 찍혀 있다.',
        '학교에서 제일 높은 창이다. 운동장 조명이 전부 꺼져 있다.',
        '창밖으로 비상계단이 보인다. 난간에 교복 재킷 하나가 걸려 있다.',
    ],
}


def window_text(floor_no, key):
    lines = WINDOW_LINES.get(floor_no) or WINDOW_LINES[2]
    return lines[sum(ord(c) for c in key) % len(lines)]


def add_lights_root(sc):
    """창문 광원이 들어갈 `Lights`와 달빛 그라디언트를 낸다(#274).

    씬 골격에서 부른다. 광원은 그려지는 것이 아니라 다른 것을 밝히므로
    선언 순서(레이어)와 무관하다 — 다만 자식보다 먼저 있어야 한다.
    """
    sc.node(NL.join(['[node name="Lights" type="Node2D" parent="."]', '']))
    sc.raw_subs.append(NL.join([
        '[sub_resource type="Gradient" id="Gradient_moon"]',
        'offsets = PackedFloat32Array(0, 0.5, 1)',
        'colors = PackedColorArray(1, 1, 1, 1, 1, 1, 1, 0.35, 1, 1, 1, 0)',
        '']))
    sc.raw_subs.append(NL.join([
        '[sub_resource type="GradientTexture2D" id="GradientTexture2D_moon"]',
        'gradient = SubResource("Gradient_moon")',
        'width = 512',
        'height = 512',
        'fill = 1',
        'fill_from = Vector2(0.5, 0.5)',
        'fill_to = Vector2(0.5, 0)',
        '']))


def add_room(sc, key, label, x0, y0, x1, y1, door):
    """축정렬 방: 바닥 + 사방 벽(+문 틈). door in {top,bottom,left,right,None}."""
    sc.rooms[key] = (x0, y0, x1, y1)
    sc.room_meta[key] = (label, door, x0, x1,
                         lambda x, v=y0: v, lambda x, v=y1: v)
    sc.poly2d(key, "Rooms", room_floor(key, label), rect(x0, y0, x1, y1))
    if label:
        sc.label(key, label, (x0 + x1) / 2, (y0 + y1) / 2)

    cx = (x0 + x1) / 2
    dl, dr = cx - DOOR / 2, cx + DOOR / 2
    cy = (y0 + y1) / 2
    dt, db = cy - DOOR / 2, cy + DOOR / 2

    if door == "top":
        sc.wall(f"{key}_topL", rect(x0, y0, dl, y0 + T))
        sc.wall(f"{key}_topR", rect(dr, y0, x1, y0 + T))
        sc.poly2d(f"Door_{key}", "WallGlow/RoomWallVisuals", C_DOOR, rect(dl, y0, dr, y0 + T), z=1)
        sc.wall(f"{key}_bot", rect(x0, y1 - T, x1, y1))
    elif door == "bottom":
        sc.wall(f"{key}_top", rect(x0, y0, x1, y0 + T))
        sc.wall(f"{key}_botL", rect(x0, y1 - T, dl, y1))
        sc.wall(f"{key}_botR", rect(dr, y1 - T, x1, y1))
        sc.poly2d(f"Door_{key}", "WallGlow/RoomWallVisuals", C_DOOR, rect(dl, y1 - T, dr, y1), z=1)
    else:   # 막힌 공간: 사방 폐쇄
        sc.wall(f"{key}_top", rect(x0, y0, x1, y0 + T))
        sc.wall(f"{key}_bot", rect(x0, y1 - T, x1, y1))

    if door == "left":
        sc.wall(f"{key}_leftT", rect(x0, y0, x0 + T, dt))
        sc.wall(f"{key}_leftB", rect(x0, db, x0 + T, y1))
        sc.poly2d(f"Door_{key}", "WallGlow/RoomWallVisuals", C_DOOR, rect(x0, dt, x0 + T, db), z=1)
    else:
        sc.wall(f"{key}_left", rect(x0, y0, x0 + T, y1))

    if door == "right":
        sc.wall(f"{key}_rightT", rect(x1 - T, y0, x1, dt))
        sc.wall(f"{key}_rightB", rect(x1 - T, db, x1, y1))
        sc.poly2d(f"Door_{key}", "WallGlow/RoomWallVisuals", C_DOOR, rect(x1 - T, dt, x1, db), z=1)
    else:
        sc.wall(f"{key}_right", rect(x1 - T, y0, x1, y1))


# 본편에서 오갈 수 있는 층 범위 — floor_manager.gd의 MIN_FLOOR/MAX_FLOOR와 맞춘다.
MIN_FLOOR, MAX_FLOOR = 1, 4
C_ARROW = "Color(0.55, 0.8, 0.85, 1)"


def add_stair_markers(sc, name, x0, y0, x1, y1, floor):
    """계단실 반쪽마다 방향 표시: 왼쪽=위층 ▲ / 오른쪽=아래층 ▼ (기존 규약).
    본편에서 갈 수 없는 방향(4층에서 위, 1층에서 아래)은 표시하지 않는다."""
    mid = (x0 + x1) / 2
    cy = y0 + 104
    s = 26
    for cx, target, up in (((x0 + mid) / 2, floor + 1, True),
                           ((mid + x1) / 2, floor - 1, False)):
        if not (MIN_FLOOR <= target <= MAX_FLOOR):
            continue
        tag = "Up" if up else "Dn"
        if up:
            tri = poly((cx, cy - s), (cx + s * 0.9, cy + s * 0.6), (cx - s * 0.9, cy + s * 0.6))
        else:
            tri = poly((cx, cy + s), (cx + s * 0.9, cy - s * 0.6), (cx - s * 0.9, cy - s * 0.6))
        sc.poly2d(f"Arrow_{name}_{tag}", "WallGlow", C_ARROW, tri, z=2)
        sc.label(f"{name}_{tag}", f"{target}층", cx, cy + 58)


SCRIPTS = {
    "1_locked_door": "res://scripts/interactions/locked_door.gd",
    "2_pickup": "res://scripts/interactions/pickup_item.gd",
    "3_interactable": "res://scripts/interactions/interactable.gd",
    "4_exit": "res://scripts/interactions/exit_door.gd",
    "5_hiding": "res://scripts/interactions/hiding_spot.gd",
    "6_sliding": "res://scripts/interactions/sliding_door.gd",
    "7_roomlights": "res://scripts/game/room_lights.gd",
}


def text_of(sc):
    return "".join(sc.nodes)


def ext_for(body):
    """실제로 참조된 스크립트·타일만 ext_resource로 선언한다(미사용 선언 방지).

    verify_scenes가 load_steps = ext + sub + 1과 파일 존재를 검사하므로, 참조하지 않는
    타일을 선언해 두면 바로 걸린다.
    """
    out = [f'[ext_resource type="Script" path="{path}" id="{rid}"]'
           for rid, path in SCRIPTS.items() if f'ExtResource("{rid}")' in body]
    out += [f'[ext_resource type="Texture2D" path="{path}" id="{rid}"]'
            for rid, path in TEXTURES.items() if f'ExtResource("{rid}")' in body]
    return out


EXT_LOCKED_DOOR = ('[ext_resource type="Script" '
                   'path="res://scripts/interactions/locked_door.gd" id="1_locked_door"]')
EXT_PICKUP = ('[ext_resource type="Script" '
              'path="res://scripts/interactions/pickup_item.gd" id="2_pickup"]')

# ── 진행 요소 배치 (#159 P3 / #161 선택지 3: 기획서를 새 맵에 맞게 개정) ──
# 단서 노드의 본문(플래그·메시지·스크립트)은 tools/story_objects.json에 main에서
# 추출해 두고 위치만 새 방으로 옮긴다. 플래그 ID를 유지해야 엔딩 판정이 깨지지 않는다.
# 기획서의 방이 새 도면에 없어 대체한 곳은 주석에 원래 방을 적는다.
PLACEMENT = {
    4: [("Dasan7", ["DasanStairKey", "FriendNote"]),              # 다산실
        ("CreativeDept", ["CounselRecord", "SiwooPainting"]),     # ← 상담실
        ("InfoDept", ["CrisisManual", "InkCan"]),                 # ← 인쇄실
        # 4층 계단 열쇠는 다산7실 하나로 충분하다 — 중복 열쇠 제거(#219).
        # story_objects.json의 StairKey 항목은 남겨 둔다(되돌리기 쉽게).
        ("ComputerRoom", ["ScienceClue"]),                        # ← 과학 실험실
        ("Dasan6", ["HistoryClue"]),                              # ← 역사자료실
        ("Storage2", ["TaehoNote"])],                             # ← 수학교구실
    3: [("North4", ["NayeonClue"]),                               # 생활지도부 ← 방송실
        ("North5", ["JanitorWarning", "KeyCabinet", "SpareKeyHook"]),  # 2학년부 ← 교무실
        ("CareerRoom", ["ReportFlyer"]),                          # 진로실 ← 학생회실
        ("North2", ["HideClass2"]), ("North7", ["HideClass5"]),
        ("Storage2", ["HideBroadcastRoom"])],
    2: [("PEStorage", ["YujinClue"]),                             # 체육창고 ← 체육관 입구
        ("MensRoomB", ["ShowerMarks", "DrainKey", "HideShower"]), # 화장실 ← 샤워실
        ("EduRoom", ["SeunghoClue"]),                             # 교육실 ← 2층 교무실
        ("North1", ["HideClass1"]), ("North7", ["HideClass6"])],
    1: [("StaffRoom", ["PrincipalLetter"]),                       # 교무실 ← 교장실
        ("JanitorRoom", ["PhotoWall", "StudentCards", "JanitorNotebook", "JanitorSafe"]),
        ("Storage1", ["StairKey"]),                               # 창고 ← 행정실
        ("Entrance", ["ExitDoor"]),
        ("Class1", ["HideClass1_1"]), ("Class3", ["HideMusicRoom"]),
        ("Storage2", ["HideEmptyRoom"])],
    5: [("ArtRoom", ["Blackboard", "ArtRoomDoorLock"]),
        ("ArtStorage", ["StairKey"])],
}
# 영구 봉인 계단(열쇠로도 열리지 않음). 2층 하단 중앙 계단은 그 아래가 1층
# 현관·중앙 구역이라 계단이 내려갈 자리가 없다 — 도면 구조를 지키려고 막는다.
SEALED = {2: {1}}

# 각 층 계단은 그 층 열쇠로 연다. 열쇠 획득처는 PLACEMENT 참조(한 층 위에서도 얻는다).
LOCKED = {1: "stair_key_1", 2: "stair_key_2", 3: "stair_key_3",
          4: "stair_key_4", 5: "stair_key_5"}


# 특정 단서의 위치를 방 안 자동 배치 대신 직접 지정한다.
# 현관(ExitDoor)은 바깥으로 나가는 아래쪽 정문 앞에 둬야 안내와 실제 위치가 맞는다.
POS_OVERRIDE = {
    (1, "ExitDoor"): (1800, 2432),
    # 4층 창의체험부(750,1520)~(1640,1940) — 자동 배치는 방 한가운데라 대사와 어긋났다(#215).
    # 액자는 "벽에 걸린" 것이므로 아래쪽 벽 안쪽에 붙이고,
    # 상담기록부는 아래에 깐 책상 위(FURNITURE의 DeskCreativeDept)에 올린다.
    (4, "SiwooPainting"): (1350, 1906),
    (4, "CounselRecord"): (1045, 1752),
    # 3층 2학년부(1527.6,20)~(1872.4,540), 내벽 안쪽 (1543.6,36)~(1856.4,524).
    # 자동 배치는 방 한가운데 = 아래변 문(x 1645~1755) 정면이라 벽걸이 보관함이
    # 허공에 떠 보이고 통행도 막았다(#227). 위쪽 벽 왼쪽 구석에 붙이고,
    # "보관함 옆 고리"인 SpareKeyHook을 같은 벽면 오른쪽에 나란히 둔다.
    (3, "KeyCabinet"): (1560, 54),
    (3, "SpareKeyHook"): (1620, 50),
}

# 방 안 가구(시각 전용). 충돌은 넣지 않는다 — 통행·수위 경로탐색·도달성 검사에
# 영향을 주기 때문. 단서보다 먼저 그려서 아래에 깔린다.
FURNITURE = {
    4: [("DeskCreativeDept", 960, 1720, 1130, 1800)],
}
# C_DESK는 위쪽 집기 색 블록에 이미 있다. #215가 여기서 다시 정의하고 있었는데
# 나중 정의가 이겨서 절차적 집기 색이 전부 그 값으로 덮였다.


def add_furniture(sc, floor):
    """단서를 받치는 손배치 가구(시각 전용). add_props의 절차적 집기와 별개다.

    add_props보다 먼저 돌고, 놓은 사각형을 sc.furniture에 남긴다 —
    절차적 집기가 그 위에 겹쳐 깔리지 않게 하려는 것이다.
    """
    items = FURNITURE.get(floor, [])
    if not items:
        return
    sc.node('[node name="Furniture" type="Node2D" parent="."]\n')
    for name, x0, y0, x1, y1 in items:
        sc.poly2d(name, "Furniture", C_DESK, rect(x0, y0, x1, y1))
        sc.furniture.append((x0, y0, x1, y1))

# 열쇠를 주는 오브젝트는 층에 상관없이 "다가가면 획득"으로 통일한다(사용자 요청).
# 원래는 4층 열쇠 2개만 pickup_item(접촉)이고 나머지는 interactable(E 필요)이라
# 층마다 조작이 달랐다. 메시지와 플래그는 그대로 옮긴다.
# KeyCabinet은 #207에서 열쇠 지급을 뗐으므로 여기 들어가지 않는다(E 조사 단서).
# TaehoNote는 #222에서 열쇠 지급을 뗐으므로 여기 들어가지 않는다(E 조사 단서).
AUTO_PICKUP = {"SpareKeyHook", "DrainKey", "JanitorSafe"}


def to_pickup(body):
    """interactable(E 조사) 노드를 pickup_item(접촉 획득)으로 바꾼다."""
    if "required_item_id" in body:
        raise SystemExit("조건부 조사 오브젝트는 접촉 획득으로 바꿀 수 없다")
    body = body.replace('script = ExtResource("3_interactable")',
                        'script = ExtResource("2_pickup")')
    body = body.replace("\ngrants_item_id = ", "\nitem_id = ")
    body = body.replace("\ngrants_flag = ", "\npickup_id = ")
    # 접촉 감지: 플레이어 몸(레이어 1)을 이 Area2D가 감지해야 한다
    body = body.replace("collision_layer = 2\ncollision_mask = 0",
                        "collision_layer = 0\ncollision_mask = 1")
    body = re.sub(r"^prompt_text = .*\n", "", body, flags=re.M)
    # 접촉 획득은 다시 지나가기 쉬우므로 획득 기록이 없으면 층 재방문 때 중복된다.
    if "pickup_id = " not in body:
        node = re.search(r'\[node name="(\w+)"', body).group(1)
        body = body.rstrip("\n") + f'\npickup_id = "{node.lower()}_taken"\n'
    return body


# 추가 은신처(#172 후속): 층마다 두 곳씩 더 둔다. 기존 은신처는
# story_objects.json에서 오고, 여기 있는 것은 새로 만드는 것이다.
# 방 안 위쪽(0.3 지점)에 놓아 단서 오브젝트(0.62 지점)와 겹치지 않게 한다.
EXTRA_HIDING = {
    4: [("HideInfoDept", "InfoDept", "사물함에 숨기",
         "정보부실 사물함. 종이 냄새와 먼지 사이에 몸을 접었다."),
        ("HideDasan6", "Dasan6", "청소함에 숨기",
         "청소함 안. 대걸레 자루가 어깨를 누른다.")],
    3: [("HideScienceLab1", "ScienceLab1", "약품장에 숨기",
         "약품장 아래 칸. 시큼한 냄새에 숨이 막힌다."),
        ("HideCareerDept", "CareerDept", "서류함에 숨기",
         "서류함 뒤 빈 공간. 파일 더미에 등을 붙였다.")],
    2: [("HideEduRoom", "EduRoom", "사물함에 숨기",
         "교육실 사물함. 문틈으로 복도가 가늘게 보인다."),
        ("HidePEDept", "PEDept", "장비함에 숨기",
         "체육 장비함. 공 사이에 몸을 밀어 넣었다.")],
    1: [("HideStorage1", "Storage1", "적재함에 숨기",
         "창고 적재함 뒤. 먼지가 목을 긁는다."),
        ("HideWomensRoom1", "WomensRoom1", "칸에 숨기",
         "화장실 칸 안. 문고리를 안에서 붙잡았다.")],
}


def add_hiding(sc, floor):
    """은신처 Area2D + 캐비닛 시각 + 상호작용 존을 방 안에 만든다."""
    spots = EXTRA_HIDING.get(floor, [])
    for i, (name, room_key, prompt, message) in enumerate(spots):
        if room_key not in sc.rooms:
            raise SystemExit(f"floor{floor}: 은신처 대상 방 {room_key}가 없다")
        x0, y0, x1, y1 = sc.rooms[room_key]
        cx = x0 + (i + 1) * (x1 - x0) / (len(spots) + 1)
        cy = y0 + (y1 - y0) * 0.30
        sc.clue_pts.append((cx, cy))
        sc.node(f'[node name="{name}" type="Area2D" parent="."]\n'
                f'position = Vector2({n(cx)}, {n(cy)})\n'
                f'collision_layer = 2\ncollision_mask = 0\n'
                f'script = ExtResource("5_hiding")\n'
                f'prompt_text = "{prompt}"\nmessage = "{message}"\n')
        # 사물함·청소함 상자 — 색을 C_LOCKER로 맞춰 다른 금속 집기와 같은 타일을 받는다.
        sc.poly2d(f"{name}Visual", name, C_LOCKER, rect(-18, -26, 18, 26), z=1)
        sc.node(f'[node name="{name}Zone" type="CollisionShape2D" parent="{name}"]\n'
                f'shape = SubResource("RectangleShape2D_key_zone")\n')


def add_story(sc, floor):
    """추출해 둔 단서 노드를 방 안에 배치. 본문은 그대로, position만 새 좌표."""
    data = json.loads((pathlib.Path(__file__).parent / "story_objects.json").read_text())
    nodes = data[str(floor)]
    for room_key, names in PLACEMENT.get(floor, []):
        if room_key not in sc.rooms:
            raise SystemExit(f"floor{floor}: 배치 대상 방 {room_key}가 없다")
        x0, y0, x1, y1 = sc.rooms[room_key]
        for i, name in enumerate(names):
            if name not in nodes:
                raise SystemExit(f"floor{floor}: 단서 노드 {name}를 찾을 수 없다")
            if (floor, name) in POS_OVERRIDE:
                cx, cy = POS_OVERRIDE[(floor, name)]
            else:
                cx = x0 + (i + 1) * (x1 - x0) / (len(names) + 1)
                cy = y0 + (y1 - y0) * 0.62  # 라벨(중앙)과 겹치지 않게 아래쪽
            body = re.sub(r"^position = Vector2\([^)]*\)$",
                          f"position = Vector2({n(cx)}, {n(cy)})",
                          nodes[name]["body"], count=1, flags=re.M)
            sc.clue_pts.append((cx, cy))
            if name in AUTO_PICKUP:
                body = to_pickup(body)
            sc.node(body if body.endswith("\n") else body + "\n")
            for kid in nodes[name]["kids"]:
                sc.node(kid if kid.endswith("\n") else kid + "\n")


def add_stair_locks(sc, floor, key_id, stairwells):
    """계단 입구 자물쇠. 한 층의 계단 전부를 열쇠 하나로 연다(기존 규약).
    SEALED에 든 계단은 열쇠로도 열리지 않으므로, 배리어를 StairLocks 밖에 두어
    자물쇠가 풀려도 남게 하고 자물쇠 대신 안내 문구만 붙인다."""
    sealed = SEALED.get(floor, set())
    tags = ["SU", "SD"][:len(stairwells)]
    sc.node('[node name="StairLocks" type="Node2D" parent="."]\n')
    if sealed:
        sc.node('[node name="SealedStairs" type="Node2D" parent="."]\n')

    visual_paths = []
    for i, (tag, (x0, y0, x1, y1)) in enumerate(zip(tags, stairwells)):
        mid = (x0 + x1) / 2
        bar = rect(mid - DOOR, y0, mid + DOOR, y0 + T)
        if i in sealed:
            sc.node(f'[node name="{tag}Seal" type="StaticBody2D" parent="SealedStairs"]\n')
            sc.solid(f"{tag}SealCollision", f"SealedStairs/{tag}Seal", bar)
            sc.poly2d(f"{tag}SealVisual", "WallGlow", C_SEAL, bar, z=2)
        else:
            sc.node(f'[node name="{tag}Barrier" type="StaticBody2D" parent="StairLocks"]\n')
            sc.solid(f"{tag}BarrierCollision", f"StairLocks/{tag}Barrier", bar)
            sc.poly2d(f"{tag}BarrierVisual", "WallGlow", C_LOCK, bar, z=2)
            visual_paths.append(f'NodePath("../WallGlow/{tag}BarrierVisual")')

    open_tags = [tg for i, tg in enumerate(tags) if i not in sealed]
    for i, (tag, (x0, y0, x1, y1)) in enumerate(zip(tags, stairwells)):
        mid = (x0 + x1) / 2
        if i in sealed:
            sc.node(
                f'[node name="{tag}Sealed" type="Area2D" parent="."]\n'
                f'position = Vector2({n(mid)}, {n(y0 - 24)})\n'
                f'collision_layer = 2\ncollision_mask = 0\n'
                f'script = ExtResource("3_interactable")\n'
                f'message = "계단 입구가 콘크리트로 메워져 있다. 아래층으로는 통하지 않는다."\n'
                f'prompt_text = "계단 살펴보기"\n')
            sc.node(f'[node name="{tag}SealedZone" type="CollisionShape2D" parent="{tag}Sealed"]\n'
                    f'shape = SubResource("RectangleShape2D_stair_zone")\n')
            continue
        removes = [f'NodePath("../{o}Lock")' for o in open_tags if o != tag] + visual_paths
        sc.node(
            f'[node name="{tag}Lock" type="Area2D" parent="."]\n'
            f'position = Vector2({n(mid)}, {n(y0 + T / 2)})\n'
            f'collision_layer = 2\ncollision_mask = 0\n'
            f'script = ExtResource("1_locked_door")\n'
            f'required_item_id = "{key_id}"\n'
            f'locked_message = "계단 입구가 잠겨 있다. 이 층 어딘가에 열쇠가 있을 것이다."\n'
            f'open_message = "계단 자물쇠를 열었다."\n'
            f'barrier_path = NodePath("../StairLocks")\n'
            f'prompt_text = "계단 열기"\n'
            f'door_id = "stairs_f{floor}_unlocked"\n'
            f'consume_key = true\n'
            f'also_remove_paths = Array[NodePath]([{", ".join(removes)}])\n')
        sc.node(f'[node name="{tag}LockZone" type="CollisionShape2D" parent="{tag}Lock"]\n'
                f'shape = SubResource("RectangleShape2D_stair_zone")\n')


def add_keys(sc, floor):
    for name, item_id, x, y, msg in KEYS.get(floor, []):
        sc.node(f'[node name="{name}" type="Area2D" parent="."]\n'
                f'position = Vector2({n(x)}, {n(y)})\n'
                f'collision_layer = 0\ncollision_mask = 1\n'
                f'script = ExtResource("2_pickup")\n'
                f'item_id = "{item_id}"\nmessage = "{msg}"\n'
                f'pickup_id = "{item_id}_taken"\n')
        sc.node(f'[node name="{name}Visual" type="Polygon2D" parent="{name}"]\n'
                f'z_index = 2\ncolor = {C_KEY}\n'
                f'polygon = {rect(-11, -5, 11, 5)}\n')
        sc.node(f'[node name="{name}Zone" type="CollisionShape2D" parent="{name}"]\n'
                f'shape = SubResource("RectangleShape2D_key_zone")\n')


def add_stairwell(sc, name, x0, y0, x1, y1):
    """계단실: 바닥 + 계단 단 + 난간(좌·우·앞) + 가운데 분할 난간."""
    sc.poly2d(f"Slab_{name}", "Stairwells", C_SLAB, rect(x0, y0, x1, y1))
    for i in range(4):
        yy = y1 - 42 - i * 26
        sc.poly2d(f"Step_{name}_{i+1}", "Stairwells", C_STEP, rect(x0 + 26, yy, x1 - 26, yy + 14))
    mid = (x0 + x1) / 2
    for key, p in [
        (f"RC_{name}_L", rect(x0, y0, x0 + T, y1)),
        (f"RC_{name}_R", rect(x1 - T, y0, x1, y1)),
        (f"RC_{name}_F", rect(x0, y1 - T, x1, y1)),
        (f"RC_{name}_EL", rect(x0, y0, mid - DOOR, y0 + T)),
        (f"RC_{name}_ER", rect(mid + DOOR, y0, x1, y0 + T)),
        (f"RC_{name}_M", rect(mid - T / 2, y0 + T, mid + T / 2, y1 - T)),
    ]:
        sc.solid(key, "StairWalls", p)
        sc.poly2d(f"Rail_{name}_{key.split('_')[-1]}", "WallGlow", C_WALL, p)


# ── 방 내부 집기 · 복도 ──────────────────────────────────────
# 방이 색칠된 빈 사각형이라 문을 열고 들어가도 볼 것이 없었다. 방 종류마다 다른
# 집기를 절차적으로 깐다. 좌표를 손으로 박지 않는 이유는 벽과 같다 — LAYOUT을
# 고치면 방 크기가 바뀌고, 박아 둔 좌표는 그때마다 어긋난다.
#
# 배치가 지켜야 하는 것:
#   1. 방 중심을 비운다 — verify_floor_reach가 방 폴리곤 중심으로 도달성을 본다.
#      교실은 문과 같은 x에 중앙 통로를 내서 이 조건을 자연히 만족시킨다.
#   2. 문 틈 앞을 비운다 — 복도 사물함은 문 양옆으로 CORR_DOOR_PAD를 남긴다.
#      수위 순찰의 문 앞 대기 지점이 여기 잡힌다(verify_janitor_route).
#   3. 단서·은신처 좌표(sc.clue_pts) 주변을 비운다 — 덮으면 조사할 수 없다.
#   4. 벽 안쪽 면에서 띄운다 — 붙이면 플레이어 반경(10)이 끼어 통로가 사라진다.
PROP_EDGE = 32        # 벽 안쪽 면에서 띄우는 거리(일반 방)
PROP_DOOR_PAD = 26    # 문 틈 좌우 여유
PROP_CLUE_CLEAR = 76  # 단서 오브젝트 중심에서 비워 둘 반경
PROP_AISLE_MIN = 34   # 방 중앙 가로 통로 반폭 하한(플레이어 반경 10 + 여유)
PROP_AISLE_MAX = 62
PROP_MIN_W = 34       # 이보다 좁은 자리에는 아무것도 두지 않는다
PROP_MIN_H = 24

# 교실 전용 치수 — 책상 하나가 사각형 하나면 뭔지 알아볼 수 없어 책상+의자로 놓는다.
CLASS_EDGE = 24       # 교실은 벽 여유를 줄여 책상 열을 하나라도 더 넣는다
CLASS_DESK = (44, 26)
CLASS_CHAIR = (26, 12)
CLASS_CHAIR_GAP = 5   # 책상과 의자 사이
CLASS_COL_GAP = 20
CLASS_ROW_GAP = 22
CLASS_AISLE = 68      # 문과 같은 x에 내는 중앙 통로 폭
CLASS_BOARD_H = 14    # 칠판 두께(장식, 충돌 없음)
CLASS_TEACHER = (86, 32)
CLASS_LOCKER_D = 30   # 뒷벽 사물함 깊이
CLASS_CLEAN_W = 38    # 청소도구함 폭(뒷벽 한쪽 구석)
CLASS_BIN = 24        # 쓰레기통 한 변
CLASS_WALL_DECOR_D = 8   # 옆벽에 붙는 창문·게시판 두께
CLASS_LOCKER_W = 40      # 교실 뒷벽 사물함 폭 — 복도용(58)보다 좁다
CLASS_BACK_PAD = 12      # 뒷벽에서 문 틈 좌우로 남기는 폭
CLASS_DOOR_LANE = 72     # 문에서 가로 통로까지 이어지는 세로 통로 폭
CLASS_WIN_LANE = 20      # 창 쪽 벽과 첫 책상 열 사이 통로(#274)
CLASS_WALK = 46          # 플레이어가 지나갈 수 있는 최소 틈(격자 20px + 여유)
#   문 틈(110)만큼 통째로 비우면 북쪽 교실에서 책상 열 3개 중 3개가 다 걸려
#   문 쪽 절반이 통째로 빈다. 플레이어 반경이 10이라 72면 충분히 지난다.
#   교실은 방 안쪽이라 문 앞 여유가 복도만큼 필요하지 않다. 복도 규격을
#   그대로 쓰면 북쪽 교실(폭 373)에서 양옆 자투리가 24px만 남아 사물함이
#   한 칸도 안 들어갔다.

# 복도 비품
CORR_LOCKER_D = 32
CORR_LOCKER_W = 58
CORR_LOCKER_GAP = 8
CORR_DOOR_PAD = 46    # 문 틈 양옆으로 남기는 폭(수위 대기 지점 확보)
CORR_NOTICE_W = 120   # 사물함이 안 들어간 자리에 붙이는 게시판(장식)
CORR_NOTICE_D = 10
CORR_FIRE = (14, 22)   # 소화기(장식)
CORR_HYDRANT = (44, 16)  # 소화전 함(장식) — 넓은 벽면에만
CORR_WATER = (40, 26)    # 정수기(집기) — 몇 칸에 하나
CORR_MAT = (150, 22)     # 문 앞 발판(장식)
WAINSCOT = 5             # 걸레받이 두께(벽 16 안쪽)
PILASTER = (16, 0)       # 기둥 폭 — 높이는 벽 두께 전체
PILASTER_GAP = 340       # 기둥 간격
CORR_LINE_H = 6       # 바닥 유도선(장식)

# 방 종류 -> (단위 최대 크기, 단위 간격, 색).
# 크기는 최대치다 — 남은 자리가 좁으면 PROP_MIN_* 까지 줄여서 넣는다. 규격을
# 고집하면 화장실·현관처럼 짧은 방이 통째로 비어 버린다.
PROP_SPECS = {
    "office":    ((96, 40), (28, 24), C_DESK),     # 교사 책상
    "computer":  ((54, 36), (22, 22), C_METAL),    # 컴퓨터 책상
    "lab":       ((140, 38), (30, 26), C_DESK),    # 실험대
    "storage":   ((68, 40), (20, 18), C_SHELF),    # 선반
    "toilet":    ((58, 44), (20, 16), C_STALL),    # 칸막이
    "entrance":  ((110, 36), (36, 28), C_BENCH),   # 신발장·벤치
    "janitor":   ((96, 40), (28, 24), C_DESK),
    "hall":      ((84, 40), (30, 26), C_BENCH),    # 탁자
}

# 도달 불가로 남겨야 하는 방에는 집기를 두지 않는다(verify_floor_reach가 확인).
PROP_SKIP = {"YardExit"}


def prop_kind(key, label):
    """방 키·라벨로 집기 종류를 정한다. 라벨 없는 방(막힌 공간)은 제외."""
    if key in PROP_SKIP or not label:
        return None
    if key.startswith(("MensRoom", "WomensRoom")):
        return "toilet"
    if key.startswith("Storage") or key in ("PEStorage", "ArtStorage", "MusicPrep"):
        return "storage"
    if key == "Entrance":
        return "entrance"
    if key == "JanitorRoom":
        return "janitor"
    if key.startswith("ComputerRoom"):
        return "computer"
    if key.startswith("ScienceLab") or key == "InfoDept":
        return "lab"
    if key == "StaffRoom" or label.endswith("부"):
        return "office"
    if label.endswith("반") or key.startswith(("Class", "Dasan", "North", "EmptyClass")):
        return "classroom"
    return "hall"


def _overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _free_spans(bx0, bx1, by0, by1, keepout, floor_w=PROP_MIN_W):
    """띠와 세로로 겹치는 keepout을 x축에 투영해 남는 가로 구간을 낸다.

    걸리는 칸을 그냥 버리면 문 통로와 단서가 방 가운데를 지나는 방(현관 등)에서
    양쪽 자투리가 규격보다 좁아 통째로 비어 버린다. 먼저 구간을 나눈 뒤 각
    구간에 맞춰 단위를 줄이면 자투리도 쓴다.
    """
    spans = [(bx0, bx1)]
    for kx0, ky0, kx1, ky1 in keepout:
        if ky1 <= by0 or ky0 >= by1:
            continue
        nxt = []
        for sx0, sx1 in spans:
            if kx1 <= sx0 or kx0 >= sx1:
                nxt.append((sx0, sx1))
                continue
            if kx0 > sx0:
                nxt.append((sx0, min(kx0, sx1)))
            if kx1 < sx1:
                nxt.append((max(kx1, sx0), sx1))
        spans = nxt
    return [sp for sp in spans if sp[1] - sp[0] >= floor_w]


def _fill(topf, botf, bx0, bx1, unit, gap, keepout):
    """띠를 단위 크기로 채운다.

    위·아래 경계가 사선일 수 있어(MID_RIGHT·교무실) 열마다 높이를 다시 잰다.
    """
    uw, uh = unit
    gx, gy = gap
    by0 = min(topf(bx0), topf(bx1))
    by1 = max(botf(bx0), botf(bx1))
    if by1 - by0 < PROP_MIN_H:
        return []
    out = []
    for sx0, sx1 in _free_spans(bx0, bx1, by0, by1, keepout):
        avail = sx1 - sx0
        uw_eff = min(uw, avail)
        cols = max(1, int((avail + gx) // (uw_eff + gx)))
        span = cols * uw_eff + (cols - 1) * gx
        ox = sx0 + (avail - span) / 2
        for c in range(cols):
            x = ox + c * (uw_eff + gx)
            top = max(topf(x), topf(x + uw_eff))
            bot = min(botf(x), botf(x + uw_eff))
            if bot - top < PROP_MIN_H:
                continue
            uh_eff = min(uh, bot - top)
            rows = max(1, int((bot - top + gy) // (uh_eff + gy)))
            hgt = rows * uh_eff + (rows - 1) * gy
            oy = top + (bot - top - hgt) / 2
            for r in range(rows):
                y = oy + r * (uh_eff + gy)
                cell = (x, y, x + uw_eff, y + uh_eff)
                if not any(_overlap(cell, k) for k in keepout):
                    out.append(cell)
    return out


def _row(sx0, sx1, y0, y1, uw, gap, keepout):
    """[sx0,sx1]에 폭 uw 단위를 한 줄로 채운다(사물함처럼 벽에 붙는 것)."""
    out = []
    for ax0, ax1 in _free_spans(sx0, sx1, y0, y1, keepout, floor_w=uw * 0.6):
        avail = ax1 - ax0
        uw_eff = min(uw, avail)
        cols = max(1, int((avail + gap) // (uw_eff + gap)))
        span = cols * uw_eff + (cols - 1) * gap
        ox = ax0 + (avail - span) / 2
        for c in range(cols):
            x = ox + c * (uw_eff + gap)
            out.append((x, y0, x + uw_eff, y1))
    return out


def _free_spans_v(by0, by1, bx0, bx1, keepout, floor_h=PROP_MIN_H):
    """_free_spans의 세로판 — keepout을 y축에 투영해 남는 세로 구간을 낸다."""
    spans = [(by0, by1)]
    for kx0, ky0, kx1, ky1 in keepout:
        if kx1 <= bx0 or kx0 >= bx1:
            continue
        nxt = []
        for sy0, sy1 in spans:
            if ky1 <= sy0 or ky0 >= sy1:
                nxt.append((sy0, sy1))
                continue
            if ky0 > sy0:
                nxt.append((sy0, min(ky0, sy1)))
            if ky1 < sy1:
                nxt.append((max(ky1, sy0), sy1))
        spans = nxt
    return [sp for sp in spans if sp[1] - sp[0] >= floor_h]


def _col(x0, x1, sy0, sy1, uh, gap, keepout):
    """[sy0,sy1]에 높이 uh 단위를 한 줄로 세운다(옆벽에 붙는 사물함)."""
    out = []
    for ay0, ay1 in _free_spans_v(sy0, sy1, x0, x1, keepout, floor_h=uh * 0.6):
        avail = ay1 - ay0
        uh_eff = min(uh, avail)
        rows = max(1, int((avail + gap) // (uh_eff + gap)))
        span = rows * uh_eff + (rows - 1) * gap
        oy = ay0 + (avail - span) / 2
        for r in range(rows):
            y = oy + r * (uh_eff + gap)
            out.append((x0, y, x1, y + uh_eff))
    return out


def _spread(a0, a1, size, count, fixed0, fixed1, horizontal=True):
    """[a0,a1]에 최대 count개를 균등 배치한다(창문·게시판 같은 벽 장식).

    규격을 고집하면 좁은 방에서 한 장도 안 걸린다 — 들어가는 만큼으로 개수를
    줄이고, 그래도 안 되면 폭을 줄여 한 장이라도 건다.
    """
    avail = a1 - a0
    n = min(count, int((avail + 20) // (size + 20)))
    if n < 1:
        if avail < 60:
            return []
        n, size = 1, avail - 30
    gap = (avail - n * size) / (n + 1)
    out = []
    for i in range(n):
        v = a0 + gap * (i + 1) + size * i
        out.append((v, fixed0, v + size, fixed1) if horizontal
                   else (fixed0, v, fixed1, v + size))
    return out


def _windows(sc, key, room, ix0, ix1, cy, win_y, count=3):
    """창문 + 커튼 + 달빛 광원 + 창가 조사(#274). 교실과 교무실이 함께 쓴다.

    `win_y`는 창이 붙을 벽면 띠 (y0, y1)다. 문 반대쪽 벽 — 그쪽이 건물
    외벽이다. 돌려주는 것은 창 칸 목록이라, 부르는 쪽이 그 앞을 비워
    창가 통로를 낼 수 있다.
    """
    cells = list(_spread(ix0, ix1, 72, count, *win_y))
    if not cells:
        return cells
    # 광원 묶음을 먼저 낸다 — 자식보다 앞에 선언돼야 한다.
    sc.room_lights(key, *room)
    for i, (px0, py0, px1, py1) in enumerate(cells):
        sc.wall_decor(f"{key}_win{i}", rect(px0, py0, px1, py1), C_WINDOW)
        sc.wall_decor(f"{key}_curtainL{i}", rect(px0 - 8, py0, px0, py1), C_CURTAIN)
        sc.wall_decor(f"{key}_curtainR{i}", rect(px1, py0, px1 + 8, py1), C_CURTAIN)
        # 달빛 — 창마다 광원 하나(#274). 폴리곤으로 세 번 실패한 뒤 진짜
        # 광원으로 바꿨다. 벽(LO_)에 막히므로 방 밖으로 새지 않는다.
        down = py0 < cy
        ly = (py1 + MOON_INSET) if down else (py0 - MOON_INSET)
        sc.window_light(f"{key}_{i}", (px0 + px1) / 2, ly, key)
    # 창가 조사(E) — 방마다 하나. 창마다 달면 층당 서른 개가 되는데,
    # _find_interactable는 겹친 것 중 아무거나 돌려주므로 단서를 가로챈다.
    if cells:
        wy0 = min(c[1] for c in cells)
        wy1 = max(c[3] for c in cells)
        zw, zh = WINDOW_ZONE
        pcx = (min(c[0] for c in cells) + max(c[2] for c in cells)) / 2
        pcy = (wy1 + zh / 2) if wy0 < cy else (wy0 - zh / 2)
        # 그래도 단서·은신처와 겹치면 그 방은 건너뛴다 — 창밖 묘사보다
        # 진행 요소가 먼저다.
        if not any(abs(px - pcx) <= zw / 2 and abs(py - pcy) <= zh / 2
                   for px, py in sc.clue_pts):
            sc.window_probe(key, pcx, pcy, window_text(sc.floor_no, key))
    return cells


def _classroom(sc, key, x0, y0, x1, y1, door, keepout):
    """교실 — 가로 배치. 칠판은 왼쪽 옆벽, 학생은 왼쪽을 보고 앉는다.

    세로 배치(칠판을 문 반대쪽 벽에)에서 90도 돌린 것이다. 북쪽 교실은 위쪽이
    건물 외벽이라 창문이 거기 있어야 맞고, 복도와 맞닿은 아래쪽 벽에는 칠판을
    걸 수 없다. 돌리면 칠판은 옆벽, 창문은 외벽(문 반대쪽)으로 제자리를 찾는다.

    통로는 두 갈래다. **가로 통로**는 방 중심을 지나간다 — verify_floor_reach가
    방 폴리곤 중심으로 도달성을 보므로 여기가 막히면 안 된다. **세로 통로**는
    문에서 가로 통로까지 이어져, 들어오자마자 책상에 막히지 않게 한다.

    벽에서 CLASS_EDGE만큼 안쪽까지가 집기 자리고, 그 바깥 띠(벽면)는 장식
    전용이다. 시계·태극기·TV·스피커를 여기 걸면 통행에 전혀 영향이 없다.
    """
    ix0, ix1 = x0 + T + CLASS_EDGE, x1 - T - CLASS_EDGE
    iy0, iy1 = y0 + T + CLASS_EDGE, y1 - T - CLASS_EDGE
    if ix1 - ix0 < 150 or iy1 - iy0 < 130:
        return
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    wl, wr = x0 + T, x1 - T          # 좌·우 벽 안쪽 면
    wt, wb = y0 + T, y1 - T          # 위·아래 벽 안쪽 면

    # ── 앞(왼쪽 벽): 칠판 · 분필받이 · 태극기 · TV ──────────────
    bh = min((iy1 - iy0) * 0.6, 240)
    sc.decor(f"{key}_board", rect(wl, cy - bh / 2, wl + CLASS_BOARD_H,
                                  cy + bh / 2), C_BOARD)
    sc.decor(f"{key}_tray", rect(wl + CLASS_BOARD_H, cy - bh / 2,
                                 wl + CLASS_BOARD_H + 4, cy + bh / 2), C_TRAY)
    if cy - bh / 2 - 40 > wt:
        sc.decor(f"{key}_flag", rect(wl, cy - bh / 2 - 36, wl + 14,
                                     cy - bh / 2 - 8), C_FLAG)
    # 시계는 앞쪽 벽(칠판 위)에 건다(#277). 예전에는 오른쪽 벽면에 걸었는데,
    # 사물함을 벽에 붙이면서 그 자리가 없어졌다. 실제 교실에서도 시계는
    # 칠판 쪽에 있다.
    if cy - bh / 2 - 78 > wt:
        sc.decor(f"{key}_clock", rect(wl, cy - bh / 2 - 74, wl + 14,
                                      cy - bh / 2 - 46), C_CLOCK)
    if cy + bh / 2 + 48 < wb:
        sc.decor(f"{key}_tv", rect(wl, cy + bh / 2 + 10, wl + 16,
                                   cy + bh / 2 + 46), C_TV)

    # ── 교탁 · 교사 의자 · 학급문고 ────────────────────────────
    tw, th = CLASS_TEACHER[1], CLASS_TEACHER[0]
    teach = (ix0, cy - th / 2, ix0 + tw, cy + th / 2)
    if not any(_overlap(teach, k) for k in keepout):
        sc.prop(f"{key}_teacher", rect(*teach), C_DESK)
        sc.overlay(f"{key}_papers", rect(ix0 + 6, cy - 12, ix0 + tw - 8, cy + 12),
                   C_PAPER)
        chair = (ix0 + tw + 6, cy - 16, ix0 + tw + 22, cy + 16)
        if not any(_overlap(chair, k) for k in keepout):
            sc.prop(f"{key}_tchair", rect(*chair), C_CHAIR)
    # 학급문고 — 교탁 위아래 빈 구석. 책상 격자가 교탁 오른쪽부터라 여기가 남는다.
    for i, shelf in enumerate(((ix0, iy0, ix0 + tw, iy0 + 68),
                               (ix0, iy1 - 68, ix0 + tw, iy1))):
        if shelf[3] - shelf[1] > 40 and not any(_overlap(shelf, k) for k in keepout):
            sc.prop(f"{key}_shelf{i}", rect(*shelf), C_SHELF)
            sc.overlay(f"{key}_books{i}", rect(shelf[0] + 5, shelf[1] + 6,
                                               shelf[2] - 5, shelf[1] + 18), C_BOOK)

    # ── 뒤(오른쪽 벽): 청소도구함 · 사물함 · 쓰레기통 · 시계 ────
    # 벽면(wr)에 **붙인다**(#277). 예전에는 ix1(벽에서 CLASS_EDGE만큼 안쪽)에
    # 세워 사물함이 벽에서 24px 떠 있었다. 그 띠는 장식 전용이었지만 실제로
    # 거기 걸린 것은 시계뿐이었고, 시계는 앞쪽 벽으로 옮겼다.
    lx0, lx1 = wr - CLASS_LOCKER_D, wr
    clean = (lx0, iy0, lx1, iy0 + CLASS_CLEAN_W)
    bin_ = (lx1 - CLASS_BIN, iy1 - CLASS_BIN, lx1, iy1)
    if not any(_overlap(clean, k) for k in keepout):
        sc.prop(f"{key}_clean", rect(*clean), C_CLEAN)
    if not any(_overlap(bin_, k) for k in keepout):
        sc.prop(f"{key}_bin", rect(*bin_), C_BIN)
    for i, r4 in enumerate(_col(lx0, lx1, iy0 + CLASS_CLEAN_W + 8,
                                iy1 - CLASS_BIN - 8, CLASS_LOCKER_W, 6,
                                keepout + [clean, bin_])):
        sc.prop(f"{key}_back{i}", rect(*r4), C_LOCKER)

    # ── 외벽: 창문 + 커튼 / 문 쪽 벽: 스피커 + 게시판 ───────────
    door_gap = (cx - DOOR / 2 - CLASS_BACK_PAD, cx + DOOR / 2 + CLASS_BACK_PAD)
    # 가로 벽 장식은 벽 **앞면 위**에 그린다(#268). 위쪽 벽은 앞면이 방 안으로
    # 내려오므로 그 자리에, 아래쪽 벽은 앞면이 방 밖(복도)으로 가므로 벽 띠에.
    # 레이어도 Props(PD_)가 아니라 WallGlow(WD_)여야 앞면에 안 가린다.
    top_band = (wt, wt + WALL_FACE)
    bot_band = (wb - CLASS_WALL_DECOR_D, wb)
    if door == "top":
        win_y, note_y = bot_band, top_band
    else:
        win_y, note_y = top_band, bot_band
    win_cells = _windows(sc, key, (x0, y0, x1, y1), ix0, ix1, cy, win_y)
    # 스피커도 게시판과 같은 벽면에 붙는다. note_y[0]에서 아래로 재면 문 쪽
    # 벽이 아래일 때 벽을 파고든다 — 벽면 방향에 맞춰 앵커를 잡는다.
    spk_y = (wt, wt + 14) if door == "top" else (wb - 14, wb)
    speakers = [(ix0, spk_y[0], ix0 + 18, spk_y[1]),
                (ix1 - 18, spk_y[0], ix1, spk_y[1])]
    for i, r4 in enumerate(speakers):
        sc.wall_decor(f"{key}_spk{i}", rect(*r4), C_SPEAKER)
    # 게시판은 문 틈과 스피커를 피해, 남는 벽면 구간마다 한 장씩. 대칭으로 두
    # 장을 깔면 문이 가운데라 두 장 다 문에 걸려 한 장도 안 남는다.
    lanes = _free_spans(ix0, ix1, note_y[0], note_y[1],
                        [(door_gap[0], note_y[0] - 1, door_gap[1], note_y[1] + 1)]
                        + [(a, note_y[0] - 1, b + 6, note_y[1] + 1)
                           for a, _, b, _ in speakers],
                        floor_w=60)
    for i, (sx0, sx1) in enumerate(lanes):
        w = min(78, sx1 - sx0 - 16)
        mx = (sx0 + sx1) / 2
        sc.wall_decor(f"{key}_notice{i}", rect(mx - w / 2, note_y[0], mx + w / 2,
                                               note_y[1]), C_NOTICE)

    # ── 학생 책상 — 교탁과 사물함 사이. 책상 오른쪽에 의자(왼쪽을 본다) ──
    dw, dh = CLASS_DESK[1], CLASS_DESK[0]      # 90도 돌린 책상
    cw, ch = CLASS_CHAIR[1], CLASS_CHAIR[0]
    unit_w = dw + CLASS_CHAIR_GAP + cw
    gx0, gx1 = ix0 + tw + 26, lx0 - 18
    if gx1 - gx0 < unit_w:
        return
    cols = max(1, int((gx1 - gx0 + CLASS_COL_GAP) // (unit_w + CLASS_COL_GAP)))
    total = cols * unit_w + (cols - 1) * CLASS_COL_GAP
    slack = gx1 - gx0 - total
    ox = gx0 + (gx1 - gx0 - total) / 2

    aisle = CLASS_AISLE / 2
    door_lane = (cx - CLASS_DOOR_LANE / 2, y0, cx + CLASS_DOOR_LANE / 2, y1)
    idx = 0
    # 창가에 다가갈 길을 낸다(#274). 창 쪽 절반은 원래 책상이 빈틈없이 들어차
    # 있어 플레이어가 아예 못 들어가는 죽은 공간이었다 — 열 사이 20px, 행 사이
    # 22px은 플레이어(반경 8, 도달 격자에서 10으로 부풀림)가 지날 수 없다.
    # 둘 중 하나로 길을 낸다.
    #  ① 여유가 있으면 열 사이 한 자리를 넓힌다. 책상은 그대로 두는 대신
    #     창 쪽 벽과 첫 행 사이도 CLASS_WIN_LANE만큼 비워야 통로가 창에 닿는다.
    #  ② 여유가 없으면 가운데 열 하나를 뺀다. 그 자리가 그대로 창까지 이어지므로
    #     창가 통로는 따로 필요 없다 — 행을 하나 더 살린다.
    wide = cols >= 2 and CLASS_COL_GAP + slack >= CLASS_WALK
    win_lane = CLASS_WIN_LANE if (cols < 2 or wide) else 0
    dy0 = iy0 + (win_lane if door == "bottom" else 0)
    dy1 = iy1 - (win_lane if door == "top" else 0)
    for by0, by1, near in ((dy0, cy - aisle, door == "top"),
                           (cy + aisle, dy1, door != "top")):
        rows = max(1, int((by1 - by0 + CLASS_ROW_GAP) // (dh + CLASS_ROW_GAP)))
        span = rows * dh + (rows - 1) * CLASS_ROW_GAP
        oy = by0 + (by1 - by0 - span) / 2
        # 창 쪽 절반에는 통로를 **비우지 않고 열 사이 한 자리를 넓힌다**(#274).
        # 처음엔 문 쪽처럼 가운데를 통째로 비웠는데, 교실은 열이 둘뿐이라
        # 책상이 사분의 일 넘게 사라졌다 — 예전에 지적받은 '교실이 비어보인다'로
        # 되돌아가는 셈이다. 남는 폭을 한 자리에 몰아주면 책상을 그대로 두고
        # 통로가 난다. 그래도 좁으면(교실이 빠듯하면) 그 자리 열 하나를 뺀다.
        # 문 쪽 절반은 **열 하나를 문 앞에 맞춰 통째로 뺀다**(#277). 예전에는
        # door_lane(72px)에 걸리는 열을 지웠는데, 통로 폭이 열 간격(63px)보다
        # 넓어 늘 **두 열**이 걸렸다. 빠질 열을 cx에 맞춰 옮기고 그 하나만
        # 빼면 통로가 83px 나면서 책상은 하나만 잃는다.
        block = keepout
        pitch = unit_w + CLASS_COL_GAP
        even = [ox + c * pitch for c in range(cols)]
        if near and cols >= 2:
            k = max(0, min(cols - 1, round((cx - unit_w / 2 - gx0) / pitch)))
            base = cx - unit_w / 2 - k * pitch
            if base >= gx0 - 2 and base + (cols - 1) * pitch + unit_w <= gx1 + 2:
                col_xs = [base + c * pitch for c in range(cols) if c != k]
            else:   # 자리를 못 맞추면 예전처럼 통로에 걸리는 열을 지운다
                col_xs = even
                block = keepout + [door_lane]
        elif near or cols < 2:
            col_xs = even
        elif wide:
            col_xs, x = [], gx0
            for c in range(cols):
                col_xs.append(x)
                x += unit_w + CLASS_COL_GAP + (slack if c == (cols - 1) // 2 else 0)
        else:
            col_xs = [v for c, v in enumerate(even) if c != (cols - 1) // 2]
        for x in col_xs:
            for r in range(rows):
                y = oy + r * (dh + CLASS_ROW_GAP)
                desk = (x, y, x + dw, y + dh)
                chair = (x + dw + CLASS_CHAIR_GAP, y + (dh - ch) / 2,
                         x + dw + CLASS_CHAIR_GAP + cw, y + (dh + ch) / 2)
                if any(_overlap(desk, k) or _overlap(chair, k) for k in block):
                    continue
                sc.prop(f"{key}_d{idx}", rect(*desk), C_DESK)
                sc.prop(f"{key}_c{idx}", rect(*chair), C_CHAIR)
                # 책상마다 다 올리면 격자가 뭉개져 보인다 — 셋에 하나만.
                if idx % 3 == 0:
                    sc.overlay(f"{key}_txt{idx}",
                               rect(x + 4, y + 9, x + dw - 4, y + dh - 9), C_BOOK)
                idx += 1


OFFICE_EDGE = 18          # 벽면 장식 전용 띠
OFFICE_DESK = (84, 36)    # 교사 책상 — 가로로 눕힌다
OFFICE_PART = 6           # 마주 본 책상 사이 칸막이 두께
OFFICE_CHAIR = 22         # 의자 한 변
OFFICE_WALK = 46          # 사람이 지나갈 통로(도달 격자 20px + 플레이어 여유)
OFFICE_WIN_LANE = 46      # 창가 통로 — 창가 조사(#274)에 다가갈 수 있어야 한다
OFFICE_GAP = 16           # 벽면 집기끼리의 간격
OFFICE_SIDE = 150         # 옆벽에 남기고 싶은 폭 — 회의 탁자(132)가 들어갈 만큼
OFFICE_MAX_COLS = 6       # 섬 열 상한. 넓다고 책상만 늘리면 다시 창고가 된다
OFFICE_HEAD = (104, 44)   # 부장 책상
OFFICE_CLUE_CLEAR = 62    # 단서·은신처 여유. verify_props는 30이면 되지만,
                          # 은신처는 **걸어가 닿아야** 하므로(verify_hiding_spots)
                          # 통로 폭(46)보다 넉넉해야 한다. 40으로 줄였더니
                          # 체육건강부·진로진학부 은신처가 집기에 막혔다.


def _stack(sc, key, x0, x1, y0, y1, items, taken, keepout, outer):
    """[x0,x1] 띠에 물건을 위에서 아래로 쌓는다. 목록을 되풀이해 띠를 채운다.

    옆벽 자투리를 채우는 데 쓴다 — 방마다 남는 폭이 45px에서 330px까지
    제각각이라, 넓으면 회의 탁자까지 들어가고 좁으면 캐비닛만 들어간다.
    한 바퀴 돌아 아무것도 못 놓으면 멈춘다(무한 반복 방지).

    항목의 `wall`이 참이면 바깥 벽(`outer` 쪽)에 붙이고, 거짓이면 띠 가운데
    놓는다 — 캐비닛은 벽에 붙어야 하고 회의 탁자는 떠 있어야 자연스럽다.
    """
    y = y0
    n = 0
    while y < y1:
        placed = False
        for name, w, h, color, wall in items:
            if w > x1 - x0 or y + h > y1:
                continue
            px = (x0 if outer == "left" else x1 - w) if wall else (x0 + x1 - w) / 2
            cell = (px, y, px + w, y + h)
            if any(_overlap(cell, k) for k in taken + keepout):
                continue
            sc.prop(f"{key}_{name}{n}", rect(*cell), color)
            taken.append(cell)
            y += h + OFFICE_GAP
            placed = True
        if not placed:
            return
        n += 1


def _office(sc, key, x0, y0, x1, y1, door, keepout):
    """교무실·부서실 — 칸막이 책상 섬 + 부장 자리 + 캐비닛 + 회의·접견(#277).

    예전에는 일반 방과 같은 격자(`PROP_SPECS["office"]`)를 썼다. 96x40 책상을
    위아래 두 덩어리로 늘어놓을 뿐이라 373x520 방에 책상 여덟 개가 떠 있고
    가운데가 통째로 비었다. 실제 부서실은 책상을 마주 붙이고 사이에 칸막이를
    세운 섬을 놓고, 벽을 따라 서류 캐비닛을 세우고, 남는 자리에 회의 탁자와
    접견 소파를 둔다.

    **통로를 먼저 잡고 남는 자리에 집기를 넣는다.** 세로 통로는 문 바로
    앞(cx)에 두고 열을 **짝수**로 맞춰 그 자리가 늘 비게 한다 — 홀수면 가운데
    열이 문을 막는다. 가로 통로는 섬 줄 사이에 OFFICE_WALK씩 남는다.

    창문·달빛·창가 조사는 교실과 같은 `_windows()`를 쓴다(#274). 부서실도
    북쪽 외벽에 붙어 있어 창이 있어야 맞는데 예전에는 없었다.
    """
    wl, wr = x0 + T, x1 - T
    wt, wb = y0 + T, y1 - T
    ix0, ix1 = wl + OFFICE_EDGE, wr - OFFICE_EDGE
    iy0, iy1 = wt + OFFICE_EDGE, wb - OFFICE_EDGE
    if ix1 - ix0 < 200 or iy1 - iy0 < 200:
        return
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    win_top = door != "top"          # 문 반대쪽이 외벽이다
    # 단서 여유를 방마다 좁게 다시 잡는다. 공용 값(PROP_CLUE_CLEAR=76)은 폭
    # 84 x 높이 130짜리 섬에는 너무 넓어, 단서가 둘 있는 방은 섬이 전부 밀려
    # 방이 도로 텅 빈다. verify_props가 실제로 요구하는 것은 집기 가장자리가
    # 단서에서 CLUE_CLEAR(30)만큼 떨어지는 것이므로 40이면 증명적으로 충분하다.
    keepout = _keepout_for(sc, x0, x1, OFFICE_CLUE_CLEAR)

    # ── 창문 + 달빛 + 창가 조사 ────────────────────────────────
    win_y = (wt, wt + WALL_FACE) if win_top else (wb - CLASS_WALL_DECOR_D, wb)
    _windows(sc, key, (x0, y0, x1, y1), ix0, ix1, cy, win_y,
             max(3, int((ix1 - ix0) // 210)))

    # ── 작업 구역: 창가 통로를 뺀 나머지 ───────────────────────
    ay0 = iy0 + (OFFICE_WIN_LANE if win_top else 0)
    ay1 = iy1 - (0 if win_top else OFFICE_WIN_LANE)

    dw, dh = OFFICE_DESK
    isle_h = dh * 2 + OFFICE_PART                      # 마주 본 책상 + 칸막이
    unit_h = isle_h + 2 * (4 + OFFICE_CHAIR)           # 의자까지 낀 한 줄
    rows = max(1, int((ay1 - ay0 + OFFICE_WALK) // (unit_h + OFFICE_WALK)))
    # 열 수는 **옆벽에 OFFICE_SIDE를 남기고** 정한다. 폭을 전부 책상으로
    # 채우면 회의 탁자·캐비닛 자리가 없어 다시 책상만 늘어선 방이 된다.
    usable = (ix1 - ix0) - 2 * OFFICE_SIDE
    cols = int((usable + OFFICE_WALK) // (dw + OFFICE_WALK)) if usable > 0 else 0
    if cols < 2:                                       # 좁은 방은 폭을 다 쓴다
        cols = int((ix1 - ix0 + OFFICE_WALK) // (dw + OFFICE_WALK))
    cols = min(cols - (cols % 2), OFFICE_MAX_COLS)     # 짝수 — 문 앞이 비어야 한다
    if cols < 2:
        return

    grid_w = cols * dw + (cols - 1) * OFFICE_WALK
    grid_h = rows * unit_h + (rows - 1) * OFFICE_WALK
    gx0 = cx - grid_w / 2
    # 섬을 문 쪽으로 붙이고 남는 세로 여유는 창가에 몰아준다 — 그 자리에
    # 부장 책상이 들어간다. 가운데 정렬하면 위아래로 나뉘어 둘 다 못 쓴다.
    gy0 = (ay1 - grid_h - OFFICE_GAP) if win_top else (ay0 + OFFICE_GAP)
    taken = []

    # ── 책상 섬 ────────────────────────────────────────────────
    def seat(nm, lx, dy, chair_below):
        """책상 한 자리 — 모니터·서류를 올리고 바깥쪽에 의자를 붙인다."""
        sc.prop(f"{key}_desk{nm}", rect(lx, dy, lx + dw, dy + dh), C_DESK)
        sc.overlay(f"{key}_pc{nm}", rect(lx + 8, dy + 6, lx + 34, dy + dh - 6),
                   C_MONITOR)
        sc.overlay(f"{key}_doc{nm}", rect(lx + 42, dy + 9, lx + dw - 8, dy + dh - 9),
                   C_PAPER)
        chy = dy + dh + 4 if chair_below else dy - 4 - OFFICE_CHAIR
        sc.prop(f"{key}_ch{nm}",
                rect(lx + dw / 2 - OFFICE_CHAIR / 2, chy,
                     lx + dw / 2 + OFFICE_CHAIR / 2, chy + OFFICE_CHAIR), C_CHAIR)

    n = 0
    for r in range(rows):
        top = gy0 + r * (unit_h + OFFICE_WALK) + 4 + OFFICE_CHAIR
        for c in range(cols):
            lx = gx0 + c * (dw + OFFICE_WALK)
            isle = (lx, top - 4 - OFFICE_CHAIR, lx + dw,
                    top + isle_h + 4 + OFFICE_CHAIR)
            if not any(_overlap(isle, k) for k in keepout):
                # 마주 본 책상 둘 + 사이 칸막이. 칸막이가 있어야 섬으로 읽힌다.
                seat(f"{n}_0", lx, top, False)
                seat(f"{n}_1", lx, top + dh + OFFICE_PART, True)
                sc.prop(f"{key}_part{n}",
                        rect(lx, top + dh, lx + dw, top + dh + OFFICE_PART),
                        C_PARTITION)
                taken.append(isle)
                n += 1
                continue
            # 섬이 안 들어가면 **반쪽이라도** 넣는다. 단서 여유에 몇 px
            # 걸렸다고 통째로 비우면 방이 도로 휑해진다 — 큰 방일수록
            # 섬 하나가 빠진 자리가 크게 보인다.
            for half, dy in ((0, top), (1, top + dh + OFFICE_PART)):
                cell = ((lx, dy - 4 - OFFICE_CHAIR, lx + dw, dy + dh) if half == 0
                        else (lx, dy, lx + dw, dy + dh + 4 + OFFICE_CHAIR))
                if any(_overlap(cell, k) for k in keepout + taken):
                    continue
                seat(f"{n}_{half}", lx, dy, half == 1)
                taken.append(cell)
            n += 1

    # ── 부장 책상 — 창가 쪽 남는 띠에서 방을 마주 본다 ─────────
    hw, hh = OFFICE_HEAD
    band = (ay0, gy0) if win_top else (gy0 + grid_h, ay1)
    if band[1] - band[0] >= hh + OFFICE_CHAIR + 12:
        hy = band[0] + 6 if win_top else band[1] - hh - 6
        head = (cx - hw / 2, hy, cx + hw / 2, hy + hh)
        if not any(_overlap(head, k) for k in taken + keepout):
            sc.prop(f"{key}_head", rect(*head), C_DESK)
            sc.overlay(f"{key}_headdoc",
                       rect(head[0] + 10, hy + 10, head[2] - 10, hy + hh - 10), C_PAPER)
            chy = hy + hh + 4 if win_top else hy - 4 - OFFICE_CHAIR
            sc.prop(f"{key}_headch",
                    rect(cx - OFFICE_CHAIR / 2, chy,
                         cx + OFFICE_CHAIR / 2, chy + OFFICE_CHAIR), C_CHAIR)
            taken.append((head[0], min(hy, chy), head[2],
                          max(hy + hh, chy + OFFICE_CHAIR)))

    # ── 옆벽 자투리 — 넓으면 회의·접견까지, 좁으면 캐비닛만 ────
    for sx0, sx1, tag in ((ix0, gx0, "L"), (gx0 + grid_w, ix1, "R")):
        if sx1 - sx0 < 34:
            continue
        wide = sx1 - sx0 >= 150
        items = [(f"cab{tag}", min(46, sx1 - sx0), 34, C_CABINET, True),
                 (f"shelf{tag}", min(40, sx1 - sx0), 58, C_SHELF, True)]
        if wide:
            # 부서 회의 탁자와 접견 소파 — 넓은 방에만. 벽에 안 붙이고
            # 띠 가운데 둔다.
            items = [(f"table{tag}", 132, 76, C_DESK, False),
                     (f"sofa{tag}", 104, 38, C_SOFA, False),
                     (f"lowtbl{tag}", 66, 34, C_BENCH, False)] + items
        items += [(f"copier{tag}", min(52, sx1 - sx0), 42, C_COPIER, True),
                  (f"fridge{tag}", min(40, sx1 - sx0), 40, C_FRIDGE, True),
                  (f"water{tag}", min(30, sx1 - sx0), 30, C_WATER, True),
                  (f"plant{tag}", min(28, sx1 - sx0), 28, C_PLANT, True)]
        _stack(sc, key, sx0, sx1, ay0, ay1, items, taken, keepout,
               "left" if tag == "L" else "right")

    # ── 벽 장식 ────────────────────────────────────────────────
    # 화이트보드는 옆벽에. 가로 벽은 창(외벽)과 문(복도)이 이미 쓴다.
    bh = min((iy1 - iy0) * 0.45, 200)
    sc.decor(f"{key}_wboard", rect(wl, cy - bh / 2, wl + 8, cy + bh / 2), C_WBOARD)
    sc.decor(f"{key}_clock", rect(wr - 8, cy - 14, wr, cy + 14), C_CLOCK)
    # 게시판 — 문 쪽 벽면, 문 틈을 피해서.
    note_y = (wb - CLASS_WALL_DECOR_D, wb) if win_top else (wt, wt + WALL_FACE)
    gap = (cx - DOOR / 2 - 14, y0, cx + DOOR / 2 + 14, y1)
    for i, (bx0, bx1) in enumerate(_free_spans(ix0, ix1, note_y[0], note_y[1],
                                               [gap], 90)):
        w = min(150, bx1 - bx0 - 12)
        if w < 60:
            continue
        mx = (bx0 + bx1) / 2
        sc.wall_decor(f"{key}_notice{i}",
                      rect(mx - w / 2, note_y[0], mx + w / 2, note_y[1]), C_NOTICE)



# ── 집기 위 작은 소품(#289) ──────────────────────────────────────
# 방마다 손으로 놓지 않고 **이미 놓인 집기를 훑어** 얹는다. 종류·자리·있고 없고를
# 집기 이름 해시로 정하므로 재생성해도 같은 자리에 같은 것이 온다.
#
# 전부 `PT_`(충돌 없음)이고 집기 경계 안에 들어간다 — 통행·수위 경로·도달성에
# 영향이 없고 `verify_props`의 "소품은 집기 안" 규칙을 자동으로 지킨다.
#
# **바닥에 흩뿌리지 않는다.** 유도선·배관·형광등·닳은 자국·스프링클러로 다섯 번
# 실패한 길이다(#271·#274·#277). 물건은 물건 위에 놓는다.
#
# 집기 색 -> [(이름, 폭 비율, 높이 비율, 소품 색), ...]
CLUTTER = {
    C_DESK:    [("book", 0.40, 0.34, C_BOOK), ("cup", 0.15, 0.20, C_CUP),
                ("case", 0.34, 0.18, C_CASE), ("note", 0.36, 0.26, C_PAPER),
                ("bottle", 0.13, 0.26, C_WATER)],
    C_CHAIR:   [("bag", 0.66, 0.40, C_BAG), ("gym", 0.60, 0.34, C_CLOTHES)],
    C_LOCKER:  [("tag", 0.70, 0.09, C_PAPER)],
    C_METAL:   [("tag", 0.70, 0.09, C_PAPER), ("box", 0.44, 0.24, C_BOOK)],
    C_SHELF:   [("box", 0.50, 0.28, C_BOOK), ("files", 0.64, 0.18, C_PAPER),
                ("kit", 0.30, 0.24, C_CASE)],
    C_CABINET: [("files", 0.60, 0.15, C_PAPER), ("box", 0.42, 0.24, C_BOOK)],
    C_CLEAN:   [("tag", 0.56, 0.10, C_PAPER)],
    C_SINK:    [("soap", 0.20, 0.15, C_CUP)],
    C_BENCH:   [("bag", 0.34, 0.28, C_BAG), ("cup", 0.14, 0.18, C_CUP)],
    C_BED:     [("fold", 0.68, 0.22, C_CLOTHES)],
    C_RACK:    [("tag", 0.52, 0.10, C_PAPER)],
    C_SOFA:    [("cushion", 0.30, 0.44, C_CLOTHES)],
    C_COPIER:  [("stack", 0.50, 0.16, C_PAPER)],
}

# 집기 색 -> 소품이 붙을 확률(%). 노드 예산(3300) 안에서 방이 채워 보이게 맞춘 값.
# 책상은 사람이 쓰던 자리라 높이고, 벽에 붙는 수납장은 낮춘다.
CLUTTER_CHANCE = {
    C_DESK: 88, C_CHAIR: 44, C_LOCKER: 40, C_METAL: 55, C_SHELF: 80,
    C_CABINET: 60, C_CLEAN: 70, C_SINK: 60, C_BENCH: 55, C_BED: 60,
    C_RACK: 60, C_SOFA: 70, C_COPIER: 60,
}
CLUTTER_PAD = 3        # 집기 가장자리에서 띄우는 여백
CLUTTER_TOP = 0.62     # 소품은 집기 위쪽 이만큼 안에만 — 아래쪽은 앞면이다(#289)


def _name_hash(name):
    h = 2166136261
    for ch in name:
        h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h


def add_clutter(sc):
    """집기를 훑어 위에 작은 소품을 얹는다(#289). 놓은 개수를 돌려준다.

    자리는 집기 위쪽 `CLUTTER_TOP` 안에서 고른다 — 아래쪽 띠는 오브젝트 그림의
    **앞면**이라(#289) 거기 물건을 얹으면 공중에 뜬 것으로 보인다.
    """
    placed = 0
    for key, box, color in list(sc.prop_rects):
        table = CLUTTER.get(color)
        if not table:
            continue
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        if w < 18 or h < 14:
            continue
        seed = _name_hash(key)
        if seed % 100 >= CLUTTER_CHANCE.get(color, 50):
            continue
        # 넓은 집기에는 둘까지 — 좁은 책상에 둘을 얹으면 서로 밀려 하나도 못 놓는다.
        want = 2 if (w >= 56 or h >= 38) else 1
        for i in range(want):
            name, fw, fh, col = table[(seed // (7 + i * 11)) % len(table)]
            # 비율이 작으면 몇 px밖에 안 나와 걸러졌다(사물함 이름표가 3.6px였다).
            # 최소 크기로 바닥을 받쳐 준다.
            iw = min(w - 2 * CLUTTER_PAD, max(6.0, w * fw))
            ih = min((h - 2 * CLUTTER_PAD) * CLUTTER_TOP, max(4.0, h * fh))
            if iw < 5 or ih < 3.5:
                break
            # 위쪽 세 자리 중 하나 — 왼쪽·오른쪽·가운데
            slot = (seed // (13 + i * 17)) % 3
            if slot == 0:
                px = x0 + CLUTTER_PAD
            elif slot == 1:
                px = x1 - CLUTTER_PAD - iw
            else:
                px = (x0 + x1 - iw) / 2
            py = y0 + CLUTTER_PAD + ((seed // (29 + i * 7)) % 3) * 1.5
            cell = (px, py, px + iw, py + ih)
            if any(_overlap(cell, r) for r in sc.overlay_rects):
                continue
            sc.overlay(f"{key}_{name}{i}", rect(*cell), col)
            placed += 1
    return placed


def add_sliding_doors(sc):
    """방 문을 한 짝짜리 미닫이문으로 만든다(라벨 있는 방 전부, #252).

    루트가 Area2D다 — 플레이어의 InteractionArea가 겹치는 Area2D 중
    interact()를 가진 것을 찾아 E로 부르기 때문에, 스크립트가 Area2D 본체에
    붙어야 한다. collision_layer 2는 플레이어가 찾는 층이고, mask 1은 수위
    몸을 감지하는 쪽이다(수위는 E 없이 지나간다).

    패널 폴리곤은 절대 좌표로 낸다(부모 노드는 원점에 둔다). 검사 스크립트들이
    노드 position을 반영하지 않고 폴리곤을 그대로 읽기 때문이다.

    `SDPanel*` StaticBody2D는 경로탐색·도달성에서 제외된다 — 수위가 열고
    지나가므로 막힌 것으로 보면 안 된다. 제외는 janitor.gd·verify_floor_reach·
    verify_janitor_route·verify_hiding_spots 네 곳에 같은 이름 규칙으로 있다.
    """
    # 문 틈 목록을 먼저 모은다 — 열린 문짝이 옆 방의 문 자리를 덮지 않는 방향을
    # 고르는 데 쓴다(사선 띠의 좁은 화장실은 제 벽 안에 문짝이 다 들어가지 않는다).
    gaps = []
    for key, (label, door, x0, x1, topf, botf) in sc.room_meta.items():
        if prop_kind(key, label) is None or door not in ("top", "bottom"):
            continue
        cx = (x0 + x1) / 2
        wy = topf(cx) if door == "top" else botf(cx) - T
        gaps.append((key, cx - DOOR / 2, cx + DOOR / 2, wy + T / 2))

    def covers_gap(key, lo, hi, y):
        for okey, ox0, ox1, oy in gaps:
            if okey != key and lo < ox1 and hi > ox0 and abs(oy - y) < T:
                return True
        return False

    for key, (label, door, x0, x1, topf, botf) in sc.room_meta.items():
        # 라벨 없는 막힌 공간만 뺀다. #252 전에는 교실에만 문이 있어서 화장실·
        # 창고·부서실은 문 표식만 있고 그냥 통과됐다.
        if prop_kind(key, label) is None or door not in ("top", "bottom"):
            continue
        cx = (x0 + x1) / 2
        # 사선 띠(오른쪽 중간)의 벽은 110px 문 폭에서 28px 내려간다 — 문짝과
        # 충돌판을 축정렬 사각형으로 내면 벽을 벗어난다. 벽 윗변 함수로 낸다.
        wall_top = (lambda x: topf(x)) if door == "top" else (lambda x: botf(x) - T)
        wy0, wy1 = wall_top(cx), wall_top(cx) + T
        my = (wy0 + wy1) / 2
        dl, dr = cx - DOOR / 2, cx + DOOR / 2
        yl, yr = wall_top(dl), wall_top(dr)
        slope = (yr - yl) / DOOR
        # 미는 방향 — 맵 밖으로 나가지 않고, 옆 방 문 자리를 덮지 않는 쪽.
        # 방끼리 벽을 맞대고 있어 어느 쪽이든 벽 위를 지나간다(벽 속으로 들어가는
        # 것처럼 보인다). 사선 벽에서는 기울기만큼 같이 내려가야 벽에 붙어 있다.
        cands = [d for d in (DOOR, -DOOR)
                 if EDGE <= dl + d and dr + d <= W - EDGE]
        if not cands:
            cands = [DOOR if dr + DOOR <= W - EDGE else -DOOR]
        travel = next((d for d in cands
                       if not covers_gap(key, dl + d, dr + d, my + d * slope)),
                      cands[0])
        ty = n(travel * slope)
        root = f"SlideDoor_{key}"
        sc.node(f'[node name="{root}" type="Area2D" parent="."]\n'
                f'collision_layer = 2\ncollision_mask = 1\n'
                f'script = ExtResource("6_sliding")\n'
                f'travel = {n(travel)}\n'
                + (f'travel_y = {ty}\n' if float(ty) != 0.0 else "")
                + f'leaf_visual = NodePath("../WallGlow/RoomWallVisuals/SDVis_{key}")\n'
                # 방 창문 달빛은 이 문이 켠다(#292). 창 없는 방은 묶음이 없다.
                + (f'room_lights = NodePath("../Lights/Room_{key}")\n'
                   if f'name="Room_{key}"' in text_of(sc) else ''))
        sc.node(f'[node name="Zone" type="CollisionShape2D" parent="{root}"]\n'
                f'position = Vector2({n(cx)}, {n(my)})\n'
                f'shape = SubResource("RectangleShape2D_door_zone")\n')
        sc.node(f'[node name="SDPanel" type="StaticBody2D" parent="{root}"]\n')
        # 충돌 + 광원 차단체를 짝으로 낸다(#256). 닫힌 문이 빛을 막아야 문 너머
        # 방 안이 안 보인다 — 없으면 문 틈이 벽 없는 구간이라 손전등이 그대로
        # 통과해 문이 있으나 마나였다.
        #
        # 차단체는 문짝 몸체의 자식이라 문과 함께 움직인다. 열리면 벽 쪽으로
        # 비켜나 그 자리 벽 차단체와 겹치고 문 틈이 비므로, 여닫이에 맞춰
        # 켜고 끄는 코드가 필요 없다.
        #
        # 이름을 …DoorCollision으로 두면 verify_scenes의 벽↔차단체 1:1 검사에
        # 자동으로 편입되어 누락·폴리곤 불일치를 검사기가 잡아 준다.
        #
        # 두께는 벽 전체다. 예전처럼 DOOR_LEAF_T(10)로 끼워 두면 위아래 3px씩
        # 틈이 남아 그리로 빛이 샌다.
        sc.solid(f"{key}DoorCollision", f"{root}/SDPanel",
                 poly((dl, yl), (dr, yr), (dr, yr + T), (dl, yl + T)))
        # 시각은 WallGlow 안에. 레이어 0에 두면 CanvasLayer(layer=1)의 문 표식·
        # 벽 시각이 z_index와 무관하게 덮어 문이 아예 안 보인다(#234). 같은 문의
        # Door_ 마커보다 뒤에 선언되므로 그 위에 그려지고, 열려서 밀리면 벽 시각
        # 뒤로 숨는다. 충돌·차단체와 같은 벽 두께 전체를 쓴다.
        sc.poly2d(f"SDVis_{key}", "WallGlow/RoomWallVisuals",
                  C_LEAF, poly((dl, yl), (dr, yr), (dr, yr + T), (dl, yl + T)), z=2)


def _keepout_for(sc, x0, x1, clear=PROP_CLUE_CLEAR):
    out = [(px - clear, py - clear, px + clear, py + clear)
           for px, py in sc.clue_pts if x0 - 40 <= px <= x1 + 40]
    # 손배치 가구(#215) 위에도 깔지 않는다. 단서 여유(76px)로는 가구 가장자리가
    # 삐져나온다 — 창의체험부 책상은 단서보다 넓다.
    out += [(fx0 - 8, fy0 - 8, fx1 + 8, fy1 + 8)
            for fx0, fy0, fx1, fy1 in sc.furniture if x0 - 40 <= fx0 <= x1 + 40]
    return out


# ── 방 종류별 부속 ───────────────────────────────────────────
# 규격 사각형만 깔면 실험대와 선반이 크기만 다른 상자로 보인다. 단위 위에
# 올리는 소품(PT_), 단위 옆에 붙는 동반 집기(PC_), 벽에 거는 장식(PD_),
# 문에서 먼 구석에 두는 집기(PC_)를 종류마다 다르게 붙인다.

# 종류 -> (이름, 폭 비율, 높이 비율, 색). 단위 안쪽에 들어가는 소품.
PROP_OVERLAY = {
    "office":   ("papers", 0.55, 0.42, C_PAPER),
    "computer": ("monitor", 0.72, 0.52, C_MONITOR),
    "lab":      ("sink", 0.20, 0.60, C_SINK),
    "storage":  ("box", 0.62, 0.46, C_BOOK),
    "entrance": ("mat", 0.80, 0.34, C_MAT),
    "janitor":  ("papers", 0.55, 0.42, C_PAPER),
    "hall":     ("cup", 0.40, 0.36, C_PAPER),
}

# 종류 -> (이름, 폭, 높이, 색). 단위 아래에 붙는 의자.
PROP_COMPANION = {
    "office":   ("chair", 26, 15, C_CHAIR),
    "computer": ("chair", 22, 14, C_CHAIR),
    "janitor":  ("chair", 26, 15, C_CHAIR),
    "hall":     ("chair", 24, 14, C_CHAIR),
}

# 종류 -> (이름, 폭, 두께, 색). 문 반대쪽 벽 가운데에 거는 장식.
WALL_DECOR = {
    "office":   ("wboard", 200, 10, C_WBOARD),
    "lab":      ("wboard", 170, 10, C_WBOARD),
    "computer": ("wboard", 150, 10, C_WBOARD),
    "janitor":  ("keys", 90, 10, C_KEYBOARD_WALL),
    "entrance": ("sign", 160, 10, C_SIGN),
    "storage":  ("sign", 90, 8, C_SIGN),
    "hall":     ("sign", 110, 8, C_SIGN),
}

# 종류 -> (이름, 폭, 높이, 색). 문에서 먼 구석, 벽 여유 띠 안에 세우는 집기.
# 폭은 PROP_EDGE(32)보다 좁아야 단위 격자와 겹치지 않는다.
CORNER_PROP = {
    "computer": ("rack", 28, 46, C_RACK),
    "lab":      ("chem", 28, 60, C_CABINET),
    "office":   ("cabinet", 28, 56, C_CABINET),
    "janitor":  ("bed", 28, 64, C_BED),
    "hall":     ("plant", 26, 26, C_PLANT),
    "entrance": ("plant", 26, 26, C_PLANT),
    "toilet":   ("bin", 22, 24, C_BIN),
}

TOILET_SINK = (26, 30)     # 세면대 — 왼쪽 벽 여유 띠에 세로로 세운다
TOILET_URINAL = (22, 26)   # 소변기 — 오른쪽 벽 여유 띠(남자 화장실만)


# 대변기 칸(#262, #265에서 오른쪽 벽으로). 예전에는 막힌 사각형이라 들어갈 수
# 없고 변기도 없었다. 칸막이 세 면 + 열린 앞면으로 만들어 실제로 걸어 들어갈 수
# 있게 한다.
#
# **오른쪽 벽에 등을 대고 세로로 쌓이며 왼쪽으로 열린다**(#265 사용자 결정).
# 세면대는 왼쪽 벽, 소변기는 문 반대쪽 벽으로 간다 — 실제 학교 화장실 배치다.
#
# 크기 기준은 플레이어 **충돌**(캡슐 반경 8·높이 26)이지 스프라이트(60x72)가
# 아니다. 스프라이트가 칸보다 커서 칸막이 위로 삐져나오는 것은 탑다운에서
# 흔한 일이고, 플레이어는 집기 위에 그려진다(#250).
CUB_DEPTH = 96      # 오른쪽 벽에서 왼쪽으로 나오는 깊이(칸막이 포함)
CUB_H = 84          # 칸 하나의 세로 크기(목표) — 남는 높이는 나눠 넓힌다
CUB_PART = 8        # 칸막이 두께
CUB_MIN_H = 52      # 이보다 낮으면 칸을 만들지 않는다
CUB_MAX_DEPTH_RATIO = 0.46   # 방 안쪽 폭 대비 깊이 상한
#   방 중심은 비어 있어야 한다(verify_floor_reach가 방 폴리곤 중심으로 도달성을
#   본다). 깊이를 방 폭의 절반 넘게 잡으면 칸 앞면이 방 중심을 덮는다.


def _toilet_cubicles(sc, key, wr, by0, by1, door, keepout, taken, room_w):
    """오른쪽 벽 [by0,by1] 구간에 대변기 칸을 세로로 쌓는다. 앞(왼쪽)이 열린다."""
    avail = by1 - by0
    if avail < CUB_MIN_H + 2 * CUB_PART:
        return
    depth = min(CUB_DEPTH, room_w * CUB_MAX_DEPTH_RATIO)
    if depth < CUB_PART + 44:
        return
    cx1 = wr                                  # 오른쪽 벽 안쪽 면 = 칸 뒷면
    cx0 = cx1 - depth                         # 칸 앞면(열린 쪽)

    n = max(1, int((avail - CUB_PART) // (CUB_H + CUB_PART)))
    inner_h = (avail - CUB_PART * (n + 1)) / n
    if inner_h < CUB_MIN_H:
        n = max(1, n - 1)
        inner_h = (avail - CUB_PART * (n + 1)) / n
    if inner_h < CUB_MIN_H:
        return
    if any(_overlap((cx0, by0, cx1, by1), k) for k in keepout + taken):
        return

    # 뒷벽 칸막이 한 줄(오른쪽 벽에 붙는다)
    back = (cx1 - CUB_PART, by0, cx1, by1)
    sc.prop(f"{key}_cubback", rect(*back), C_STALL)
    taken.append(back)

    for i in range(n + 1):
        py = by0 + i * (inner_h + CUB_PART)
        # 칸 사이 칸막이는 뒷벽 안쪽 면까지만 온다. 모서리에서 겹치면
        # verify_props가 집기끼리 겹쳤다고 잡는다.
        div = (cx0, py, cx1 - CUB_PART, py + CUB_PART)
        sc.prop(f"{key}_cubdiv{i}", rect(*div), C_STALL)
        taken.append(div)

    for i in range(n):
        iy0 = by0 + CUB_PART + i * (inner_h + CUB_PART)
        iy1 = iy0 + inner_h
        # 변기 — 뒷벽(오른쪽)에 붙인다. 칸을 다 채우면 안 된다: 도달성 격자가
        # 장애물을 플레이어 반경(10)만큼 부풀리므로 변기 앞에 40px은 남아야 한다.
        bw = min(36.0, (cx1 - CUB_PART - cx0) * 0.40)
        bh = min(38.0, inner_h - 16)
        my = (iy0 + iy1) / 2
        bx1 = cx1 - CUB_PART - 6
        sc.prop(f"{key}_bowl{i}", rect(bx1 - bw, my - bh / 2, bx1, my + bh / 2),
                C_TOILET)
        # 열린 문 — 앞쪽 한 귀퉁이에만 짧게. 앞을 가로지르면 못 들어가는 칸으로
        # 보인다.
        sc.decor(f"{key}_cubdoor{i}",
                 rect(cx0, iy0, cx0 + CUB_PART, iy0 + inner_h * 0.42), C_STALLDOOR)
        # 휴지걸이 — 칸막이 위에 얹는다(PT_는 집기 안에 온전히 들어가야 한다).
        sc.overlay(f"{key}_tissue{i}",
                   rect(cx1 - CUB_PART - 13, iy0 - CUB_PART + 1,
                        cx1 - CUB_PART - 1, iy0 - 1), C_TISSUE)


def add_room_fixtures(sc, key, kind, x0, x1, topf, botf, door, keepout, units):
    """방 종류에 맞는 부속을 붙인다. units는 이미 놓인 단위 사각형들이다."""
    wl, wr = x0 + T, x1 - T
    cx = (x0 + x1) / 2
    wt, wb = topf(cx) + T, botf(cx) - T
    iy0, iy1 = wt + PROP_EDGE, wb - PROP_EDGE
    taken = list(units)
    def strip_bounds(sx0, sx1):
        """[sx0,sx1] 구간에서 집기를 놓을 수 있는 세로 범위(벽 안쪽 + 2px).

        #265에서 사선 방을 없앤 뒤로는 어느 x에서 재도 같다. 구간을 받는 꼴은
        남겨 둔다 — 호출부가 이미 그렇게 쓰고 있고, 방 모양이 다시 바뀌어도
        여기만 고치면 된다.
        """
        return topf(sx0) + T + 2, botf(sx1) - T - 2

    # 단위 위 소품 + 단위 아래 의자
    over = PROP_OVERLAY.get(kind)
    comp = PROP_COMPANION.get(kind)
    for i, (ux0, uy0, ux1, uy1) in enumerate(units):
        if over is not None:
            name, fw, fh, color = over
            w = (ux1 - ux0) * fw
            h = (uy1 - uy0) * fh
            mx, my = (ux0 + ux1) / 2, (uy0 + uy1) / 2
            sc.overlay(f"{key}_{name}{i}",
                       rect(mx - w / 2, my - h / 2, mx + w / 2, my + h / 2), color)
        if comp is None:
            continue
        name, cw, ch, color = comp
        mx = (ux0 + ux1) / 2
        cell = (mx - cw / 2, uy1 + 4, mx + cw / 2, uy1 + 4 + ch)
        if cell[3] > iy1 or any(_overlap(cell, k) for k in keepout + taken):
            continue
        sc.prop(f"{key}_{name}{i}", rect(*cell), color)
        taken.append(cell)

    # 문 반대쪽 벽 장식
    deco = WALL_DECOR.get(kind)
    if deco is not None:
        name, dw, dt, color = deco
        dw = min(dw, (wr - wl) * 0.7)
        dy = (wb - dt, wb) if door == "top" else (wt, wt + dt)
        sc.decor(f"{key}_{name}", rect(cx - dw / 2, dy[0], cx + dw / 2, dy[1]), color)

    # 문에서 먼 구석의 집기
    corner = CORNER_PROP.get(kind)
    if corner is not None:
        name, cw, ch, color = corner
        # 좌·우 벽 구석을 문에서 먼 쪽부터 네 자리 시도한다. 수위실은 단서
        # 4개가 방 가운데 띠를 차지해 한 자리만 보면 늘 막혔다.
        # 화장실만 예외로 왼쪽 벽만 쓴다 — 오른쪽 벽은 대변기 칸 자리다.
        # (휴지통이 오른쪽 구석을 차지한 방은 칸이 통째로 취소됐다: 25곳 중 13곳)
        sides = (wl + 2,) if kind == "toilet" else (wl + 2, wr - 2 - cw)
        for sx in sides:
            stop, sbot = strip_bounds(sx, sx + cw)
            order = (sbot - ch, stop) if door == "top" else (stop, sbot - ch)
            spot = None
            for cy0 in order:
                cell = (sx, cy0, sx + cw, cy0 + ch)
                if cell[1] < stop or cell[3] > sbot:
                    continue
                if any(_overlap(cell, k) for k in keepout + taken):
                    continue
                spot = cell
                break
            if spot is not None:
                sc.prop(f"{key}_{name}", rect(*spot), color)
                taken.append(spot)
                break

    # 화장실: 왼쪽 벽 여유 띠에 세면대를 세우고 그 위 벽에 거울을 건다.
    # 칸막이는 반대쪽에 이미 깔려 있어 이 띠가 비어 있다.
    if kind == "toilet":
        # 바닥 줄눈은 `floor_matte` **무늬**가 낸다(#277). 예전에는 여기서
        # 60px마다 폴리곤을 그었는데, 층당 46개의 2x328 막대가 바닥에 누워
        # 있었고 32px 타일 격자와도 어긋났다.
        # 배수구 — 방 가운데 아래쪽. 바닥 표시라 통행에 영향 없다.
        dx, dy = cx, (wt + wb) / 2 + (wb - wt) * 0.18
        sc.floor_mark(f"{key}_drain",
                      rect(dx - 11, dy - 11, dx + 11, dy + 11), C_DRAIN)
        # 바닥 물때 — 배수구 쪽으로 번진 자국 몇 군데.
        for i in range(3):
            sx0 = wl + (wr - wl) * (0.22 + 0.28 * i)
            sy0 = dy - 26 + 18 * (i % 2)
            sc.floor_mark(f"{key}_stain{i}",
                          rect(sx0, sy0, sx0 + 30 + 8 * i, sy0 + 14), C_STAIN)

        # 대변기 칸이 오른쪽 벽을 먼저 차지한다(#265). 나중에 놓으면 청소도구·
        # 휴지통이 이미 그 자리에 서 있어 칸이 안 들어간다.
        ctop, cbot = strip_bounds(wr - CUB_DEPTH, wr)
        _toilet_cubicles(sc, key, wr, ctop, cbot, door, keepout, taken, wr - wl)

        # 소변기 — 남자 화장실만. 오른쪽 벽은 대변기 칸이 쓰므로 문 반대쪽 벽에
        # 가로로 건다.
        if key.startswith("MensRoom"):
            uh, uw = TOILET_URINAL          # 가로로 걸어 폭·높이가 뒤바뀐다
            uy = (wb - 2 - uw) if door == "top" else (wt + 2)
            for i, cell in enumerate(_row(wl + 42, wr - CUB_DEPTH - 10, uy,
                                          uy + uw, uh, 16, keepout + taken)):
                sc.prop(f"{key}_urinal{i}", rect(*cell), C_URINAL)
                taken.append(cell)
                # 소변기 사이 칸막이 — 왼쪽 소변기의 왼 끝에 얇게 걸친다.
                if i > 0:
                    sc.decor(f"{key}_udiv{i}",
                             rect(cell[0] - 9, uy - 6, cell[0] - 3, uy + uw),
                             C_STALLDOOR)

        sw, sh = TOILET_SINK
        # 손건조기는 세면대보다 먼저 자리를 잡는다. 세면대가 왼쪽 띠를 세로로
        # 꽉 채워서 나중에 놓으면 남는 자리가 없다(처음에 0개였다).
        dtop0, dbot0 = strip_bounds(wl, wl + 9)
        # 구석 집기(휴지통)가 문에서 먼 끝을 먼저 차지한다 — 손건조기는
        # 반대쪽 끝에 붙인다. 같은 끝을 노리면 늘 밀려서 0개가 된다.
        dry_y = dtop0 + 4 if door == "top" else dbot0 - 34
        dry = (wl, dry_y, wl + 9, dry_y + 30)
        if not any(_overlap(dry, k) for k in keepout + taken):
            sc.decor(f"{key}_dryer", rect(*dry), C_DRYER)
            taken.append((wl, dry_y - 4, wl + 36, dry_y + 34))
        # 거울은 벽면 wl~wl+6, 세면대는 그 앞 wl+8부터 — 붙여 놓으면 거울이
        # 세면대에 파묻힌다(verify_props가 장식↔집기 겹침을 오류로 잡는다).
        sx = wl + 8
        stop, sbot = strip_bounds(sx, sx + sw)
        placed = _col(sx, sx + sw, stop, sbot, sh, 14, keepout + taken)
        for i, cell in enumerate(placed):
            sc.prop(f"{key}_sink{i}", rect(*cell), C_SINK)
            taken.append(cell)
        if placed:
            top = min(c[1] for c in placed)
            bot = max(c[3] for c in placed)
            sc.decor(f"{key}_mirror", rect(wl, top, wl + 6, bot), C_MIRROR)

        # 환풍기 — 문 쪽 벽, 문 틈 **왼쪽**에. 오른쪽은 대변기 칸이 벽까지 차지해
        # 자리가 없다(오른쪽에 뒀더니 25곳 전부 안 들어갔다).
        fan_y = (wt, wt + WALL_FACE) if door == "top" else (wb - 9, wb)
        fx1 = cx - DOOR / 2 - 20
        fan = (fx1 - 28, fan_y[0], fx1, fan_y[1])
        if fan[0] > wl + 40:
            sc.wall_decor(f"{key}_fan", rect(*fan), C_FAN)

        # 청소도구 — 문 반대쪽 벽 왼쪽 끝. 왼쪽 벽은 세면대가, 오른쪽 벽은 칸이
        # 다 쓴다(둘 다 시도했다가 0개가 나왔다).
        my0 = (wb - 2 - 30) if door == "top" else (wt + 2)
        cursor = wl + 44
        for name, w, h, color in (("mop", 30, 12, C_MOP),
                                  ("bucket", 18, 20, C_BUCKET)):
            cell = (cursor, my0, cursor + w, my0 + h)
            if cell[2] < wr - CUB_DEPTH - 10                     and not any(_overlap(cell, k) for k in keepout + taken):
                sc.prop(f"{key}_{name}", rect(*cell), color)
                taken.append(cell)
                cursor += w + 8


def add_props(sc, corridors=()):
    """방마다 종류에 맞는 집기를 깔고, 복도 벽에 비품을 붙인다.

    add_story·add_hiding 뒤에 불러야 한다 — 단서·은신처 좌표(sc.clue_pts)가
    채워진 뒤라야 그 자리를 피할 수 있다.
    """
    for key, (label, door, x0, x1, topf, botf) in sc.room_meta.items():
        kind = prop_kind(key, label)
        if kind is None:
            continue
        keepout = _keepout_for(sc, x0, x1)
        if kind == "classroom":
            _classroom(sc, key, x0, topf(x0), x1, botf(x1), door, keepout)
            continue
        if kind == "office":
            _office(sc, key, x0, topf(x0), x1, botf(x1), door, keepout)
            continue
        unit, gap, color = PROP_SPECS[kind]

        def inner_top(x, f=topf):
            return f(x) + T + PROP_EDGE

        def inner_bot(x, f=botf):
            return f(x) - T - PROP_EDGE

        ix0, ix1 = x0 + T + PROP_EDGE, x1 - T - PROP_EDGE
        cx = (x0 + x1) / 2
        height = inner_bot(cx) - inner_top(cx)
        aisle = min(PROP_AISLE_MAX, max(PROP_AISLE_MIN, height * 0.16))

        def mid(x):
            return (inner_top(x) + inner_bot(x)) / 2

        door_gap = (cx - DOOR / 2 - PROP_DOOR_PAD, cx + DOOR / 2 + PROP_DOOR_PAD)
        near = []
        if door == "top":
            near = [(door_gap[0], topf(cx), door_gap[1], mid(cx))]
        elif door == "bottom":
            near = [(door_gap[0], mid(cx), door_gap[1], botf(cx))]

        if kind == "toilet":
            # 화장실은 규격 사각형 대신 대변기 칸을 놓는다(#262).
            # 칸은 add_room_fixtures가 세면대·소변기 자리를 잡은 뒤에 만든다.
            rects = []
        else:
            rects = _fill(inner_top, lambda x: mid(x) - aisle, ix0, ix1, unit, gap,
                          keepout + (near if door == "top" else []))
            rects += _fill(lambda x: mid(x) + aisle, inner_bot, ix0, ix1, unit, gap,
                           keepout + (near if door == "bottom" else []))
        for i, (rx0, ry0, rx1, ry1) in enumerate(rects):
            sc.prop(f"{key}_{i}", rect(rx0, ry0, rx1, ry1), color)
        add_room_fixtures(sc, key, kind, x0, x1, topf, botf, door, keepout, rects)

    add_corridor_props(sc, corridors)


def add_corridor_props(sc, corridors):
    """복도 벽마다 사물함·게시판·소화기를 붙인다.

    복도가 맨바닥이라 층을 내려가도 같은 회색 통로만 보였다. 사물함은 실체가
    있어 시야도 조금 가리고, 게시판·소화기는 충돌이 없어 통행에 영향이 없다.
    """
    for cy0, cy1 in corridors:
        seat = 0          # 벽면 순번 — 몇 칸에 하나씩 정수기를 둔다
        for key, (label, door, x0, x1, topf, botf) in sc.room_meta.items():
            if not label:
                continue
            cx = (x0 + x1) / 2
            door_gap = (cx - DOOR / 2 - CORR_DOOR_PAD, cx + DOOR / 2 + CORR_DOOR_PAD)
            keepout = _keepout_for(sc, x0, x1)
            keepout.append((door_gap[0], cy0 - 1, door_gap[1], cy1 + 1))
            # 벽면이 복도의 위쪽인지 아래쪽인지에 따라 장식을 붙이는 방향이
            # 뒤집힌다. 두께가 서로 다르므로(게시판 10, 소화기 22) 각각 벽면에
            # 맞춰 앵커를 잡아야 벽을 파고들지 않는다.
            if abs(botf(x1) - cy0) < 1:          # 방이 복도 위쪽에 접한다
                # 이 방의 아래 벽은 앞면이 복도로 WALL_FACE만큼 내려온다(#268).
                # 사물함·비품을 그만큼 비켜 놓지 않으면 앞면에 가린다.
                base = cy0 + WALL_FACE
                ly0, ly1 = base, base + CORR_LOCKER_D
                wain = (base - WAINSCOT, base)   # 걸레받이는 앞면 **아래 끝**에
                pil = (cy0, base)                # 기둥은 앞면 전체를 덮는다

                def face(depth, base=base):
                    return base, base + depth
            elif abs(topf(x0) - cy1) < 1:        # 방이 복도 아래쪽에 접한다
                # 이쪽 벽의 앞면은 방 안으로 내려가므로 복도 쪽은 그대로 쓴다.
                ly0, ly1 = cy1 - CORR_LOCKER_D, cy1
                wain = (cy1, cy1 + WAINSCOT)
                pil = (cy1, cy1 + T)

                def face(depth, base=cy1):
                    return base - depth, base
            else:
                continue
            # 걸레받이와 기둥 — 벽 띠 안에 그린다. 사물함은 벽 바깥(복도 쪽)에
            # 서므로 가리지 않는다. WallGlow 안이라 벽 위에 그려지고 어둠을
            # 받지 않는다 — 벽과 같은 취급이다.
            gap0, gap1 = cx - DOOR / 2, cx + DOOR / 2
            for seg0, seg1 in ((x0 + T, gap0), (gap1, x1 - T)):
                if seg1 - seg0 > 20:
                    sc.wall_decor(f"Wain_{key}_{int(cy0)}_{int(seg0)}",
                                  rect(seg0, wain[0], seg1, wain[1]), C_WAINSCOT)
            px = x0 + T + PILASTER_GAP
            pi = 0
            while px < x1 - T - PILASTER[0]:
                if not (gap0 - 24 < px < gap1 + 24):
                    sc.wall_decor(f"Pil_{key}_{int(cy0)}_{pi}",
                                  rect(px, pil[0], px + PILASTER[0], pil[1]),
                                  C_PILASTER)
                    pi += 1
                px += PILASTER_GAP

            # 문 앞 발판 — 복도 바닥에 리듬을 준다. 장식이라 통행에 영향 없음.
            if door in ("top", "bottom"):
                mw, mh = CORR_MAT
                my0, my1 = face(mh + 6)
                sc.decor(f"Mat_{key}_{int(cy0)}",
                         rect(cx - mw / 2, min(my0, my1) + 4,
                              cx + mw / 2, min(my0, my1) + 4 + mh), C_MAT)
            # 정수기 — 벽면 네 곳마다 하나. 사물함보다 먼저 자리를 잡고,
            # 그 자리를 keepout에 넣어 사물함이 겹치지 않게 한다.
            seat += 1
            # 소화전 함은 사물함보다 먼저 자리를 잡는다. 자투리 벽면을
            # 기다리면 사물함이 벽을 다 먹어서 한 개도 안 걸린다.
            if seat % 3 == 0:
                hw, hh = CORR_HYDRANT
                top_side = abs(botf(x1) - cy0) < 1
                hy0, hy1 = (cy0, cy0 + hh) if top_side else (cy1 - hh, cy1)
                cell = (x1 - T - 8 - hw, hy0, x1 - T - 8, hy1)
                if not any(_overlap(cell, k) for k in keepout):
                    sc.decor(f"Hydrant_{key}_{int(cy0)}", rect(*cell), C_HYDRANT)
                    keepout.append((cell[0] - 8, ly0 - 1, cell[2] + 8, ly1 + 1))
            if seat % 4 == 0:
                ww, wh = CORR_WATER
                wy0, wy1 = (cy0, cy0 + wh) if abs(botf(x1) - cy0) < 1 else (cy1 - wh, cy1)
                cell = (x0 + T + 6, wy0, x0 + T + 6 + ww, wy1)
                if not any(_overlap(cell, k) for k in keepout):
                    sc.prop(f"Corr_{key}_{int(cy0)}_water", rect(*cell), C_WATER)
                    sc.corridor_props.append(cell)
                    keepout.append((cell[0] - 8, ly0 - 1, cell[2] + 8, ly1 + 1))
            placed = _row(x0 + T, x1 - T, ly0, ly1, CORR_LOCKER_W,
                          CORR_LOCKER_GAP, keepout)
            for i, r4 in enumerate(placed):
                sc.prop(f"Corr_{key}_{int(cy0)}_{i}", rect(*r4), C_LOCKER)
                sc.corridor_props.append(r4)
            # 사물함이 못 들어간 벽면(문 옆 자투리)에 소화기와 게시판을 건다
            taken = [(a, ly0, b, ly1) for a, _, b, _ in placed]
            spans = _free_spans(x0 + T, x1 - T, ly0, ly1, keepout + taken,
                                floor_w=CORR_FIRE[0] + 8)
            for j, (sx0, sx1) in enumerate(spans):
                # 자투리 폭에 맞춰 가려 건다. 무조건 소화기부터 걸면 좁은
                # 자투리마다 소화기만 늘어서고 게시판이 한 장도 안 남는다.
                fw, fh = CORR_FIRE
                width = sx1 - sx0
                nx0 = sx0
                if width >= 90 or width < 44:
                    fy0, fy1 = face(fh)
                    sc.decor(f"Fire_{key}_{int(cy0)}_{j}",
                             rect(sx0 + 4, fy0, sx0 + 4 + fw, fy1), C_FIRE)
                    nx0 = sx0 + fw + 12
                if sx1 - nx0 >= 40:
                    w = min(CORR_NOTICE_W, sx1 - nx0 - 8)
                    mx = (nx0 + sx1) / 2
                    ny0, ny1 = face(CORR_NOTICE_D)
                    sc.decor(f"Notice_{key}_{int(cy0)}_{j}",
                             rect(mx - w / 2, ny0, mx + w / 2, ny1), C_NOTICE)


def room_floor(key, label):
    """방 바닥색. 막힌 공간은 더 어둡게 해 들어갈 수 없는 곳임을 드러낸다."""
    kind = prop_kind(key, label)
    if kind is None:
        return C_BLOCKED_FLOOR if not label else C_ROOM
    return ROOM_FLOOR.get(kind, C_ROOM)


# ── 바닥 구역 · 복도 분위기 ──────────────────────────────────
# 맵 전체가 C_FLOOR 한 색이고 방만 조금 어두워서, 복도인지 방인지 화장실인지
# 창고인지가 바닥으로 전혀 읽히지 않았다. 구역마다 바닥을 따로 칠한다.
#
# 레이어 순서가 곧 그리기 순서다(먼저 선언된 형제가 먼저 그려진다):
#   Floor(맵 전체 바탕) → Ground(복도 바닥·타일 이음매) → Rooms(방 바닥)
#   → Props(집기) → Stairwells → WallGlow(벽·문·라벨, CanvasLayer)
# Ground는 충돌이 없는 순수 시각 레이어다.
PLANK = 64            # 마루 널 폭
PLANK_SEAM = 2        # 널 이음매 두께
PLANK_JOINT = 560     # 널 이음매 간격(줄마다 엇갈림)


def add_ground(sc, corridors):
    """복도 바닥을 깐다.

    Rooms보다 먼저 선언된 Ground 아래에 들어가므로 방 바닥이 이 위에 덮인다 —
    복도 띠가 방과 겹쳐도 결과가 어긋나지 않는다.

    널 선은 **폴리곤이 아니라 `floor_board` 무늬가 낸다**(#268). #242는 64px마다
    Polygon2D로 그렸는데, 널을 직각으로 돌리자 층당 150개가 넘게 생겨 노드
    예산을 넘겼다. 무늬로 옮기니 노드 0개에 타일 격자(32px)와도 정확히 맞는다.
    """
    for cy0, cy1 in corridors:
        sc.ground(f"Corridor_{int(cy0)}", rect(EDGE, cy0, W - EDGE, cy1),
                  C_CORRIDOR)


def build_common(fl, spec):
    sc = Scene()
    sc.floor_no = fl
    sc.rect_shapes = [("RectangleShape2D_wall_h", f"Vector2({W}, 40)"),
                      ("RectangleShape2D_wall_v", f"Vector2(40, {H})")]
    sc.rect_shapes += [("RectangleShape2D_stair_zone", "Vector2(240, 56)"),
                       ("RectangleShape2D_key_zone", "Vector2(48, 48)"),
                       ("RectangleShape2D_door_zone", "Vector2(140, 60)"),
                      ("RectangleShape2D_window_zone", "Vector2(170, 52)")]

    sc.node('[node name="SchoolFloor" type="Node2D"]\n' + TEX_FLAGS)
    sc.poly2d("Floor", ".", C_FLOOR, rect(0, 0, W, H))
    sc.node('[node name="Ground" type="Node2D" parent="."]\n')
    sc.node('[node name="WallGlow" type="CanvasLayer" parent="."]\n'
            'layer = 1\nfollow_viewport_enabled = true\n')
    sc.node('[node name="RoomWallVisuals" type="Node2D" parent="WallGlow"]\n'
            + TEX_FLAGS)
    sc.node('[node name="Rooms" type="Node2D" parent="."]\n')
    sc.node('[node name="RoomMarks" type="Node2D" parent="."]\n')
    sc.node('[node name="Props" type="Node2D" parent="."]\n')
    add_lights_root(sc)
    sc.node('[node name="Stairwells" type="Node2D" parent="."]\n')
    sc.node('[node name="Labels" type="Node2D" parent="WallGlow"]\n')
    sc.node('[node name="RoomWalls" type="StaticBody2D" parent="."]\n')
    sc.node('[node name="PropBodies" type="StaticBody2D" parent="."]\n')
    sc.node('[node name="StairWalls" type="StaticBody2D" parent="."]\n')

    # 북쪽 교실 8칸 (문은 아래변)
    for i, nm in enumerate(spec["north"]):
        x0, x1 = north_x(i, len(spec["north"]))
        add_room(sc, f"North{i+1}", nm, x0, NORTH_Y0, x1, NORTH_Y1, "bottom")

    # 중간 띠 좌 — 문은 북쪽 복도(위)로 낸다
    for key, lb, x0, x1 in MID_LEFT:
        add_room(sc, key, lb, x0, MID_Y0, x1, MID_Y1, "top" if lb else None)
    # 중간 띠 우(사선) — 문은 위쪽 복도
    for key, lb, x0, x1 in MID_RIGHT:
        add_room(sc, key, lb, x0, MID_Y0, x1, MID_Y1, "top" if lb else None)

    # 계단실 2곳
    add_stairwell(sc, "StairA", *STAIR_A)
    add_stairwell(sc, "StairB", *STAIR_B)
    add_stair_markers(sc, "StairA", *STAIR_A, floor=fl)
    if 1 not in SEALED.get(fl, set()):
        add_stair_markers(sc, "StairB", *STAIR_B, floor=fl)
    if fl in LOCKED:
        add_stair_locks(sc, fl, LOCKED[fl], [STAIR_A, STAIR_B])

    # 공백 구역(건물 밖) 봉인 — 중앙다리 폭만 열어 둔다.
    # 위 경계: 왼쪽은 수평, 오른쪽은 중간 띠와 같은 기울기.
    sc.wall("VoidTopL", rect(0, MID_Y1, BRIDGE_X0, MID_Y1 + T))
    sc.wall("VoidTopR", rect(BRIDGE_X1, MID_Y1, W, MID_Y1 + T))
    # 아래 경계: 남쪽 복도와 맞닿는 수평선
    sc.wall("VoidBotL", rect(0, VOID_Y1 - T, BRIDGE_X0, VOID_Y1))
    sc.wall("VoidBotR", rect(BRIDGE_X1, VOID_Y1 - T, W, VOID_Y1))

    # 공백 구역 내부를 메워 통행 후보에서 뺀다(수위 스폰 방지)
    fill_void(sc, "VoidFillL", 0, BRIDGE_X0 - T, lambda x: MID_Y1 + T, VOID_Y1 - T)
    fill_void(sc, "VoidFillR", BRIDGE_X1 + T, W,
              lambda x: MID_Y1 + T, VOID_Y1 - T)

    # 중앙다리 — 좌·우 벽
    sc.wall("BridgeL", rect(BRIDGE_X0 - T, BRIDGE_Y0, BRIDGE_X0, BRIDGE_Y1))
    sc.wall("BridgeR", rect(BRIDGE_X1, BRIDGE_Y0, BRIDGE_X1 + T, BRIDGE_Y1))

    # 남쪽 동
    for key, lb, x0, x1 in spec["south_left"] + spec["south_right"]:
        add_room(sc, key, lb, x0, SOUTH_Y0, x1, SOUTH_Y1, "top")
    # 하단 띠
    for key, lb, x0, x1 in spec["bottom_left"] + BOTTOM_RIGHT:
        add_room(sc, key, lb, x0, BOT_Y0, x1, BOT_Y1, "top")

    add_furniture(sc, fl)
    add_story(sc, fl)
    add_hiding(sc, fl)
    corridors = [(NORTH_Y1, MID_Y0), (VOID_Y1, SOUTH_Y0), (SOUTH_Y1, BOT_Y0)]
    add_ground(sc, corridors)
    add_props(sc, corridors)
    add_clutter(sc)
    add_sliding_doors(sc)
    add_outer(sc)
    return sc


def build_floor1():
    sc = Scene()
    sc.floor_no = 1
    sc.rect_shapes = [("RectangleShape2D_wall_h", f"Vector2({W}, 40)"),
                      ("RectangleShape2D_wall_v", f"Vector2(40, {H})"),
                      ("RectangleShape2D_stair_zone", "Vector2(240, 56)"),
                      ("RectangleShape2D_key_zone", "Vector2(48, 48)"),
                      ("RectangleShape2D_door_zone", "Vector2(140, 60)"),
                      ("RectangleShape2D_window_zone", "Vector2(170, 52)")]
    sc.node('[node name="SchoolFloor" type="Node2D"]\n' + TEX_FLAGS)
    sc.poly2d("Floor", ".", C_FLOOR, rect(0, 0, W, H))
    sc.node('[node name="Ground" type="Node2D" parent="."]\n')
    sc.node('[node name="WallGlow" type="CanvasLayer" parent="."]\n'
            'layer = 1\nfollow_viewport_enabled = true\n')
    sc.node('[node name="RoomWallVisuals" type="Node2D" parent="WallGlow"]\n'
            + TEX_FLAGS)
    sc.node('[node name="Rooms" type="Node2D" parent="."]\n')
    sc.node('[node name="RoomMarks" type="Node2D" parent="."]\n')
    sc.node('[node name="Props" type="Node2D" parent="."]\n')
    add_lights_root(sc)
    sc.node('[node name="Stairwells" type="Node2D" parent="."]\n')
    sc.node('[node name="Labels" type="Node2D" parent="WallGlow"]\n')
    sc.node('[node name="RoomWalls" type="StaticBody2D" parent="."]\n')
    sc.node('[node name="PropBodies" type="StaticBody2D" parent="."]\n')
    sc.node('[node name="StairWalls" type="StaticBody2D" parent="."]\n')

    for key, lb, x0, y0, x1, y1, door in FLOOR1["rooms"]:
        add_room(sc, key, lb, x0, y0, x1, y1, door)
    # 교무실(사선)
    sx0, sy0, sx1, sy1 = FLOOR1["staff"]
    add_room(sc, "StaffRoom", "교무실", sx0, sy0, sx1, sy1, "bottom")
    add_stairwell(sc, "StairA", *FLOOR1["stair"])
    add_stair_markers(sc, "StairA", *FLOOR1["stair"], floor=1)
    add_stair_locks(sc, 1, LOCKED[1], [FLOOR1["stair"]])
    # 1층 건물은 도면상 아래쪽 절반뿐이다. 북쪽 빈 구역에 경계벽을 세우고
    # 안쪽을 메워, 플레이어가 들어가지도 수위가 스폰되지도 않게 한다.
    sc.wall("Floor1North", rect(0, 1004, W, 1020))
    fill_void(sc, "VoidFillN", 0, W, lambda x: 0.0, 1004)

    # 현관 정문 — 방 아래변(건물 바깥쪽)에 보이는 문. ExitDoor 상호작용도 이 앞이다.
    ex0, ey1, ex1 = 1600, 2480, 2000
    sc.poly2d("Door_FrontGate", "WallGlow/RoomWallVisuals", C_DOOR,
              rect((ex0 + ex1) / 2 - DOOR / 2, ey1 - T, (ex0 + ex1) / 2 + DOOR / 2, ey1), z=1)
    add_furniture(sc, 1)
    add_story(sc, 1)
    add_hiding(sc, 1)
    # 1층은 아래쪽 절반만 건물이라 큰 홀 하나가 복도 역할을 한다.
    corridors = [(1500, BOT_Y0)]
    add_ground(sc, corridors)
    add_props(sc, corridors)
    add_clutter(sc)
    add_sliding_doors(sc)

    add_outer(sc)
    return sc


def fill_void(sc, key, x0, x1, top_fn, y_bottom, step=100):
    """건물 밖 구역을 실체(충돌+광원차단)로 메운다.

    벽으로 둘러싸기만 하면 그 안쪽 칸이 여전히 "통행 가능"으로 잡혀서,
    수위 스폰 후보(corridor_cells)에 들어간다 → 플레이어가 닿을 수 없는
    빈 구역에 수위가 나타나 영영 안 보인다(#159 F5: 1층에 수위 미등장).
    사선 경계는 좁은 세로 띠로 나눠 채운다."""
    x = x0
    i = 0
    while x < x1:
        right = min(x + step, x1)
        top = max(top_fn(x), top_fn(right))
        if y_bottom - top > 1.0:
            sc.solid(f"WC_{key}{i}", "RoomWalls", rect(x, top, right, y_bottom))
            i += 1
        x = right


def add_outer(sc):
    sc.node('[node name="Walls" type="StaticBody2D" parent="."]\n')
    for nm, pos, shape in [
        ("TopWall", f"Vector2({W/2}, 0)", "RectangleShape2D_wall_h"),
        ("BottomWall", f"Vector2({W/2}, {H})", "RectangleShape2D_wall_h"),
        ("LeftWall", f"Vector2(0, {H/2})", "RectangleShape2D_wall_v"),
        ("RightWall", f"Vector2({W}, {H/2})", "RectangleShape2D_wall_v"),
    ]:
        sc.node(f'[node name="{nm}" type="CollisionShape2D" parent="Walls"]\n'
                f'position = {pos}\nshape = SubResource("{shape}")\n')


ROOT = pathlib.Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    for fl in (1, 2, 3, 4, 5):
        sc = build_floor1() if fl == 1 else build_common(fl, LAYOUT[fl])
        text = sc.render(ext_for(text_of(sc)))
        path = ROOT / f"scenes/background/school_floor_{fl}.tscn"
        # write_text 기본값은 플랫폼 로케일·줄바꿈을 따른다. Windows에서 돌리면
        # cp949로 쓰려다 한글에서 죽고, 살아남아도 전 파일이 CRLF가 되어
        # 한 줄만 고쳐도 5개 층이 통째로 바뀐 것처럼 보인다(#169).
        with open(path, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
        print(f"OK floor{fl}: 노드 {len(sc.nodes)}개, 차단체 {len(sc.subs)}개")
