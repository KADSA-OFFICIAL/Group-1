#!/usr/bin/env python3
"""플레이어(이설) 스프라이트 생성기 (#210, 걷기 #365·#368·#372·#375·#378·#381, 12프레임 #384).

원본이 두 장이다.

`player_design.png`       대기 정면(+ 배율 기준이 되는 측면 포즈).
`player_walk_design.png`  측면 걷기 **열두 포즈**(2행×6열 시트, 사용자가 직접 그렸다).
                          왼쪽 위부터 가로로 1~6, 다음 줄이 7~12 — 한 장이 전체 걷기
                          사이클(두 걸음)이다.

이 도구가 배경을 지우고 게임 크기로 줄여 아래 열세 장을 만든다.

    assets/sprites/player_idle.png      대기(정면)
    assets/sprites/player_walk_1.png    ~
    ...                                  걷기 1~12(시트 순서 그대로)
    assets/sprites/player_walk_12.png   ~

이동 중에는 `player_controller.gd`가 `player_walk_1 → 2 → … → 12 → (루프) 1`을 순서대로
돈다 — 반복되는 "기본 프레임"을 끼우는 인덱스 표(수위 방식, #375)는 없다. 열두 장이
전부 서로 다른, 직접 그린 포즈라 그럴 필요가 없다. 열두 장 모두 오른쪽을 보고 있어
왼쪽으로 갈 때만 flip_h 한다.

**원본을 그대로 줄인다. 합성 단계는 없다(#378 이후 계속).** #372·#375에는 한두 장뿐인
원본에서 다리를 모으고 엉덩이를 올리고 팔을 당기는 코드 합성이 있었는데, 세 번(#368·
#372·#375) 다 "다리 윤곽이 거칠다"로 끝났다. 이번 원본은 걸음 하나를 열두 장으로 나눠
그려서 그 문제 자체가 없다 — 코드는 자르고 줄이기만 한다.

원본이 있는 폴더에는 `.gdignore`를 뒀다 — 1254x1254 / 1774x887 원본까지 Godot이
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

# 출력 캔버스. 열세 장이 같은 크기여야 Sprite2D 오프셋(SPRITE_OFFSET_Y)을 하나로 쓸 수
# 있다. 폭은 가장 벌어진 포즈(뒤로 뻗은 다리 + 앞으로 뻗은 팔)가 잘리지 않을 만큼
# 필요하다 — #381의 활보 포즈 기준 대칭 중심 정렬 최소 72.1칸이라 여유를 두고 74로
# 잡았다(`_check_fits`가 검사한다). #384의 12프레임 걷기 사이클은 보폭이 이보다 훨씬
# 좁아 74 안에 여유 있게 들어간다 — 새 원본을 넣을 때마다 다시 잴 것.
CANVAS_W = 74
# 인물의 키. 배율의 기준이고 **화면에서 보이는 크기를 정하는 값**이다.
FIGURE_H = 72
# 머리 위에 비워 두는 줄 수. 포즈마다 키가 달라(걸음의 상하 흔들림) 인물이 캔버스
# 바닥에 붙은 채 머리끝이 프레임마다 오르내리므로 그만큼 여유가 필요하다 — 지금 원본은
# 통과 포즈가 접지보다 1칸 높다.
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

# 걷기 원본은 2행×6열 시트다(#384). 값은 (출력 이름, 가로 창, 세로 창, 머리 중심).
# 같은 열의 위·아래 포즈가 가로로는 겹치므로(같은 x 구간을 공유) 세로 창으로 행을
# 갈라야 한다 — 안 그러면 bbox가 두 포즈를 하나로 합쳐 잡는다. 행 사이 빈 띠가
# 421~476(원본px)이라 443을 경계로 잡았다.
_WALK_COLS = ((140, 319), (397, 555), (658, 835), (927, 1096), (1190, 1349), (1458, 1636))
_WALK_ROWS = ((0, 443), (443, 887))
_WALK_HEADS = (226.0, 490.0, 754.0, 1016.5, 1280.0, 1545.0,   # 1~6행(위)
               219.5, 481.5, 745.0, 1005.5, 1267.0, 1541.5)   # 7~12행(아래)
WALK_POSES = tuple(
    (f"player_walk_{i + 1}", _WALK_COLS[i % 6], _WALK_ROWS[i // 6], _WALK_HEADS[i])
    for i in range(12)
)

# 배율 기준이 되는 포즈. 이 포즈의 캔버스 높이를 기존 아트의 측면 포즈와 같은 71.5px로
# 맞춘다 — **그 값이 지금 화면에 보이는 인물 크기다.** 다른 포즈는 원본 키 그대로
# 줄어들므로 키 차이가 그대로 상하 흔들림이 된다(진짜 걸음처럼 자연스러운 정도라
# 굳이 맞추지 않는다 — #372·#375의 인위적인 `raise_hips`와 달리 이번엔 그림 자체의
# 높이 차이를 그대로 쓴다).
WALK_SCALE_POSE = "player_walk_1"

# 포즈들의 키가 이만큼(원본 px) 넘게 다르면 멈춘다. 12장 다 같은 걸음 사이클 안이라
# 키 차이가 크지 않다(실측 378~380, 2px) — #381의 두 발이 다 공중에 뜨는 포즈처럼
# 극단적으로 짧아지는 컷이 없다. 그래도 사고를 잡을 여유는 남겨 둔다.
WALK_HEIGHT_TOLERANCE = 20


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


def bbox(width: int, height: int, mask: bytearray, x0: int, x1: int,
         y0: int = 0, y1: int | None = None) -> tuple[int, int, int, int]:
    """[x0,x1] x [y0,y1) 구간의 실루엣 경계상자. y0/y1을 생략하면 이미지 전체 높이를 본다.

    2행짜리 시트(#384)처럼 같은 열에 포즈가 둘 이상 겹쳐 있을 때만 y0/y1이 필요하다
    — 안 주면 위아래 포즈가 하나의 경계상자로 합쳐진다.
    """
    if y1 is None:
        y1 = height
    left, right, top, bottom = x1, x0, y1, y0 - 1
    for y in range(y0, y1):
        row = y * width
        for x in range(x0, x1 + 1):
            if not mask[row + x]:
                left = min(left, x)
                right = max(right, x)
                top = min(top, y)
                bottom = max(bottom, y)
    if bottom < y0:
        raise SystemExit(f"x {x0}~{x1} y {y0}~{y1} 구간에 캐릭터가 없다")
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
    # 발끝은 캔버스 바닥에 붙어야 한다. 네 장이 같은 오프셋(SPRITE_OFFSET_Y) 하나를
    # 쓰므로, 어긋나면 프레임이 바뀔 때 인물이 위아래로 튄다.
    if not any(px[((CANVAS_H - 1) * CANVAS_W + x) * 4 + 3] for x in range(CANVAS_W)):
        raise SystemExit(f"{name}: 발끝이 캔버스 바닥(y={CANVAS_H - 1})에 닿지 않는다 "
                         "— 잘라낼 위치나 배율을 확인할 것")
    write_png(OUT_DIR / f"{name}.png", CANVAS_W, CANVAS_H, px)
    print(f"{name}.png  {CANVAS_W}x{CANVAS_H}  칠한 칸 {opaque}  {note}")


def build_all() -> None:
    for src in (SRC, SRC_WALK):
        if not src.exists():
            raise SystemExit(f"원본 아트가 없다: {src}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    width, height, rgba = read_png(SRC)
    mask = background_mask(width, height, rgba)
    side_box = bbox(width, height, mask, *RUN_X)
    idle_box = bbox(width, height, mask, *IDLE_X)

    # 두 포즈는 같은 축척으로 그려져 있다(키 1059 vs 1067). 대기 포즈를 기준으로
    # 배율을 잡는다. 기준은 캔버스가 아니라 **인물 키(FIGURE_H)** 다 — 캔버스에는
    # 머리 위 흔들림 여유가 붙어 있다.
    scale = (idle_box[3] - idle_box[2] + 1) / float(FIGURE_H)
    _write("player_idle", _cut("player_idle", width, height, rgba, mask, idle_box,
                              IDLE_X, IDLE_ANCHOR_X, scale),
           f"대기(정면)  배율 1px = 원본 {scale:.2f}px")

    # 걷기 원본은 **축척이 다르다** — 인물이 캔버스를 덜 채운다. 원본 bbox 비율로
    # 줄이면 걷기 포즈만 작아지므로, 기존 아트의 측면 포즈가 캔버스에서 차지한
    # 높이(71.5px)에 맞춰 배율을 거꾸로 계산한다. 그 값이 지금 화면에 보이는 크기다.
    side_canvas_h = (side_box[3] - side_box[2] + 1) / scale

    wwidth, wheight, wrgba = read_png(SRC_WALK)
    wmask = background_mask(wwidth, wheight, wrgba)
    boxes = {name: bbox(wwidth, wheight, wmask, xlim[0], xlim[1], ylim[0], ylim[1])
             for name, xlim, ylim, _ in WALK_POSES}
    heights = [b[3] - b[2] + 1 for b in boxes.values()]
    if max(heights) - min(heights) > WALK_HEIGHT_TOLERANCE:
        raise SystemExit(f"걷기 포즈의 키가 너무 다르다 {heights} — 배율이 하나뿐이므로 "
                         "인물이 커졌다 작아진다. 원본을 확인할 것")
    ref = boxes[WALK_SCALE_POSE]
    walk_scale = (ref[3] - ref[2] + 1) / side_canvas_h

    for name, xlim, _ylim, anchor in WALK_POSES:
        box = boxes[name]
        px = _cut(name, wwidth, wheight, wrgba, wmask, box, xlim, anchor, walk_scale)
        _write(name, px, f"원본 {box[1] - box[0] + 1}x{box[3] - box[2] + 1}  "
                         f"배율 1px = 원본 {walk_scale:.2f}px")


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
