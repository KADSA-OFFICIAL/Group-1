#!/usr/bin/env python3
"""플레이어(이설) 스프라이트 생성기 (#210, 걷기 #365·#368, 전면 재작업 #372).

원본이 두 장이다.

`player_design.png`  두 포즈(왼쪽=달리기 측면, 오른쪽=대기 정면)가 같은 축척으로 있다.
`player_walk_design.png`  측면 걷기 두 포즈(왼쪽=넓은 활보, 오른쪽=뒷발 들기).

이 도구가 배경을 지우고 게임 크기로 줄여 아래 다섯 장을 만든다.

    assets/sprites/player_idle.png     대기(정면)
    assets/sprites/player_walk_1.png   걷기 1 — 활보(접지). 엉덩이가 가장 낮다
    assets/sprites/player_walk_2.png   걷기 2 — 뒷발이 들리기 시작
    assets/sprites/player_walk_3.png   걷기 3 — 뒷발이 높이 들림
    assets/sprites/player_walk_4.png   걷기 4 — 다리가 몸 아래를 지남. 엉덩이가 가장 높다

이동 중에는 walk_1 → 2 → 3 → 4 순으로 순환한다(`player_controller.gd`).
네 장 모두 오른쪽을 보고 있어 왼쪽으로 갈 때만 flip_h 한다.

**원본 포즈를 그대로 쓰지 않는다(#372).** 아트에 있는 세 측면 포즈는 셋 다 앞다리가
앞으로 뻗은 채 고정이고, 머리 높이도 팔 위치도 서로 같다. 그대로 쓰면 뒷다리만 떠는
그림이 된다 — 걷기의 부자연스러움은 프레임 수가 아니라 **상체가 전혀 움직이지 않는
데서** 온다(측정: 네 컷의 머리끝 y가 모두 1, 팔 좌우 끝 차이 1px).

그래서 `WALK_CYCLE` 위상표가 프레임마다 세 값을 주고, 아래 세 변형이 그것을 만든다.

    close_legs()   다리를 엉덩이 축으로 모은다 — 앞다리도 프레임마다 움직인다
    tuck_arms()    팔을 몸통 쪽으로 당긴다 — 상체가 마네킹처럼 굳어 있지 않게
    raise_hips()   치마 밑단 위를 올린다 — 다리가 모일수록 엉덩이가 올라간다

**손으로 그린 컷이 합성보다 좋다.** 포즈 원본이 생기면 `WALK_CYCLE`의 위상값을
1.00 / 0 / 0으로 두고 그 그림을 그대로 쓰면 된다.

원본이 있는 폴더에는 `.gdignore`를 뒀다 — 1254x1254 / 1650x953 원본까지 Godot이
임포트해 빌드에 실을 이유가 없다(이 도구는 파일시스템에서 직접 읽는다).

gen_sfx.py / gen_music.py와 같은 규약: **표준 라이브러리만 쓰고 결정론적**이다.
톤이 아니라 크기·잘라낼 위치를 바꾸려면 아래 상수만 고치고 다시 돌리면 된다.
같은 원본에 같은 상수면 출력 바이트도 같으므로 재실행해도 diff가 나오지 않는다.

주의: 배경을 "어두운 색"으로 판별하면 안 된다 — 머리카락·치마·구두도 거의 검다.
그래서 이미지 테두리에서 시작하는 flood fill로 *바깥과 이어진* 어두운 곳만 배경으로 본다.
"""
from __future__ import annotations

import pathlib
import struct
import sys
import zlib
from collections import deque

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "sprites" / "source" / "player_design.png"
SRC_WALK = ROOT / "assets" / "sprites" / "source" / "player_walk_design.png"
OUT_DIR = ROOT / "assets" / "sprites"

# 출력 캔버스. 다섯 장이 같은 크기여야 Sprite2D 오프셋(SPRITE_OFFSET_Y)을 하나로 쓸 수 있다.
# 폭은 달리기 포즈(뒤로 뻗은 다리 + 앞으로 뻗은 팔)가 잘리지 않을 만큼 필요하다
# — 인물 키 72에서는 59가 최소치라 여유를 두고 60으로 잡았다(_check_fits가 검사한다).
CANVAS_W = 60
# 인물의 키. 배율의 기준이고 **화면에서 보이는 크기를 정하는 값**이다.
FIGURE_H = 72
# 머리 위에 비워 두는 줄 수(#372). 발끝이 캔버스 바닥에 고정이므로, 엉덩이를 올리려면
# 위쪽에 자리가 있어야 한다. WALK_CYCLE의 엉덩이 높이 최대치(3)보다 커야 한다.
# **짝수로 둘 것** — 캔버스 높이가 홀수면 Sprite2D 중앙 정렬이 반 칸에 걸려
# SPRITE_OFFSET_Y가 .5로 떨어지고, Nearest 필터에서 스프라이트가 떨린다.
BOB_HEADROOM = 4
CANVAS_H = FIGURE_H + BOB_HEADROOM

# 배경으로 볼 밝기 상한(R+G+B). 머리카락은 (26,26,26)=78이라 걸리지 않는다.
BG_LUMA = 40

# 한 칸의 절반 이상이 캐릭터일 때만 칠한다 — 실루엣이 흐려지지 않게.
COVER = 0.5

# 원본에서 각 포즈가 놓인 x 구간(서로 침범하지 않도록 잘라내는 창).
RUN_X = (61, 768)
IDLE_X = (872, 1138)

# 가로 기준점 = **머리 중심**(머리 bbox의 가운데). 전체 bbox 중심을 쓰면 뻗은 팔다리
# 때문에 걸을 때 몸이 좌우로 쏠린다 — 걷기 사이클에서 팔다리는 움직이지만 머리는
# 몸통 위에 그대로 있으므로 프레임이 바뀌어도 몸이 튀지 않는다.
RUN_ANCHOR_X = (380 + 603) / 2.0
IDLE_ANCHOR_X = (902 + 1117) / 2.0

# 걷기 원본(#365). 두 인물 사이에 넉넉한 빈 띠(x 676~944)가 있어 가운데서 자른다.
# 값은 (출력 이름, 잘라낼 창, 머리 중심). 창은 배경뿐인 여백을 넉넉히 물어도 되지만
# 옆 인물을 물면 안 된다.
WALK_POSES = (
    ("stride", (0, 810), (421 + 566) / 2.0),
    ("lift", (811, 1649), (1121 + 1269) / 2.0),
)

# 걷기 두 포즈의 키가 이만큼(원본 px) 넘게 다르면 멈춘다. 배율을 첫 포즈에서 잡아
# 둘 다에 쓰므로, 키가 다르면 프레임이 바뀔 때 몸집이 커졌다 작아진다.
WALK_HEIGHT_TOLERANCE = 2

# ── 걷기 위상표 (#372, 수위 방식으로 #375) ────────────────────────────────
# (출력 이름, 원본 포즈, 다리 모음, 엉덩이 높이, 팔 모음)
#
# **그림은 3장이고 순환은 4칸이다** — `player_controller.gd`의
# `WALK_CYCLE := [0, 1, 0, 2]`가 기본 프레임을 두 걸음 사이에 끼운다(수위 janitor.gd와
# 같은 구조). 수위 쪽 주석에 이유가 적혀 있다: "기본 프레임을 사이에 끼워야 두 걸음
# 사이에 몸이 지나가는 순간이 생긴다." #372의 단조 진행(1→2→3→4)에는 그 순간이 없어
# 다리가 모이기만 하다 루프에서 되돌아왔다.
# 좌우 다리를 구분할 표식이 없는 그림이라 걸음 A/B가 수위의 "왼발/오른발"을 대신한다.
#
# **다리 모음**: 1.00이면 원본 그대로, 작을수록 두 다리가 엉덩이 축으로 모인다.
#   0.52 밑으로는 두 다리가 한 덩어리로 뭉쳐 무엇이 무엇인지 알 수 없다.
# **엉덩이 높이**(px): 다리가 모일수록 커야 한다 — 다리를 세우면 엉덩이가 올라간다.
#   기본 프레임에서 최대, 걸음 프레임에서 최소다. 순환이 3 → 0 → 3 → 1이라 한 바퀴에
#   **두 번** 올라간다(걸음이 두 번이므로). #372에서는 한 번만 올라갔다.
# **팔 모음**(px): 몸통 쪽으로 당기는 거리. 다리가 모일 때 붙는다. 2px을 넘기면 팔이
#   몸통에 삼켜져 잘린 것처럼 보인다.
WALK_CYCLE = (
    ("player_walk_0", "stride", 0.52, 3, 2),   # 기본 — 두 발이 몸 아래로 모임
    ("player_walk_1", "stride", 1.00, 0, 0),   # 걸음 A — 활보(접지)
    ("player_walk_2", "lift",   0.90, 1, 1),   # 걸음 B — 뒷발 들림(접지)
)

# 기본 프레임은 **두 발이 땅에 모인 자세**다(수위의 0번 열과 같다). 발을 든 통과
# 자세로도 만들어 봤지만(`high` 포즈를 0.60까지 모음) 든 발이 치마 높이에서 가로
# 막대로 뭉쳐 보였다 — 뒷발이 이미 수평인 그림이라 엉덩이 쪽으로 밀어도 수평이다.
# 활보를 조이면 두 다리가 나란히 내려와 그림이 깨지지 않는다.
#
# 그래서 이동 3프레임이 모두 `player_walk_design.png` 한 장에서 나온다 — 기존
# 아트의 달리기 포즈(`high`)는 이제 쓰지 않는다. **머리 폭이 2px 좁던 문제(#372
# 잔여 위험)도 같이 없어진다.** 배율 기준으로는 계속 쓰므로 잘라내기 자체는 남는다.

# 치마로 볼 어두운 픽셀 수의 하한(한 행 기준). 구두도 어둡지만 한 행에 4~6칸뿐이라
# 걸리지 않는다 — 치마는 10칸이 넘는다.
SKIRT_RUN = 10
# 치마 밑단이 이 구간(캔버스 바닥에서 위로) 밖이면 멈춘다. 다리는 늘 아래 1/3이므로,
# 밑단을 잘못 잡으면(구두를 치마로 봤다든지) 몸통을 다리로 알고 뭉갠다.
HEM_ABOVE_FLOOR = (18, 38)


# --------------------------------------------------------------------------- PNG

def read_png(path: pathlib.Path) -> tuple[int, int, bytearray]:
    """인터레이스 없는 8비트 PNG를 RGBA 바이트열로 읽는다."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"PNG가 아니다: {path}")

    pos, idat, plte = 8, bytearray(), None
    width = height = depth = ctype = 0
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if ctag == b"IHDR":
            width, height, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if interlace:
                raise SystemExit("인터레이스 PNG는 지원하지 않는다")
            if depth != 8:
                raise SystemExit(f"8비트 PNG만 지원한다 (bit depth={depth})")
        elif ctag == b"PLTE":
            plte = body
        elif ctag == b"IDAT":
            idat += body
        pos += 12 + length

    raw = zlib.decompress(bytes(idat))
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    stride = width * nch
    lines = bytearray(height * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(height):
        filt = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if filt == 1:
            for i in range(nch, stride):
                line[i] = (line[i] + line[i - nch]) & 0xFF
        elif filt == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filt == 3:
            for i in range(stride):
                left = line[i - nch] if i >= nch else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filt == 4:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                c = prev[i - nch] if i >= nch else 0
                b = prev[i]
                guess = a + b - c
                pa, pb, pc = abs(guess - a), abs(guess - b), abs(guess - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif filt != 0:
            raise SystemExit(f"알 수 없는 PNG 필터 {filt}")
        lines[y * stride:(y + 1) * stride] = line
        prev = line

    rgba = bytearray(width * height * 4)
    for i in range(width * height):
        if ctype == 2:
            r, g, b = lines[i * 3:i * 3 + 3]
            a = 255
        elif ctype == 6:
            r, g, b, a = lines[i * 4:i * 4 + 4]
        elif ctype == 0:
            r = g = b = lines[i]
            a = 255
        elif ctype == 4:
            r = g = b = lines[i * 2]
            a = lines[i * 2 + 1]
        else:
            idx = lines[i]
            r, g, b = plte[idx * 3:idx * 3 + 3]
            a = 255
        rgba[i * 4:i * 4 + 4] = bytes((r, g, b, a))
    return width, height, rgba


def write_png(path: pathlib.Path, width: int, height: int, rgba: bytes) -> None:
    raw = bytearray()
    for y in range(height):
        raw.append(0)   # 필터 없음 — 작은 이미지라 압축률보다 재현성이 중요하다
        raw += rgba[y * width * 4:(y + 1) * width * 4]

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    out += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    out += chunk(b"IEND", b"")
    path.write_bytes(out)


# ------------------------------------------------------------------- 배경 제거

def background_mask(width: int, height: int, rgba: bytearray) -> bytearray:
    """테두리에서 이어지는 어두운 픽셀만 배경(1)으로 표시한다."""
    mask = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def push(x: int, y: int) -> None:
        i = y * width + x
        if mask[i]:
            return
        j = i * 4
        if rgba[j] + rgba[j + 1] + rgba[j + 2] > BG_LUMA:
            return
        mask[i] = 1
        queue.append((x, y))

    for x in range(width):
        push(x, 0)
        push(x, height - 1)
    for y in range(height):
        push(0, y)
        push(width - 1, y)
    while queue:
        x, y = queue.popleft()
        if x > 0:
            push(x - 1, y)
        if x + 1 < width:
            push(x + 1, y)
        if y > 0:
            push(x, y - 1)
        if y + 1 < height:
            push(x, y + 1)
    return mask


def bbox(width: int, height: int, mask: bytearray, x0: int, x1: int) -> tuple[int, int, int, int]:
    left, right, top, bottom = x1, x0, height, -1
    for y in range(height):
        row = y * width
        for x in range(x0, x1 + 1):
            if not mask[row + x]:
                left = min(left, x)
                right = max(right, x)
                top = min(top, y)
                bottom = max(bottom, y)
    if bottom < 0:
        raise SystemExit(f"x {x0}~{x1} 구간에 캐릭터가 없다")
    return left, right, top, bottom


# --------------------------------------------------------------------- 축소

def shrink(width: int, height: int, rgba: bytearray, mask: bytearray,
           xlim: tuple[int, int], anchor_x: float, ground_y: int,
           scale: float) -> bytearray:
    """anchor_x(몸통 중심)를 가로 중앙, ground_y(발끝)를 캔버스 바닥에 맞춰 줄인다.

    한 칸에 들어오는 원본 픽셀을 평균 낸다. 원본은 AI가 그린 도트풍 그림이라
    격자가 정확히 맞지 않는데(칸 ≈ 9.7px), 평균을 내면 그 오차가 사라진다.
    """
    out = bytearray(CANVAS_W * CANVAS_H * 4)
    for oy in range(CANVAS_H):
        # 아래에서부터 쌓아야 발끝이 항상 바닥에 붙는다(포즈마다 키가 조금 다름).
        sy0 = int(round(ground_y + 1 - (CANVAS_H - oy) * scale))
        sy1 = int(round(ground_y + 1 - (CANVAS_H - oy - 1) * scale))
        for ox in range(CANVAS_W):
            sx0 = int(round(anchor_x + (ox - CANVAS_W / 2.0) * scale))
            sx1 = int(round(anchor_x + (ox + 1 - CANVAS_W / 2.0) * scale))
            r = g = b = hit = total = 0
            for y in range(sy0, sy1):
                if not 0 <= y < height:
                    continue
                row = y * width
                for x in range(sx0, sx1):
                    if not xlim[0] <= x <= xlim[1]:
                        continue
                    total += 1
                    if mask[row + x]:
                        continue
                    j = (row + x) * 4
                    r += rgba[j]
                    g += rgba[j + 1]
                    b += rgba[j + 2]
                    hit += 1
            if total == 0 or hit < total * COVER:
                continue
            k = (oy * CANVAS_W + ox) * 4
            out[k:k + 4] = bytes((r // hit, g // hit, b // hit, 255))
    return out


# ------------------------------------------------------ 걷기 위상 변형 (#372)

def _rows(px: bytearray) -> dict[int, tuple[int, int]]:
    """칠해진 행마다 (왼끝, 오른끝)."""
    out = {}
    for y in range(CANVAS_H):
        xs = [x for x in range(CANVAS_W) if px[(y * CANVAS_W + x) * 4 + 3]]
        if xs:
            out[y] = (min(xs), max(xs))
    return out


def _width(rows: dict[int, tuple[int, int]], y: int) -> int:
    return rows[y][1] - rows[y][0] + 1


def _landmarks(px: bytearray) -> tuple[int, float, int, int, int]:
    """(치마 밑단 y, 엉덩이 축 x, 몸통 왼끝, 몸통 오른끝, 어깨 y).

    변형 세 가지가 모두 이 네 좌표로 "무엇을 옮길지"를 가른다.

    - 치마 밑단: 캔버스에서 가장 아래에 있는 넓은 어두운 띠. 그 아래는 전부 다리·구두다.
    - 엉덩이 축: 그 띠의 가로 중심. 다리를 모을 때의 중심이 된다.
    - 몸통 폭: **팔이 끝난 뒤 밑단까지 중 가장 좁은 행**. 팔은 이 폭 밖으로 나간
      픽셀이므로, 이 두 값이 팔과 몸통을 가른다.
    - 어깨: 머리 아래 가장 좁은 행(목) 다음 행. 팔은 여기서부터 시작한다.
    """
    rows = _rows(px)
    if not rows:
        raise SystemExit("빈 스프라이트다")
    top = min(rows)

    hem = -1
    hip = 0.0
    for y in range(CANVAS_H):
        dark = [x for x in range(CANVAS_W)
                if px[(y * CANVAS_W + x) * 4 + 3]
                and px[(y * CANVAS_W + x) * 4] + px[(y * CANVAS_W + x) * 4 + 1]
                + px[(y * CANVAS_W + x) * 4 + 2] < 220]
        if len(dark) >= SKIRT_RUN:
            hem = y
            hip = (min(dark) + max(dark)) / 2.0
    above = CANVAS_H - 1 - hem
    if not HEM_ABOVE_FLOOR[0] <= above <= HEM_ABOVE_FLOOR[1]:
        raise SystemExit(f"치마 밑단이 바닥에서 {above}칸 위다 — {HEM_ABOVE_FLOOR} 밖이라 "
                         "다리와 몸통을 가를 수 없다. SKIRT_RUN을 확인할 것")

    neck = min(range(top + 6, top + 22), key=lambda y: _width(rows, y))
    waist = min(range(neck + 8, hem + 1), key=lambda y: _width(rows, y))
    torso_l, torso_r = rows[waist]
    if not 8 <= torso_r - torso_l + 1 <= 26:
        raise SystemExit(f"몸통 폭이 {torso_r - torso_l + 1}칸이다 — 목/허리 검출이 "
                         "빗나갔다. neck·waist 탐색 구간을 확인할 것")
    return hem, hip, torso_l, torso_r, neck + 1


def _clear_rows(out: bytearray, y0: int, y1: int) -> None:
    for y in range(y0, y1 + 1):
        for x in range(CANVAS_W):
            j = (y * CANVAS_W + x) * 4
            out[j:j + 4] = b"\0\0\0\0"


def close_legs(px: bytearray, close: float) -> bytearray:
    """다리를 엉덩이 축으로 모은다. close=1.0이면 그대로.

    **행마다 정수로 밀고, 배율을 걸지 않는다.** 가로로 눌러 줄이면 다리가 그만큼
    얇아져 젓가락이 되고, 엉덩이를 축으로 회전시키면 접지한 다리가 세워지면서
    발끝이 캔버스 바닥을 뚫는다(발이 바닥에 닿아 있으므로 다리를 세우려면 몸이
    떠올라야 한다 — 그 상승은 raise_hips()가 따로 맡는다). 행을 통째로 미는 것은
    다리 두께를 그대로 두고 기울기만 세우는 방법이다.

    한 행에서 엉덩이 축의 좌/우를 각각 한 다리로 보고, 그 행의 중심을 축 쪽으로
    (1 - close)만큼 당긴다. 축에서 멀리 나간 행이 더 많이 당겨지므로 다리가
    통째로 세워진다.
    """
    if close >= 1.0:
        return bytearray(px)
    hem, hip, _, _, _ = _landmarks(px)
    out = bytearray(px)
    _clear_rows(out, hem + 1, CANVAS_H - 1)
    for y in range(hem + 1, CANVAS_H):
        for near_side in (True, False):
            xs = [x for x in range(CANVAS_W)
                  if px[(y * CANVAS_W + x) * 4 + 3]
                  and ((x < hip) if near_side else (x >= hip))]
            if not xs:
                continue
            center = (min(xs) + max(xs)) / 2.0
            shift = int(round((hip - center) * (1.0 - close)))
            for x in xs:
                nx = x + shift
                if 0 <= nx < CANVAS_W:
                    j = (y * CANVAS_W + x) * 4
                    k = (y * CANVAS_W + nx) * 4
                    out[k:k + 4] = px[j:j + 4]
    return out


def tuck_arms(px: bytearray, inward: int) -> bytearray:
    """팔을 몸통 쪽으로 inward칸 당긴다. 0이면 그대로.

    원본 세 포즈의 팔 위치가 서로 1px밖에 차이 나지 않아 상체가 마네킹처럼 굳어
    보였다(#372). 팔이 실제로 움직이게 하려면 프레임마다 옮겨야 한다.

    **안쪽으로만 당긴다.** 밖으로 밀면 어깨와 팔 사이가 벌어져 팔이 떨어져 나간다.
    안쪽으로 당기면 팔이 몸통 위에 겹치는데, 앞팔은 원래 몸통 앞에 있으므로 맞다.
    """
    if inward <= 0:
        return bytearray(px)
    hem, _, torso_l, torso_r, shoulder = _landmarks(px)
    out = bytearray(px)
    for y in range(shoulder, hem + 1):
        for side_left in (True, False):
            xs = [x for x in range(CANVAS_W)
                  if px[(y * CANVAS_W + x) * 4 + 3]
                  and ((x < torso_l) if side_left else (x > torso_r))]
            if not xs:
                continue
            for x in xs:
                j = (y * CANVAS_W + x) * 4
                out[j:j + 4] = b"\0\0\0\0"
            shift = inward if side_left else -inward
            for x in xs:
                nx = x + shift
                if 0 <= nx < CANVAS_W:
                    j = (y * CANVAS_W + x) * 4
                    k = (y * CANVAS_W + nx) * 4
                    out[k:k + 4] = px[j:j + 4]
    return out


def raise_hips(px: bytearray, bob: int) -> bytearray:
    """치마 밑단 위(머리·팔·몸통·치마)를 bob칸 올린다. 0이면 그대로.

    걷기에는 다리가 모일 때 엉덩이가 올라가고 활보에서 내려앉는 상하 운동이 있다.
    원본 세 포즈는 머리끝 y가 모두 같아 그 운동이 0이었고, 그래서 몸이 레일 위를
    미끄러지는 것처럼 보였다(#372).

    발끝은 바닥에 고정이므로 **다리가 그만큼 길어진다** — 실제로도 다리를 세우면
    엉덩이-발끝 거리가 늘어난다. 그래서 생긴 틈은 **넓적다리**(밑단 바로 아래 행)로
    채운다. 밑단 행으로 채우면 치마가 프레임마다 길어져 늘어나는 것처럼 보인다.
    """
    if bob <= 0:
        return bytearray(px)
    hem, _, _, _, _ = _landmarks(px)
    out = bytearray(px)
    for y in range(0, hem + 1):
        src = y + bob
        for x in range(CANVAS_W):
            j = (y * CANVAS_W + x) * 4
            if src <= hem:
                k = (src * CANVAS_W + x) * 4
                out[j:j + 4] = px[k:k + 4]
            else:
                out[j:j + 4] = b"\0\0\0\0"
    thigh = hem + 1
    for y in range(hem - bob + 1, hem + 1):
        for x in range(CANVAS_W):
            j = (y * CANVAS_W + x) * 4
            k = (thigh * CANVAS_W + x) * 4
            out[j:j + 4] = px[k:k + 4]
    return out


def walk_frame(px: bytearray, close: float, bob: int, arms: int) -> bytearray:
    """위상값 하나로 걷기 프레임 한 장을 만든다.

    순서가 중요하다 — raise_hips()를 마지막에 둬야 앞의 두 변형이 원래 밑단 좌표로
    일한다. 먼저 올려 버리면 치마 밑단이 옮겨져 다리·팔의 경계가 어긋난다.
    """
    top_before = min(_rows(px))
    out = raise_hips(tuck_arms(close_legs(px, close), arms), bob)

    rows = _rows(out)
    if not rows:
        raise SystemExit("변형 결과가 비었다")
    if min(rows) != top_before - bob:
        raise SystemExit(f"머리끝이 y={min(rows)}다 (기대 {top_before - bob}) — "
                         "엉덩이를 올리다 머리가 캔버스를 넘었다. BOB_HEADROOM을 늘릴 것")
    if max(rows) != CANVAS_H - 1:
        raise SystemExit(f"발끝이 y={max(rows)}로 옮겨졌다 (바닥 {CANVAS_H - 1}) — "
                         "다리가 캔버스 밖으로 밀려 발이 떠 있다. 다리 모음을 확인할 것")
    return out


# ------------------------------------------------------------------- 굽기

def _cut(name: str, width: int, height: int, rgba: bytearray, mask: bytearray,
         box: tuple[int, int, int, int], xlim: tuple[int, int], anchor: float,
         scale: float) -> bytearray:
    """한 포즈를 CANVAS_W x CANVAS_H 픽셀로 잘라 낸다(파일로 쓰지는 않는다)."""
    _check_fits(name, box, anchor, scale)
    return shrink(width, height, rgba, mask, xlim, anchor, box[3], scale)


def _write(name: str, px: bytearray, note: str) -> None:
    opaque = sum(1 for i in range(CANVAS_W * CANVAS_H) if px[i * 4 + 3])
    if opaque < 200:
        raise SystemExit(f"{name}: 칠해진 칸이 {opaque}개뿐이다 — 잘라낼 위치를 확인할 것")
    write_png(OUT_DIR / f"{name}.png", CANVAS_W, CANVAS_H, px)
    print(f"{name}.png  {CANVAS_W}x{CANVAS_H}  칠한 칸 {opaque}  {note}")


def build_all() -> None:
    for src in (SRC, SRC_WALK):
        if not src.exists():
            raise SystemExit(f"원본 아트가 없다: {src}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    width, height, rgba = read_png(SRC)
    mask = background_mask(width, height, rgba)
    high_box = bbox(width, height, mask, *RUN_X)
    idle_box = bbox(width, height, mask, *IDLE_X)

    # 두 포즈는 같은 축척으로 그려져 있다(키 1059 vs 1067). 대기 포즈를 기준으로
    # 배율을 잡고 나머지에도 그대로 써야 이동 중 몸집이 안 변한다. 기준은 캔버스가
    # 아니라 **인물 키(FIGURE_H)** 다 — 캔버스에는 머리 위 흔들림 여유가 붙어 있다.
    scale = (idle_box[3] - idle_box[2] + 1) / float(FIGURE_H)

    poses = {}
    if any(key == "high" for _, key, _, _, _ in WALK_CYCLE):
        poses["high"] = _cut("high", width, height, rgba, mask, high_box, RUN_X,
                             RUN_ANCHOR_X, scale)
    _write("player_idle", _cut("player_idle", width, height, rgba, mask, idle_box,
                               IDLE_X, IDLE_ANCHOR_X, scale),
           f"대기(정면)  배율 1px = 원본 {scale:.2f}px")

    # 걷기 원본은 **축척이 다르다** — 인물이 캔버스를 덜 채운다(키 604 / 953).
    # 원본 bbox 비율로 줄이면 걷기 포즈만 작아지므로, 달리기 포즈가 캔버스에서
    # 차지한 높이(71.5px)에 맞춰 배율을 거꾸로 계산한다. 그러면 모든 이동 포즈의
    # 머리 위·발끝이 캔버스에서 같은 자리에 온다.
    high_canvas_h = (high_box[3] - high_box[2] + 1) / scale

    wwidth, wheight, wrgba = read_png(SRC_WALK)
    wmask = background_mask(wwidth, wheight, wrgba)
    boxes = [bbox(wwidth, wheight, wmask, *xlim) for _, xlim, _ in WALK_POSES]
    heights = [b[3] - b[2] + 1 for b in boxes]
    if max(heights) - min(heights) > WALK_HEIGHT_TOLERANCE:
        raise SystemExit(f"걷기 포즈의 키가 다르다 {heights} — 배율이 프레임마다 달라져 "
                         "몸집이 커졌다 작아진다. 원본을 확인할 것")
    walk_scale = heights[0] / high_canvas_h

    for (key, xlim, wanchor), box in zip(WALK_POSES, boxes):
        poses[key] = _cut(key, wwidth, wheight, wrgba, wmask, box, xlim,
                          wanchor, walk_scale)

    for name, key, close, bob, arms in WALK_CYCLE:
        _write(name, walk_frame(poses[key], close, bob, arms),
               f"{key} 포즈  다리 {close:.2f}  엉덩이 +{bob}  팔 -{arms}")


def _check_fits(name: str, box: tuple[int, int, int, int], anchor_x: float,
                scale: float) -> None:
    """캔버스가 포즈 전체를 담는지 미리 본다 — 손발이 잘린 채 커밋되지 않게."""
    left = (box[0] - anchor_x) / scale + CANVAS_W / 2.0
    right = (box[1] + 1 - anchor_x) / scale + CANVAS_W / 2.0
    top = CANVAS_H - (box[3] + 1 - box[2]) / scale
    # 대기 포즈는 배율의 기준이라 위·아래가 인물 키에 딱 맞는다 — 부동소수 오차가
    # 음수로 새는 걸 EPS로 넘긴다.
    eps = 1e-6
    if left < -eps or right > CANVAS_W + eps:
        raise SystemExit(f"{name}: 가로가 넘친다 ({left:.1f}~{right:.1f} / 0~{CANVAS_W}) "
                         "— CANVAS_W를 넓힐 것")
    if top < -eps:
        raise SystemExit(f"{name}: 세로가 넘친다 (머리 위 {top:.1f}) — FIGURE_H를 줄이거나 "
                         "BOB_HEADROOM을 늘릴 것")


if __name__ == "__main__":
    sys.exit(build_all())
