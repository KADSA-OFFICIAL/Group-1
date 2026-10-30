#!/usr/bin/env python3
"""외부 가구 그림을 잘라 게임에 넣는다(#716, #717). 표준 라이브러리만.

    python3 tools/import_ext_sprites.py --darklight <Darklight 팩 폴더> --haunted <Haunted School 폴더> --horror <Horror 팩 폴더>

둘 중 하나만 줘도 된다 — 준 팩의 그림만 다시 굽는다.

- **Darklight Academia Furniture Pack**(kueyhorse, #716): 그림 한 장이 파일 하나다.
  투명 여백만 잘라 낸다.
- **Haunted School Tiles**(Thurraya, #717): RPG Maker MZ용 시트(`Inside_B.png`,
  48px 칸)다. 쓰는 칸의 **사각형을 손으로 적는다** — 시트의 그림끼리 붙어 있는
  곳(책상+의자 묶음)이 있어 자동으로 덩어리를 가르면 묶음이 쪼개지거나 이웃과 붙는다.
  자른 뒤 다시 투명 여백을 걷는다.

- **Top Down Pixel Art Horror**(AnisAous, #763): Haunted School과 같은 48px RPG Maker
  시트(`Inside_D.png`). 사물함·신발장 칸을 손으로 적는다.

출처·조건은 `CREDITS.md`. **원본 팩은 저장소에 넣지 않는다**(둘 다 원본 재배포 금지).
크기는 바꾸지 않는다 — 배율은 게임이 정한다(`gen_floors.EXT_SCALE`/`ext_scale()`).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_key_sprite import read_png, write_png  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets/sprites/ext"
ALPHA_MIN = 20

# 게임 안 이름 → 원본 파일. 이름은 `gen_floors`가 쓰는 이름과 같아야 한다.
DARKLIGHT = {
    "desk_exec": "diningTablelarge.png",      # 교장 책상
    "sofa_red": "RedSuite-export.png",        # 접견 소파
    "armchair_red": "RedSuiteOneSeater-export.png",
    "bookcase_tall": "BookshelfTall.png",
    "grandfather_clock": "grandfatherClock.png",
    "globe": "Globe.png",
    "floor_lamp": "standinglamp1.png",
    "vase_blue": "VaseBlue.png",
    "bed_green": "bedGreen.png",              # 보건실 침대
    "rug_long": "rugLong.png",
    # 단서(#723)
    "painting_dark": "painting1.png",         # 시우 그림 — 밤 풍경 액자
    "book_closed": "book.png",                # 인사 기록(서류철)
    "books_pile": "booksPile1.png",           # 대응 매뉴얼
    # 선반·캐비닛(#758) — **앞모습과 옆모습이 짝**이다. 옆벽(세로 벽)에 붙은 집기는
    # 옆모습, 가로로 긴 집기는 앞모습을 쓴다(`gen_floors.WALL_ART`).
    "dl_bookshelf": "bookshelf.png",
    "dl_bookshelf_side": "bookshelfSide.png",
    "dl_cabinet": "cabinet1.png",
    "dl_cabinet_side": "cabinet1Side.png",
    "dl_crate": "crate.png",                  # 창고 벽 줄 상자
}

# 게임 안 이름 → (시트, x0, y0, x1, y1) — 끝 좌표 포함.
# **`hs_` 앞머리가 배율을 정한다**(`gen_floors.ext_scale` — 1배).
HAUNTED = {
    # 학생 자리: 밝은 세로 책상 + 오른쪽 의자(앉은 사람이 왼쪽 칠판을 본다).
    "hs_student_desk": ("Inside_B.png", 243, 380, 286, 431),
    # 교탁: 짙은 책상 + 왼쪽 의자(칠판 쪽에서 학생을 본다).
    "hs_teacher_desk": ("Inside_B.png", 481, 385, 527, 431),
    # 교무실 섬 위 자리: 의자 위·책상 아래(칸막이를 향해 아래를 본다).
    "hs_office_desk_down": ("Inside_B.png", 387, 374, 430, 431),
    # 교무실 섬 아래 자리: 책상 위·의자 아래(칸막이를 향해 위를 본다).
    "hs_office_desk_up": ("Inside_B.png", 339, 396, 382, 445),
    # 단서(#723) — 작은 소품들. 게임에서는 2배로 놓는다(`gen_floors.CLUE_ART_SCALE`).
    "hs_calendar": ("Inside_B.png", 394, 102, 421, 135),       # 날짜 벽
    "hs_id_card": ("Inside_B.png", 311, 125, 333, 137),        # 학생증
    "hs_bag_spilled": ("Inside_B.png", 294, 211, 333, 236),    # 소지품 봉투
    "hs_book_purple": ("Inside_B.png", 347, 210, 359, 226),    # 국어책
    "hs_books_green": ("Inside_B.png", 405, 206, 419, 227),    # 상담기록부
    "hs_book_open": ("Inside_B.png", 445, 210, 471, 227),      # 졸업앨범
    "hs_notebook": ("Inside_B.png", 391, 207, 403, 226),       # 수위 공책
    "hs_papers_pile": ("Inside_B.png", 341, 147, 381, 179),    # 사안 파일
    "hs_papers_two": ("Inside_B.png", 396, 157, 416, 175),     # 교장 편지(편지지 두 장)
    "hs_note_small": ("Inside_B.png", 362, 102, 374, 114),     # 태호 쪽지
    "hs_paper_crumpled": ("Inside_B.png", 348, 120, 374, 135), # 강유진 쪽지
    "hs_memo_grey": ("Inside_B.png", 317, 147, 328, 160),      # 신고 전단(인쇄물)
    "hs_frame_map": ("Inside_B.png", 438, 151, 474, 178),      # 사진 벽
    # 바닥(#725) — `Inside_A2.png`. **이어붙여도 이음매가 안 보이는 칸만** 고른다
    # (4x4로 이어붙여 눈으로 확인했다). 복도·교실은 외부 마루를 쓰지
    # 않는다(#733 — 사용자가 예전 절차 바닥을 골랐다). 카펫 두 장은 테두리 무늬가 칸마다 되풀이돼 안 쓴다.
    "hs_floor_planks_v": ("Inside_A2.png", 0, 48, 95, 143),      # 세로 마루
    "hs_floor_herringbone": ("Inside_A2.png", 192, 48, 287, 143),  # 헤링본 — 교무실
    "hs_floor_worn": ("Inside_A2.png", 0, 480, 95, 575),         # 낡은 마루 — 수위실
    "hs_floor_stone": ("Inside_A2.png", 192, 336, 287, 431),     # 회색 석재 — 창고·현관
    "hs_floor_tile_white": ("Inside_A2.png", 96, 480, 191, 575),  # 흰 타일 — 화장실
    # 벽 앞면(#727) — `Inside_A4.png` 크림색 벽의 **아랫부분 30줄**(크림 + 초록 징두리).
    # 팩의 벽은 96px 높이라 우리 앞면(`WALL_FACE` 34 - 그림자 4)에 맞춰 잘라 쓴다.
    "hs_wall_face": ("Inside_A4.png", 192, 195, 287, 224),
}

# Top Down Pixel Art Horror(#763) — (시트, x0, y0, x1, y1), 끝 좌표 포함. **칠이 벗겨진
# 어두운 사물함**이라 #721의 깨끗한 철제 사물함("분위기에 안 맞는다", #730)과 다르다.
HORROR = {
    "hr_locker_bank": ("Inside_D.png", 683, 301, 753, 372),   # 2단 3칸 사물함 — 앞모습
    "hr_locker_side": ("Inside_D.png", 401, 345, 417, 383),   # 키 큰 사물함 — 옆모습
    "hr_shoe_cubby": ("Inside_D.png", 446, 446, 521, 529),    # 신발 든 나무 신발장
}


def trim(w, h, px, x0=0, y0=0, x1=None, y1=None):
    """사각형 안에서 투명 여백을 걷어 낸 RGBA를 돌려준다."""
    x1 = w - 1 if x1 is None else x1
    y1 = h - 1 if y1 is None else y1
    pts = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)
           if px[(y * w + x) * 4 + 3] >= ALPHA_MIN]
    if not pts:
        raise SystemExit(f"빈 칸: {x0},{y0}~{x1},{y1}")
    ax0, ax1 = min(p[0] for p in pts), max(p[0] for p in pts)
    ay0, ay1 = min(p[1] for p in pts), max(p[1] for p in pts)
    cw, ch = ax1 - ax0 + 1, ay1 - ay0 + 1
    out = bytearray(cw * ch * 4)
    for y in range(ch):
        for x in range(cw):
            i = ((y + ay0) * w + (x + ax0)) * 4
            o = (y * cw + x) * 4
            out[o:o + 4] = px[i:i + 4]
    return cw, ch, bytes(out)


def main():
    args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
    if not args or set(args) - {"--darklight", "--haunted", "--horror"}:
        raise SystemExit(__doc__)
    OUT.mkdir(parents=True, exist_ok=True)
    if "--darklight" in args:
        src = pathlib.Path(args["--darklight"])
        for name, fname in DARKLIGHT.items():
            cw, ch, data = trim(*read_png(src / fname))
            write_png(OUT / f"{name}.png", cw, ch, data)
            print(f"{name}.png: {cw}x{ch}")
    for flag, table in (("--haunted", HAUNTED), ("--horror", HORROR)):
        if flag not in args:
            continue
        src = pathlib.Path(args[flag])
        sheets = {}
        for name, (sheet, x0, y0, x1, y1) in table.items():
            if sheet not in sheets:
                sheets[sheet] = read_png(src / sheet)
            w, h, px = sheets[sheet]
            cw, ch, data = trim(w, h, px, x0, y0, x1, y1)
            write_png(OUT / f"{name}.png", cw, ch, data)
            print(f"{name}.png: {cw}x{ch}")


if __name__ == "__main__":
    main()
