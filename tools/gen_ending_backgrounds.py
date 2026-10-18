#!/usr/bin/env python3
"""엔딩 컷신 배경 생성기 (#642).

원본 아트 `assets/backgrounds/source/*_design.png`(이미지 생성기가 뽑은 1672x940)를
게임용 도트 배경으로 굽는다.

    assets/backgrounds/ending_entrance.png   학교 현관(밤)
    assets/backgrounds/ending_gate.png       정문(새벽)
    assets/backgrounds/ending_home.png       집 식탁(아침, #647)
    assets/backgrounds/ending_police.png     경찰서 책상(새벽, #650)

`gen_key_sprite.py`와 같은 규약이다 — **표준 라이브러리만 쓰고 결정론적**이고
정수 연산만 쓴다. 원본은 `source/`의 `.gdignore` 아래라 Godot이 임포트하지 않는다.

**왜 후처리가 필요한가.** 원본은 "도트처럼 보이는 고해상도 그림"이다 — 색이 10만
가지가 넘고 도트 경계마다 번짐·노이즈가 있어서, 월드의 진짜 도트 타일·스프라이트
옆에 놓으면 한 화면에 두 가지 질감이 섞인다. 격자가 실제로 없으므로(실측: 가로 런
길이가 1px에 몰려 있고 주기 검사에도 걸리지 않는다) 격자를 찾아 샘플링하는 길은
없고, **면적 평균으로 줄인 뒤 팔레트를 제한**하는 수밖에 없다.

  1. GRID(400x225)로 면적 평균 축소. 400x225인 이유는 게임 뷰포트(1600x900)의
     **정수 약수**라서다 — 480x270은 3.33배라 도트 폭이 3px/4px로 들쭉날쭉하다.
  2. 가중 중앙값 분할(median cut)로 COLORS색 팔레트를 뽑는다. **가중치는 빈도가
     아니라 빈도의 제곱근이다.** 빈도 그대로 쓰면 화면 대부분인 남색 계열이 팔레트를
     다 먹어서 현관 문틈의 호박색 불빛·달·창문 불빛(= 이 그림의 유일한 광원)이
     남색으로 뭉개진다(실측: 32색 빈도 가중에서 호박색이 사라졌다).
  3. 각 픽셀을 가장 가까운 팔레트 색으로 찍는다(디더링 없음 — 하늘의 격자 무늬는
     원본에 이미 들어 있다).
  4. UP(4)배 최근접 확대. 뷰포트와 정확히 1600x900이라 `texture_filter`와 상관없이
     도트가 또렷하다.

재실행 안전장치: 이미 있는 출력과 픽셀이 같으면 파일을 건드리지 않는다.
"""
from __future__ import annotations

import math
import pathlib
import sys

from gen_key_sprite import read_png, write_png

ROOT = pathlib.Path(__file__).resolve().parent.parent
BG = ROOT / "assets" / "backgrounds"
SRC = BG / "source"

GRID_W, GRID_H = 400, 225
UP = 4          # 400x225 x 4 = 1600x900 (project.godot의 뷰포트)
COLORS = 40

JOBS = [
    ("ending_entrance_design.png", "ending_entrance.png"),
    ("ending_gate_design.png", "ending_gate.png"),
    ("ending_home_design.png", "ending_home.png"),
    ("ending_police_design.png", "ending_police.png"),
]


def downscale(sw: int, sh: int, rgba: bytearray) -> list[tuple[int, int, int]]:
    """면적 평균. 경계가 정수로 떨어지게 잡아서 부동소수를 쓰지 않는다."""
    out: list[tuple[int, int, int]] = []
    for oy in range(GRID_H):
        y0, y1 = oy * sh // GRID_H, max(oy * sh // GRID_H + 1, (oy + 1) * sh // GRID_H)
        for ox in range(GRID_W):
            x0, x1 = ox * sw // GRID_W, max(ox * sw // GRID_W + 1, (ox + 1) * sw // GRID_W)
            r = g = b = n = 0
            for y in range(y0, y1):
                base = y * sw * 4
                for x in range(x0, x1):
                    i = base + x * 4
                    r += rgba[i]
                    g += rgba[i + 1]
                    b += rgba[i + 2]
                    n += 1
            out.append(((r + n // 2) // n, (g + n // 2) // n, (b + n // 2) // n))
    return out


def median_cut(pixels: list[tuple[int, int, int]], count: int) -> list[tuple[int, int, int]]:
    freq: dict[tuple[int, int, int], int] = {}
    for p in pixels:
        freq[p] = freq.get(p, 0) + 1
    # 빈도의 제곱근 — 모듈 머리말 2번. 정수로 쓰려고 256을 곱해 isqrt를 건다.
    boxes = [sorted((c[0], c[1], c[2], math.isqrt(n * 256)) for c, n in freq.items())]

    def span(box: list[tuple[int, int, int, int]]) -> tuple[int, int]:
        best_ch, best = 0, -1
        for ch in range(3):
            lo = min(c[ch] for c in box)
            hi = max(c[ch] for c in box)
            if hi - lo > best:
                best_ch, best = ch, hi - lo
        return best_ch, best

    while len(boxes) < count:
        pick, pick_score = -1, 0
        for i, box in enumerate(boxes):
            if len(box) < 2:
                continue
            _, rng = span(box)
            score = rng * sum(c[3] for c in box)
            if score > pick_score:
                pick, pick_score = i, score
        if pick < 0:
            break
        box = boxes.pop(pick)
        ch, _ = span(box)
        box.sort(key=lambda c: (c[ch], c[0], c[1], c[2]))
        half = sum(c[3] for c in box) // 2
        acc, cut = 0, 1
        for i, c in enumerate(box):
            acc += c[3]
            if acc >= half:
                cut = min(max(i + 1, 1), len(box) - 1)
                break
        boxes.insert(pick, box[:cut])
        boxes.insert(pick + 1, box[cut:])

    palette = []
    for box in boxes:
        total = sum(c[3] for c in box)
        palette.append(tuple((sum(c[ch] * c[3] for c in box) + total // 2) // total
                             for ch in range(3)))
    return palette


def remap(pixels: list[tuple[int, int, int]],
          palette: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    cache: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    out = []
    for p in pixels:
        hit = cache.get(p)
        if hit is None:
            hit = min(palette, key=lambda q: ((q[0] - p[0]) ** 2 * 3
                                              + (q[1] - p[1]) ** 2 * 4
                                              + (q[2] - p[2]) ** 2 * 2, q))
            cache[p] = hit
        out.append(hit)
    return out


def upscale(pixels: list[tuple[int, int, int]]) -> bytearray:
    width = GRID_W * UP
    row = bytearray()
    out = bytearray()
    for y in range(GRID_H):
        row.clear()
        for x in range(GRID_W):
            r, g, b = pixels[y * GRID_W + x]
            row += bytes((r, g, b, 255)) * UP
        out += bytes(row) * UP
    assert len(out) == width * GRID_H * UP * 4
    return out


def bake(src: pathlib.Path) -> tuple[list[tuple[int, int, int]], bytearray]:
    sw, sh, rgba = read_png(src)
    small = downscale(sw, sh, rgba)
    palette = median_cut(small, COLORS)
    mapped = remap(small, palette)
    return palette, upscale(mapped)


def check(name: str, palette: list[tuple[int, int, int]], img: bytearray) -> None:
    used = {tuple(img[i:i + 3]) for i in range(0, len(img), 4 * UP * 997)}
    if len(palette) > COLORS:
        raise SystemExit(f"{name}: 팔레트가 {len(palette)}색 (한도 {COLORS})")
    if len(img) != GRID_W * UP * GRID_H * UP * 4:
        raise SystemExit(f"{name}: 출력 크기가 뷰포트와 어긋난다")
    # 밝은 광원이 살아남았는지 — 가장 밝은 색이 너무 어두우면 팔레트가 남색에 먹힌 것이다.
    if max(sum(c) for c in palette) < 3 * 140:
        raise SystemExit(f"{name}: 밝은 색이 없다 (최대 휘도 합 {max(sum(c) for c in palette)})")
    print(f"  {name}: 팔레트 {len(palette)}색, 표본에서 {len(used)}색 확인")


def main() -> int:
    print(f"엔딩 배경 ({GRID_W}x{GRID_H} x{UP}, {COLORS}색)")
    for src_name, out_name in JOBS:
        src, out = SRC / src_name, BG / out_name
        palette, img = bake(src)
        check(out_name, palette, img)
        w, h = GRID_W * UP, GRID_H * UP
        if out.exists():
            old_w, old_h, old = read_png(out)
            if (old_w, old_h) == (w, h) and old == img:
                print(f"{out.relative_to(ROOT)} 그대로 (픽셀 동일)")
                continue
        write_png(out, w, h, bytes(img))
        print(f"{out.relative_to(ROOT)} {w}x{h} 씀")
    return 0


if __name__ == "__main__":
    sys.exit(main())
