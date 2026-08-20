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
새 타일을 추가하면 gen_floors.py의 `TEX`(색 -> 타일) 표에도 넣어야 실제로 쓰인다.
반대로 `TEX`에서 빠진 타일은 굽지 않는다 — 쓰지 않는 에셋을 남기지 않는다.
"""
from __future__ import annotations

import pathlib
import struct
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets" / "tiles"

DOT = 2             # 무늬 최소 단위(월드 px)
FLOOR = 48          # 바닥 타일 한 변 — 플레이어(60x72)에 맞춘 쯔꾸르식 칸 크기
SMALL = 16          # 벽·집기 타일 한 변 — 벽 두께 T=16과 같아 두께 방향으로 딱 한 장 들어간다

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
    ph = 6
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
    """복도 마루 표면. **선을 내지 않는다** — 널과 이음매는 #242가 폴리곤으로
    그리고 있고(널 폭 64px), 타일은 48px마다 반복되므로 여기서 한 줄이라도
    통째로 어둡게 하면 48px 간격의 가짜 널선이 그 위에 겹친다.

    대신 길이 3도트짜리 결 조각을 널 방향(가로)으로 흩뿌린다. 시작점만 해시로
    고르므로 조각이 이어지지 않고, 행·열 평균이 고르게 남는다(`_check_lineless`).
    """
    dx, dy = dx % gw, dy % gh
    v = 0.86 + jit(0.05, dx // 2, dy, 141)
    for k in range(3):                                # 조각의 시작점을 3도트 뒤까지 본다
        if rnd((dx - k) % gw, dy, 142) > 0.93:
            v -= 0.24                                 # 결 조각
            break
    v += jit(0.03, dx, dy, 143)
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
    """실험실 데코타일. 24px 큰 장에 대리석 흉내 얼룩이 섞여 있다."""
    dx, dy = dx % gw, dy % gh
    s = 12
    v = 0.86 + jit(0.05, dx // s, dy // s, 61)
    v += jit(0.09, dx // 2, dy // 2, 62)
    if dx % s == 0 or dy % s == 0:
        v = 0.62                                      # 장 이음매
    return v


def p_panel(dx: int, dy: int, gw: int, gh: int) -> float:
    """컴퓨터실 액세스플로어. 24px 패널 + 네 귀퉁이 나사."""
    dx, dy = dx % gw, dy % gh
    s = 12
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
    """벽 콘크리트 블록. 8px 단(段)마다 반 칸 엇물리고, 위는 밝고 아래는 그늘진다."""
    dx, dy = dx % gw, dy % gh
    ch = 4                                            # 한 단 높이(도트)
    course = dy // ch
    iy = dy % ch
    v = 0.84 + jit(0.05, course, dx // ch, 91)
    v += jit(0.03, dx, dy, 92)
    if iy == 1:
        v += 0.09                                     # 블록 윗면 빛
    elif iy == ch - 1:
        v -= 0.07                                     # 아랫면 그늘
    if iy == 0:
        v = 0.62                                      # 가로 줄눈
    if dx % ch == (0 if course % 2 == 0 else ch // 2):
        v = 0.62                                      # 세로 줄눈(단마다 엇물림)
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
LINELESS = ("floor_board", "floor_matte")
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
    print(f"타일 {len(PATTERNS)}장 -> {OUT_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    try:
        build_all()
    except SystemExit as exc:
        if exc.code:
            print(f"실패: {exc.code}", file=sys.stderr)
        raise
