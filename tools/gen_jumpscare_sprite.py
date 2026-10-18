#!/usr/bin/env python3
"""점프스케어 얼굴 생성기 (#662).

수위 정면 원본(`assets/sprites/source/janitor/janitor_down_0.png`)에서 머리와
어깨만 잘라 점프스케어용 도트 그림 한 장을 굽는다.

    assets/sprites/janitor_face.png   CROP_W x CROP_H (원본의 논리 도트 그대로)

게임에서는 `scenes/ui/jumpscare.tscn`이 이 그림을 Nearest로 화면 높이까지
키운다 — 논리 한 도트가 화면에서 16px 남짓이 된다.

gen_janitor_sprites.py와 같은 규약: **표준 라이브러리만 쓰고 결정론적**이다.
PNG 입출력과 배경 제거(테두리에서 이어진 흰색만 지운다)는 그쪽 것을 그대로 쓴다.

원본에 대해 알아 둘 것(실측):
  * 512x512에 **4px 블록 도트 아트**(논리 128x128)이고 블록이 전부 단색이다
    (블록 안에서 색이 다른 픽셀 0개). 그래서 축소에 최빈색을 낼 필요 없이
    **블록 한가운데 한 점**을 읽으면 논리 도트가 정확히 나온다.
  * 머리는 논리 y 0~33, 어깨가 그 아래로 퍼진다. y 50부터 왼팔 완장(노랑)과
    가슴 명찰(흰색)이 들어와서 그 위에서 자른다.

손댄 것 두 가지 — 원본 그대로는 겁나지 않았다:
  * **눈을 둘로 늘리고 빛나게 한다.** 원본은 모자 그늘 속에 붉은 점이 **하나**
    (논리 1도트)뿐이라 화면을 채워도 눈으로 안 읽힌다. 그 점을 찾아 머리
    중심선에 대해 반대쪽에 하나 더 찍고, 둘 다 `EYE_W`도트로 넓히고, 둘레
    그늘(거의 검정)에만 붉은 번짐을 깐다. 번짐이 모자 천이나 살에 번지면
    얼룩이 되므로 어두운 칸에만 칠한다.
  * **눈·이빨 말고는 어둡게 누른다**(`SHADE`). 원본은 밝은 낮 톤이라 화면을
    덮었을 때 무섭기보다 만화 같다. 눈과 입(이빨)은 그대로 두어 어둠 속에서
    그 둘만 떠오르게 한다.

재실행 안전장치: 이미 있는 출력과 픽셀이 같으면 파일을 건드리지 않는다.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_janitor_sprites import background_mask, read_png, write_png  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "sprites" / "source" / "janitor" / "janitor_down_0.png"
OUT = ROOT / "assets" / "sprites" / "janitor_face.png"

BLOCK = 4            # 원본 한 도트의 크기(px)
LOGICAL = 128        # 원본의 논리 해상도

# 자를 구역(논리 도트). 머리 실루엣(x 39~92)에 좌우 여백을 조금 둔다.
CROP_X0, CROP_X1 = 36, 96
CROP_Y0, CROP_Y1 = 0, 50
CROP_W = CROP_X1 - CROP_X0
CROP_H = CROP_Y1 - CROP_Y0

# 머리 중심선을 재는 줄(논리 y). 모자 몸통이라 좌우가 대칭이다 — 귀나 어깨가
# 걸리는 줄에서 재면 손전등 쪽으로 기운다.
CENTER_ROW = 10

# 원본의 붉은 눈을 찾는 조건과 범위(모자 그늘 띠).
EYE_SEARCH_Y = (20, 32)
EYE_MIN_R = 120
EYE_MAX_G = 90

EYE_W = 2                       # 눈 한 짝의 폭(논리 도트)
EYE_CORE = (255, 236, 214)      # 눈 한가운데 — 거의 흰 빛
EYE_RED = (255, 44, 32)
EYE_GLOW = (110, 8, 8)          # 둘레 번짐. 어두운 칸에만 깐다.
GLOW_DARK_MAX = 48              # 이보다 밝은 칸(모자 천·살)에는 번짐을 안 깐다.

# 눈·이빨 밖의 색에 곱하는 값(/256). 푸른 쪽을 덜 눌러 차갑게 가라앉힌다.
SHADE = (118, 112, 140)
# 이빨(밝은 크림색)은 누르지 않는다 — 판정 문턱.
TEETH_MIN = 200


def bake() -> tuple[int, int, bytearray]:
    if not SRC.exists():
        raise SystemExit(f"원본이 없다: {SRC}")
    w, h, rgba = read_png(SRC)
    if (w, h) != (LOGICAL * BLOCK, LOGICAL * BLOCK):
        raise SystemExit(f"원본 크기가 바뀌었다 ({w}x{h}) — 블록 가정을 다시 잴 것")
    mask = background_mask(w, h, rgba)

    def src(lx: int, ly: int) -> tuple[int, int, int] | None:
        sx, sy = lx * BLOCK + BLOCK // 2, ly * BLOCK + BLOCK // 2
        i = sy * w + sx
        if mask[i]:
            return None
        return rgba[i * 4], rgba[i * 4 + 1], rgba[i * 4 + 2]

    # 머리 중심선.
    xs = [lx for lx in range(LOGICAL) if src(lx, CENTER_ROW) is not None]
    if not xs:
        raise SystemExit(f"y={CENTER_ROW}에서 머리를 못 찾았다")
    mirror_sum = xs[0] + xs[-1]

    # 원본의 붉은 눈.
    eyes_src = [
        (lx, ly)
        for ly in range(*EYE_SEARCH_Y)
        for lx in range(CROP_X0, CROP_X1)
        if (c := src(lx, ly)) is not None and c[0] >= EYE_MIN_R and c[1] <= EYE_MAX_G
    ]
    if len(eyes_src) != 1:
        raise SystemExit(f"붉은 눈이 한 점이어야 한다 (찾은 것 {eyes_src})")
    ex, ey = eyes_src[0]
    other = mirror_sum - ex
    # 두 짝을 같은 방향으로 넓히면 중심선에서 어긋나므로 바깥쪽으로 넓힌다.
    right, left = (ex, other) if ex > other else (other, ex)
    eye_cells = {(right + k, ey) for k in range(EYE_W)} | {(left - k, ey) for k in range(EYE_W)}
    core_cells = {(right, ey), (left, ey)}

    out = bytearray(CROP_W * CROP_H * 4)
    for ly in range(CROP_Y0, CROP_Y1):
        for lx in range(CROP_X0, CROP_X1):
            c = src(lx, ly)
            if c is None:
                continue
            if (lx, ly) in core_cells:
                r, g, b = EYE_CORE
            elif (lx, ly) in eye_cells:
                r, g, b = EYE_RED
            elif min(c) >= TEETH_MIN:
                r, g, b = c
            else:
                near_eye = any(abs(lx - x) <= 1 and abs(ly - y) <= 1 for x, y in eye_cells)
                if near_eye and max(c) <= GLOW_DARK_MAX:
                    r, g, b = EYE_GLOW
                else:
                    r, g, b = (c[0] * SHADE[0] >> 8, c[1] * SHADE[1] >> 8, c[2] * SHADE[2] >> 8)
            j = ((ly - CROP_Y0) * CROP_W + (lx - CROP_X0)) * 4
            out[j:j + 4] = bytes((r, g, b, 255))
    return CROP_W, CROP_H, out


def check(width: int, height: int, img: bytearray) -> None:
    filled = sum(1 for i in range(width * height) if img[i * 4 + 3])
    if filled * 2 < width * height:
        raise SystemExit(f"얼굴이 그림의 절반도 안 찬다 ({filled}/{width * height})")
    red = sum(1 for i in range(width * height)
              if (img[i * 4], img[i * 4 + 1], img[i * 4 + 2]) == EYE_RED)
    if red != 2 * (EYE_W - 1):
        raise SystemExit(f"빛나는 눈 칸 수가 맞지 않는다 ({red})")
    # 바닥 줄은 어깨로 꽉 차야 한다 — 화면 아래로 잘려 나가는 그림이라 떠 있으면 안 된다.
    bottom = sum(1 for x in range(width) if img[((height - 1) * width + x) * 4 + 3])
    if bottom * 4 < width * 3:
        raise SystemExit(f"맨 아래 줄이 어깨로 차지 않는다 ({bottom}/{width})")


def main() -> int:
    print(f"점프스케어 얼굴 ({CROP_W}x{CROP_H})")
    width, height, img = bake()
    check(width, height, img)

    if OUT.exists():
        old_w, old_h, old = read_png(OUT)
        if (old_w, old_h) == (width, height) and old == img:
            print(f"{OUT.relative_to(ROOT)} 그대로 (픽셀 동일)")
            return 0
    write_png(OUT, width, height, img)
    print(f"{OUT.relative_to(ROOT)} 씀")
    return 0


if __name__ == "__main__":
    sys.exit(main())
