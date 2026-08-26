#!/usr/bin/env python3
"""단서 노트 스프라이트 생성기 (#390).

원본 아트 `assets/sprites/source/note_design.png`(투명 배경 위 도트 노트)에서
게임용 스프라이트 한 장을 굽는다.

    assets/sprites/note.png   (긴 변 MAX_SIDE, 짧은 변은 원본 비율)

`gen_key_sprite.py`(#333)와 같은 규약이다 — **표준 라이브러리만 쓰고
결정론적**이고, 정수 연산만 써서 부동소수 오차로 결과가 흔들리지 않는다.
PNG 입출력과 칸 굽기는 그 스크립트에서 그대로 가져다 쓴다. 원본은 상위
`source/`의 `.gdignore` 아래라 Godot이 임포트하지 않는다.

열쇠 생성기와 다른 점 둘 — **둘 다 원본이 다르기 때문이지 취향이 아니다**:

  * **배경을 알파로만 가른다.** 열쇠 원본은 불투명한 흰 배경이라 테두리
    flood fill로 "바깥과 이어진 흰색"만 지워야 했지만(몸통 하이라이트도
    거의 희다), 노트 원본은 배경이 이미 알파 0이다.
  * **구멍을 뚫지 않는다.** 열쇠의 `punch_holes()`는 윤곽선에 둘러싸인 넓은
    흰 덩어리를 배경으로 돌리는데, 노트는 **속장이 통째로 그 조건에 든다**
    (크림색 종이 면이 캔버스의 30%가 넘는다). 그대로 걸면 노트가 아니라
    테두리만 남은 액자가 된다.

축소는 평균이 아니라 **최빈색**이다(`gen_key_sprite.bake_cell`). 평균을 내면
원본에 없던 중간색이 생겨 도트 아트가 흐려진다.

재실행 안전장치: 이미 있는 출력과 픽셀이 같으면 파일을 건드리지 않는다.
"""
from __future__ import annotations

import pathlib
import sys

from gen_key_sprite import bake_cell, read_png, write_png

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "sprites" / "source" / "note_design.png"
OUT = ROOT / "assets" / "sprites" / "note.png"

# 긴 변의 도트 수 = 월드 픽셀 수(Sprite2D scale 1). 이 자리에 있던 폴리곤은
# 28x20이었고 열쇠는 24다.
#
# **32는 왼쪽 스프링 고리가 살아남는 최소 크기다.** 26에서는 고리 여섯 개가
# 전부 표지 색으로 뭉개져 공책이 아니라 식빵 한 조각으로 읽혔고, 남은 것은
# 속장 한가운데 점 두 개(원본의 'NOTE' 글씨)뿐이라 눈처럼 보였다. 32면 등에
# 어두운 띠와 금색 고리 두 점이 남아 묶인 쪽이 어디인지 보인다.
#
# 더 키우면(38~44) 고리도 글씨도 또렷해지지만 인물(74x76) 키의 절반이 되고
# 교실 책상(44x26)보다 커진다 — 책상 위에 놓인 공책이 아니게 된다.
MAX_SIDE = 32

# 이 미만이면 배경으로 본다. 원본 가장자리에 알파 1~7짜리 안티에일리어싱이
# 남아 있어 0으로 가르면 실루엣이 한 겹 부푼다.
ALPHA_MIN = 8

# 칸의 이 비율 이상이 그림일 때만 찍는다(열쇠와 같은 2/5). 노트는 기울어
# 놓여 있어 축과 어긋난 가장자리가 칸을 반쯤만 채운다 — 1/2로 자르면 모서리가
# 뭉텅뭉텅 잘려 나간다.
COVER_NUM = 2
COVER_DEN = 5


def background_mask(width: int, height: int, rgba: bytearray) -> bytearray:
    """투명한 픽셀만 배경(1)으로 표시한다."""
    return bytearray(1 if rgba[i * 4 + 3] < ALPHA_MIN else 0
                     for i in range(width * height))


def content_box(width: int, height: int, mask: bytearray) -> tuple[int, int, int, int]:
    """배경이 아닌 픽셀의 경계상자. 원본은 캔버스에 여백을 두고 있다."""
    x0, y0, x1, y1 = width, height, -1, -1
    for y in range(height):
        row = y * width
        for x in range(width):
            if mask[row + x]:
                continue
            x0, x1 = min(x0, x), max(x1, x)
            y0, y1 = min(y0, y), max(y1, y)
    if x1 < 0:
        raise SystemExit("배경을 지우고 나니 남는 픽셀이 없다 — ALPHA_MIN을 확인할 것")
    return x0, y0, x1 + 1, y1 + 1


def out_size(box_w: int, box_h: int) -> tuple[int, int]:
    """긴 변을 MAX_SIDE로 맞추고 짧은 변은 비율대로(정수 나눗셈, 최소 1)."""
    if box_w >= box_h:
        return MAX_SIDE, max(1, (box_h * MAX_SIDE + box_w // 2) // box_w)
    return max(1, (box_w * MAX_SIDE + box_h // 2) // box_h), MAX_SIDE


def bake() -> tuple[int, int, bytearray]:
    if not SRC.exists():
        raise SystemExit(f"원본이 없다: {SRC}")
    w, h, rgba = read_png(SRC)
    mask = background_mask(w, h, rgba)
    bx0, by0, bx1, by1 = content_box(w, h, mask)
    box_w, box_h = bx1 - bx0, by1 - by0
    ow, oh = out_size(box_w, box_h)
    print(f"  원본 {w}x{h} → 내용 {box_w}x{box_h} → 출력 {ow}x{oh}")

    img = bytearray(ow * oh * 4)
    for ty in range(oh):
        cy0 = by0 + ty * box_h // oh
        cy1 = by0 + (ty + 1) * box_h // oh
        for tx in range(ow):
            cx0 = bx0 + tx * box_w // ow
            cx1 = bx0 + (tx + 1) * box_w // ow
            packed = bake_cell(w, rgba, mask, cx0, cy0, cx1, cy1,
                               COVER_NUM, COVER_DEN)
            if packed < 0:
                continue
            j = (ty * ow + tx) * 4
            img[j] = (packed >> 16) & 0xFF
            img[j + 1] = (packed >> 8) & 0xFF
            img[j + 2] = packed & 0xFF
            img[j + 3] = 255
    return ow, oh, img


def check(ow: int, oh: int, img: bytearray) -> None:
    opaque = sum(1 for i in range(ow * oh) if img[i * 4 + 3] >= 8)
    if opaque == 0:
        raise SystemExit("빈 스프라이트다")
    if opaque == ow * oh:
        raise SystemExit("투명 픽셀이 하나도 없다 — 배경이 지워지지 않았다")

    # 속장이 구멍으로 뚫려 있으면 노트가 아니라 액자다. 그림 안쪽(불투명
    # 픽셀에 사방이 둘러싸인 자리)에 투명 픽셀이 있으면 잡는다.
    holes = 0
    for y in range(1, oh - 1):
        for x in range(1, ow - 1):
            i = y * ow + x
            if img[i * 4 + 3] >= 8:
                continue
            if all(img[((y + dy) * ow + (x + dx)) * 4 + 3] >= 8
                   for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                holes += 1
    if holes:
        raise SystemExit(f"그림 안쪽에 뚫린 자리가 {holes}칸 있다 — 배경 판정을 확인할 것")

    shades = len({tuple(img[i * 4:i * 4 + 3]) for i in range(ow * oh)
                  if img[i * 4 + 3] >= 8})
    if shades < 4:
        raise SystemExit(f"색이 {shades}가지뿐이다 — 축소가 너무 뭉갰다")

    print(f"  불투명 {opaque} / {ow * oh} 픽셀, 색 {shades}가지")
    for y in range(oh):
        row = "".join(".#"[img[(y * ow + x) * 4 + 3] >= 8] for x in range(ow))
        print(f"  {row}")


def main() -> int:
    print(f"노트 스프라이트 (긴 변 {MAX_SIDE})")
    ow, oh, img = bake()
    check(ow, oh, img)

    if OUT.exists():
        old_w, old_h, old = read_png(OUT)
        if (old_w, old_h) == (ow, oh) and old == img:
            print(f"{OUT.relative_to(ROOT)} 그대로 (픽셀 동일)")
            return 0

    write_png(OUT, ow, oh, bytes(img))
    print(f"{OUT.relative_to(ROOT)} {ow}x{oh} 씀")
    return 0


if __name__ == "__main__":
    sys.exit(main())
