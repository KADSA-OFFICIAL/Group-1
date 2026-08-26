#!/usr/bin/env python3
"""집기 단서 스프라이트 생성기 (#427).

원본 아트 두 장에서 게임용 스프라이트 두 장을 굽는다.

    assets/sprites/source/ink_can_design.png  →  assets/sprites/ink_can.png
    assets/sprites/source/beaker_design.png   →  assets/sprites/beaker.png

`gen_key_sprite.py`(#333)·`gen_note_sprite.py`(#390)와 같은 규약이다 —
**표준 라이브러리만 쓰고 결정론적**이고, 정수 연산만 써서 부동소수 오차로
결과가 흔들리지 않는다. PNG 입출력과 칸 굽기는 열쇠 생성기에서 그대로
가져다 쓴다. 원본은 상위 `source/`의 `.gdignore` 아래라 Godot이 임포트하지
않는다.

노트 생성기와 **같은** 점 둘 — 둘 다 원본이 같은 조건이기 때문이다:

  * **배경을 알파로만 가른다.** 두 원본 다 배경이 이미 알파 0이라, 열쇠의
    테두리 flood fill(`background_mask`)이 필요 없다.
  * **구멍을 뚫지 않는다.** `punch_holes()`를 걸면 잉크 웅덩이와 비커 유리면이
    통째로 '윤곽선에 둘러싸인 넓은 밝은 덩어리' 조건에 들어 배경으로 넘어간다.

노트 생성기와 **다른** 점 둘:

  * **알파 문턱이 높다**(ALPHA_MIN). 두 원본에는 광원 글로우가 반투명 픽셀로
    그려져 있다 — 잉크통 원본은 캔버스의 26%가 알파 1~7짜리 후광이고, A>=8과
    A>=224 사이에도 6.4%가 더 있다(노트는 그 차이가 0.4%뿐이다). 노트 값
    8을 그대로 쓰면 그 번짐이 실루엣으로 잡혀 물체보다 후광이 넓어진다.
  * **안쪽 뚫림을 몇 칸까지 허용한다**(HOLE_MAX). 노트 생성기는 하나라도
    있으면 멈추는데, 그 검사는 `punch_holes`가 속장을 날린 것을 잡으려고 둔
    것이다. 여기는 뚫는 단계가 없고, 남는 구멍은 **알파가 아니라 COVER
    문턱이 낸다** — 실측으로 알파를 8에서 160까지 옮겨도 구멍 수가 0~3에서
    거의 그대로였다(잉크통 1→2→0, 비커 3→3→2). 유리·물웅덩이 안쪽의
    한두 칸이라 눈에 띄지 않는다.

축소는 평균이 아니라 **최빈색**이다(`gen_key_sprite.bake_cell`). 평균을 내면
원본에 없던 중간색이 생겨 도트 아트가 흐려진다.

재실행 안전장치: 이미 있는 출력과 픽셀이 같으면 파일을 건드리지 않는다
(PNG 인코더 버전이 달라도 diff가 나지 않게).
"""
from __future__ import annotations

import pathlib
import sys

from gen_key_sprite import bake_cell, read_png, write_png

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "assets" / "sprites" / "source"
OUT_DIR = ROOT / "assets" / "sprites"

# 긴 변의 도트 수 = 월드 픽셀 수(Sprite2D scale 1). 예전 폴리곤은 잉크통
# 20x24, 비커 28x20이었고 노트는 32다.
#
# **48은 실측으로 정한 값이다.** 두 원본은 노트보다 훨씬 촘촘하게 그려져
# 있다 — 원본 안의 논리 도트 한 칸이 10px 남짓이라 그림의 실질 해상도가
# 가로 110~140칸이다. 32로 줄이면 그 4배를 뭉개는 셈이라, 최빈색이 칸마다
# 하이라이트와 그늘 사이를 왔다 갔다 해서 **물체가 아니라 소금·후추 잡음**이
# 됐다(뚜껑과 병이 붙고, 비커 조각이 웅덩이에 묻혔다). 40도 같았다. 48에서
# 잉크통은 뚜껑·병·웅덩이 세 덩어리가, 비커는 몸통·물·조각이 갈린다.
#
# 이 크기는 교실 책상(44x26)과 비슷하고 인물(74x76)의 2/3다. 노트(32)를
# 그보다 작게 잡은 이유("책상 위에 놓인 공책")가 여기서는 반대로 걸린다 —
# 둘 다 **바닥에 쏟아진 것**이라 웅덩이가 퍼진 만큼이 그림의 크기다. 단서
# 둘레는 `verify_props`의 `CLUE_CLEAR`(76)가 비워 두므로 집기와 겹치지 않는다.
MAX_SIDE = 48

# 이 미만이면 배경으로 본다. 원본 실측(1536x1024, 캔버스 대비 비율):
#
#   | 알파      | 잉크통 | 비커  | (참고) 노트 |
#   |-----------|--------|-------|-------------|
#   | = 0       | 39.2%  | 71.7% | 62.3%       |
#   | 1 ~ 7     | 26.0%  |  1.7% |  0.1%       |
#   | >= 8      | 34.9%  | 26.6% | 37.4%       |
#   | >= 64     | 29.8%  | 26.3% | 37.2%       |
#   | >= 128    | 29.2%  | 26.1% | 37.2%       |
#   | >= 224    | 28.5%  | 25.8% | 37.0%       |
#
# 64를 넘으면 곡선이 평평해진다 — 그 위는 물체 자신이고 아래가 글로우다.
# 128은 그 무릎에서 양쪽으로 두 배 여유를 둔 자리다. 224까지 올려도 그림은
# 거의 같지만, 비커 유리면이 원본에서 반투명하게 그려져 있어 더 올릴 이유가
# 없다.
ALPHA_MIN = 128

# 칸의 이 비율 이상이 그림일 때만 찍는다(열쇠·노트와 같은 2/5). 두 물체 다
# 축과 어긋난 가장자리가 많아 1/2로 자르면 유리 테두리와 물방울이 끊긴다.
COVER_NUM = 2
COVER_DEN = 5

# 그림 안쪽에 허용하는 투명 칸 수. 위 docstring 참조 — COVER 문턱이 내는
# 것이라 알파를 어떻게 잡아도 0~3이다. 8이면 실측치의 두 배가 넘고, 그보다
# 많아지면 배경 판정이나 크기가 잘못됐다는 뜻이다.
HOLE_MAX = 8

# (원본 파일 이름, 출력 파일 이름, 사람이 읽을 이름)
ITEMS = (("ink_can_design.png", "ink_can.png", "잉크통"),
         ("beaker_design.png", "beaker.png", "깨진 비커"))


def background_mask(width: int, height: int, rgba: bytearray) -> bytearray:
    """`ALPHA_MIN` 미만인 픽셀만 배경(1)으로 표시한다."""
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


def bake(src: pathlib.Path) -> tuple[int, int, bytearray]:
    if not src.exists():
        raise SystemExit(f"원본이 없다: {src}")
    w, h, rgba = read_png(src)
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

    # 그림 안쪽(불투명 픽셀에 사방이 둘러싸인 자리)의 투명 칸. 몇 칸은
    # COVER 문턱이 내는 것이라 정상이고, 많아지면 배경 판정이 잘못됐다.
    holes = 0
    for y in range(1, oh - 1):
        for x in range(1, ow - 1):
            i = y * ow + x
            if img[i * 4 + 3] >= 8:
                continue
            if all(img[((y + dy) * ow + (x + dx)) * 4 + 3] >= 8
                   for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))):
                holes += 1
    if holes > HOLE_MAX:
        raise SystemExit(f"그림 안쪽에 뚫린 자리가 {holes}칸 있다 "
                         f"(허용 {HOLE_MAX}) — 배경 판정을 확인할 것")

    shades = len({tuple(img[i * 4:i * 4 + 3]) for i in range(ow * oh)
                  if img[i * 4 + 3] >= 8})
    if shades < 4:
        raise SystemExit(f"색이 {shades}가지뿐이다 — 축소가 너무 뭉갰다")

    print(f"  불투명 {opaque} / {ow * oh} 픽셀, 색 {shades}가지, 안쪽 뚫림 {holes}칸")
    for y in range(oh):
        row = "".join(".#"[img[(y * ow + x) * 4 + 3] >= 8] for x in range(ow))
        print(f"  {row}")


def main() -> int:
    print(f"집기 단서 스프라이트 (긴 변 {MAX_SIDE}, 알파 문턱 {ALPHA_MIN})")
    for src_name, out_name, label in ITEMS:
        print(f"{label} — {src_name}")
        out = OUT_DIR / out_name
        ow, oh, img = bake(SRC_DIR / src_name)
        check(ow, oh, img)

        if out.exists():
            old_w, old_h, old = read_png(out)
            if (old_w, old_h) == (ow, oh) and old == img:
                print(f"{out.relative_to(ROOT)} 그대로 (픽셀 동일)")
                continue

        write_png(out, ow, oh, bytes(img))
        print(f"{out.relative_to(ROOT)} {ow}x{oh} 씀")
    return 0


if __name__ == "__main__":
    sys.exit(main())
