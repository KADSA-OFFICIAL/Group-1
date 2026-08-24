#!/usr/bin/env python3
"""수위(박종태) 스프라이트 시트 생성기 (#310).

원본 캐릭터 아트 `assets/sprites/source/janitor/`의 열 장에서
게임용 스프라이트 시트 한 장을 굽는다.

    assets/sprites/janitor_sheet.png   3열(걸음) x 4행(방향), 칸 48x80

행 순서는 janitor.gd의 ROW_DOWN/LEFT/RIGHT/UP과 같아야 한다.
열은 [기본, 걸음A, 걸음B]이고 janitor.gd의 WALK_CYCLE이 [0,1,0,2]로 굴린다.

원본이 있는 폴더는 상위 `source/`의 `.gdignore` 아래라 Godot이 임포트하지
않는다 — 512~1024짜리 원본까지 빌드에 실을 이유가 없다(이 도구는 파일시스템에서
직접 읽는다).

gen_player_sprites.py와 같은 규약: **표준 라이브러리만 쓰고 결정론적**이다.
정수 연산만 쓰므로 부동소수 오차로 결과가 흔들리지 않는다.

원본에 대해 알아 둘 것(실측):
  * 옆·정면 아홉 장은 512x512에 **4px 블록 도트 아트**(논리 128x128)다.
  * 뒷모습(`janitor_up_0.png`)만 1024x1024이고 블록 격자가 없는 보간된 그림이다.
    배율이 정확히 2배라 같은 식으로 줄이면 나머지와 크기가 맞는다.
  * 열 장 모두 인물이 캔버스를 세로로 꽉 채운다(머리 y=0, 발끝 y=마지막 줄).
    그래서 **캔버스째 줄이면 발 높이가 저절로 맞는다** — 인물 bbox에 맞춰 줄이면
    발을 든 걸음 프레임에서 키가 늘어난다.
  * 배경은 전부 **불투명한 흰색**이다. 투명 픽셀은 한 개도 없다.

주의: 배경을 "흰색"으로만 판별하면 안 된다 — 가슴 명찰과 손전등 렌즈도 희다.
그래서 이미지 테두리에서 시작하는 flood fill로 *바깥과 이어진* 흰색만 지운다.

축소는 평균이 아니라 **최빈색**으로 한다. 평균을 내면 원본에 없던 중간색이
생겨 도트 아트가 흐려진다.

재실행 안전장치: 이미 있는 출력과 픽셀이 같으면 파일을 건드리지 않는다.
PNG 인코더(zlib 버전 등)가 달라도 diff가 나지 않게 하려는 것이다.
"""
from __future__ import annotations

import pathlib
import struct
import sys
import zlib
from collections import deque

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "assets" / "sprites" / "source" / "janitor"
OUT = ROOT / "assets" / "sprites" / "janitor_sheet.png"

# 한 칸의 크기. 높이는 플레이어(72)보다 조금 커서 어른으로 보이게 잡았고,
# 폭은 정면 프레임에서 손전등을 든 팔이 잘리지 않는 최소치(47)에 1px 여유다.
# 바꾸면 janitor.gd의 SPRITE_OFFSET_Y도 (발끝 y) - (높이/2)로 다시 계산할 것.
CELL_W = 48
CELL_H = 80

# 테두리에서 이어진 이 밝기(채널별) 이상만 배경으로 본다. 뒷모습 원본은
# 보간된 그림이라 흰색과 윤곽선 사이에 회색 띠가 있어 255로 잡으면 남는다.
BG_MIN = 200

# 한 칸의 절반 이상이 캐릭터일 때만 찍는다 — 실루엣이 흐려지지 않게.
# 정수 비교로 쓴다: ink * COVER_DEN >= total * COVER_NUM
COVER_NUM = 1
COVER_DEN = 2

# 행 = 방향. janitor.gd의 ROW_* 상수와 순서가 같아야 한다.
# 뒷모습은 원본이 한 장뿐이라 세 열을 같은 그림으로 채운다 — janitor.gd가
# 위로 걸을 때만 1px 흔들어 걸음을 만든다.
ROWS: list[tuple[str, list[str]]] = [
    ("down", ["janitor_down_0.png", "janitor_down_1.png", "janitor_down_2.png"]),
    ("left", ["janitor_left_0.png", "janitor_left_1.png", "janitor_left_2.png"]),
    ("right", ["janitor_right_0.png", "janitor_right_1.png", "janitor_right_2.png"]),
    ("up", ["janitor_up_0.png", "janitor_up_0.png", "janitor_up_0.png"]),
]


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
                raise SystemExit(f"인터레이스 PNG는 지원하지 않는다: {path}")
            if depth != 8:
                raise SystemExit(f"8비트 PNG만 지원한다 (bit depth={depth}): {path}")
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
            raise SystemExit(f"알 수 없는 PNG 필터 {filt}: {path}")
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
    """테두리에서 이어지는 흰 픽셀만 배경(1)으로 표시한다.

    윤곽선에 둘러싸인 흰색(가슴 명찰·손전등 렌즈)은 바깥과 끊겨 있어 남는다.
    """
    mask = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def push(x: int, y: int) -> None:
        i = y * width + x
        if mask[i]:
            return
        j = i * 4
        if rgba[j + 3] >= 8 and not (
                rgba[j] >= BG_MIN and rgba[j + 1] >= BG_MIN and rgba[j + 2] >= BG_MIN):
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


# ----------------------------------------------------------------------- 축소

def cell_bounds(size: int, tx: int, ty: int) -> tuple[int, int, int, int]:
    """칸 하나가 원본에서 차지하는 구역. 전부 정수 나눗셈이다.

    세로는 원본 캔버스 전체를 CELL_H로 나눈다(인물이 캔버스를 꽉 채우므로
    이것이 곧 발 높이 정렬이다). 가로는 캔버스 중심을 기준으로 CELL_W 폭만
    잘라 낸다 — 화가가 인물을 캔버스 중앙에 두었으므로, 손전등을 든 팔이
    프레임마다 흔들려도 몸이 좌우로 밀리지 않는다.
    """
    y0 = ty * size // CELL_H
    y1 = (ty + 1) * size // CELL_H
    x0 = size * (CELL_H + 2 * tx - CELL_W) // (2 * CELL_H)
    x1 = size * (CELL_H + 2 * (tx + 1) - CELL_W) // (2 * CELL_H)
    return x0, y0, x1, y1


def bake_cell(width: int, size: int, rgba: bytearray, mask: bytearray,
              tx: int, ty: int) -> int:
    """칸 하나의 색. 캐릭터가 절반 미만이면 -1(투명)."""
    x0, y0, x1, y1 = cell_bounds(size, tx, ty)
    x0 = max(x0, 0)
    x1 = min(x1, width)
    total = (y1 - y0) * (x1 - x0)
    if total <= 0:
        return -1

    counts: dict[int, int] = {}
    ink = 0
    for y in range(y0, y1):
        row = y * width
        for x in range(x0, x1):
            if mask[row + x]:
                continue
            j = (row + x) * 4
            if rgba[j + 3] < 8:
                continue
            ink += 1
            packed = (rgba[j] << 16) | (rgba[j + 1] << 8) | rgba[j + 2]
            counts[packed] = counts.get(packed, 0) + 1

    if ink * COVER_DEN < total * COVER_NUM:
        return -1
    # 최빈색. 같은 수면 작은 값 쪽으로 — 사전 순서에 기대면 결정론적이지 않다.
    return min(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]


def bake() -> tuple[int, int, bytearray]:
    sheet_w = CELL_W * len(ROWS[0][1])
    sheet_h = CELL_H * len(ROWS)
    sheet = bytearray(sheet_w * sheet_h * 4)

    cache: dict[str, tuple[int, int, bytearray, bytearray]] = {}
    for row, (label, names) in enumerate(ROWS):
        for col, name in enumerate(names):
            if name not in cache:
                path = SRC_DIR / name
                if not path.exists():
                    raise SystemExit(f"원본이 없다: {path}")
                w, h, rgba = read_png(path)
                if w != h:
                    raise SystemExit(f"정사각 원본만 지원한다 ({w}x{h}): {path}")
                cache[name] = (w, h, rgba, background_mask(w, h, rgba))
            w, h, rgba, mask = cache[name]

            filled = 0
            for ty in range(CELL_H):
                for tx in range(CELL_W):
                    packed = bake_cell(w, h, rgba, mask, tx, ty)
                    if packed < 0:
                        continue
                    filled += 1
                    px = col * CELL_W + tx
                    py = row * CELL_H + ty
                    j = (py * sheet_w + px) * 4
                    sheet[j] = (packed >> 16) & 0xFF
                    sheet[j + 1] = (packed >> 8) & 0xFF
                    sheet[j + 2] = packed & 0xFF
                    sheet[j + 3] = 255
            print(f"  {label:<5} f{col}  {name:<22} 채운 픽셀 {filled}")
    return sheet_w, sheet_h, sheet


# ----------------------------------------------------------------------- 검사

def check_cells(sheet_w: int, sheet: bytearray) -> None:
    """칸마다 인물이 칸 안에 들어가고 발끝이 바닥 줄에 닿는지 본다.

    기본 프레임의 발끝이 칸마다 다른 높이에 있으면 방향을 바꿀 때 수위가
    위아래로 튄다. 걸음 프레임은 발을 들 수 있으므로 검사하지 않는다.
    """
    for row, (label, names) in enumerate(ROWS):
        for col in range(len(names)):
            x0, y0 = col * CELL_W, row * CELL_H
            bottom = -1
            for ty in range(CELL_H):
                for tx in range(CELL_W):
                    if sheet[((y0 + ty) * sheet_w + x0 + tx) * 4 + 3] >= 8:
                        bottom = max(bottom, ty)
            if bottom < 0:
                raise SystemExit(f"{label} f{col}: 빈 칸이다")
            if col == 0 and bottom != CELL_H - 1:
                raise SystemExit(
                    f"{label} f0: 발끝이 칸 바닥에 닿지 않는다"
                    f" (y={bottom}, 기대 {CELL_H - 1})")


def main() -> int:
    print(f"수위 스프라이트 시트 ({CELL_W}x{CELL_H}, {len(ROWS[0][1])}열 x {len(ROWS)}행)")
    sheet_w, sheet_h, sheet = bake()
    check_cells(sheet_w, sheet)

    if OUT.exists():
        old_w, old_h, old = read_png(OUT)
        if (old_w, old_h) == (sheet_w, sheet_h) and old == sheet:
            # 인코더가 달라도 diff가 나지 않게, 픽셀이 같으면 그대로 둔다.
            print(f"{OUT.relative_to(ROOT)} 그대로 (픽셀 동일)")
            return 0

    write_png(OUT, sheet_w, sheet_h, bytes(sheet))
    print(f"{OUT.relative_to(ROOT)} {sheet_w}x{sheet_h} 씀")
    return 0


if __name__ == "__main__":
    sys.exit(main())
