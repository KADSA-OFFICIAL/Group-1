#!/usr/bin/env python3
"""타이틀 오른쪽 위 설정 버튼의 톱니바퀴 도트 스프라이트를 굽는다(#781).

`scenes/ui/main_menu.tscn`의 `SettingsButton`이 쓴다. 글자 "설정" 대신 아이콘으로
바꾸라는 요청(사용자)이고, 화면이 전부 도트 그림이라 **매끈한 벡터 도형이 아니라
픽셀로 굽는다**(수위 화살표 #739가 매끈한 도형을 전부 거절당한 뒤의 규칙).

- **회색조**다. 색(평소 흐린 회색 / 고르면 미색)은 버튼의 `icon_*_color`가 곱해 입힌다 —
  윤곽의 검정은 곱해도 검정이라 그대로 남는다(`gen_alert_arrow.py`와 같은 방식).
- 모양은 중심에서의 거리 `r`과 각도 `θ`로 정한다 — 이빨 8개(`cos(8θ)`가 문턱을 넘는
  각도에서 `R_TOOTH`, 아니면 `R_BODY`), 가운데는 `R_HOLE`로 뚫는다.
- **왼쪽 위에서 빛이 온다.** 오른쪽 아래로 갈수록 어두운 세 단계(`TONES`)를 주고,
  위쪽 가장자리 한 줄은 밝게·아래쪽 한 줄은 어둡게 둬 납작한 판이 아니라 두께가
  보이게 한다(집기 그림의 `solid_obj()`와 같은 생각, #289).
- 캔버스는 18x18이고 화면에는 정수 3배(54px), Nearest로 놓는다 — 월드 도트 폭을
  고르게 하려는 것이다. 버튼이 정확히 54x54이고 아이콘이 `expand_icon`으로 꽉 차야
  3배가 맞는다(그 밖의 크기는 도트 폭이 들쭉날쭉해진다).

표준 라이브러리만 쓰고 결정론적이다 — 숫자를 안 바꿨으면 다시 돌려도 diff가 없다.
"""
from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_key_sprite import write_png  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "assets" / "ui" / "settings_gear.png"

SIZE = 18          # 캔버스 한 변. 몸통 14칸 + 윤곽 1칸씩 + 가장자리 1칸 여백
R_TOOTH = 7.3      # 이빨 끝 반지름(도트)
R_BODY = 4.9       # 이빨 사이 몸통 반지름
R_HOLE = 2.3       # 가운데 구멍 반지름
TEETH = 8
TOOTH_CUT = 0.0    # cos(TEETH·θ)가 이보다 크면 이빨 — 0이면 이빨과 홈의 폭이 같다

# 왼쪽 위 → 오른쪽 아래 명도(0~255). 앞이 밝다.
TONES = (255, 214, 172)
OUTLINE = 0
EDGE_LIGHT = 1.10  # 위쪽 가장자리 밝힘
EDGE_DARK = 0.72   # 아래쪽 가장자리 어둡힘


def inside(dx: float, dy: float) -> bool:
    r = math.hypot(dx, dy)
    if r < R_HOLE:
        return False
    tooth = math.cos(TEETH * math.atan2(dy, dx)) > TOOTH_CUT
    return r < (R_TOOTH if tooth else R_BODY)


def bake() -> bytearray:
    c = SIZE / 2.0
    mask = [[inside(x + 0.5 - c, y + 0.5 - c) for x in range(SIZE)] for y in range(SIZE)]

    def filled(x: int, y: int) -> bool:
        return 0 <= x < SIZE and 0 <= y < SIZE and mask[y][x]

    rgba = bytearray(SIZE * SIZE * 4)
    for y in range(SIZE):
        for x in range(SIZE):
            i = (y * SIZE + x) * 4
            if mask[y][x]:
                # 빛 방향(왼쪽 위)으로 얼마나 가까운가 — -1(왼쪽 위) ~ 1(오른쪽 아래).
                t = ((x + 0.5 - c) + (y + 0.5 - c)) / (2.0 * R_TOOTH)
                k = min(len(TONES) - 1, max(0, int((t + 1.0) / 2.0 * len(TONES))))
                tone = TONES[k]
                if not filled(x, y - 1):
                    tone = min(255, int(tone * EDGE_LIGHT))
                elif not filled(x, y + 1):
                    tone = int(tone * EDGE_DARK)
                rgba[i:i + 4] = bytes((tone, tone, tone, 255))
            elif any(filled(x + ox, y + oy) for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                rgba[i:i + 4] = bytes((OUTLINE, OUTLINE, OUTLINE, 255))
    return rgba


def check(rgba: bytearray) -> None:
    opaque = sum(1 for i in range(3, len(rgba), 4) if rgba[i])
    tones = {rgba[i] for i in range(0, len(rgba), 4) if rgba[i + 3] and rgba[i] > 0}
    if opaque < 100:
        raise SystemExit(f"톱니바퀴가 너무 작다({opaque}칸)")
    if len(tones) < 3:
        raise SystemExit(f"음영 단계가 안 산다(명도 {len(tones)}가지)")
    # 구멍이 뚫려 있어야 한다 — 가운데 칸이 투명이거나 윤곽(검정)이어야 톱니바퀴로 읽힌다.
    mid = (SIZE // 2 * SIZE + SIZE // 2) * 4
    if rgba[mid + 3] and rgba[mid] > 0:
        raise SystemExit("가운데 구멍이 안 뚫렸다 — R_HOLE을 키울 것")
    # 테두리 칸은 비어 있어야 한다 — 윤곽이 캔버스 밖으로 잘리면 안 된다.
    for k in range(SIZE):
        for x, y in ((k, 0), (k, SIZE - 1), (0, k), (SIZE - 1, k)):
            if rgba[(y * SIZE + x) * 4 + 3]:
                raise SystemExit(f"캔버스 가장자리({x},{y})까지 찼다 — SIZE를 키울 것")
    print(f"settings_gear.png: {SIZE}x{SIZE}, 불투명 {opaque}칸, 명도 {len(tones)}가지")


def main() -> None:
    rgba = bake()
    check(rgba)
    write_png(OUT, SIZE, SIZE, bytes(rgba))
    if "--ascii" in sys.argv:
        for y in range(SIZE):
            print("".join(
                " " if not rgba[(y * SIZE + x) * 4 + 3]
                else ("#" if rgba[(y * SIZE + x) * 4] > 150 else ("+" if rgba[(y * SIZE + x) * 4] > 0 else "."))
                for x in range(SIZE)))


if __name__ == "__main__":
    main()
