#!/usr/bin/env python3
"""플레이어(이설) 스프라이트 생성기 (#210).

원본 캐릭터 아트 `assets/sprites/source/player_design.png` 한 장에
두 포즈(왼쪽=달리기 측면, 오른쪽=대기 정면)가 같은 축척으로 그려져 있다.
이 도구가 배경을 지우고 게임 크기로 줄여 아래 두 장을 만든다.

    assets/sprites/player_idle.png   대기(정면)
    assets/sprites/player_run.png    이동(달리기, 오른쪽을 봄 — 왼쪽은 flip_h)

원본이 있는 폴더에는 `.gdignore`를 뒀다 — 1254x1254 원본까지 Godot이 임포트해
빌드에 실을 이유가 없다(이 도구는 파일시스템에서 직접 읽는다).

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
OUT_DIR = ROOT / "assets" / "sprites"

# 출력 캔버스. 두 포즈가 같은 크기여야 Sprite2D 오프셋을 하나로 쓸 수 있다.
# 폭은 달리기 포즈(뒤로 뻗은 다리 + 앞으로 뻗은 팔)가 잘리지 않을 만큼 필요하다
# — 높이 56에서는 46이 최소치라 여유를 두고 48로 잡았다(_check_fits가 검사한다).
CANVAS_W = 48
CANVAS_H = 56

# 배경으로 볼 밝기 상한(R+G+B). 머리카락은 (26,26,26)=78이라 걸리지 않는다.
BG_LUMA = 40

# 한 칸의 절반 이상이 캐릭터일 때만 칠한다 — 실루엣이 흐려지지 않게.
COVER = 0.5

# 원본에서 두 포즈가 놓인 x 구간(서로 침범하지 않도록 잘라내는 창).
RUN_X = (61, 768)
IDLE_X = (872, 1138)

# 가로 기준점 = 몸통(재킷) 중심. 전체 bbox 중심을 쓰면 뻗은 팔다리 때문에
# 달릴 때 몸이 한쪽으로 쏠린다.
RUN_ANCHOR_X = (380 + 603) / 2.0
IDLE_ANCHOR_X = (902 + 1117) / 2.0


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


def build_all() -> None:
    if not SRC.exists():
        raise SystemExit(f"원본 아트가 없다: {SRC}")

    width, height, rgba = read_png(SRC)
    mask = background_mask(width, height, rgba)
    run_box = bbox(width, height, mask, *RUN_X)
    idle_box = bbox(width, height, mask, *IDLE_X)

    # 두 포즈는 같은 축척으로 그려져 있다(키 1059 vs 1067). 대기 포즈를
    # 기준으로 배율을 잡고 달리기에도 그대로 써야 이동 중 몸집이 안 변한다.
    scale = (idle_box[3] - idle_box[2] + 1) / float(CANVAS_H)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, box, xlim, anchor in (
        ("player_idle", idle_box, IDLE_X, IDLE_ANCHOR_X),
        ("player_run", run_box, RUN_X, RUN_ANCHOR_X),
    ):
        _check_fits(name, box, anchor, scale)
        px = shrink(width, height, rgba, mask, xlim, anchor, box[3], scale)
        opaque = sum(1 for i in range(CANVAS_W * CANVAS_H) if px[i * 4 + 3])
        if opaque < 200:
            raise SystemExit(f"{name}: 칠해진 칸이 {opaque}개뿐이다 — 잘라낼 위치를 확인할 것")
        write_png(OUT_DIR / f"{name}.png", CANVAS_W, CANVAS_H, px)
        print(f"{name}.png  {CANVAS_W}x{CANVAS_H}  칠한 칸 {opaque}  "
              f"원본 {box[1] - box[0] + 1}x{box[3] - box[2] + 1}")
    print(f"배율 1px = 원본 {scale:.2f}px")


def _check_fits(name: str, box: tuple[int, int, int, int], anchor_x: float,
                scale: float) -> None:
    """캔버스가 포즈 전체를 담는지 미리 본다 — 손발이 잘린 채 커밋되지 않게."""
    left = (box[0] - anchor_x) / scale + CANVAS_W / 2.0
    right = (box[1] + 1 - anchor_x) / scale + CANVAS_W / 2.0
    top = CANVAS_H - (box[3] + 1 - box[2]) / scale
    # 대기 포즈는 배율의 기준이라 위·아래가 캔버스에 딱 맞는다 — 부동소수 오차가
    # 음수로 새는 걸 EPS로 넘긴다.
    eps = 1e-6
    if left < -eps or right > CANVAS_W + eps:
        raise SystemExit(f"{name}: 가로가 넘친다 ({left:.1f}~{right:.1f} / 0~{CANVAS_W}) "
                         "— CANVAS_W를 넓힐 것")
    if top < -eps:
        raise SystemExit(f"{name}: 세로가 넘친다 (머리 위 {top:.1f}) — CANVAS_H를 늘릴 것")


if __name__ == "__main__":
    sys.exit(build_all())
