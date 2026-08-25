#!/usr/bin/env python3
"""플레이어(이설) 스프라이트 생성기 (#210, 걷기 프레임 #365).

원본이 두 장이다.

`player_design.png`  두 포즈(왼쪽=달리기 측면, 오른쪽=대기 정면)가 같은 축척으로 있다.
`player_walk_design.png`  측면 걷기 두 포즈(왼쪽=넓은 활보, 오른쪽=뒷발 들기).

이 도구가 배경을 지우고 게임 크기로 줄여 아래 네 장을 만든다.

    assets/sprites/player_idle.png        대기(정면)
    assets/sprites/player_walk_1.png     걷기 1 — 뒷다리를 뒤로 뻗음
    assets/sprites/player_walk_2.png     걷기 2 — 뒷발이 들리기 시작
    assets/sprites/player_run.png        걷기 3 — 뒷발이 높이 들림
    assets/sprites/player_walk_pass.png  걷기 4 — 다리가 몸 아래를 지남 (#368, 합성)

이동 중에는 walk_1 → walk_2 → run → walk_pass 순으로 순환한다
(`player_controller.gd`). 뒷다리가 뒤로 뻗음 → 들리기 시작 → 높이 들림 → 몸 아래
통과로 한 바퀴를 돌아야 걸음으로 읽히므로 **순서를 바꾸려면 그림의 뒷다리를 먼저
볼 것**. 네 장 모두 오른쪽을 보고 있어 왼쪽으로 갈 때만 flip_h 한다.

마지막 한 장은 원본 아트가 없어 `passing_pose()`가 walk_1에서 합성한다(#368) —
**손으로 그린 컷이 생기면 이 단계를 지우고 그 그림으로 갈아탈 것**.

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

# 출력 캔버스. 네 포즈가 같은 크기여야 Sprite2D 오프셋(SPRITE_OFFSET_Y)을 하나로 쓸 수 있다.
# 폭은 달리기 포즈(뒤로 뻗은 다리 + 앞으로 뻗은 팔)가 잘리지 않을 만큼 필요하다
# — 높이 72에서는 59가 최소치라 여유를 두고 60으로 잡았다(_check_fits가 검사한다).
CANVAS_W = 60
CANVAS_H = 72

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
    ("player_walk_1", (0, 810), (421 + 566) / 2.0),
    ("player_walk_2", (811, 1649), (1121 + 1269) / 2.0),
)

# 걷기 두 포즈의 키가 이만큼(원본 px) 넘게 다르면 멈춘다. 배율을 첫 포즈에서 잡아
# 둘 다에 쓰므로, 키가 다르면 프레임이 바뀔 때 몸집이 커졌다 작아진다.
WALK_HEIGHT_TOLERANCE = 2

# ── passing pose 합성 (#368) ────────────────────────────────────────────────
# 다리를 엉덩이 축으로 이 비율까지 모은다(1.0이면 그대로, 0.0이면 한 줄로 겹침).
# 0.5는 눈으로 고른 값이다 — 더 조이면 두 다리가 한 덩어리로 뭉쳐 무엇이 무엇인지
# 알 수 없고, 덜 조이면 walk_1과 구별이 안 돼 컷을 넣은 의미가 없다.
PASS_CLOSE = 0.5
# 치마로 볼 어두운 픽셀 수의 하한(한 행 기준). 구두도 어둡지만 한 행에 4~6칸뿐이라
# 걸리지 않는다 — 치마는 15칸이 넘는다.
PASS_SKIRT_RUN = 10
# 치마 밑단이 이 구간 밖이면 멈춘다. 캔버스 72칸 중 다리는 늘 아래 1/3이므로,
# 밑단을 잘못 잡으면(구두를 치마로 봤다든지) 몸통을 다리로 알고 뭉갠다.
PASS_HEM_BAND = (38, 56)


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


# ------------------------------------------------------- passing pose 합성 (#368)

def _skirt_hem(px: bytearray) -> tuple[int, float]:
    """치마 밑단의 y와 그 행의 가로 중심(= 엉덩이 축)을 찾는다.

    치마는 캔버스에서 가장 넓은 어두운 띠다. 그 아래는 전부 다리·구두이므로,
    밑단 한 줄만 알면 "몸통은 그대로, 다리만 옮긴다"를 좌표로 나눌 수 있다.
    """
    hem = -1
    hip = 0.0
    for y in range(CANVAS_H):
        dark = [x for x in range(CANVAS_W)
                if px[(y * CANVAS_W + x) * 4 + 3]
                and px[(y * CANVAS_W + x) * 4] + px[(y * CANVAS_W + x) * 4 + 1]
                + px[(y * CANVAS_W + x) * 4 + 2] < 220]
        if len(dark) >= PASS_SKIRT_RUN:
            hem = y
            hip = (min(dark) + max(dark)) / 2.0
    if not PASS_HEM_BAND[0] <= hem <= PASS_HEM_BAND[1]:
        raise SystemExit(f"치마 밑단을 y={hem}에서 찾았다 — {PASS_HEM_BAND} 밖이라 "
                         "다리와 몸통을 가를 수 없다. PASS_SKIRT_RUN을 확인할 것")
    return hem, hip


def passing_pose(px: bytearray) -> bytearray:
    """다리를 엉덩이 축으로 모아 "몸 아래를 지나는" 컷을 만든다(#368).

    원본 아트가 두 포즈뿐이라 빠진 박자를 그림 없이 채워야 한다. 몸통·팔·머리는
    손대지 않고 치마 밑단 아래만 옮기므로 프레임이 바뀔 때 상체가 흔들리지 않는다.

    **행마다 정수로 밀고, 배율을 걸지 않는다.** 가로로 눌러 줄이면 다리가 그만큼
    얇아져 젓가락이 되고, 회전시키면 접지한 다리가 캔버스 바닥을 뚫는다(발이 바닥에
    닿아 있으므로 세우면 몸이 떠올라야 하는데 머리 위에 1px밖에 없다). 행을 통째로
    미는 것은 다리 두께를 그대로 두고 기울기만 세우는 방법이다.

    한 행에서 엉덩이 축의 좌/우를 각각 한 다리로 보고, 그 행의 중심을 축 쪽으로
    (1 - PASS_CLOSE)만큼 당긴다. 축에서 멀리 나간 행이 더 많이 당겨지므로 다리가
    통째로 세워진다.
    """
    hem, hip = _skirt_hem(px)
    out = bytearray(px)
    for y in range(hem + 1, CANVAS_H):
        for x in range(CANVAS_W):
            j = (y * CANVAS_W + x) * 4
            out[j:j + 4] = b"\0\0\0\0"

    for y in range(hem + 1, CANVAS_H):
        for near_side in (True, False):
            xs = [x for x in range(CANVAS_W)
                  if px[(y * CANVAS_W + x) * 4 + 3]
                  and ((x < hip) if near_side else (x >= hip))]
            if not xs:
                continue
            center = (min(xs) + max(xs)) / 2.0
            shift = int(round((hip - center) * (1.0 - PASS_CLOSE)))
            for x in xs:
                nx = x + shift
                if 0 <= nx < CANVAS_W:
                    j = (y * CANVAS_W + x) * 4
                    k = (y * CANVAS_W + nx) * 4
                    out[k:k + 4] = px[j:j + 4]

    # 발끝은 바닥선에 그대로 있어야 한다 — 세로로 손대지 않았으므로 어긋나면
    # 다리가 캔버스 밖으로 밀려 나갔다는 뜻이다(발이 공중에 뜬 컷이 나온다).
    if _floor_row(out) != _floor_row(px):
        raise SystemExit(f"passing pose의 발끝이 y={_floor_row(out)}로 옮겨졌다 "
                         f"(원본 {_floor_row(px)}) — PASS_CLOSE를 확인할 것")
    return out


def _floor_row(px: bytearray) -> int:
    """칠해진 가장 아래 행 = 발끝이 닿는 바닥선."""
    for y in range(CANVAS_H - 1, -1, -1):
        if any(px[(y * CANVAS_W + x) * 4 + 3] for x in range(CANVAS_W)):
            return y
    return -1


def _bake(name: str, width: int, height: int, rgba: bytearray, mask: bytearray,
          box: tuple[int, int, int, int], xlim: tuple[int, int], anchor: float,
          scale: float) -> bytearray:
    """한 포즈를 잘라 CANVAS_W x CANVAS_H PNG로 굽고, 그 픽셀을 돌려준다."""
    _check_fits(name, box, anchor, scale)
    px = shrink(width, height, rgba, mask, xlim, anchor, box[3], scale)
    _write(name, px, f"원본 {box[1] - box[0] + 1}x{box[3] - box[2] + 1}  "
                     f"배율 1px = 원본 {scale:.2f}px")
    return px


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
    run_box = bbox(width, height, mask, *RUN_X)
    idle_box = bbox(width, height, mask, *IDLE_X)

    # 두 포즈는 같은 축척으로 그려져 있다(키 1059 vs 1067). 대기 포즈를
    # 기준으로 배율을 잡고 달리기에도 그대로 써야 이동 중 몸집이 안 변한다.
    scale = (idle_box[3] - idle_box[2] + 1) / float(CANVAS_H)

    _bake("player_idle", width, height, rgba, mask, idle_box, IDLE_X, IDLE_ANCHOR_X, scale)
    _bake("player_run", width, height, rgba, mask, run_box, RUN_X, RUN_ANCHOR_X, scale)

    # 걷기 프레임(#365)은 **원본이 달라 축척도 다르다** — 새 원본은 인물이 캔버스를
    # 덜 채운다(키 604 / 953). 원본 bbox 비율로 줄이면 걷기 프레임만 작아지므로,
    # 달리기 포즈가 캔버스에서 차지한 높이(71.5px)에 맞춰 배율을 거꾸로 계산한다.
    # 그러면 세 이동 프레임의 머리 위·발끝이 캔버스에서 같은 자리에 온다.
    run_canvas_h = (run_box[3] - run_box[2] + 1) / scale

    wwidth, wheight, wrgba = read_png(SRC_WALK)
    wmask = background_mask(wwidth, wheight, wrgba)
    boxes = [bbox(wwidth, wheight, wmask, *xlim) for _, xlim, _ in WALK_POSES]
    heights = [b[3] - b[2] + 1 for b in boxes]
    if max(heights) - min(heights) > WALK_HEIGHT_TOLERANCE:
        raise SystemExit(f"걷기 포즈의 키가 다르다 {heights} — 배율이 프레임마다 달라져 "
                         "몸집이 커졌다 작아진다. 원본을 확인할 것")
    walk_scale = heights[0] / run_canvas_h

    baked = {}
    for (name, xlim, wanchor), box in zip(WALK_POSES, boxes):
        baked[name] = _bake(name, wwidth, wheight, wrgba, wmask, box, xlim,
                            wanchor, walk_scale)

    # 다리가 몸 아래를 지나는 컷(#368). 원본 아트가 없어 walk_1에서 합성한다 —
    # 활보 컷의 다리를 모으면 되므로 몸통을 다시 자를 필요가 없다.
    _write("player_walk_pass", passing_pose(baked["player_walk_1"]),
           f"player_walk_1에서 합성  다리 모음 {PASS_CLOSE}")


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
