#!/usr/bin/env python3
"""외부 가구 그림을 잘라 게임에 넣는다(#716). 표준 라이브러리만.

    python3 tools/import_ext_sprites.py <Darklight Academia Furniture Pack 폴더>

원본은 kueyhorse의 "Darklight Academia Furniture Pack"(무료판, 비상업)이다 —
출처·조건은 `CREDITS.md`. **원본 팩은 저장소에 넣지 않는다**(재배포 금지).
쓰는 그림만 투명 여백을 잘라 `assets/sprites/ext/`에 둔다.

**자르기만 하고 크기는 바꾸지 않는다.** 원본이 32px 칸에 그린 도트라 게임에서는
정수 2배(`gen_floors.EXT_SCALE`)로 놓는다 — 월드의 도트 한 칸(2px)과 같다.
상자에 맞춰 늘리면(예전 `obj_*` 방식) 도트 폭이 들쭉날쭉해진다.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_key_sprite import read_png, write_png  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets/sprites/ext"
ALPHA_MIN = 20

# 게임 안 이름 → 원본 파일. 이름은 `gen_floors.EXT_SPRITE_FILES`와 같아야 한다.
PICKS = {
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


def crop(path):
    w, h, px = read_png(path)
    pts = [(x, y) for y in range(h) for x in range(w) if px[(y * w + x) * 4 + 3] >= ALPHA_MIN]
    if not pts:
        raise SystemExit(f"{path.name}: 빈 그림")
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    cw, ch = x1 - x0 + 1, y1 - y0 + 1
    out = bytearray(cw * ch * 4)
    for y in range(ch):
        for x in range(cw):
            i = ((y + y0) * w + (x + x0)) * 4
            o = (y * cw + x) * 4
            out[o:o + 4] = px[i:i + 4]
    return cw, ch, bytes(out)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    src = pathlib.Path(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fname in PICKS.items():
        cw, ch, data = crop(src / fname)
        write_png(OUT / f"{name}.png", cw, ch, data)
        print(f"{name}.png: {cw}x{ch}")


if __name__ == "__main__":
    main()
