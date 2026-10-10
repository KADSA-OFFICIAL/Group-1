#!/usr/bin/env python3
"""일시정지 메뉴 제목 뒤 핏자국 생성기 (#627).

    assets/ui/blood_splatter.png   (W x H 도트, 한 도트 = DOT px)

시안 비교에서 고른 "한쪽에서 튄 자국"이다 — 왼쪽 아래 한 점에서 피가 날아와
오른쪽 위로 부채꼴로 흩뿌려진다. 출발점에는 고인 얼룩과 흘러내린 줄기가 있고,
멀리 날아간 방울일수록 작고 길쭉하다(날아간 방향으로 꼬리가 남는다).

다른 생성기(`gen_key_sprite.py` 등)와 같은 규약이다 — **표준 라이브러리만 쓰고
결정론적**이다. 난수는 고정 시드의 정수 LCG이고, 삼각함수 결과는 1/64 격자로
반올림해 플랫폼마다 libm의 마지막 비트가 달라도 래스터가 흔들리지 않게 한다.
PNG 쓰기는 `gen_key_sprite.write_png`를 그대로 쓴다.

**도트로 굽는다.** 게임 도트 규약(#246)대로 한 도트가 화면 2px이고, 안티에일리어싱
없이 팔레트 네 색만 쓴다. 벡터로 매끈하게 그리면 도트 그림인 게임 화면 위에서
혼자 떠 보인다.

재실행 안전장치: 이미 있는 출력과 바이트가 같으면 파일을 건드리지 않는다.
"""
from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_key_sprite import write_png  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "ui" / "blood_splatter.png"

## 캔버스(도트). 제목 라벨(400 x 약 100px) 둘레를 덮을 만큼.
W, H = 180, 104
## 한 도트의 화면 크기(px). 게임 도트 규약(#246)과 같다.
DOT = 2

## 마른 피(바깥) → 덜 마른 피 → 갓 튄 피. 바깥이 어둡고 안쪽이 밝아야 고인 것으로 읽힌다.
DRY = (78, 7, 7)
MID = (111, 12, 11)
FRESH = (142, 19, 15)
WET = (165, 26, 19)

## 출발점(도트)과 뿌려지는 방향·퍼짐(라디안)·거리.
ORIGIN = (20.0, 86.0)
ANGLE = -0.45
SPREAD = 0.75
REACH = 160.0
DROPS = 54
SEED = 11


class Rng:
    """시안(브라우저)과 같은 Park–Miller LCG. 정수만 써서 어디서나 같은 열이 나온다."""

    def __init__(self, seed: int) -> None:
        self.s = seed

    def __call__(self) -> float:
        self.s = (self.s * 16807) % 2147483647
        return self.s / 2147483647


def q(v: float) -> float:
    """1/64 격자로 반올림 — libm 차이로 마지막 비트가 흔들려도 래스터는 같다."""
    return round(v * 64.0) / 64.0


class Canvas:
    def __init__(self) -> None:
        self.px: list[tuple[int, int, int] | None] = [None] * (W * H)

    def _fill(self, x0: float, y0: float, x1: float, y1: float, inside, color) -> None:
        for y in range(max(0, int(y0) - 1), min(H, int(y1) + 2)):
            for x in range(max(0, int(x0) - 1), min(W, int(x1) + 2)):
                if inside(x + 0.5, y + 0.5):
                    self.px[y * W + x] = color

    def blob(self, cx: float, cy: float, rx: float, ry: float, color, rng: Rng,
             n: int = 22, jitter: float = 0.4) -> None:
        """울퉁불퉁한 타원. 꼭짓점마다 반지름을 흔든다."""
        pts = []
        for i in range(n):
            a = i / n * math.tau
            k = 1.0 - jitter / 2 + rng() * jitter
            pts.append((q(cx + math.cos(a) * rx * k), q(cy + math.sin(a) * ry * k)))

        def inside(px: float, py: float) -> bool:
            hit = False
            j = len(pts) - 1
            for i, (xi, yi) in enumerate(pts):
                xj, yj = pts[j]
                if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                    hit = not hit
                j = i
            return hit

        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        self._fill(min(xs), min(ys), max(xs), max(ys), inside, color)

    def drop(self, x: float, y: float, angle: float, length: float, radius: float,
             color) -> None:
        """날아간 방울 — 머리(원) + 날아온 쪽으로 가늘어지는 꼬리.

        (x, y)가 꼬리 끝, 머리는 angle 방향으로 length만큼 앞이다.
        """
        dx, dy = q(math.cos(angle)), q(math.sin(angle))
        hx, hy = x + dx * length, y + dy * length

        def inside(px: float, py: float) -> bool:
            if (px - hx) ** 2 + (py - hy) ** 2 <= radius * radius:
                return True
            vx, vy = px - x, py - y
            t = (vx * dx + vy * dy) / length if length > 0 else 1.0
            if t < 0.0 or t > 1.0:
                return False
            ox, oy = vx - dx * t * length, vy - dy * t * length
            return ox * ox + oy * oy <= (radius * (0.2 + 0.8 * t)) ** 2

        r = radius + 1
        self._fill(min(x, hx) - r, min(y, hy) - r, max(x, hx) + r, max(y, hy) + r, inside, color)

    def drip(self, x: float, y: float, length: float, width: float, color) -> None:
        """아래로 흘러내린 줄기 + 끝에 맺힌 방울."""
        half = width / 2

        def inside(px: float, py: float) -> bool:
            if y <= py <= y + length and abs(px - x) <= half:
                return True
            return (px - x) ** 2 + (py - (y + length)) ** 2 <= (half * 1.5) ** 2

        self._fill(x - width, y, x + width, y + length + width * 2, inside, color)

    def rgba(self) -> bytes:
        """도트 하나를 DOT x DOT 픽셀로 키운다."""
        out = bytearray()
        for y in range(H):
            row = bytearray()
            for x in range(W):
                c = self.px[y * W + x]
                row += bytes((*c, 255)) if c else b"\x00\x00\x00\x00"
            wide = bytearray()
            for i in range(0, len(row), 4):
                wide += row[i:i + 4] * DOT
            out += bytes(wide) * DOT
        return bytes(out)


def build() -> Canvas:
    rng = Rng(SEED)
    cv = Canvas()
    ox, oy = ORIGIN

    # 부채꼴로 뿌려진 방울 — 멀수록 작고, 날아간 방향으로 꼬리가 길다.
    for i in range(DROPS):
        a = q(ANGLE + (rng() - 0.5) * SPREAD)
        d = REACH * (0.12 + rng() * 0.88)
        size = (1.0 - d / REACH) * 3.4 + 0.7
        x = ox + math.cos(a) * d
        y = oy + math.sin(a) * d
        color = FRESH if i % 4 == 0 else (MID if i % 3 else DRY)
        tail = size * 3.4
        cv.drop(q(x - math.cos(a) * tail), q(y - math.sin(a) * tail), a, tail, max(0.7, size * 0.8), color)

    # 출발점 쪽 굵은 줄기 몇 개 — 피가 처음 튀어 나간 자리.
    for _ in range(5):
        a = q(ANGLE + (rng() - 0.5) * SPREAD * 0.6)
        length = 14 + rng() * 18
        cv.drop(q(ox + math.cos(a) * 4), q(oy + math.sin(a) * 4), a, length, 1.4 + rng() * 1.2, MID)

    # 출발점에 고인 얼룩 — 바깥이 마르고 안쪽이 젖어 있다.
    cv.blob(ox, oy, 9.0, 6.0, DRY, rng)
    cv.blob(ox + 1.0, oy - 0.5, 6.5, 4.2, MID, rng)
    cv.blob(ox + 1.5, oy - 1.0, 3.2, 2.2, FRESH, rng, n=14, jitter=0.5)
    cv.blob(ox + 2.0, oy - 1.5, 1.2, 0.9, WET, rng, n=10, jitter=0.3)

    # 흘러내린 줄기.
    cv.drip(ox + 3.0, oy + 3.0, 11.0, 2.2, MID)
    cv.drip(ox - 4.0, oy + 2.0, 5.0, 1.6, DRY)
    return cv


def check(cv: Canvas) -> None:
    filled = sum(1 for c in cv.px if c is not None)
    ratio = filled / (W * H)
    # 너무 적으면 안 보이고, 너무 많으면 제목을 덮는다.
    if not 0.04 <= ratio <= 0.25:
        sys.exit(f"핏자국 면적 {ratio:.1%} — 4~25% 밖이다")
    palette = {DRY, MID, FRESH, WET}
    stray = {c for c in cv.px if c is not None and c not in palette}
    if stray:
        sys.exit(f"팔레트 밖의 색이 있다: {sorted(stray)[:4]}")


def main() -> int:
    cv = build()
    check(cv)
    data = cv.rgba()
    tmp = OUT.with_suffix(".tmp.png")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_png(tmp, W * DOT, H * DOT, data)
    if OUT.exists() and OUT.read_bytes() == tmp.read_bytes():
        tmp.unlink()
        print(f"{OUT.relative_to(ROOT)}: 변화 없음")
        return 0
    tmp.replace(OUT)
    filled = sum(1 for c in cv.px if c is not None)
    print(f"{OUT.relative_to(ROOT)}: {W * DOT}x{H * DOT}px, 칠한 도트 {filled}/{W * H}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
