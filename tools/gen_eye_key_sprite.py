#!/usr/bin/env python3
"""2층 계단 열쇠 스프라이트 생성기 (#438).

원본 아트 `assets/sprites/source/eye_key_design.png`(미색 종이 위에 그린,
한쪽 눈구멍에 열쇠가 박힌 머리)에서 게임용 도트 스프라이트 한 장을 굽는다.

    assets/sprites/eye_key.png   (긴 변 MAX_SIDE, 짧은 변은 원본 비율)

`gen_key_sprite.py`(#333)·`gen_note_sprite.py`(#390)·`gen_item_sprites.py`(#427)와
같은 규약이다 — **표준 라이브러리만 쓰고 결정론적**이고, 정수 연산만 써서
부동소수 오차로 결과가 흔들리지 않는다. PNG 입출력·배경 flood fill·칸 굽기는
열쇠 생성기에서 그대로 가져다 쓴다. 원본은 상위 `source/`의 `.gdignore` 아래라
Godot이 임포트하지 않는다.

**노트·잉크통 생성기와 달리 배경이 알파 0이 아니다.** 저 둘은 투명 배경 위에
그린 것이라 알파 문턱만으로 갈렸는데, 이 원본은 사진처럼 **불투명한 미색
종이**다(위아래에 회색 레터박스 띠까지 있다). 그래서 열쇠 생성기의 테두리
flood fill(`background_mask`)을 쓴다.

**`punch_holes()`를 걸면 안 된다.** 얼굴 피부가 칠해지지 않은 흰색이라
윤곽선에 둘러싸인 거대한 밝은 덩어리다 — 열쇠의 고리 구멍 기준(캔버스의
0.5%)으로 뚫으면 얼굴이 통째로 배경으로 넘어가고 머리카락과 피만 남는다.
실측이 그대로 보여 준다: 밝기 문턱만으로 밝은 픽셀이 70.81%인데 테두리에서
이어지는 것은 64.77%뿐이라, **차이 6.04%가 갇힌 얼굴 피부**다.

축소는 평균이 아니라 **최빈색**이다(`gen_key_sprite.bake_cell`). 평균을 내면
원본에 없던 중간색이 생겨 도트 아트가 흐려진다.

재실행 안전장치: 이미 있는 출력과 픽셀이 같으면 파일을 건드리지 않는다
(PNG 인코더 버전이 달라도 diff가 나지 않게).
"""
from __future__ import annotations

import pathlib
import sys

from gen_key_sprite import (background_mask, bake_cell, content_box, read_png,
                            write_png)

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "sprites" / "source" / "eye_key_design.png"
OUT = ROOT / "assets" / "sprites" / "eye_key.png"

# 긴 변(여기서는 세로)의 도트 수 = 월드 픽셀 수(Sprite2D scale 1).
#
# **64는 실측으로 정한 값이다.** 이 그림에서 반드시 읽혀야 하는 것은 눈구멍에
# 박힌 **열쇠**다 — 그게 안 보이면 그냥 피 흘리는 머리이고, 이 물건이 2층
# 계단을 여는 열쇠라는 것을 그림이 말하지 못한다. 네 크기를 구워서 봤다:
#
#   | MAX_SIDE | 출력  | 눈의 열쇠                          |
#   |----------|-------|------------------------------------|
#   | 40       | 29x40 | 사라진다 (금색 1~2칸)              |
#   | 48       | 35x48 | 금색 얼룩 하나 — 열쇠로 안 읽힌다  |
#   | 56       | 41x56 | 작은 금색 자국                     |
#   | 64       | 46x64 | 손잡이·자루가 갈린다               |
#
# 더 키울 수도 있지만 64에서 이미 인물(74x76)의 높이에 가깝다 — 머리 하나가
# 사람만 해지면 크기가 거짓말이 된다. 잉크통·비커(48)보다 큰 것은 머리가
# 원래 그것들보다 크기 때문이고, 단서 둘레는 `gen_floors.py`의
# `PROP_CLUE_CLEAR`(중심에서 반경 76)가 비워 두므로 집기와 겹치지 않는다.
MAX_SIDE = 64

# 테두리에서 이어진 이 밝기(채널별) 이상만 배경으로 본다.
#
# 원본 실측(1322x1647). 최소 채널값 기준 누적 비율:
#
#   | 최소 채널 | 비율   |
#   |-----------|--------|
#   | >= 150    | 71.68% |
#   | >= 200    | 70.81% |
#   | >= 240    | 68.44% |
#   | >= 245    | 51.13% |
#
# **150부터 240까지 곡선이 평평하다**(3.24%p뿐). 그 구간에 아무것도 없다는
# 뜻이다 — 종이는 (252,253,248), 위아래 회색 레터박스 띠는 (243,243,243),
# 얼굴 피부는 (248,244,241)이고 그림은 전부 검은 잉크·붉은 피다. 245에서
# 곡선이 꺾이는 것은 거기서 회색 띠와 피부가 빠지기 때문이다.
#
# 그래서 200은 넓은 무인지대 한가운데다 — 열쇠 생성기와 같은 값을 쓰지만
# 이 원본에서는 근거가 다르다(저쪽은 흰 배경 위 황금 열쇠였다).
BG_MIN = 200

# 칸의 이 비율 이상이 그림일 때만 찍는다. 열쇠와 같은 2/5다 — 머리카락 끝의
# 삐친 가닥과 피가 흘러내린 자국이 칸을 반쯤만 채워서, 인물 기준(1/2)으로
# 자르면 실루엣 가장자리가 끊긴다.
COVER_NUM = 2
COVER_DEN = 5

# 실루엣 안쪽에 뚫린 칸의 허용치. 뚫는 단계가 없으므로 여기 남는 구멍은
# 위 COVER 문턱이 내는 것뿐이다(잉크통·비커와 같은 사정, #427).
HOLE_MAX = 8


def out_size(box_w: int, box_h: int) -> tuple[int, int]:
    """긴 변을 MAX_SIDE로 맞추고 짧은 변은 비율대로(정수 나눗셈, 최소 1)."""
    if box_w >= box_h:
        return MAX_SIDE, max(1, (box_h * MAX_SIDE + box_w // 2) // box_w)
    return max(1, (box_w * MAX_SIDE + box_h // 2) // box_h), MAX_SIDE


def bake() -> tuple[int, int, bytearray]:
    if not SRC.exists():
        raise SystemExit(f"원본이 없다: {SRC}")
    w, h, rgba = read_png(SRC)

    # 열쇠 생성기의 flood fill은 모듈 상수 BG_MIN을 읽는다. 이 원본은 근거가
    # 다르지만 값이 같으므로, 어긋나면 조용히 다른 그림이 나오는 것을 막는다.
    import gen_key_sprite
    if gen_key_sprite.BG_MIN != BG_MIN:
        raise SystemExit(
            f"gen_key_sprite.BG_MIN({gen_key_sprite.BG_MIN})과 이 파일의 "
            f"BG_MIN({BG_MIN})이 다르다 — background_mask가 저쪽 값을 쓴다")

    mask = background_mask(w, h, rgba)
    # **punch_holes를 부르지 않는다** — 위 독스트링 참조. 얼굴이 통째로 날아간다.
    bx0, by0, bx1, by1 = content_box(w, h, mask)
    box_w, box_h = bx1 - bx0, by1 - by0
    ow, oh = out_size(box_w, box_h)
    bg = sum(mask)
    print(f"  원본 {w}x{h} → 배경 {100.0 * bg / (w * h):.2f}% 제거 "
          f"→ 내용 {box_w}x{box_h} → 출력 {ow}x{oh}")

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


def interior_holes(ow: int, oh: int, img: bytearray) -> int:
    """실루엣 안쪽(테두리와 이어지지 않은) 투명 칸의 수."""
    from collections import deque

    seen = bytearray(ow * oh)
    queue: deque[int] = deque()

    def push(i: int) -> None:
        if seen[i] or img[i * 4 + 3] >= 8:
            return
        seen[i] = 1
        queue.append(i)

    for x in range(ow):
        push(x)
        push((oh - 1) * ow + x)
    for y in range(oh):
        push(y * ow)
        push(y * ow + ow - 1)
    while queue:
        i = queue.popleft()
        x, y = i % ow, i // ow
        if x > 0:
            push(i - 1)
        if x + 1 < ow:
            push(i + 1)
        if y > 0:
            push(i - ow)
        if y + 1 < oh:
            push(i + ow)
    return sum(1 for i in range(ow * oh)
               if img[i * 4 + 3] < 8 and not seen[i])


def check(ow: int, oh: int, img: bytearray) -> None:
    opaque = sum(1 for i in range(ow * oh) if img[i * 4 + 3] >= 8)
    if opaque == 0:
        raise SystemExit("빈 스프라이트다 — BG_MIN을 확인할 것")
    if opaque == ow * oh:
        raise SystemExit("투명 픽셀이 하나도 없다 — 배경이 지워지지 않았다")

    holes = interior_holes(ow, oh, img)
    if holes > HOLE_MAX:
        raise SystemExit(f"실루엣 안쪽 구멍이 {holes}칸이다 (허용 {HOLE_MAX}) "
                         f"— 얼굴이 배경으로 넘어갔는지 확인할 것")

    # 색이 뭉개졌는지 — 머리카락(검정)·피(붉은색)·피부(흰색)·열쇠(금색)가
    # 갈려야 한다. 서로 다른 색이 손에 꼽을 만큼밖에 안 남으면 축소가 그림을
    # 죽인 것이다(#427의 '소금·후추' 반대 방향 실패).
    colors = {(img[i * 4] << 16) | (img[i * 4 + 1] << 8) | img[i * 4 + 2]
              for i in range(ow * oh) if img[i * 4 + 3] >= 8}
    if len(colors) < 8:
        raise SystemExit(f"남은 색이 {len(colors)}가지뿐이다 — 축소가 그림을 뭉갰다")

    print(f"  불투명 {opaque} / {ow * oh} 픽셀, 색 {len(colors)}가지, "
          f"안쪽 구멍 {holes}칸")
    for y in range(oh):
        row = "".join(".#"[img[(y * ow + x) * 4 + 3] >= 8] for x in range(ow))
        print(f"  {row}")


def main() -> int:
    print(f"눈에 박힌 열쇠 스프라이트 (긴 변 {MAX_SIDE})")
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
