#!/usr/bin/env python3
"""수위 접근 방향 화살표 도트 스프라이트를 굽는다(#739).

`scripts/ui/janitor_alert.gd`가 화면 테두리에 띄우는 화살표다. 매끈한 벡터 도형
(사다리꼴·갈매기·호·배지…)은 도트 그림뿐인 화면에서 겉돌아 전부 거절됐다 —
그래서 다른 스프라이트처럼 픽셀 단위로 굽는다.

- **두 장**을 굽는다: 곧은 화살표(→) `alert_arrow.png`와 대각선(↘)
  `alert_arrow_diag.png`. 도트 그림은 임의 각도로 돌리면 칸이 비틀려 깨지므로
  90도 배수로만 돌리고(픽셀이 그대로 맞는다), 두 장 x 네 방향 = 8방향을 낸다.
- **회색조**다. 색(들림 호박 / 추격 빨강)은 런타임에 `modulate`로 입힌다 —
  윤곽의 검정은 곱해도 검정이라 그대로 남는다.
- **뒷부분(꼬리 쪽)에 단계 음영**을 넣는다(사용자 지시). 촉이 가장 밝고 꼬리로
  갈수록 어두워져 앞으로 쏠리는 느낌을 준다. 단계는 `TONES`이고 경계가
  반 칸씩 엇갈리는 디더 줄이 단계 사이를 잇는다.
- 위쪽 가장자리 한 줄은 밝게, 아래쪽은 어둡게 둬 납작한 판이 아니라 두께가
  보이게 한다(집기 그림의 `solid_obj()`와 같은 생각, #289).

모양은 축(u: 진행 방향, v: 옆) 위의 부등식으로 정한다. 대각선은 같은 부등식을
45도 돌린 좌표로 평가하므로 두 장의 모양이 같은 화살표에서 나온다.

표준 라이브러리만 쓰고 결정론적이다 — 숫자를 안 바꿨으면 다시 돌려도 diff가 없다.
"""
from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_key_sprite import write_png  # noqa: E402

OUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "assets" / "ui"

# 화살표 치수(도트). 촉 끝이 u = TIP, 촉 밑동이 u = HEAD_BASE, 꼬리 끝이 u = TAIL.
TIP = 7.5
HEAD_BASE = 0.5
TAIL = -7.5
HEAD_HALF = 6.5     # 촉 밑동의 반 폭 — 촉은 이 폭에서 끝까지 좁아진다
SHAFT_HALF = 2.5    # 자루 반 폭

# 꼬리 → 촉 순서의 명도(0~255). 앞이 밝고 뒤가 어둡다.
TONES = (112, 150, 190, 228, 255)
OUTLINE = 0        # 검정 윤곽
EDGE_LIGHT = 1.12  # 위쪽 가장자리 밝힘
EDGE_DARK = 0.70   # 아래쪽 가장자리 어둡힘

SIZE = 19          # 캔버스 한 변(홀수 — 가운데 칸이 화살표 중심이다)


# 대각선은 칸이 계단으로 놓여 같은 폭도 더 굵어 보인다 — 자루를 가늘게 한다.
DIAG_SHAFT_HALF = 1.6


def inside(u: float, v: float, shaft_half: float) -> bool:
    if HEAD_BASE <= u <= TIP:
        return abs(v) <= HEAD_HALF * (TIP - u) / (TIP - HEAD_BASE)
    if TAIL <= u < HEAD_BASE:
        return abs(v) <= shaft_half
    return False


def bake(diagonal: bool) -> bytearray:
    c = SIZE // 2
    # 1) 모양 — 칸 중심을 (u, v)로 바꿔 판정한다.
    mask = [[False] * SIZE for _ in range(SIZE)]
    coords: dict[tuple[int, int], tuple[float, float]] = {}
    for y in range(SIZE):
        for x in range(SIZE):
            dx, dy = x - c, y - c
            if diagonal:
                # 45도 돌린 축. 대각선은 칸 간격이 √2라 그만큼 늘려 길이를 맞춘다.
                u = (dx + dy) / math.sqrt(2)
                v = (dy - dx) / math.sqrt(2)
            else:
                u, v = dx, dy
            coords[(x, y)] = (u, v)
            mask[y][x] = inside(u, v, DIAG_SHAFT_HALF if diagonal else SHAFT_HALF)

    # 2) 윤곽 — 모양 바깥이면서 모양과 4-이웃으로 닿는 칸.
    def filled(x: int, y: int) -> bool:
        return 0 <= x < SIZE and 0 <= y < SIZE and mask[y][x]

    rgba = bytearray(SIZE * SIZE * 4)
    for y in range(SIZE):
        for x in range(SIZE):
            i = (y * SIZE + x) * 4
            if mask[y][x]:
                u, v = coords[(x, y)]
                t = (u - TAIL) / (TIP - TAIL)          # 0 = 꼬리, 1 = 촉
                level = t * (len(TONES) - 1)
                k = int(level)
                # 단계 경계에서 반 칸씩 엇갈려 다음 단계를 섞는다(디더). 대각선은
                # 단계 경계가 이미 계단이라 디더를 얹으면 체크무늬가 된다.
                if not diagonal and level - k > 0.72 and (x + y) % 2 == 0:
                    k += 1
                tone = TONES[min(k, len(TONES) - 1)]
                if not filled(x, y - 1):
                    tone = min(255, int(tone * EDGE_LIGHT))
                elif not filled(x, y + 1):
                    tone = int(tone * EDGE_DARK)
                rgba[i:i + 4] = bytes((tone, tone, tone, 255))
            elif any(filled(x + ox, y + oy) for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                rgba[i:i + 4] = bytes((OUTLINE, OUTLINE, OUTLINE, 255))
    return rgba


def check(name: str, rgba: bytearray) -> None:
    opaque = sum(1 for i in range(3, len(rgba), 4) if rgba[i])
    tones = {rgba[i] for i in range(0, len(rgba), 4) if rgba[i + 3] and rgba[i] > 0}
    if opaque < 40:
        raise SystemExit(f"{name}: 화살표가 너무 작다({opaque}칸)")
    if len(tones) < 4:
        raise SystemExit(f"{name}: 음영 단계가 안 산다(명도 {len(tones)}가지)")
    # 테두리 칸은 비어 있어야 한다 — 윤곽이 캔버스 밖으로 잘리면 안 된다.
    for k in range(SIZE):
        for x, y in ((k, 0), (k, SIZE - 1), (0, k), (SIZE - 1, k)):
            if rgba[(y * SIZE + x) * 4 + 3]:
                raise SystemExit(f"{name}: 캔버스 가장자리({x},{y})까지 찼다 — SIZE를 키울 것")
    print(f"{name}: {SIZE}x{SIZE}, 불투명 {opaque}칸, 명도 {len(tones)}가지")


def main() -> None:
    for name, diagonal in (("alert_arrow.png", False), ("alert_arrow_diag.png", True)):
        rgba = bake(diagonal)
        check(name, rgba)
        write_png(OUT_DIR / name, SIZE, SIZE, bytes(rgba))


if __name__ == "__main__":
    main()
