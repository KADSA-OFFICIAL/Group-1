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

T = 16          # 벽 두께
DOOR = 110      # 문 틈 폭
W, H = 3400, 2500   # 캔버스

C_FLOOR = "Color(0.14, 0.14, 0.16, 1)"
C_ROOM = "Color(0.1, 0.11, 0.12, 1)"
C_WALL = "Color(0.45, 0.48, 0.55, 1)"
C_DOOR = "Color(0.45, 0.32, 0.2, 1)"
C_SLAB = "Color(0.1, 0.12, 0.13, 1)"
C_STEP = "Color(0.22, 0.24, 0.28, 1)"
C_LOCK = "Color(0.55, 0.26, 0.22, 1)"   # 잠긴 계단 배리어
C_KEY = "Color(0.85, 0.74, 0.32, 1)"    # 열쇠
C_SEAL = "Color(0.38, 0.38, 0.40, 1)"   # 영구 봉인된 계단(콘크리트)

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
NORTH_GAP = 32

def north_x(i, count):
    span = W - 2 * EDGE
    pitch = (span + NORTH_GAP) / count
    x0 = EDGE + i * pitch
    return x0, x0 + pitch - NORTH_GAP

# 사선 우측 동: x가 늘면 y가 SLOPE만큼 내려간다
SLOPE = 0.26
RIGHT_X0 = 1920

def slope_y(x, base):
    return round(base + (x - RIGHT_X0) * SLOPE, 1)


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

# 1층: 도면이 다르다 — 상단 교실 3칸+운동장출입구+교무실, 하단 계단(좌)·화장실·현관·수위실·창고2
FLOOR1 = {
    "rooms": [   # (키, 라벨, x0, y0, x1, y1, 문 위치)
        ("Class1", "교실1", 20, 1020, 460, 1500, "bottom"),
        ("Class2", "교실2", 490, 1020, 810, 1500, "bottom"),
        ("Class3", "교실3", 840, 1020, 1360, 1500, "bottom"),
        ("YardExit", "운동장 출입구", 1390, 1020, 1920, 1500, None),   # 닫힘
        ("MensRoom1", "남자 화장실", 900, 2120, 1160, 2370, "top"),
        ("WomensRoom1", "여자 화장실", 1190, 2120, 1450, 2370, "top"),
        ("Entrance", "현관", 1600, 2120, 2000, 2480, "top"),           # 탈출구
        ("JanitorRoom", "수위실", 2100, 2120, 2560, 2480, "top"),
        ("Storage1", "창고", 2620, 2120, 2960, 2370, "top"),
        ("Storage2", "창고", 3000, 2120, 3380, 2370, "top"),
    ],
    "staff": (1950, 1020, 3380, 1500),   # 교무실(사선)
    "stair": (220, 2120, 660, 2440),     # 1층 계단 — 다른 층과 위치가 다르다
}


# ── 유틸 ────────────────────────────────────────────────────
def n(v):
    return int(v) if float(v) == int(float(v)) else round(float(v), 1)


def poly(*pts):
    return "PackedVector2Array(" + ", ".join(str(n(p)) for xy in pts for p in xy) + ")"


def rect(x0, y0, x1, y1):
    return poly((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class Scene:
    """노드/서브리소스를 모아 .tscn 텍스트로 직렬화."""

    def __init__(self):
        self.subs = []      # (id, polygon)
        self.nodes = []     # 텍스트 블록
        self.rect_shapes = []
        self.rooms = {}

    def occ(self, oid, polygon):
        self.subs.append((oid, polygon))

    def node(self, text):
        self.nodes.append(text)

    def poly2d(self, name, parent, color, polygon, z=None):
        z_line = f"z_index = {z}\n" if z is not None else ""
        self.node(f'[node name="{name}" type="Polygon2D" parent="{parent}"]\n'
                  f'{z_line}color = {color}\npolygon = {polygon}\n')

    def solid(self, key, parent_body, polygon):
        """충돌 + 광원차단 한 쌍 (시각은 별도로 추가)."""
        self.node(f'[node name="{key}" type="CollisionPolygon2D" parent="{parent_body}"]\n'
                  f'polygon = {polygon}\n')
        oid = f"Occ_{key}"
        self.occ(oid, polygon)
        self.node(f'[node name="LO_{key}" type="LightOccluder2D" parent="{parent_body}"]\n'
                  f'occluder = SubResource("{oid}")\n')

    def wall(self, key, polygon, body="RoomWalls"):
        """벽 3종 세트: 충돌 WC_ + 시각 WV_(WallGlow) + 광원차단 LO_WC_."""
        self.solid(f"WC_{key}", body, polygon)
        self.poly2d(f"WV_{key}", "WallGlow/RoomWallVisuals", C_WALL, polygon)

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
        steps = len(ext) + len(self.subs) + len(self.rect_shapes) + 1
        out = [f"[gd_scene load_steps={steps} format=3]\n"]
        for e in ext:
            out.append(e)
        out.append("")
        for sid, size in self.rect_shapes:
            out.append(f'[sub_resource type="RectangleShape2D" id="{sid}"]\nsize = {size}\n')
        for oid, p in self.subs:
            out.append(f'[sub_resource type="OccluderPolygon2D" id="{oid}"]\npolygon = {p}\n')
        out.append("")
        out.extend(self.nodes)
        return "\n".join(out)


def add_room(sc, key, label, x0, y0, x1, y1, door):
    """축정렬 방: 바닥 + 사방 벽(+문 틈). door in {top,bottom,left,right,None}."""
    sc.rooms[key] = (x0, y0, x1, y1)
    sc.poly2d(key, "Rooms", C_ROOM, rect(x0, y0, x1, y1))
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


def add_sloped_room(sc, key, label, x0, x1, base_top, base_bot, door="bottom"):
    """사선 방: 위·아래 변이 SLOPE만큼 기운 평행사변형(#159 사용자 결정)."""
    ty0, ty1 = slope_y(x0, base_top), slope_y(x1, base_top)
    by0, by1 = slope_y(x0, base_bot), slope_y(x1, base_bot)
    sc.rooms[key] = (x0, min(ty0, ty1), x1, max(by0, by1))
    sc.poly2d(key, "Rooms", C_ROOM, poly((x0, ty0), (x1, ty1), (x1, by1), (x0, by0)))
    if label:
        sc.label(key, label, (x0 + x1) / 2, (slope_y((x0 + x1) / 2, base_top)
                                             + slope_y((x0 + x1) / 2, base_bot)) / 2)

    # 좌·우 세로 벽
    sc.wall(f"{key}_left", poly((x0, ty0), (x0 + T, ty0), (x0 + T, by0), (x0, by0)))
    sc.wall(f"{key}_right", poly((x1 - T, ty1), (x1, ty1), (x1, by1), (x1 - T, by1)))
    cx = (x0 + x1) / 2
    dl, dr = cx - DOOR / 2, cx + DOOR / 2

    # 위 변(사선) — door=="top"이면 가운데를 문 틈으로 비운다
    if door == "top":
        tdl, tdr = slope_y(dl, base_top), slope_y(dr, base_top)
        sc.wall(f"{key}_topL", poly((x0, ty0), (dl, tdl), (dl, tdl + T), (x0, ty0 + T)))
        sc.wall(f"{key}_topR", poly((dr, tdr), (x1, ty1), (x1, ty1 + T), (dr, tdr + T)))
        sc.poly2d(f"Door_{key}", "WallGlow/RoomWallVisuals", C_DOOR,
                  poly((dl, tdl), (dr, tdr), (dr, tdr + T), (dl, tdl + T)), z=1)
    else:
        sc.wall(f"{key}_top", poly((x0, ty0), (x1, ty1), (x1, ty1 + T), (x0, ty0 + T)))

    # 아래 변(사선)
    if door == "bottom":
        sc.wall(f"{key}_botL", poly((x0, by0 - T), (dl, slope_y(dl, base_bot) - T),
                                    (dl, slope_y(dl, base_bot)), (x0, by0)))
        sc.wall(f"{key}_botR", poly((dr, slope_y(dr, base_bot) - T), (x1, by1 - T),
                                    (x1, by1), (dr, slope_y(dr, base_bot))))
        sc.poly2d(f"Door_{key}", "WallGlow/RoomWallVisuals", C_DOOR,
                  poly((dl, slope_y(dl, base_bot) - T), (dr, slope_y(dr, base_bot) - T),
                       (dr, slope_y(dr, base_bot)), (dl, slope_y(dl, base_bot))), z=1)
    else:
        sc.wall(f"{key}_bot", poly((x0, by0 - T), (x1, by1 - T), (x1, by1), (x0, by0)))


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
}


def text_of(sc):
    return "".join(sc.nodes)


def ext_for(body):
    """실제로 참조된 스크립트만 ext_resource로 선언한다(미사용 선언 방지)."""
    return [f'[ext_resource type="Script" path="{path}" id="{rid}"]'
            for rid, path in SCRIPTS.items() if f'ExtResource("{rid}")' in body]


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
        ("ComputerRoom", ["StairKey", "ScienceClue"]),            # ← 과학 실험실
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
POS_OVERRIDE = {(1, "ExitDoor"): (1800, 2432)}

# 열쇠를 주는 오브젝트는 층에 상관없이 "다가가면 획득"으로 통일한다(사용자 요청).
# 원래는 4층 열쇠 2개만 pickup_item(접촉)이고 나머지는 interactable(E 필요)이라
# 층마다 조작이 달랐다. 메시지와 플래그는 그대로 옮긴다.
AUTO_PICKUP = {"TaehoNote", "KeyCabinet", "SpareKeyHook", "DrainKey", "JanitorSafe"}


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


def build_common(fl, spec):
    sc = Scene()
    sc.rect_shapes = [("RectangleShape2D_wall_h", f"Vector2({W}, 40)"),
                      ("RectangleShape2D_wall_v", f"Vector2(40, {H})")]
    sc.rect_shapes += [("RectangleShape2D_stair_zone", "Vector2(240, 56)"),
                       ("RectangleShape2D_key_zone", "Vector2(48, 48)"),
                       ("RectangleShape2D_door_zone", "Vector2(140, 60)")]

    sc.node('[node name="SchoolFloor" type="Node2D"]\n')
    sc.poly2d("Floor", ".", C_FLOOR, rect(0, 0, W, H))
    sc.node('[node name="WallGlow" type="CanvasLayer" parent="."]\n'
            'layer = 1\nfollow_viewport_enabled = true\n')
    sc.node('[node name="RoomWallVisuals" type="Node2D" parent="WallGlow"]\n')
    sc.node('[node name="Rooms" type="Node2D" parent="."]\n')
    sc.node('[node name="Stairwells" type="Node2D" parent="."]\n')
    sc.node('[node name="Labels" type="Node2D" parent="WallGlow"]\n')
    sc.node('[node name="RoomWalls" type="StaticBody2D" parent="."]\n')
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
        add_sloped_room(sc, key, lb, x0, x1, MID_Y0, MID_Y1, "top" if lb else None)

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
    sc.wall("VoidTopR", poly((BRIDGE_X1, slope_y(BRIDGE_X1, MID_Y1)), (W, slope_y(W, MID_Y1)),
                             (W, slope_y(W, MID_Y1) + T), (BRIDGE_X1, slope_y(BRIDGE_X1, MID_Y1) + T)))
    # 아래 경계: 남쪽 복도와 맞닿는 수평선
    sc.wall("VoidBotL", rect(0, VOID_Y1 - T, BRIDGE_X0, VOID_Y1))
    sc.wall("VoidBotR", rect(BRIDGE_X1, VOID_Y1 - T, W, VOID_Y1))

    # 공백 구역 내부를 메워 통행 후보에서 뺀다(수위 스폰 방지)
    fill_void(sc, "VoidFillL", 0, BRIDGE_X0 - T, lambda x: MID_Y1 + T, VOID_Y1 - T)
    fill_void(sc, "VoidFillR", BRIDGE_X1 + T, W,
              lambda x: slope_y(x, MID_Y1) + T, VOID_Y1 - T)

    # 중앙다리 — 좌·우 벽
    sc.wall("BridgeL", rect(BRIDGE_X0 - T, BRIDGE_Y0, BRIDGE_X0, BRIDGE_Y1))
    sc.wall("BridgeR", rect(BRIDGE_X1, BRIDGE_Y0, BRIDGE_X1 + T, BRIDGE_Y1))

    # 남쪽 동
    for key, lb, x0, x1 in spec["south_left"] + spec["south_right"]:
        add_room(sc, key, lb, x0, SOUTH_Y0, x1, SOUTH_Y1, "top")
    # 하단 띠
    for key, lb, x0, x1 in spec["bottom_left"] + BOTTOM_RIGHT:
        add_room(sc, key, lb, x0, BOT_Y0, x1, BOT_Y1, "top")

    add_story(sc, fl)
    add_outer(sc)
    return sc


def build_floor1():
    sc = Scene()
    sc.rect_shapes = [("RectangleShape2D_wall_h", f"Vector2({W}, 40)"),
                      ("RectangleShape2D_wall_v", f"Vector2(40, {H})"),
                      ("RectangleShape2D_stair_zone", "Vector2(240, 56)"),
                      ("RectangleShape2D_key_zone", "Vector2(48, 48)"),
                      ("RectangleShape2D_door_zone", "Vector2(140, 60)")]
    sc.node('[node name="SchoolFloor" type="Node2D"]\n')
    sc.poly2d("Floor", ".", C_FLOOR, rect(0, 0, W, H))
    sc.node('[node name="WallGlow" type="CanvasLayer" parent="."]\n'
            'layer = 1\nfollow_viewport_enabled = true\n')
    sc.node('[node name="RoomWallVisuals" type="Node2D" parent="WallGlow"]\n')
    sc.node('[node name="Rooms" type="Node2D" parent="."]\n')
    sc.node('[node name="Stairwells" type="Node2D" parent="."]\n')
    sc.node('[node name="Labels" type="Node2D" parent="WallGlow"]\n')
    sc.node('[node name="RoomWalls" type="StaticBody2D" parent="."]\n')
    sc.node('[node name="StairWalls" type="StaticBody2D" parent="."]\n')

    for key, lb, x0, y0, x1, y1, door in FLOOR1["rooms"]:
        add_room(sc, key, lb, x0, y0, x1, y1, door)
    # 교무실(사선)
    sx0, sy0, sx1, sy1 = FLOOR1["staff"]
    add_sloped_room(sc, "StaffRoom", "교무실", sx0, sx1, sy0, sy1, "bottom")
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
    add_story(sc, 1)

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
        path.write_text(text)
        print(f"OK floor{fl}: 노드 {len(sc.nodes)}개, 차단체 {len(sc.subs)}개")
