#!/usr/bin/env python3
"""가구·단서 도트 그림 생성기 (#791).

    python3 tools/gen_furniture_sprites.py

`assets/sprites/furniture/`에 그림 18장을 굽는다 — 교장실 가구 10종, 보건실 침대,
단서 그림 셋(시우 그림·인사 기록·대응 매뉴얼), 선반·캐비닛의 앞모습/옆모습,
창고 상자. 예전에는 Darklight Academia Furniture Pack(kueyhorse, #716·#723·#758)의
그림이었는데 그 팩의 "NFT·AI 관련 프로젝트 사용 금지" 조항이 이 게임에 걸리는지
판단할 수 없어 걷어냈다(사용자 결정). **원본 팩을 보고 베끼지 않았다** — 가구
종류와 픽셀 크기(`SIZES`)만 같다. 크기가 같아야 배치 코드(`gen_floors`)가 잡은
자리·충돌·통로가 그대로라 검사 결과가 안 바뀐다.

규약(다른 `gen_*_sprite.py`와 같다):
  * **표준 라이브러리만, 결정론적.** 난수는 이름을 씨앗으로 하는 LCG라 다시
    돌려도 바이트가 같다.
  * 게임에서는 **정수 2배**로 놓는다(`gen_floors.EXT_SCALE`) — 한 칸이 월드 2px.
  * 그림은 **위에서 비스듬히 내려다본 3/4 시점**이다. 윗면이 밝고 앞면이 그보다
    어둡고 바닥에 닿는 줄이 가장 어둡다(#289 "높이 단서가 없으면 물건으로 안
    읽힌다").
  * **윤곽은 마지막에 한 번에 긋는다**(`outline`). 투명한 칸과 맞닿은 칸을 윤곽
    색으로 바꾸므로 그림마다 테두리를 따로 그릴 필요가 없고 빠뜨릴 수도 없다.

옆모습(`*_side`)은 **앞면이 왼쪽을 본다** — `gen_floors.WALL_ART_SIDE_FACES`가
그렇게 적고 있고, 방 왼쪽 벽에 붙으면 배치 코드가 좌우를 뒤집는다.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_key_sprite import read_png, write_png  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets/sprites/furniture"

# 이름 → (폭, 높이). 예전 그림과 같은 크기다 — 바꾸면 배치가 움직인다.
SIZES = {
    "desk_exec": (56, 25),
    "sofa_red": (28, 21),
    "armchair_red": (22, 21),
    "bookcase_tall": (30, 52),
    "grandfather_clock": (13, 40),
    "globe": (13, 18),
    "floor_lamp": (14, 32),
    "vase_blue": (16, 21),
    "bed_green": (20, 32),
    "rug_long": (96, 30),
    "painting_dark": (22, 25),
    "book_closed": (18, 11),
    "books_pile": (14, 14),
    "bookshelf": (30, 32),
    "bookshelf_side": (15, 32),
    "cabinet": (22, 32),
    "cabinet_side": (12, 32),
    "crate": (22, 28),
}
MAX_COLORS = 32     # 한 장에 이보다 많으면 도트 그림이 아니라 그라디언트다

# ── 팔레트 ─────────────────────────────────────────────────────────────
OUTLINE = (22, 15, 13)
WOOD = [(48, 30, 20), (74, 46, 30), (102, 66, 40), (134, 90, 54), (164, 116, 70)]
RED = [(70, 20, 22), (104, 32, 30), (136, 48, 40), (166, 74, 56)]
BRASS = [(110, 82, 36), (160, 126, 54), (210, 176, 88)]
CREAM = [(150, 136, 100), (196, 182, 136), (230, 218, 170)]
GREEN = [(52, 72, 44), (74, 98, 58), (100, 126, 74), (132, 154, 96)]
BLUE = [(44, 62, 90), (70, 98, 132), (110, 142, 176), (164, 190, 212)]
NIGHT = [(14, 18, 34), (22, 30, 54), (34, 46, 76)]
GREY = [(70, 72, 78), (112, 114, 120), (156, 158, 162), (196, 198, 200)]
GLASS = [(34, 46, 58), (58, 78, 94), (96, 122, 138)]
BOOKS = [RED[1], RED[2], GREEN[1], GREEN[2], BLUE[1], BLUE[2], BRASS[1],
         (96, 60, 92), (62, 44, 34), (150, 120, 70)]


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [[None] * w for _ in range(h)]

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def rect(self, x0, y0, x1, y1, c):
        """끝 좌표 포함."""
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.put(x, y, c)

    def hline(self, x0, x1, y, c):
        self.rect(x0, y, x1, y, c)

    def vline(self, x, y0, y1, c):
        self.rect(x, y0, x, y1, c)

    def ellipse(self, cx2, cy2, rx2, ry2, c):
        """중심·반지름을 **2배 정수**로 받는다(반 칸 중심을 쓰려고)."""
        for y in range(self.h):
            for x in range(self.w):
                dx, dy = 2 * x + 1 - cx2, 2 * y + 1 - cy2
                if dx * dx * ry2 * ry2 + dy * dy * rx2 * rx2 <= rx2 * rx2 * ry2 * ry2:
                    self.put(x, y, c)

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[y][x]
        return None

    def outline(self):
        """투명한 칸(또는 캔버스 끝)과 맞닿은 칸을 윤곽 색으로."""
        edge = [(x, y) for y in range(self.h) for x in range(self.w)
                if self.px[y][x] is not None and any(
                    self.get(x + dx, y + dy) is None
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
        for x, y in edge:
            self.px[y][x] = OUTLINE

    def rgba(self):
        out = bytearray()
        for row in self.px:
            for c in row:
                out += bytes((0, 0, 0, 0)) if c is None else bytes((*c, 255))
        return bytes(out)


class Rng:
    """이름을 씨앗으로 쓰는 LCG — 다시 돌려도 같은 책이 같은 자리에 꽂힌다."""

    def __init__(self, seed: str):
        self.s = sum((i + 1) * ord(ch) for i, ch in enumerate(seed)) & 0x7FFFFFFF

    def next(self, n):
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return (self.s >> 8) % n


# ── 공용 부품 ───────────────────────────────────────────────────────────

def books_row(cv, rng, x0, x1, y_floor, h_max):
    """선반 한 칸에 책을 꽂는다. 바닥 y_floor 위로 최대 h_max."""
    x = x0
    while x <= x1:
        bw = min(1 + rng.next(3), x1 - x + 1)
        if rng.next(9) == 0 and x + 2 <= x1:      # 빈자리
            x += 2
            continue
        bh = h_max - rng.next(3)
        col = BOOKS[rng.next(len(BOOKS))]
        dark = tuple(max(0, v - 26) for v in col)
        cv.rect(x, y_floor - bh + 1, x + bw - 1, y_floor, col)
        cv.vline(x + bw - 1, y_floor - bh + 1, y_floor, dark)   # 오른쪽 그늘
        if bh >= 4 and bw >= 2:
            cv.hline(x, x + bw - 2, y_floor - bh + 2, BRASS[1])  # 책등 띠
        x += bw


def shelf_unit(cv, rng, x0, x1, y0, y1, rows, divider):
    """책장 몸통: 틀 + 선반 rows칸 + 가운데 칸막이(있으면)."""
    cv.rect(x0, y0, x1, y1, WOOD[1])
    inner_h = y1 - y0 - 1
    step = inner_h // rows
    for i in range(rows):
        top = y0 + 1 + i * step
        bot = top + step - 2
        cv.rect(x0 + 2, top, x1 - 2, bot, WOOD[0])              # 안쪽 그늘
        cv.hline(x0 + 2, x1 - 2, bot + 1, WOOD[3])              # 선반 판
        mid = (x0 + x1) // 2
        if divider:
            books_row(cv, rng, x0 + 2, mid - 1, bot, step - 2)
            books_row(cv, rng, mid + 2, x1 - 2, bot, step - 2)
            cv.vline(mid, top, bot, WOOD[2])
            cv.vline(mid + 1, top, bot, WOOD[1])
        else:
            books_row(cv, rng, x0 + 2, x1 - 2, bot, step - 2)
    cv.vline(x0 + 1, y0, y1, WOOD[2])                            # 틀 하이라이트
    cv.vline(x1 - 1, y0, y1, WOOD[1])


def feet(cv, xs, y0, y1, c=WOOD[0]):
    for x in xs:
        cv.rect(x, y0, x + 1, y1, c)


# ── 그림 하나씩 ────────────────────────────────────────────────────────

def desk_exec(cv):
    w = cv.w
    cv.rect(0, 0, w - 1, 12, WOOD[3])                    # 상판
    cv.hline(1, w - 2, 1, WOOD[4])
    cv.rect(10, 3, w - 11, 10, GREEN[1])                 # 가죽 깔개
    cv.hline(10, w - 11, 3, GREEN[2])
    cv.rect(13, 5, 21, 9, CREAM[2])                      # 서류
    cv.hline(14, 20, 6, CREAM[0])
    cv.hline(14, 19, 8, CREAM[0])
    cv.rect(w - 18, 5, w - 15, 8, NIGHT[0])              # 잉크병
    cv.put(w - 17, 5, BLUE[2])
    cv.rect(w - 13, 4, w - 13, 9, BRASS[2])              # 펜
    cv.rect(0, 13, w - 1, 20, WOOD[2])                   # 앞면
    cv.hline(0, w - 1, 13, WOOD[1])
    for x0 in (3, w - 18):                               # 서랍 둘
        cv.rect(x0, 15, x0 + 14, 19, WOOD[1])
        cv.rect(x0 + 1, 16, x0 + 13, 18, WOOD[2])
        cv.rect(x0 + 6, 17, x0 + 8, 17, BRASS[2])
    cv.rect(21, 15, w - 22, 19, WOOD[0])                 # 다리 들어가는 자리
    cv.rect(0, 21, 3, 24, WOOD[1])                       # 다리
    cv.rect(w - 4, 21, w - 1, 24, WOOD[1])
    cv.hline(0, 3, 24, WOOD[0])
    cv.hline(w - 4, w - 1, 24, WOOD[0])


def _seat(cv, w, cushions):
    cv.rect(2, 0, w - 3, 7, RED[1])                      # 등받이
    cv.hline(3, w - 4, 1, RED[3])
    cv.rect(3, 2, w - 4, 6, RED[2])
    for x in range(4, w - 4, 4):                         # 단추
        cv.put(x, 4, RED[0])
    cv.rect(0, 4, 4, 16, RED[1])                         # 팔걸이
    cv.rect(w - 5, 4, w - 1, 16, RED[1])
    cv.hline(1, 3, 4, RED[3])
    cv.hline(w - 4, w - 2, 4, RED[3])
    cv.rect(1, 5, 3, 13, RED[2])
    cv.rect(w - 4, 5, w - 2, 13, RED[2])
    inner = (5, w - 6)
    span = inner[1] - inner[0] + 1
    for i in range(cushions):                            # 방석
        a = inner[0] + span * i // cushions
        b = inner[0] + span * (i + 1) // cushions - 1
        cv.rect(a, 8, b, 13, RED[2])
        cv.hline(a, b, 8, RED[3])
        cv.vline(b, 8, 13, RED[1])
    cv.rect(0, 14, w - 1, 17, RED[0])                    # 앞 치마
    cv.hline(0, w - 1, 14, RED[1])
    feet(cv, (3, w - 5), 18, 20)


def sofa_red(cv):
    _seat(cv, cv.w, 2)


def armchair_red(cv):
    _seat(cv, cv.w, 1)


def bookcase_tall(cv):
    w, h = cv.w, cv.h
    cv.rect(0, 0, w - 1, 3, WOOD[3])                     # 머리 장식
    cv.hline(1, w - 2, 1, WOOD[4])
    cv.hline(0, w - 1, 3, WOOD[1])
    shelf_unit(cv, Rng("bookcase_tall"), 0, w - 1, 4, h - 4, 6, True)
    cv.rect(0, h - 4, w - 1, h - 3, WOOD[2])             # 받침
    feet(cv, (1, w - 3), h - 2, h - 1)


def grandfather_clock(cv):
    w = cv.w
    cv.rect(1, 0, w - 2, 2, WOOD[3])                     # 머리
    cv.rect(0, 2, w - 1, 12, WOOD[2])
    cv.hline(1, w - 2, 0, WOOD[4])
    cv.ellipse(13, 15, 9, 9, CREAM[1])                   # 문자판
    cv.ellipse(13, 15, 7, 7, CREAM[2])
    for x, y in ((6, 4), (6, 10), (3, 7), (9, 7)):      # 12·6·9·3시 눈금
        cv.put(x, y, WOOD[0])
    cv.vline(6, 5, 7, NIGHT[0])                          # 바늘
    cv.hline(6, 8, 7, NIGHT[0])
    cv.rect(2, 13, w - 3, 33, WOOD[1])                   # 몸통
    cv.vline(2, 13, 33, WOOD[2])
    cv.rect(4, 15, w - 5, 30, NIGHT[1])                  # 유리 창
    cv.vline(4, 15, 30, GLASS[2])
    cv.vline(6, 15, 26, BRASS[0])                        # 추
    cv.ellipse(13, 55, 4, 4, BRASS[2])
    cv.rect(0, 34, w - 1, 37, WOOD[2])                   # 받침
    cv.hline(0, w - 1, 34, WOOD[3])
    feet(cv, (1, w - 3), 38, 39)


def globe(cv):
    cv.ellipse(13, 13, 13, 12, BLUE[1])                  # 바다
    cv.ellipse(11, 11, 7, 7, BLUE[2])
    for x, y in ((4, 3), (5, 3), (4, 4), (3, 5), (4, 5), (5, 6), (7, 6), (8, 7),
                 (7, 8), (8, 8), (3, 8), (4, 9), (8, 3), (9, 4)):
        cv.put(x, y, GREEN[2])                           # 땅
    cv.put(4, 3, GREEN[3])
    for y in range(2, 11):                               # 경선 고리(오른쪽 반)
        cv.put(11 if 3 <= y <= 9 else 10, y, BRASS[1])
    cv.rect(6, 13, 6, 14, BRASS[1])                      # 대
    cv.rect(2, 15, 10, 17, WOOD[2])                      # 받침
    cv.hline(3, 9, 15, WOOD[3])


def floor_lamp(cv):
    w = cv.w
    for y in range(0, 9):                                # 갓 — 위가 좁은 사다리꼴
        a = 4 - y * 4 // 8
        cv.hline(a, w - 1 - a, y, CREAM[2] if y < 7 else CREAM[1])
    cv.vline(w - 1 - 4, 1, 6, CREAM[1])
    cv.hline(1, w - 2, 8, BRASS[1])                      # 갓 테두리
    cv.rect(5, 9, 8, 27, BRASS[1])                       # 기둥(윤곽이 양옆을 먹는다)
    cv.vline(6, 9, 27, BRASS[2])
    cv.rect(4, 18, 9, 19, BRASS[0])                      # 마디
    cv.rect(3, 28, w - 4, 31, WOOD[1])                   # 받침
    cv.rect(1, 30, w - 2, 31, WOOD[1])
    cv.hline(4, w - 5, 28, WOOD[3])
    cv.hline(2, w - 3, 30, WOOD[2])


def vase_blue(cv):
    cv.ellipse(16, 8, 13, 8, GREEN[1])                   # 잎 덤불
    cv.ellipse(16, 6, 9, 6, RED[1])                      # 꽃 덩어리
    for x, y in ((5, 2), (8, 1), (11, 2), (6, 4), (10, 4), (8, 3)):
        cv.put(x, y, RED[3])                             # 꽃잎 하이라이트
        cv.put(x + 1, y, RED[2])
    for x, y in ((2, 5), (13, 5), (4, 6), (12, 6)):
        cv.put(x, y, GREEN[3])
    widths = [3, 3, 4, 5, 6, 7, 8, 8, 8, 7, 7, 6, 5]    # 입 → 몸통 → 굽
    for i, half in enumerate(widths):
        y = 8 + i
        cv.hline(8 - half, 7 + half, y, BLUE[1])
        cv.put(8 - half + 1, y, BLUE[2])
        cv.put(7 + half - 1, y, BLUE[0])
    cv.hline(5, 10, 8, BLUE[2])                          # 입술
    for x in range(1, 15):
        cv.put(x, 15, CREAM[1] if x % 2 else BLUE[0])    # 무늬 띠
    cv.rect(3, 12, 3, 17, BLUE[3])                       # 광택


def bed_green(cv):
    w, h = cv.w, cv.h
    cv.rect(0, 0, w - 1, 3, GREY[2])                     # 머리판(철제)
    cv.hline(1, w - 2, 1, GREY[3])
    for x in range(3, w - 3, 3):
        cv.put(x, 2, GREY[1])
    cv.rect(1, 4, w - 2, h - 4, CREAM[1])                # 매트리스
    cv.rect(3, 5, w - 4, 9, CREAM[2])                    # 베개
    cv.hline(3, w - 4, 9, CREAM[0])
    cv.rect(1, 12, w - 2, h - 4, GREEN[2])               # 담요
    cv.rect(1, 11, w - 2, 13, CREAM[2])                  # 접힌 시트
    cv.hline(1, w - 2, 14, GREEN[1])
    for y in range(17, h - 4, 4):                        # 담요 주름
        cv.hline(3, w - 4, y, GREEN[1])
    cv.vline(w - 2, 12, h - 4, GREEN[1])
    cv.vline(1, 12, h - 4, GREEN[3])
    cv.rect(0, h - 3, w - 1, h - 1, GREY[1])             # 발판
    cv.hline(1, w - 2, h - 3, GREY[2])


def rug_long(cv):
    w, h = cv.w, cv.h
    cv.rect(0, 0, w - 1, h - 1, RED[0])
    cv.rect(2, 2, w - 3, h - 3, BRASS[0])                # 테 띠
    cv.rect(4, 4, w - 5, h - 5, RED[1])
    cv.rect(6, 6, w - 7, h - 7, RED[0])                  # 안 띠
    cv.rect(7, 7, w - 8, h - 8, RED[1])
    cy = h // 2
    for cx in range(17, w - 16, 12):                     # 마름모 무늬(가운데 맞춤)
        for d in range(5):
            for sx, sy in ((d, 5 - d), (-d, 5 - d), (d, d - 5), (-d, d - 5)):
                cv.put(cx + sx, cy + sy - 1, BRASS[1])
        cv.rect(cx - 1, cy - 2, cx, cy - 1, NIGHT[2])
    for x in range(1, w - 1, 2):                         # 술
        cv.put(x, 0, CREAM[0])
        cv.put(x, h - 1, CREAM[0])


def painting_dark(cv):
    """시우 그림 — 밤의 학교. 창문 하나만 켜져 있다."""
    w, h = cv.w, cv.h
    cv.rect(0, 0, w - 1, h - 1, BRASS[1])                # 금테
    cv.hline(1, w - 2, 1, BRASS[2])
    cv.vline(1, 1, h - 2, BRASS[2])
    cv.rect(3, 3, w - 4, h - 4, NIGHT[1])                # 하늘
    cv.rect(3, 3, w - 4, 7, NIGHT[0])
    cv.rect(14, 5, 15, 6, CREAM[2])                      # 달
    cv.put(6, 5, CREAM[1])
    cv.put(10, 8, CREAM[0])
    cv.rect(5, 12, 16, h - 6, NIGHT[2])                  # 학교 건물
    cv.rect(9, 9, 12, 11, NIGHT[2])                      # 시계탑
    cv.put(10, 10, BRASS[0])
    for x in range(6, 16, 3):                            # 꺼진 창
        cv.put(x, 14, NIGHT[0])
        cv.put(x, 17, NIGHT[0])
    cv.put(12, 17, BRASS[2])                             # 켜진 창 하나
    cv.rect(3, h - 5, w - 4, h - 4, (20, 28, 22))        # 땅


def book_closed(cv):
    """인사 기록 — 끈으로 묶은 서류철."""
    w, h = cv.w, cv.h
    cv.rect(0, 0, w - 1, h - 3, BLUE[0])                 # 표지
    cv.hline(1, w - 2, 1, BLUE[1])
    cv.rect(5, 3, 12, 6, CREAM[2])                       # 이름표
    cv.hline(6, 11, 4, CREAM[0])
    cv.vline(w - 4, 0, h - 3, BRASS[1])                  # 끈
    cv.rect(0, h - 2, w - 1, h - 1, CREAM[1])            # 종이 단면
    cv.hline(1, w - 2, h - 1, CREAM[0])


def books_pile(cv):
    """대응 매뉴얼 — 책 세 권이 엇갈려 쌓였다."""
    layers = ((0, 10, 0, RED), (2, 13, 4, BLUE), (1, 12, 9, GREEN))
    for x0, x1, y0, pal in layers:
        cv.rect(x0, y0, x1, y0 + 2, pal[2])              # 표지 윗면
        cv.hline(x0 + 1, x1 - 1, y0, pal[3])
        cv.rect(x0, y0 + 3, x1, y0 + 4, CREAM[2])        # 종이 단면
        cv.vline(x0, y0 + 3, y0 + 4, pal[1])             # 책등
        cv.hline(x0 + 1, x1, y0 + 4, CREAM[0])


def bookshelf(cv):
    w, h = cv.w, cv.h
    cv.rect(0, 0, w - 1, 2, WOOD[3])
    cv.hline(1, w - 2, 0, WOOD[4])
    shelf_unit(cv, Rng("bookshelf"), 0, w - 1, 3, h - 4, 3, True)
    cv.rect(0, h - 4, w - 1, h - 3, WOOD[2])
    feet(cv, (1, w - 3), h - 2, h - 1)


def _side_panel(cv, front_detail):
    """옆모습: 윗면 + 옆판, **앞면은 왼쪽**(x 0~2)."""
    w, h = cv.w, cv.h
    cv.rect(0, 0, w - 1, 2, WOOD[3])                     # 윗면
    cv.hline(1, w - 2, 0, WOOD[4])
    cv.rect(0, 3, w - 1, h - 3, WOOD[2])                 # 옆판
    for x in range(5, w - 1, 4):                         # 나뭇결
        cv.vline(x, 5, h - 5, WOOD[1])
    cv.vline(w - 2, 3, h - 3, WOOD[1])
    cv.rect(0, 3, 2, h - 3, WOOD[1])                     # 앞 기둥
    front_detail(cv)
    cv.rect(0, h - 3, w - 1, h - 3, WOOD[0])
    feet(cv, (0, w - 3), h - 2, h - 1)


def bookshelf_side(cv):
    rng = Rng("bookshelf_side")

    def front(c):
        for top in range(5, c.h - 5, 8):                 # 칸마다 삐져나온 책등
            for y in range(top, top + 5):
                c.put(1, y, BOOKS[rng.next(len(BOOKS))])
            c.hline(0, 2, top + 6, WOOD[3])
    _side_panel(cv, front)


def cabinet(cv):
    w, h = cv.w, cv.h
    cv.rect(0, 0, w - 1, 3, WOOD[3])                     # 머리
    cv.hline(1, w - 2, 1, WOOD[4])
    cv.rect(0, 4, w - 1, h - 3, WOOD[1])                 # 몸통
    mid = w // 2
    for x0, x1 in ((2, mid - 1), (mid + 1, w - 3)):      # 유리문 둘
        cv.rect(x0, 6, x1, 20, GLASS[0])
        cv.vline(x0, 6, 20, GLASS[1])
        cv.hline(x0, x1, 13, WOOD[2])                    # 안 선반
        for y, cols in ((9, (CREAM[1], BLUE[2])), (16, (GREEN[2], CREAM[2]))):
            cv.rect(x0 + 2, y, x0 + 3, y + 3, cols[0])   # 병·상자
            cv.rect(x1 - 2, y + 1, x1 - 1, y + 3, cols[1])
        cv.put(x0 + 1, 7, GLASS[2])                      # 유리 반사
        cv.put(x0 + 2, 8, GLASS[2])
    cv.vline(mid, 5, 21, WOOD[2])
    cv.rect(2, 23, w - 3, h - 5, WOOD[2])                # 서랍
    cv.hline(2, w - 3, 23, WOOD[3])
    cv.hline(mid - 2, mid + 1, 25, BRASS[2])
    cv.rect(0, h - 3, w - 1, h - 3, WOOD[0])
    feet(cv, (1, w - 3), h - 2, h - 1)


def cabinet_side(cv):
    def front(c):
        c.rect(0, 6, 1, 20, GLASS[1])                    # 유리문 단면
        c.put(0, 8, GLASS[2])
        c.rect(0, 23, 1, c.h - 5, WOOD[2])
        c.put(0, 25, BRASS[2])
    _side_panel(cv, front)


def crate(cv):
    w, h = cv.w, cv.h
    cv.rect(0, 0, w - 1, 5, WOOD[3])                     # 뚜껑(윗면)
    for x in range(4, w - 1, 5):
        cv.vline(x, 0, 5, WOOD[2])
    cv.hline(1, w - 2, 0, WOOD[4])
    cv.rect(0, 6, w - 1, h - 1, WOOD[2])                 # 앞면
    for y in range(9, h - 1, 5):                         # 널
        cv.hline(0, w - 1, y, WOOD[1])
    cv.rect(0, 6, 2, h - 1, WOOD[1])                     # 테
    cv.rect(w - 3, 6, w - 1, h - 1, WOOD[1])
    cv.rect(0, 6, w - 1, 7, WOOD[1])
    cv.rect(0, h - 2, w - 1, h - 1, WOOD[0])
    for i in range(h - 11):                              # X자 버팀
        y = 8 + i
        x = 3 + i * (w - 7) // (h - 11)
        cv.rect(x, y, x + 1, y, WOOD[3])
        cv.rect(w - 5 - (x - 3), y, w - 4 - (x - 3), y, WOOD[3])
    for x, y in ((1, 7), (w - 2, 7), (1, h - 3), (w - 2, h - 3)):
        cv.put(x, y, GREY[1])                            # 모서리 쇠


DRAW = {name: globals()[name] for name in SIZES}


def check(name, cv):
    opaque = [c for row in cv.px for c in row if c is not None]
    if len(opaque) < cv.w * cv.h // 4:
        raise SystemExit(f"{name}: 칠한 칸이 너무 적다 ({len(opaque)})")
    colors = set(opaque)
    if len(colors) > MAX_COLORS:
        raise SystemExit(f"{name}: 색이 {len(colors)}개 — {MAX_COLORS} 이하여야 한다")
    if OUTLINE not in colors:
        raise SystemExit(f"{name}: 윤곽이 없다")
    # 가장자리 네 변이 전부 비면 크기가 그림보다 크다는 뜻이다 — 배치가 어긋난다.
    for label, cells in (("위", cv.px[0]), ("아래", cv.px[-1]),
                         ("왼쪽", [r[0] for r in cv.px]), ("오른쪽", [r[-1] for r in cv.px])):
        if all(c is None for c in cells):
            raise SystemExit(f"{name}: {label} 변이 비었다 — 그림이 캔버스를 다 안 쓴다")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (w, h) in SIZES.items():
        cv = Canvas(w, h)
        DRAW[name](cv)
        cv.outline()
        check(name, cv)
        path = OUT / f"{name}.png"
        data = cv.rgba()
        if path.exists():
            ow, oh, old = read_png(path)
            if (ow, oh) == (w, h) and bytes(old) == data:
                print(f"{name}.png: 그대로")
                continue
        write_png(path, w, h, data)
        print(f"{name}.png: {w}x{h}, {len({c for r in cv.px for c in r if c})}색")


if __name__ == "__main__":
    main()
