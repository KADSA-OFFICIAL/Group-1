#!/usr/bin/env python3
"""외부 가구 그림을 잘라 게임에 넣는다(#716, #717). 표준 라이브러리만.

    python3 tools/import_ext_sprites.py --darklight <Darklight 팩 폴더> --haunted <Haunted School 폴더>

둘 중 하나만 줘도 된다 — 준 팩의 그림만 다시 굽는다.

- **Darklight Academia Furniture Pack**(kueyhorse, #716): 그림 한 장이 파일 하나다.
  투명 여백만 잘라 낸다.
- **Haunted School Tiles**(Thurraya, #717): RPG Maker MZ용 시트(`Inside_B.png`,
  48px 칸)다. 쓰는 칸의 **사각형을 손으로 적는다** — 시트의 그림끼리 붙어 있는
  곳(책상+의자 묶음)이 있어 자동으로 덩어리를 가르면 묶음이 쪼개지거나 이웃과 붙는다.
  자른 뒤 다시 투명 여백을 걷는다.

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
    if not args or set(args) - {"--darklight", "--haunted"}:
        raise SystemExit(__doc__)
    OUT.mkdir(parents=True, exist_ok=True)
    if "--darklight" in args:
        src = pathlib.Path(args["--darklight"])
        for name, fname in DARKLIGHT.items():
            cw, ch, data = trim(*read_png(src / fname))
            write_png(OUT / f"{name}.png", cw, ch, data)
            print(f"{name}.png: {cw}x{ch}")
    if "--haunted" in args:
        src = pathlib.Path(args["--haunted"])
        sheets = {}
        for name, (sheet, x0, y0, x1, y1) in HAUNTED.items():
            if sheet not in sheets:
                sheets[sheet] = read_png(src / sheet)
            w, h, px = sheets[sheet]
            cw, ch, data = trim(w, h, px, x0, y0, x1, y1)
            write_png(OUT / f"{name}.png", cw, ch, data)
            print(f"{name}.png: {cw}x{ch}")


if __name__ == "__main__":
    main()
