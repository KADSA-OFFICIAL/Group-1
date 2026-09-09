#!/usr/bin/env python3
"""플레이어(이설) 스프라이트 생성기.

원본 넷을 굽는다(#582에서 커밋, #585에서 배선). **넷 다 시트다** — 한 파일에 포즈가
여럿 들어 있고, 행 밴드 + 연결 요소로 자동으로 가른다(`frames_of`).

    player_run_design.png         측면 달리기 12장 (2행 6열, 알파 배경)
    player_run_front_design.png   정면 달리기  4장 (1행,    알파 배경)
    player_run_back_design.png    뒷모습 달리기 8장 (2행 4열, **체크무늬 배경**)
    player_idle_breath_design.png 대기 호흡    4장 (1행,    **체크무늬 배경**)

구워 내는 것은 스물한 장이다.

    assets/sprites/player_idle.png       대기(정면, 호흡 시트의 1번 = 중립 서기)
    assets/sprites/player_walk_1~12.png  측면(시트 순서 그대로)
    assets/sprites/player_front_1~4.png  정면(1, 2, mirror(1), mirror(2))
    assets/sprites/player_back_1~4.png   뒷모습(7, 2, mirror(7), mirror(2))

**시트 좌표를 손으로 적지 않는다.** 예전에는 `_WALK_COLS`/`_WALK_ROWS`/`_WALK_HEADS`에
열두 포즈의 x·y 창과 머리 중심을 적어 뒀는데, 시트가 넷이 되면 손계측 숫자가 스물여덟
개로 늘고 원본을 갈아 끼울 때마다 다시 재야 한다. 지금은 배경 마스크에서 행 밴드를
찾고 그 안을 연결 요소로 갈라 프레임을 낸다 — 원본을 바꿔도 코드를 안 고친다.

**정면·뒷모습은 뒤 절반을 좌우 반전으로 만든다.** 원본의 뒤 절반이 미러가 아니라
복제라서다(실측: 정면 1↔3 실루엣 거리 0.062, 이웃 프레임 거리 0.154~0.175 — 사실상
같은 그림이다. 뒷모습도 3↔7 0.098 · 4↔8 0.116). 그대로 쓰면 한쪽 다리만 까딱거린다.
`FRONT_PICK`/`BACK_PICK`이 쓸 두 장을 고르고 나머지 둘은 뒤집어 채운다 — 반전 검사
결과 0.000, 정의상 완전 대칭이다. 이것은 #378에서 걷어낸 "포즈 합성"이 아니다:
다리를 모으거나 엉덩이를 올리는 변형이 아니라 그림 전체를 뒤집는 것뿐이라 윤곽이
거칠어질 자리가 없다. 대가는 넥타이·앞머리 가르마가 반대로 가는 것인데, 게임 크기
(키 72px)에서 넥타이는 4px짜리 점이고 뒷모습은 얼굴도 넥타이도 안 보인다. 측면도
이미 `flip_h`로 뒤집어 쓴다.

**배율은 키로 맞춘다 — 머리로 맞추지 않는다.** 네 시트를 이미지 생성기가 따로 뽑아서
서로 비례가 안 맞는다(머리/키: 대기 0.328 · 뒷모습 0.326 · 정면 0.368 · 측면 0.377).
두 무리로 14% 갈리므로 하나의 규칙으로 전부 맞출 수 없다 — 키를 맞추면 방향에 따라
머리가 14%(70px 기준 약 3px) 달라지고, 머리를 맞추면 **키가 10px** 달라진다. 탑다운
화면에서 방향을 바꿀 때 인물이 커졌다 작아지는 쪽이 훨씬 눈에 띄고, 기존 코드도
`_bake_pair()`가 키를 맞추고 있었다. 그래서 **세트마다 가장 큰 프레임의 키를
`FIGURE_H`에 맞춘다** — 평균이 아니라 최대인 이유는 어떤 프레임도 캔버스를 넘지 않게
하기 위해서다(평균 기준이면 측면 최대 프레임이 75.4px까지 올라가 여유가 0.6px뿐이다).
상하 흔들림은 최대 프레임 아래로 자연히 남는다.

**원본을 그대로 줄인다(좌우 반전 외에 합성은 없다).** #372·#375에는 한두 장뿐인
원본에서 다리를 모으고 팔을 당기는 코드 합성이 있었는데 세 번 다 "다리 윤곽이 거칠다"로
끝났다. 지금 원본은 사이클을 여러 장으로 나눠 그려서 그 문제 자체가 없다.

원본이 있는 폴더에는 `.gdignore`를 뒀다 — 1536x1024 원본까지 Godot이 임포트해 빌드에
실을 이유가 없다(이 도구는 파일시스템에서 직접 읽는다).

gen_sfx.py / gen_music.py와 같은 규약: **표준 라이브러리만 쓰고 결정론적**이다.
같은 원본에 같은 상수면 출력 바이트도 같으므로 재실행해도 diff가 나오지 않는다.

주의: 배경을 "어두운 색"으로만 판별하면 안 된다 — 머리카락·치마·구두도 거의 검다.
그래서 이미지 테두리에서 시작하는 flood fill로 *바깥과 이어진* 곳만 배경으로 본다.
"""

from __future__ import annotations

import pathlib
import struct
import sys
import zlib
from collections import deque

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "assets" / "sprites" / "source"
OUT_DIR = ROOT / "assets" / "sprites"

# 원본 넷(#582). 전부 시트라 `frames_of`가 프레임을 자동으로 가른다.
SRC_RUN = SRC_DIR / "player_run_design.png"
SRC_FRONT = SRC_DIR / "player_run_front_design.png"
SRC_BACK = SRC_DIR / "player_run_back_design.png"
SRC_IDLE = SRC_DIR / "player_idle_breath_design.png"

# 출력 캔버스. 스물한 장이 같은 크기여야 Sprite2D 오프셋(SPRITE_OFFSET_Y)을 하나로 쓸 수
# 있다. 폭은 가장 벌어진 포즈가 잘리지 않을 만큼 필요하다(`_check_fits`가 검사한다).
CANVAS_W = 74
# 인물의 키. 배율의 기준이고 **화면에서 보이는 크기를 정하는 값**이다.
# 이 값을 바꾸면 `CLAUDE.md`의 `WALL_FACE`(34)를 다시 재야 한다 — 그 값이 스프라이트가
# 충돌 캡슐 위로 뻗는 높이에서 나왔다.
FIGURE_H = 72
# 머리 위에 비워 두는 줄 수. 세트마다 **가장 큰 프레임**을 FIGURE_H에 맞추므로 다른
# 프레임은 그보다 낮게 들어온다 — 그래도 부동소수 여유는 남겨 둔다.
# **짝수로 둘 것** — 캔버스 높이가 홀수면 Sprite2D 중앙 정렬이 반 칸에 걸려
# SPRITE_OFFSET_Y가 .5로 떨어지고, Nearest 필터에서 스프라이트가 떨린다.
BOB_HEADROOM = 4
CANVAS_H = FIGURE_H + BOB_HEADROOM

# 배경으로 볼 밝기 상한(R+G+B). 머리카락은 (26,26,26)=78이라 걸리지 않는다.
# **불투명 검정 배경 원본에만 쓴다** — 아래 알파·체크무늬 규칙 참고.
BG_LUMA = 40
# 알파가 이보다 낮으면 투명으로 본다. 그리고 투명한 칸이 이 비율을 넘으면
# **알파 배경 원본**으로 보고 밝기 규칙을 쓰지 않는다(#519).
ALPHA_BG = 8
ALPHA_BG_RATIO = 0.5
# **체크무늬/흰 배경**(#582). 뒷모습·대기 원본은 알파가 없고 투명을 나타내는 체크무늬가
# 픽셀로 구워져 있다(254/239 회색 격자). 밝기만으로는 못 자른다 — 어두운 칸(239,
# 합 717)이 밝은 칸(254, 합 762)과 100 넘게 벌어져서, 한 문턱으로는 둘 중 하나를 놓친다.
# 대신 **무채색이고 밝은 것**을 본다: 체크무늬는 R=G=B인데 인물은 그렇지 않다
# (카디건 (171,152,145) 채도 26, 피부 (250,222,212) 채도 38).
# 흰 칼라 (255,255,255)는 무채색이지만 인물 안쪽이라 테두리 flood fill이 닿지 않는다.
# **문턱을 222로 잡으면 안 된다** — 경계의 222짜리 픽셀 한 줄이 남아 인물 둘레에
# 흰 후광이 생긴다(실측).
BRIGHT_BG_SAT = 20
BRIGHT_BG_MIN = 110

# 한 칸의 절반 이상이 캐릭터일 때만 칠한다 — 실루엣이 흐려지지 않게.
COVER = 0.5

# ── 시트 가르기 ─────────────────────────────────────────────
# 인물이 있는 행 띠로 볼 최소 높이. 이보다 낮은 띠는 (있다면) 숫자 라벨 따위다.
FRAME_ROW_MIN_H = 100
# 한 프레임으로 셀 최소 넓이(px). 워터마크·부스러기를 거른다.
FRAME_MIN_PX = 2000
# 한 세트 안에서 프레임 키가 이 비율 넘게 벌어지면 멈춘다. 배율이 세트마다 하나뿐이라
# 어긋나면 프레임이 넘어갈 때 인물이 커졌다 작아진다. 실측 최대는 대기의 4.9%다.
HEIGHT_SPREAD_MAX = 0.15

# 가로 기준점 = **머리 중심**(실루엣 위쪽 이 비율의 가운데). 전체 bbox 중심을 쓰면
# 뻗은 팔다리 때문에 몸이 좌우로 쏠린다 — 달리는 동안 팔다리는 움직이지만 머리는
# 몸통 위에 그대로 있다.
HEAD_ROWS = 0.10

# 정면·뒷모습에서 **실제로 쓸 프레임**(1부터). 나머지는 복제라 버리고 좌우 반전으로
# 채운다. 뒷모습의 7·2는 후보 여섯 조합 중 이웃 프레임 거리 평균이 가장 큰 조합이다
# (0.274 — 1+2는 0.245, 3+2는 0.255, 3+6은 0.214, 5+2는 0.223).
FRONT_PICK = (1, 2)
BACK_PICK = (7, 2)


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
    """배경(1)을 표시한다. **원본에 따라 규칙이 다르다.**

    - **알파 배경**(측면·정면 원본): 투명한 칸이 곧 배경이다. flood fill을 쓰면
      안 된다 — 원본에 따라 머리가 순수 검정(0,0,0)이고 투명 배경도 RGB가 0이라,
      "테두리에서 이어지는 어두운 픽셀"에 **머리카락이 통째로 걸려 지워졌다**(#519).
    - **밝은 배경**(뒷모습·대기 원본의 체크무늬, 그리고 흰 배경): 테두리에서 이어지는
      **무채색이고 밝은** 픽셀을 배경으로 본다. 밝기만으로 자르면 체크무늬의 어두운
      칸(합 717)과 밝은 칸(합 762) 중 하나를 놓치고, 피부(합 684)까지 위험해진다.
      채도를 같이 보면 인물이 안전하다 — 카디건 채도 26, 피부 38, 배경 0~2.
    - **불투명 검정 배경**(옛 원본): 테두리에서 이어지는 **어두운** 픽셀만 배경으로
      본다. 인물 안의 어두운 부분(머리카락 (26,26,26)=78)은 테두리와 이어지지 않아
      살아남는다.

    어느 쪽인지는 **스스로 가린다** — 투명한 칸의 비율로 알파 배경을 가리고, 아니면
    **네 모서리**를 보고 밝은/검은 배경을 가린다. 손으로 지정하는 인자를 두면 원본을
    갈아 끼울 때 같이 고쳐야 하는 자리가 하나 늘어난다.
    """
    transparent = sum(1 for i in range(width * height) if rgba[i * 4 + 3] < ALPHA_BG)
    if transparent > width * height * ALPHA_BG_RATIO:
        return bytearray(1 if rgba[i * 4 + 3] < ALPHA_BG else 0
                         for i in range(width * height))

    mask = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def bright(j: int) -> bool:
        """무채색이고 밝은가 — 체크무늬·흰 배경의 조건."""
        r, g, b = rgba[j], rgba[j + 1], rgba[j + 2]
        return max(r, g, b) - min(r, g, b) <= BRIGHT_BG_SAT and min(r, g, b) >= BRIGHT_BG_MIN

    # 네 모서리를 보고 정한다 — 한 점만 보면 그 자리에 인물이 걸친 원본에서 어긋난다.
    corners = [0, (width - 1) * 4, (height - 1) * width * 4,
               ((height - 1) * width + width - 1) * 4]
    bright_bg = all(bright(c) for c in corners)

    def push(x: int, y: int) -> None:
        i = y * width + x
        if mask[i]:
            return
        j = i * 4
        if not bright(j) if bright_bg else rgba[j] + rgba[j + 1] + rgba[j + 2] > BG_LUMA:
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


def frames_of(width: int, height: int, bg: bytearray) -> list[tuple[tuple[int, int, int, int], list[int]]]:
    """시트를 프레임으로 가른다 — (경계상자, 그 프레임의 픽셀 인덱스).

    **행 밴드를 먼저 찾고 그 안을 연결 요소로 가른다.** 열 투영만 쓰면 안 된다 —
    앞으로 뻗은 발이 옆 프레임의 x 구간까지 들어와 두 인물이 한 덩어리로 뭉친다
    (측면 원본의 1·2번이 실제로 그랬다). 세로로는 행 밴드가, 가로로는 연결 요소가
    가르므로 붙어 보이는 프레임도 정확히 갈린다.

    프레임 순서는 **읽는 순서**다 — 행 밴드 위에서 아래로, 각 밴드 안에서 왼쪽부터.
    시트의 1번이 곧 목록의 첫 번째다.
    """
    bands: list[tuple[int, int]] = []
    start = None
    for y in range(height):
        base = y * width
        filled = False
        for x in range(width):
            if not bg[base + x]:
                filled = True
                break
        if filled and start is None:
            start = y
        elif not filled and start is not None:
            bands.append((start, y - 1))
            start = None
    if start is not None:
        bands.append((start, height - 1))
    bands = [b for b in bands if b[1] - b[0] + 1 >= FRAME_ROW_MIN_H]
    if not bands:
        raise SystemExit("시트에서 인물 행을 못 찾았다")

    out = []
    for y0, y1 in bands:
        seen = bytearray((y1 - y0 + 1) * width)
        found = []
        for y in range(y0, y1 + 1):
            for x in range(width):
                i = (y - y0) * width + x
                if seen[i] or bg[y * width + x]:
                    continue
                # 8-이웃 BFS. 4-이웃으로 세면 대각선으로만 붙은 획이 끊겨 한 인물이
                # 여러 덩어리로 갈린다.
                pixels = []
                left = right = x
                top = bottom = y
                seen[i] = 1
                queue: deque[tuple[int, int]] = deque([(x, y)])
                while queue:
                    cx, cy = queue.popleft()
                    pixels.append(cy * width + cx)
                    if cx < left:
                        left = cx
                    if cx > right:
                        right = cx
                    if cy < top:
                        top = cy
                    if cy > bottom:
                        bottom = cy
                    for dy in (-1, 0, 1):
                        ny = cy + dy
                        if not y0 <= ny <= y1:
                            continue
                        for dx in (-1, 0, 1):
                            nx = cx + dx
                            if not 0 <= nx < width:
                                continue
                            k = (ny - y0) * width + nx
                            if seen[k] or bg[ny * width + nx]:
                                continue
                            seen[k] = 1
                            queue.append((nx, ny))
                if len(pixels) >= FRAME_MIN_PX:
                    found.append(((left, right, top, bottom), pixels))
        found.sort(key=lambda f: f[0][0])
        out.extend(found)
    return out


def mirror(px: bytearray) -> bytearray:
    """구운 캔버스를 좌우로 뒤집는다.

    `shrink()`가 머리 중심을 캔버스 정중앙(CANVAS_W / 2)에 두므로, 캔버스를 통째로
    뒤집어도 기준점이 그대로다 — 뒤집은 장과 원래 장이 겹칠 때 몸이 좌우로 튀지 않는다.
    """
    out = bytearray(len(px))
    for y in range(CANVAS_H):
        row = y * CANVAS_W * 4
        for x in range(CANVAS_W):
            j = row + x * 4
            k = row + (CANVAS_W - 1 - x) * 4
            out[k:k + 4] = px[j:j + 4]
    return out



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


def head_anchor(width: int, mask: bytearray, box: tuple[int, int, int, int],
                rows_ratio: float) -> float:
    """실루엣 위쪽 `rows_ratio`만큼의 가로 중심 = **머리 중심**(#519).

    측면 12장은 시트 좌표를 손으로 적어 뒀지만(`_WALK_HEADS`), 뒷모습은 원본이
    한 장에 한 포즈라 그림에서 바로 잰다 — 손으로 적은 숫자가 원본과 어긋날 자리를
    없앤다. 기준을 머리로 잡는 이유는 측면과 같다: 걷는 동안 팔다리는 움직이지만
    머리는 몸통 위에 그대로 있다.
    """
    rows = max(1, int((box[3] - box[2] + 1) * rows_ratio))
    left, right = box[1], box[0]
    for y in range(box[2], box[2] + rows):
        row = y * width
        for x in range(box[0], box[1] + 1):
            if not mask[row + x]:
                left = min(left, x)
                right = max(right, x)
    if right < left:
        raise SystemExit("머리 중심을 잡을 수 없다 — 실루엣 위쪽이 비어 있다")
    return (left + right) / 2.0


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
    # 발끝은 캔버스 바닥에 붙어야 한다. 열일곱 장이 같은 오프셋(SPRITE_OFFSET_Y) 하나를
    # 쓰므로, 어긋나면 프레임이 바뀔 때 인물이 위아래로 튄다.
    if not any(px[((CANVAS_H - 1) * CANVAS_W + x) * 4 + 3] for x in range(CANVAS_W)):
        raise SystemExit(f"{name}: 발끝이 캔버스 바닥(y={CANVAS_H - 1})에 닿지 않는다 "
                         "— 잘라낼 위치나 배율을 확인할 것")
    write_png(OUT_DIR / f"{name}.png", CANVAS_W, CANVAS_H, px)
    print(f"{name}.png  {CANVAS_W}x{CANVAS_H}  칠한 칸 {opaque}  {note}")


def _load(path: pathlib.Path, label: str) -> dict:
    """시트 하나를 읽어 프레임으로 가르고 배율까지 정한다."""
    width, height, rgba = read_png(path)
    bg = background_mask(width, height, rgba)
    frames = frames_of(width, height, bg)
    heights = [b[3] - b[2] + 1 for b, _ in frames]
    spread = (max(heights) - min(heights)) / float(max(heights))
    if spread > HEIGHT_SPREAD_MAX:
        raise SystemExit(f"{label}: 프레임 키가 너무 다르다 {heights} — 배율이 세트마다 "
                         "하나뿐이라 프레임이 넘어갈 때 인물이 커졌다 작아진다")
    scale = max(heights) / float(FIGURE_H)
    print(f"{label}: {len(frames)}장  키 {min(heights)}~{max(heights)}(편차 {spread * 100:.1f}%)  "
          f"배율 1px = 원본 {scale:.2f}px")
    return {"label": label, "width": width, "height": height, "rgba": rgba,
            "frames": frames, "scale": scale}


def _bake(sheet: dict, number: int, name: str) -> bytearray:
    """시트의 `number`번째(1부터) 프레임을 캔버스에 굽는다."""
    frames = sheet["frames"]
    if not 1 <= number <= len(frames):
        raise SystemExit(f"{sheet['label']}: {number}번 프레임이 없다(총 {len(frames)}장)")
    box, pixels = frames[number - 1]
    width, height = sheet["width"], sheet["height"]
    # 이 프레임만 남긴 마스크. 옆 프레임의 뻗은 팔다리가 x 구간을 침범해도 섞이지 않는다.
    mask = bytearray(b"\x01" * (width * height))
    for i in pixels:
        mask[i] = 0
    anchor = head_anchor(width, mask, box, HEAD_ROWS)
    return _cut(name, width, height, sheet["rgba"], mask, box, (0, width - 1),
                anchor, sheet["scale"])


def build_all() -> None:
    for src in (SRC_RUN, SRC_FRONT, SRC_BACK, SRC_IDLE):
        if not src.exists():
            raise SystemExit(f"원본 아트가 없다: {src}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 대기는 호흡 시트의 1번(중립 서기)만 쓴다. 나머지 셋은 시간 기반 타이머가
    # 들어와야 의미가 있어 컨트롤러 이슈로 미뤘다.
    idle = _load(SRC_IDLE, "대기")
    _write("player_idle", _bake(idle, 1, "player_idle"), "대기(정면) — 호흡 시트 1번")

    side = _load(SRC_RUN, "측면")
    for n in range(1, len(side["frames"]) + 1):
        name = f"player_walk_{n}"
        _write(name, _bake(side, n, name), f"측면 {n}/{len(side['frames'])}")

    _bake_mirrored(_load(SRC_FRONT, "정면"), "player_front", FRONT_PICK)
    _bake_mirrored(_load(SRC_BACK, "뒷모습"), "player_back", BACK_PICK)


def _bake_mirrored(sheet: dict, prefix: str, pick: tuple[int, int]) -> None:
    """한 방향의 네 장을 굽는다 — 고른 두 장과 그 좌우 반전.

    원본의 뒤 절반이 미러가 아니라 복제라 그대로 쓰면 한쪽 다리만 까딱거린다.
    뒤집어 만들면 다리 교대가 **정의상** 정확하다(반전 검사 0.000).
    """
    baked = []
    for i, number in enumerate(pick, start=1):
        name = f"{prefix}_{i}"
        px = _bake(sheet, number, name)
        baked.append(px)
        _write(name, px, f"{sheet['label']} — 원본 {number}번")
    for i, px in enumerate(baked, start=len(pick) + 1):
        name = f"{prefix}_{i}"
        _write(name, mirror(px), f"{sheet['label']} — {i - len(pick)}번의 좌우 반전")



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
