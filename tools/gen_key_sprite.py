#!/usr/bin/env python3
"""계단 열쇠 스프라이트 생성기 (#333).

원본 아트 `assets/sprites/source/key_design.png`(흰 배경 위 황금 열쇠)에서
게임용 도트 스프라이트 한 장을 굽는다.

    assets/sprites/key.png   (긴 변 MAX_SIDE, 짧은 변은 원본 비율)

`gen_player_sprites.py`·`gen_janitor_sprites.py`와 같은 규약이다 —
**표준 라이브러리만 쓰고 결정론적**이고, 정수 연산만 써서 부동소수 오차로
결과가 흔들리지 않는다. 원본은 상위 `source/`의 `.gdignore` 아래라 Godot이
임포트하지 않는다(1000px짜리 원본을 빌드에 실을 이유가 없다).

인물 스프라이트와 다른 점 둘:

  * **잘라 낸다.** 인물 원본은 캔버스를 세로로 꽉 채워서 캔버스째 줄이면 발
    높이가 저절로 맞았지만, 열쇠는 캔버스 한가운데에 여백을 두고 놓여 있다.
    캔버스째 줄이면 24px 중 열쇠가 차지하는 것이 열 몇 px뿐이라 뭉개진다.
    그래서 배경을 지운 뒤 남은 것의 경계상자로 먼저 자른다.
  * **덮임 문턱이 낮다**(COVER 2/5). 인물은 1/2이었는데, 대각선으로 누운
    열쇠는 축과 어긋난 가장자리·톱니가 칸을 반쯤만 채워서 1/2로 자르면
    실루엣이 끊긴다.

배경은 "흰색"으로만 판별하면 안 된다 — 열쇠 몸통의 하이라이트도 거의 희다.
테두리에서 시작하는 flood fill로 *바깥과 이어진* 흰색만 지운다.

축소는 평균이 아니라 **최빈색**이다. 평균을 내면 원본에 없던 중간색이 생겨
도트 아트가 흐려진다.

재실행 안전장치: 이미 있는 출력과 픽셀이 같으면 파일을 건드리지 않는다
(PNG 인코더 버전이 달라도 diff가 나지 않게).
"""
from __future__ import annotations

import pathlib
import struct
import sys
import zlib
from collections import deque

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "sprites" / "source" / "key_design.png"
OUT = ROOT / "assets" / "sprites" / "key.png"

# 긴 변의 도트 수 = 월드 픽셀 수(Sprite2D scale 1, 플레이어 60x72와 같은 규약).
# 예전 폴리곤은 22x10이었다. 24면 플레이어 키의 1/3이라 바닥에 떨어진 열쇠로
# 읽히면서, 활꼴 고리의 구멍과 톱니 두 개가 살아남는 최소 크기다.
MAX_SIDE = 24

# 테두리에서 이어진 이 밝기(채널별) 이상만 배경으로 본다.
BG_MIN = 200

# 구멍으로 볼 흰 덩어리의 최소 넓이 = 캔버스 / HOLE_DEN. 실측(1254x1254 원본):
# 고리 구멍 17862px(캔버스의 1.14%), 그 다음으로 큰 흰 덩어리는 활꼴의
# 하이라이트 4951px(0.31%)다. 0.5%로 가르면 양쪽에 두 배씩 여유가 있다.
HOLE_DEN = 200

# 칸의 이 비율 이상이 그림일 때만 찍는다. 정수 비교로 쓴다:
#   ink * COVER_DEN >= total * COVER_NUM
COVER_NUM = 2
COVER_DEN = 5


# --------------------------------------------------------------------------- PNG

def read_png(path: pathlib.Path) -> tuple[int, int, bytearray]:
    """인터레이스 없는 8비트 PNG를 RGBA 바이트열로 읽는다."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"PNG가 아니다: {path}")

    pos, idat, plte, trns = 8, bytearray(), None, None
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
        elif ctag == b"tRNS":
            trns = body
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
            a = trns[idx] if trns is not None and idx < len(trns) else 255
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
    """테두리에서 이어지는 흰(또는 투명) 픽셀만 배경(1)으로 표시한다.

    윤곽선에 둘러싸인 흰색(열쇠 몸통의 하이라이트, 고리 구멍 안)은 바깥과
    끊겨 있어 남는다 — 구멍 안쪽은 바깥과 이어져 있지 않으므로 흰색으로
    남지만, 아래 `punch_holes()`가 윤곽선에 둘러싸인 '구멍'만 따로 뚫는다.
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


def punch_holes(width: int, height: int, rgba: bytearray, mask: bytearray,
                min_area: int) -> int:
    """바깥과 끊긴 흰 덩어리 중 **넓은 것**을 배경으로 추가한다.

    열쇠 고리 한가운데 구멍은 윤곽선에 둘러싸여 있어 테두리 flood fill로는
    지워지지 않는다. 남겨 두면 열쇠가 아니라 고리가 막힌 숟가락이 된다.
    반대로 몸통의 하이라이트도 거의 흰색이라 **넓이로 가른다** — 구멍은 원본
    기준 수천 px, 하이라이트는 한 줄기 몇 px다.
    """
    seen = bytearray(width * height)
    punched = 0
    for sy in range(height):
        for sx in range(width):
            si = sy * width + sx
            if seen[si] or mask[si]:
                continue
            j = si * 4
            if not (rgba[j] >= BG_MIN and rgba[j + 1] >= BG_MIN and rgba[j + 2] >= BG_MIN):
                continue
            blob = []
            queue = deque([(sx, sy)])
            seen[si] = 1
            while queue:
                x, y = queue.popleft()
                blob.append(y * width + x)
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if not (0 <= nx < width and 0 <= ny < height):
                        continue
                    ni = ny * width + nx
                    if seen[ni] or mask[ni]:
                        continue
                    k = ni * 4
                    if (rgba[k] >= BG_MIN and rgba[k + 1] >= BG_MIN
                            and rgba[k + 2] >= BG_MIN):
                        seen[ni] = 1
                        queue.append((nx, ny))
            if len(blob) >= min_area:
                for i in blob:
                    mask[i] = 1
                punched += 1
    return punched


# ----------------------------------------------------------------------- 축소

def content_box(width: int, height: int, mask: bytearray) -> tuple[int, int, int, int]:
    """배경이 아닌 픽셀의 경계상자. 열쇠는 캔버스 한가운데에 여백을 두고 있다."""
    x0, y0, x1, y1 = width, height, -1, -1
    for y in range(height):
        row = y * width
        for x in range(width):
            if mask[row + x]:
                continue
            x0, x1 = min(x0, x), max(x1, x)
            y0, y1 = min(y0, y), max(y1, y)
    if x1 < 0:
        raise SystemExit("배경을 지우고 나니 남는 픽셀이 없다 — BG_MIN을 확인할 것")
    return x0, y0, x1 + 1, y1 + 1


def out_size(box_w: int, box_h: int) -> tuple[int, int]:
    """긴 변을 MAX_SIDE로 맞추고 짧은 변은 비율대로(정수 나눗셈, 최소 1)."""
    if box_w >= box_h:
        return MAX_SIDE, max(1, (box_h * MAX_SIDE + box_w // 2) // box_w)
    return max(1, (box_w * MAX_SIDE + box_h // 2) // box_h), MAX_SIDE


def bake_cell(width: int, rgba: bytearray, mask: bytearray,
              x0: int, y0: int, x1: int, y1: int) -> int:
    """칸 하나의 색. 그림이 COVER 미만이면 -1(투명)."""
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
    if not SRC.exists():
        raise SystemExit(f"원본이 없다: {SRC}")
    w, h, rgba = read_png(SRC)
    mask = background_mask(w, h, rgba)
    holes = punch_holes(w, h, rgba, mask, max(16, w * h // HOLE_DEN))
    bx0, by0, bx1, by1 = content_box(w, h, mask)
    box_w, box_h = bx1 - bx0, by1 - by0
    ow, oh = out_size(box_w, box_h)
    print(f"  원본 {w}x{h} → 내용 {box_w}x{box_h} (구멍 {holes}개) → 출력 {ow}x{oh}")

    img = bytearray(ow * oh * 4)
    for ty in range(oh):
        cy0 = by0 + ty * box_h // oh
        cy1 = by0 + (ty + 1) * box_h // oh
        for tx in range(ow):
            cx0 = bx0 + tx * box_w // ow
            cx1 = bx0 + (tx + 1) * box_w // ow
            packed = bake_cell(w, rgba, mask, cx0, cy0, cx1, cy1)
            if packed < 0:
                continue
            j = (ty * ow + tx) * 4
            img[j] = (packed >> 16) & 0xFF
            img[j + 1] = (packed >> 8) & 0xFF
            img[j + 2] = packed & 0xFF
            img[j + 3] = 255
    return ow, oh, img


# ----------------------------------------------------------------------- 검사

def check(ow: int, oh: int, img: bytearray) -> None:
    opaque = sum(1 for i in range(ow * oh) if img[i * 4 + 3] >= 8)
    if opaque == 0:
        raise SystemExit("빈 스프라이트다")
    if opaque == ow * oh:
        raise SystemExit("투명 픽셀이 하나도 없다 — 배경이 지워지지 않았다")
    print(f"  불투명 {opaque} / {ow * oh} 픽셀")
    for y in range(oh):
        row = "".join(".#"[img[(y * ow + x) * 4 + 3] >= 8] for x in range(ow))
        print(f"  {row}")


def main() -> int:
    print(f"열쇠 스프라이트 (긴 변 {MAX_SIDE})")
    ow, oh, img = bake()
    check(ow, oh, img)

    if OUT.exists():
        old_w, old_h, old = read_png(OUT)
        if (old_w, old_h) == (ow, oh) and old == img:
            # 인코더가 달라도 diff가 나지 않게, 픽셀이 같으면 그대로 둔다.
            print(f"{OUT.relative_to(ROOT)} 그대로 (픽셀 동일)")
            return 0

    write_png(OUT, ow, oh, bytes(img))
    print(f"{OUT.relative_to(ROOT)} {ow}x{oh} 씀")
    return 0


if __name__ == "__main__":
    sys.exit(main())
