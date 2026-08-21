#!/usr/bin/env python3
"""맵 도트(픽셀아트) 타일 텍스처 생성기 (#246).

`assets/tiles/*.png`에 이어붙는(tileable) 회색조 무늬를 굽는다. `gen_floors.py`가
이 텍스처를 기존 `Polygon2D`(바닥·벽·집기)에 물려 2D 쯔꾸르류 타일 그리드 느낌을 낸다.
gen_sfx.py / gen_music.py / gen_player_sprites.py와 같은 규약 — **표준 라이브러리만 쓰고
결정론적**이라, 무늬를 안 바꾸고 다시 돌리면 바이트가 같다(diff가 나오지 않는다).

## 왜 회색조인가
색은 `gen_floors.py`의 팔레트가 계속 쥔다. 텍스처는 무늬(휘도)만 담고 `Polygon2D.color`와
곱해진다 — 그래서 방 종류별 바닥색(#237)이 그대로 살아 있고, 타일을 새 방에 붙일 때
색을 다시 고민할 필요가 없다.

## 왜 평균 휘도를 고정하는가
텍스처를 곱하면 화면이 평균적으로 어두워진다. 이 게임은 CanvasModulate 어둠 + 손전등으로
밝기를 아슬아슬하게 맞춰 놨으므로(#74) 그 균형을 흔들면 안 된다. 그래서 **모든 타일을
평균 휘도 MEAN으로 정규화**하고, gen_floors가 텍스처를 붙인 노드의 색에만 1/MEAN 게인을
곱한다. 결과의 평균 밝기는 텍스처 도입 전과 같고, 밝은 도트는 1/MEAN배, 어두운 도트는
그만큼 아래로 갈린다.

## 왜 DOT=2인가
카메라 zoom이 1.25라 월드 1px 무늬는 화면에서 1px과 2px로 들쭉날쭉하게 확대된다.
무늬의 최소 단위를 월드 2px로 잡으면 화면 2.5px가 되어 어느 쪽으로 떨어져도 도트로 읽힌다.
모든 무늬는 DOT×DOT 블록 단위로만 칠하며, `_check_dot_grid`가 이를 검사한다.

## #241/#242가 그린 격자와 겹치지 않기
#242가 복도 마루널(폭 64px)과 화장실 줄눈(60px)을 이미 폴리곤으로 그린다. 그 면에
선이 있는 무늬를 깔면 타일 반복 주기(48px)와 어긋난 격자가 겹쳐 보인다. 그래서
`floor_board`(복도)·`floor_matte`(화장실)는 **선을 내지 않고** 흩뿌린 조각·반점만
쓰며, `LINELESS` 목록에 넣어 `_check_lineless`가 행·열 평균으로 검사한다.
#242가 아무것도 그리지 않는 면(교실·창고·실험실·컴퓨터실)에는 선이 있는 무늬를 쓴다.

## 무늬를 고칠 때
아래 무늬 함수의 반환값은 **최종 곱셈 계수(0..1)를 그대로 적은 절대값**이다. 대략
줄눈·이음매 0.56~0.62 / 바탕 0.82~0.86 / 하이라이트 0.92~0.96을 쓴다. `bake()`가
평균만 MEAN으로 옮기므로 여기 적은 명암 관계가 화면에 그대로 나온다.
새 타일을 추가하면 gen_floors.py의 `TEX`(색 -> 재질) 표에도 넣어야 실제로 쓰인다.
반대로 `TEX`에서 빠진 타일은 굽지 않는다 — 쓰지 않는 에셋을 남기지 않는다.

## 재질과 오브젝트
이 파일은 두 갈래를 굽는다(#259). `PATTERNS`는 **이어붙는 재질**(바닥·벽)이고
`OBJECTS`는 **경계가 있는 물건**(책상·사물함·세면대…)이다. 재질은 월드 좌표를
UV로 써서 맵 전체가 한 격자에 정렬되고, 오브젝트는 gen_floors가 물건마다
로컬 UV를 넣어 그림 한 장을 그 물건에 맞춰 늘린다. 오브젝트 대응표는
gen_floors.py의 `SPRITE`다.
"""
from __future__ import annotations

import pathlib
import struct
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "tiles"

DOT = 2             # 무늬 최소 단위(월드 px)
FLOOR = 32          # 바닥 타일 한 변(#259) — 쯔꾸르식 32칸. 48이던 것을 줄여
                    # 격자가 더 자주 보이게 했다. 무늬 함수의 칸 크기(널 높이·장
                    # 크기)는 FLOOR//DOT로 나누어떨어져야 이어붙는다 — 안 그러면
                    # _check_periodic이 잡는다.
SMALL = 16          # 벽·얇은 장식 타일 한 변 — 벽 두께 T=16과 같아 두께 방향으로
                    # 딱 한 장 들어간다. **면 두께보다 큰 타일을 쓰면 안 된다** —
                    # UV가 월드 좌표라 얇은 면에는 타일의 일부만, 그것도 면의 y에
                    # 따라 다른 조각이 잘려 들어간다. #259에서 32로 올렸다가
                    # 벽돌 줄눈이 벽 가장자리에 안 맞아 되돌렸다(#262).
                    # 두께 8~10px인 게시판·창문·걸레받이도 같은 이유로 이 타일을 쓴다.

MEAN = 0.78         # 목표 평균 휘도 — gen_floors.py의 TEX_MEAN과 반드시 같아야 한다
MEAN_TOL = 0.004    # 8비트 한 계단(1/255)만큼 허용
MIN_CONTRAST = 0.25  # 이보다 평평하면 텍스처를 붙인 의미가 없다



# --------------------------------------------------------------------------- 잡음

def rnd(*key: int) -> float:
    """정수 키에 대한 결정론적 0..1 난수. random 모듈을 안 써서 어느 파이썬에서도 같다."""
    v = 0x9E3779B1
    for k in key:
        v = ((v ^ (int(k) & 0xFFFFFFFF)) * 0x85EBCA6B) & 0xFFFFFFFF
        v ^= v >> 13
        v = (v * 0xC2B2AE35) & 0xFFFFFFFF
        v ^= v >> 16
    return v / 0xFFFFFFFF


def jit(amp: float, *key: int) -> float:
    """-amp/2 ~ +amp/2 흔들림."""
    return amp * (rnd(*key) - 0.5)


# --------------------------------------------------------------------------- 무늬
# 무늬 함수는 도트 격자 좌표(dx, dy)와 격자 크기(gw, gh)를 받아 곱셈 계수를 낸다.
# 첫 줄에서 좌표를 격자 크기로 감싼다 — 이래야 타일이 이어붙는다.

def p_wood(dx: int, dy: int, gw: int, gh: int) -> float:
    """교실·수위실 마루널. 널 높이 6도트(12px), 널마다 끝 맞댄 자리가 반 칸 어긋난다."""
    dx, dy = dx % gw, dy % gh
    ph = 8                                            # 널 높이(도트) — gh=16을 나눠야 이어붙는다
    plank = dy // ph
    v = 0.86 + jit(0.07, plank, 11)                   # 널마다 색이 조금 다르다
    v += jit(0.04, dx, dy, 12)                        # 잔 나뭇결
    if rnd(dx // 3, plank, 13) > 0.82:
        v -= 0.08                                     # 결 줄무늬(널 방향으로 길게)
    if dx == (0 if plank % 2 == 0 else gw // 2):
        v = 0.64                                      # 널 끝 맞댄 자리
    if dy % ph == ph - 1:
        v = 0.57                                      # 널 사이 이음매
    return v


def p_board(dx: int, dy: int, gw: int, gh: int) -> float:
    """복도 마루. **널을 세로로 세운다**(#268) — 복도가 가로로 길어서 널까지
    가로로 누우면 마루가 아니라 줄 친 종이로 보인다.

    널 선을 폴리곤이 아니라 **여기 무늬에 넣는다**. #242는 복도 널을 64px마다
    Polygon2D로 그렸는데, 직각으로 돌리자 층당 150개가 넘게 생겼다(노드 예산
    초과). 타일이 32px 주기로 이어붙으니 널 폭 32px은 공짜로 나오고, 월드
    격자에 정확히 정렬되는 덤도 있다.
    """
    dx, dy = dx % gw, dy % gh
    v = 0.87 + jit(0.06, dx // (gw // 2), 141)        # 널마다 색이 조금 다르다
    v += jit(0.04, dx, dy, 142)                       # 잔 결
    if rnd(dx, dy // 3, 143) > 0.86:
        v -= 0.06                                     # 결 줄무늬(널 방향=세로)
    if rnd(dx, dy, 144) > 0.985:
        v -= 0.20                                     # 옹이
    if dx == 0:
        v = 0.60                                      # 널 사이 이음매(세로)
    # 널 끝 맞댄 자리 — 널마다 다른 높이에 둬서 엇갈리게 보인다.
    if dy == (gh // 3 if dx < gw // 2 else (2 * gh) // 3):
        v = 0.66
    return v


def p_matte(dx: int, dy: int, gw: int, gh: int) -> float:
    """화장실 바닥면. **선을 내지 않는다** — 줄눈은 #242가 `FM_`로 60px 간격에
    긋는다. 여기서 격자를 내면 48px와 60px 두 간격이 겹쳐 어긋난 격자가 된다.
    도자기 표면의 잔 얼룩과 광택 점만 낸다."""
    dx, dy = dx % gw, dy % gh
    v = 0.86 + jit(0.05, dx, dy, 151)
    r = rnd(dx, dy, 152)
    if r > 0.93:
        v -= 0.22                                     # 물때 얼룩
    elif r < 0.05:
        v += 0.07                                     # 광택 점
    return v


def p_cement(dx: int, dy: int, gw: int, gh: int) -> float:
    """창고·막힌 공간 시멘트. 거친 두 배율 잡음 + 드러난 골재."""
    dx, dy = dx % gw, dy % gh
    v = 0.82 + jit(0.13, dx // 3, dy // 3, 41)        # 넓은 반죽 자국
    v += jit(0.07, dx, dy, 42)
    r = rnd(dx, dy, 43)
    if r > 0.94:
        v += 0.10                                     # 드러난 골재
    elif r < 0.07:
        v -= 0.16                                     # 파인 자리
    return v


def p_vinyl(dx: int, dy: int, gw: int, gh: int) -> float:
    """실험실 데코타일. 16px 장에 대리석 흉내 얼룩이 섞여 있다."""
    dx, dy = dx % gw, dy % gh
    s = 8                                             # 장 크기(도트) — gw=16을 나눠야 한다
    v = 0.86 + jit(0.05, dx // s, dy // s, 61)
    v += jit(0.09, dx // 2, dy // 2, 62)
    if dx % s == 0 or dy % s == 0:
        v = 0.62                                      # 장 이음매
    return v


def p_panel(dx: int, dy: int, gw: int, gh: int) -> float:
    """컴퓨터실 액세스플로어. 16px 패널 + 네 귀퉁이 나사."""
    dx, dy = dx % gw, dy % gh
    s = 8                                             # 패널 크기(도트) — gw=16을 나눠야 한다
    ix, iy = dx % s, dy % s
    v = 0.85 + jit(0.04, dx // s, dy // s, 71)
    v += jit(0.03, dx, dy, 72)
    if ix == 1 or iy == 1:
        v += 0.08                                     # 경계 옆 하이라이트
    if ix in (2, s - 3) and iy in (2, s - 3):
        v = 0.60                                      # 나사
    if ix == 0 or iy == 0:
        v = 0.66                                      # 패널 경계
    return v


def p_brick(dx: int, dy: int, gw: int, gh: int) -> float:
    """벽면 미장. **대비를 낮게** 가져간다(#265).

    예전엔 8px 콘크리트 블록에 줄눈을 진하게 그었는데, 벽 두께가 16px이라 두
    단밖에 안 들어가서 무늬가 아니라 지퍼처럼 보였다. 얇은 띠에는 결이 아니라
    **고른 질감**이 맞다 — 벽은 배경으로 물러나야 하고, 벽면임을 알려주는 건
    무늬가 아니라 색과 연속성이다.

    두께 8~10px인 게시판·창문·걸레받이도 이 무늬를 쓰므로 더더욱 잔잔해야 한다.
    """
    dx, dy = dx % gw, dy % gh
    # 얼룩을 넓게(6px 덩어리) 가져가면 대비가 있어도 격자로 읽히지 않는다.
    # 아주 평평하게 만들었더니 _check_contrast(0.25)에 걸렸다 — 텍스처를 붙인
    # 의미가 없다는 뜻이라, 결 대신 얼룩으로 대비를 낸다.
    v = 0.85 + jit(0.14, dx // 3, dy // 3, 91)        # 넓은 미장 얼룩
    v += jit(0.05, dx, dy, 92)                        # 잔 결
    r = rnd(dx, dy, 93)
    if r > 0.94:
        v -= 0.16                                     # 파인 자리
    elif r < 0.05:
        v += 0.09                                     # 튀어나온 자리
    return v


def p_grain(dx: int, dy: int, gw: int, gh: int) -> float:
    """집기 나무결(책상·선반·문짝). 8px 폭 세로 널."""
    dx, dy = dx % gw, dy % gh
    pw = 4
    col = dx // pw
    v = 0.86 + jit(0.07, col, 101)
    v += jit(0.05, col, dy, 102)                      # 결이 널 방향(세로)으로 흐른다
    if dx % pw == 0:
        v = 0.60                                      # 널 사이 홈
    return v


def p_metal(dx: int, dy: int, gw: int, gh: int) -> float:
    """금속판(사물함·칸막이·서버랙). 세로 골 + 리벳."""
    dx, dy = dx % gw, dy % gh
    ix = dx % 4
    v = 0.84 + jit(0.03, dx, dy, 111)
    if ix == 0:
        v += 0.10                                     # 골의 능선
    elif ix == 2:
        v -= 0.14                                     # 골의 바닥
    if (dx % 8, dy % 8) in ((1, 1), (5, 5)):
        v = 0.95                                      # 리벳
    return v


def p_cloth(dx: int, dy: int, gw: int, gh: int) -> float:
    """천·코르크(게시판·커튼·매트). 격자 짜임이 촘촘하다."""
    dx, dy = dx % gw, dy % gh
    v = 0.86 - 0.07 * ((dx % 2) ^ (dy % 2))
    v += jit(0.08, dx, dy, 121)
    if dx % 4 == 0 and dy % 4 == 0:
        v = 0.59                                      # 굵은 씨실 교차점
    return v


def p_glass(dx: int, dy: int, gw: int, gh: int) -> float:
    """유리·화면(창문·거울·모니터). 대각선 반사 띠."""
    dx, dy = dx % gw, dy % gh
    d = (dx + dy) % 8
    v = 0.78 + jit(0.03, dx, dy, 131)
    if d == 0:
        v = 0.96                                      # 반사 띠(밝은 쪽)
    elif d == 1:
        v = 0.88
    elif d == 4:
        v = 0.62                                      # 반사 사이 어두운 골
    return v


# --------------------------------------------------------------------------- 오브젝트 그림
# 위 무늬가 "이어붙는 재질"이라면 아래는 "경계가 있는 물건"이다(#259).
#
# 왜 나누는가: 재질 무늬는 `Polygon2D.uv`를 비워 정점 좌표를 UV로 쓴다 — 맵
# 전체가 하나의 격자에 정렬된다(#246 규약 ③). 넓게 이어지는 바닥·벽에는 맞지만
# 44x26짜리 책상에는 월드 격자의 아무 조각이나 잘려 들어가서, 상판도 모서리도
# 서랍선도 있을 자리가 없었다. 집기는 gen_floors가 **오브젝트 로컬 UV**를 넣어
# 그림 한 장을 물건 하나에 맞춰 늘린다.
#
# 그래서 이 그림들은 **이어붙지 않아도 된다** — `_check_periodic`을 돌리지
# 않는다. 대신 평균 휘도·명암·도트 격자 규약은 재질과 똑같이 지킨다.
#
# 크기가 제각각인 집기에 한 장을 늘려 쓰므로(책상 44x26, 실험대 140x38, 사물함
# 40x세로) **칸 수를 비율로 잡는다**. 문 네 짝짜리 사물함은 폭이 얼마든 네 짝으로
# 보이고, 늘어나도 "무엇인지"는 유지된다.

def _edge(dx: int, dy: int, gw: int, gh: int) -> int:
    """네 변 중 가장 가까운 변까지의 거리(도트)."""
    return min(dx, dy, gw - 1 - dx, gh - 1 - dy)


def o_desk(dx: int, dy: int, gw: int, gh: int) -> float:
    """책상·탁자·실험대. 어두운 모서리 + 밝은 상판 + 서랍선."""
    e = _edge(dx, dy, gw, gh)
    if e == 0:
        return 0.55                                   # 바깥 모서리 그림자
    v = 0.90 + jit(0.04, dx, dy, 301)
    if e == 1:
        v = 0.99                                      # 상판 가장자리 빛
    if dy == gh - 4:
        v = 0.68                                      # 서랍선
    if rnd(dx, dy, 302) > 0.94:
        v -= 0.05                                     # 잔 결
    return v


def o_chair(dx: int, dy: int, gw: int, gh: int) -> float:
    """의자. 놓이는 방향이 제각각(책상 아래·오른쪽)이라 상하좌우 대칭으로 만든다."""
    e = _edge(dx, dy, gw, gh)
    if e == 0:
        return 0.52
    if e == 1:
        return 0.88                                   # 등받이·팔걸이 테
    v = 0.95 + jit(0.05, dx, dy, 311)
    cx0, cy0 = (gw - 1) / 2.0, (gh - 1) / 2.0
    r = (((dx - cx0) / (gw * 0.26)) ** 2 + ((dy - cy0) / (gh * 0.26)) ** 2) ** 0.5
    if r < 1.0:
        v -= 0.12                                     # 눌린 방석
    return v


def o_locker(dx: int, dy: int, gw: int, gh: int) -> float:
    """사물함 한 벌. 문 네 짝 + 손잡이 — 폭이 얼마든 네 짝으로 보인다."""
    e = _edge(dx, dy, gw, gh)
    if e == 0:
        return 0.54
    door = max(2, gw // 4)
    ix = dx % door
    v = 0.90 + jit(0.03, dx // door, dy, 321)
    if ix == 0:
        v = 0.62                                      # 문 사이 틈
    if ix == door - 2 and abs(dy - gh // 2) <= 1:
        v = 0.55                                      # 손잡이
    if dy == 1:
        v += 0.07                                     # 위 모서리 빛
    return v


def o_shelf(dx: int, dy: int, gw: int, gh: int) -> float:
    """선반. 널 세 단 + 양옆 기둥."""
    e = _edge(dx, dy, gw, gh)
    if e == 0:
        return 0.52
    band = max(2, gh // 3)
    v = 0.88 + jit(0.05, dx, dy // band, 331)
    if dy % band == 0:
        v = 0.63                                      # 단 사이 그늘
    if dx in (1, gw - 2):
        v = 0.72                                      # 기둥
    return v


def o_sink(dx: int, dy: int, gw: int, gh: int) -> float:
    """세면대·소변기. 테두리 안에 오목한 대야, 위쪽에 수도꼭지."""
    e = _edge(dx, dy, gw, gh)
    if e == 0:
        return 0.58
    cx0, cy0 = (gw - 1) / 2.0, (gh - 1) / 2.0
    r = (((dx - cx0) / (gw * 0.40)) ** 2 + ((dy - cy0) / (gh * 0.34)) ** 2) ** 0.5
    v = 0.95 + jit(0.03, dx, dy, 341)
    if r < 1.0:
        v = 0.74 + 0.14 * r                           # 대야 — 가운데가 깊다
    if r < 0.30:
        v = 0.60                                      # 배수구
    if dy <= 2 and abs(dx - cx0) < 1.6:
        v = 0.56                                      # 수도꼭지
    return v


def o_screen(dx: int, dy: int, gw: int, gh: int) -> float:
    """모니터·화면. 두꺼운 베젤 + 대각 반사가 있는 유리."""
    if _edge(dx, dy, gw, gh) <= 1:
        return 0.50                                   # 베젤
    v = 0.74 + jit(0.02, dx, dy, 351)
    if (dx + dy) % 7 == 0:
        v = 0.94                                      # 반사 띠
    return v


def o_panel(dx: int, dy: int, gw: int, gh: int) -> float:
    """칸막이·문짝. 평평한 판 + 안쪽 홈 + 손잡이."""
    e = _edge(dx, dy, gw, gh)
    if e == 0:
        return 0.56
    v = 0.91 + jit(0.03, dx, dy, 361)
    if e == 2:
        v = 0.79                                      # 판 안쪽 홈
    if abs(dy - gh // 2) <= 1 and dx >= gw - 4:
        v = 0.58                                      # 손잡이
    return v


def o_cabinet(dx: int, dy: int, gw: int, gh: int) -> float:
    """캐비닛·약품장·청소도구함. 문 두 짝 + 손잡이."""
    e = _edge(dx, dy, gw, gh)
    if e == 0:
        return 0.54
    v = 0.90 + jit(0.03, dx // 2, dy, 371)
    if dx == gw // 2:
        v = 0.62                                      # 문 사이
    if abs(dy - gh // 2) <= 1 and dx in (gw // 2 - 2, gw // 2 + 2):
        v = 0.56                                      # 손잡이
    if dy == 1:
        v += 0.06
    return v


def o_bin(dx: int, dy: int, gw: int, gh: int) -> float:
    """쓰레기통·양동이. 둥근 테와 안쪽 그늘."""
    cx0, cy0 = (gw - 1) / 2.0, (gh - 1) / 2.0
    r = (((dx - cx0) / (gw * 0.46)) ** 2 + ((dy - cy0) / (gh * 0.46)) ** 2) ** 0.5
    if r > 1.0:
        return 0.88                                   # 통 바깥(바닥이 비쳐 보이게)
    if r > 0.80:
        return 0.97                                   # 테두리 빛
    return 0.62 + jit(0.05, dx, dy, 381)              # 통 안


def o_bed(dx: int, dy: int, gw: int, gh: int) -> float:
    """간이침상. 매트리스 + 머리맡 베개."""
    e = _edge(dx, dy, gw, gh)
    if e == 0:
        return 0.56
    v = 0.90 + jit(0.04, dx, dy, 391)
    if dy < gh // 4:
        v = 0.99                                      # 베개
    elif dy == gh // 4:
        v = 0.66                                      # 베개 아래 그늘
    return v


def o_plant(dx: int, dy: int, gw: int, gh: int) -> float:
    """화분. 아래 화분 + 위 잎 덩어리."""
    cx0 = (gw - 1) / 2.0
    if dy > gh * 0.62:
        if abs(dx - cx0) > gw * 0.30:
            return 0.90                               # 화분 바깥
        return 0.80 + jit(0.04, dx, dy, 401)          # 화분
    r = (((dx - cx0) / (gw * 0.42)) ** 2
         + ((dy - gh * 0.34) / (gh * 0.32)) ** 2) ** 0.5
    if r > 1.0:
        return 0.90
    return 0.62 + jit(0.12, dx, dy, 402)              # 잎


def o_toilet(dx: int, dy: int, gw: int, gh: int) -> float:
    """대변기. 위에서 본 물탱크 + 변기통."""
    e = _edge(dx, dy, gw, gh)
    if e == 0:
        return 0.88                                   # 칸 바닥이 비쳐 보이게
    if dy < gh * 0.26:
        return 0.94 + jit(0.03, dx, dy, 421)          # 물탱크
    cx0 = (gw - 1) / 2.0
    r = (((dx - cx0) / (gw * 0.30)) ** 2
         + ((dy - gh * 0.62) / (gh * 0.30)) ** 2) ** 0.5
    if r > 1.0:
        return 0.88                                   # 변기 바깥
    if r > 0.72:
        return 0.99                                   # 변기 테
    return 0.60 + 0.14 * r                            # 물이 담긴 안쪽


def o_rack(dx: int, dy: int, gw: int, gh: int) -> float:
    """서버랙. 가로 슬롯이 층층이 + 표시등."""
    e = _edge(dx, dy, gw, gh)
    if e == 0:
        return 0.52
    v = 0.87 + jit(0.03, dx, dy, 411)
    if dy % 3 == 0:
        v = 0.60                                      # 슬롯 사이
    elif dy % 3 == 1 and dx > gw - 5:
        v = 0.97                                      # 표시등
    return v


OBJ = 32            # 오브젝트 그림 한 변. 재질과 같은 32라 도트 크기가 어긋나지 않는다.

OBJECTS = {
    "obj_desk": o_desk,
    "obj_chair": o_chair,
    "obj_locker": o_locker,
    "obj_shelf": o_shelf,
    "obj_sink": o_sink,
    "obj_screen": o_screen,
    "obj_panel": o_panel,
    "obj_cabinet": o_cabinet,
    "obj_bin": o_bin,
    "obj_bed": o_bed,
    "obj_plant": o_plant,
    "obj_rack": o_rack,
    "obj_toilet": o_toilet,
}


PATTERNS = {
    "floor_wood": (p_wood, FLOOR),
    "floor_board": (p_board, FLOOR),
    "floor_matte": (p_matte, FLOOR),
    "floor_cement": (p_cement, FLOOR),
    "floor_vinyl": (p_vinyl, FLOOR),
    "floor_panel": (p_panel, FLOOR),
    "wall_brick": (p_brick, SMALL),
    "prop_grain": (p_grain, SMALL),
    "prop_metal": (p_metal, SMALL),
    "prop_cloth": (p_cloth, SMALL),
    "prop_glass": (p_glass, SMALL),
}

# #242가 이미 격자를 그리는 면. 여기에는 선이 있는 무늬를 쓸 수 없다 —
# 타일 반복 주기(48px)와 #242의 간격(복도 널 64px, 화장실 줄눈 60px)이 어긋나
# 두 격자가 겹쳐 보인다. `_check_lineless`가 행·열 평균으로 검사한다.
# 화장실 줄눈은 아직 폴리곤(FM_)이 60px 간격으로 그리므로 타일에 선이 있으면
# 두 격자가 어긋나 겹친다. 복도는 #268에서 폴리곤 널을 걷어내고 무늬로
# 옮겼으므로 선이 있어도 된다.
LINELESS = ("floor_matte",)
LINE_TOL = 14       # 행·열 평균이 전체 평균에서 벗어날 수 있는 폭(8비트 계단)


# --------------------------------------------------------------------------- 굽기

def bake(fn, size: int) -> list[int]:
    """무늬 함수를 도트 격자 8비트 회색조로 굽는다. 평균 휘도를 MEAN에 맞춘다.

    평균만 곱셈으로 옮기므로(v * MEAN/mean) 무늬 함수에 적은 명암 *비율*이 살아남는다.
    그 결과 가장 밝은 도트가 1.0을 넘을 때만, 평균을 축으로 명암을 좁혀 1.0에 맞춘다.
    """
    g = size // DOT
    vals = [max(0.0, min(1.0, fn(dx, dy, g, g)))
            for dy in range(g) for dx in range(g)]
    mp = sum(vals) / len(vals)
    if mp <= 0:
        raise SystemExit("무늬가 전부 검다")

    hi = max(vals)
    if hi * MEAN / mp > 1.0:
        # 평균을 MEAN으로 올리면 밝은 쪽이 흰색을 넘는다 → 명암을 그만큼 좁힌다.
        k = mp * (1.0 / MEAN - 1.0) / (hi - mp)
        vals = [mp + k * (v - mp) for v in vals]
    scale = MEAN / mp
    vals = [max(0.0, min(1.0, v * scale)) for v in vals]

    # 8비트로 내리면서 생긴 평균 오차를 정수 한 계단으로 메운다. 넓게 흩뿌려야
    # ±1/255가 얼룩으로 보이지 않는다(같은 자리에 몰면 옅은 무늬가 생긴다).
    px = [int(v * 255 + 0.5) for v in vals]
    delta = int(round(MEAN * 255 * len(px) - sum(px)))
    step = 1 if delta > 0 else -1
    i, guard = 0, 0
    while delta != 0 and guard < len(px) * 8:
        j = (i * 7919) % len(px)
        if 0 <= px[j] + step <= 255:
            px[j] += step
            delta -= step
        i += 1
        guard += 1
    if delta != 0:
        raise SystemExit("평균 보정 실패")
    return px


def upscale(px: list[int], size: int) -> bytes:
    """도트 격자를 DOT배로 늘려 실제 픽셀로 만든다(RGBA)."""
    g = size // DOT
    out = bytearray()
    for y in range(size):
        for x in range(size):
            v = px[(y // DOT) * g + (x // DOT)]
            out += bytes((v, v, v, 255))
    return bytes(out)


def write_png(path: pathlib.Path, size: int, rgba: bytes) -> None:
    """8비트 RGBA PNG. 회색조(L8)로 쓰지 않는 이유는 백엔드에 따라 샘플링이 갈리기 때문."""
    raw = bytearray()
    for y in range(size):
        raw.append(0)                                  # 필터 없음
        raw += rgba[y * size * 4:(y + 1) * size * 4]

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    out += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    out += chunk(b"IEND", b"")
    path.write_bytes(out)


# --------------------------------------------------------------------------- 자체 검사

def _check_mean(name: str, px: list[int]) -> None:
    mean = sum(px) / len(px) / 255.0
    if abs(mean - MEAN) > MEAN_TOL:
        raise SystemExit(f"{name}: 평균 휘도 {mean:.4f} != {MEAN} (허용 {MEAN_TOL})")


def _check_contrast(name: str, px: list[int]) -> None:
    span = (max(px) - min(px)) / 255.0
    if span < MIN_CONTRAST:
        raise SystemExit(f"{name}: 명암차 {span:.3f} < {MIN_CONTRAST} — 무늬가 안 보인다")


def _check_dot_grid(name: str, rgba: bytes, size: int) -> None:
    """DOT x DOT 블록 안이 한 색인지. 무늬가 1px로 새면 zoom 1.25에서 들쭉날쭉해진다."""
    for y in range(size):
        for x in range(size):
            i = (y * size + x) * 4
            j = ((y - y % DOT) * size + (x - x % DOT)) * 4
            if rgba[i] != rgba[j]:
                raise SystemExit(f"{name}: ({x},{y})가 DOT 격자를 벗어난다")


def _check_periodic(name: str, fn, g: int) -> None:
    """무늬가 격자 크기로 주기적인지 = 타일이 이어붙는지.

    무늬 함수가 첫 줄의 `dx % gw` 를 빠뜨리면(손으로 여러 장을 쓰다 보면 나온다)
    타일 경계에 없던 줄이 생긴다. 격자 밖 좌표로 불러 안쪽 값과 대조해 잡는다.
    """
    for dy in range(g):
        for dx in range(g):
            base = fn(dx, dy, g, g)
            for ox, oy in ((g, 0), (0, g), (-g, -g)):
                if fn(dx + ox, dy + oy, g, g) != base:
                    raise SystemExit(
                        f"{name}: ({dx},{dy})가 주기적이지 않다 — 좌표를 감싸지 않았다")


def _check_lineless(name: str, px: list[int], g: int) -> None:
    """행·열 평균이 고른지 = 반복해 깔았을 때 줄이 보이지 않는지.

    #242가 폴리곤으로 격자를 그리는 면(복도 마루·화장실 바닥)에 쓰는 무늬는
    선이 있어서는 안 된다. 한 줄이 통째로 어두우면 타일 주기(48px)마다 그 줄이
    반복되어, #242의 간격(64px·60px)과 어긋난 격자가 겹쳐 보인다.
    """
    overall = sum(px) / len(px)
    rows = [sum(px[y * g:(y + 1) * g]) / g for y in range(g)]
    cols = [sum(px[y * g + x] for y in range(g)) / g for x in range(g)]
    worst = max(abs(v - overall) for v in rows + cols)
    if worst > LINE_TOL:
        raise SystemExit(f"{name}: 행/열 평균이 전체에서 {worst:.1f} 벗어난다 "
                         f"(허용 {LINE_TOL}) — 반복하면 줄무늬가 보인다")


# --------------------------------------------------------------------------- 진입점

def build_all() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, (fn, size) in sorted(PATTERNS.items()):
        if size % DOT:
            raise SystemExit(f"{name}: 타일 {size}가 DOT {DOT}로 나뉘지 않는다")
        px = bake(fn, size)
        _check_mean(name, px)
        _check_contrast(name, px)
        _check_periodic(name, fn, size // DOT)
        if name in LINELESS:
            _check_lineless(name, px, size // DOT)
        rgba = upscale(px, size)
        _check_dot_grid(name, rgba, size)
        write_png(OUT_DIR / f"{name}.png", size, rgba)
        print(f"{name}.png  {size}x{size}  평균 {sum(px)/len(px)/255:.3f}  "
              f"명암 {min(px)}~{max(px)}")
    for name, fn in sorted(OBJECTS.items()):
        # 오브젝트 그림은 이어붙지 않아도 된다 — 물건 하나에 한 장을 늘려 쓰므로
        # _check_periodic을 돌리지 않는다. 나머지 규약(평균 휘도·명암·도트 격자)은
        # 재질과 똑같이 지킨다.
        px = bake(fn, OBJ)
        _check_mean(name, px)
        _check_contrast(name, px)
        rgba = upscale(px, OBJ)
        _check_dot_grid(name, rgba, OBJ)
        write_png(OUT_DIR / f"{name}.png", OBJ, rgba)
        print(f"{name}.png  {OBJ}x{OBJ}  평균 {sum(px)/len(px)/255:.3f}  "
              f"명암 {min(px)}~{max(px)}")
    print(f"재질 {len(PATTERNS)}장 + 오브젝트 {len(OBJECTS)}장 "
          f"-> {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    try:
        build_all()
    except SystemExit as exc:
        if exc.code:
            print(f"실패: {exc.code}", file=sys.stderr)
        raise
