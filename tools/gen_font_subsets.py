#!/usr/bin/env python3
"""게임 폰트 셋을 쓰는 글자만 남긴 서브셋으로 굽는다 (#853).

원본은 assets/fonts/original/(.gdignore — Godot이 임포트하지 않고 배포본에도 안 들어간다)에
두고, 결과는 예전과 같은 경로 assets/fonts/<이름>.ttf에 쓴다. 경로가 같으므로 .import의
uid와 씬·스크립트의 참조가 그대로다.

  python3 tools/gen_font_subsets.py          # 굽기 (결정론적 — 입력이 같으면 바이트가 같다)
  python3 tools/gen_font_subsets.py --check  # 게임 문구의 글자가 서브셋에 다 있는지만 본다

문자 집합
  본문(NotoSansKR-VF): KS X 1001 한글 2350자 + 게임 문구에 쓰인 모든 문자 + EXTRA_RANGES.
    가변 축(wght)과 OpenType 레이아웃을 유지한다 — 자막·선택지·HUD가 FontVariation으로
    굵기를 바꾼다. 2350자를 넣는 것은 여유분이다(문구를 고칠 때마다 굽지 않아도 되게).
  연출(동해독도·연성): 게임 문구에 쓰인 문자 + EXTRA_RANGES. 2350자를 넣으면 2.70/2.11MB라
    절감의 대부분이 사라진다. 손으로 쓴 제목·버튼에만 쓰이고, 새 글자가 생기면 --check가 잡는다.

"게임 문구"는 TEXT_GLOBS 파일에 나오는 모든 문자다(주석 포함 — 넉넉한 쪽이 안전하다).

필요: fonttools (pip install fonttools)
"""
from __future__ import annotations

import glob
import io
import os
import sys

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ORIG_DIR = os.path.join(ROOT, "assets", "fonts", "original")
OUT_DIR = os.path.join(ROOT, "assets", "fonts")

# 게임에 실리는 문구가 들어 있는 파일. 층 씬·단서 후보는 gen_floors가 굽은 결과가 scenes/·
# scripts/에 커밋되므로 생성기 원본까지 볼 필요는 없지만, 굽기 전에 돌려도 맞도록 같이 본다.
TEXT_GLOBS = [
    "scenes/**/*.tscn",
    "scenes/**/*.tres",
    "scripts/**/*.gd",
    "assets/**/*.tres",
    "tools/story_objects.json",
    "tools/gen_floors.py",
    "tools/ci_smoke_scenes.gd",
    "project.godot",
]

# 문구에 아직 없어도 넣어 둘 범위 — 문장부호·화살표·도형 정도. 원본에 없는 것은 그냥 빠진다.
EXTRA_RANGES = [
    (0x0020, 0x007E),  # ASCII
    (0x00A0, 0x00FF),  # Latin-1 (·, × 등)
    (0x2010, 0x205E),  # 일반 문장부호 (— … ‘ ’ “ ” 등)
    (0x2190, 0x21FF),  # 화살표
    (0x25A0, 0x25FF),  # 도형 (▲▼◀▶ ■ ●)
    (0x3000, 0x303F),  # CJK 기호 (「」『』 〈〉)
    (0x3131, 0x318E),  # 한글 호환 자모 (ㅋㅋ, ㅠ)
]

# (파일 이름, KS X 1001 2350자 포함 여부)
FONTS = [
    ("NotoSansKR-VF.ttf", True),
    ("EastSeaDokdo-Regular.ttf", False),
    ("YeonSung-Regular.ttf", False),
]


def ksx1001_hangul() -> set[str]:
    out = set()
    for b1 in range(0xB0, 0xC9):
        for b2 in range(0xA1, 0xFF):
            try:
                out.add(bytes([b1, b2]).decode("euc-kr"))
            except UnicodeDecodeError:
                pass
    assert len(out) == 2350, len(out)
    return out


def game_text_chars() -> set[str]:
    chars: set[str] = set()
    for pattern in TEXT_GLOBS:
        for path in sorted(glob.glob(os.path.join(ROOT, pattern), recursive=True)):
            with open(path, encoding="utf-8", errors="ignore") as f:
                chars.update(f.read())
    # 제어 문자는 글리프가 아니다.
    return {c for c in chars if ord(c) >= 0x20}


def extra_chars() -> set[str]:
    return {chr(c) for lo, hi in EXTRA_RANGES for c in range(lo, hi + 1)}


def wanted(with_ks: bool) -> set[str]:
    s = game_text_chars() | extra_chars()
    if with_ks:
        s |= ksx1001_hangul()
    return s


def cmap_of(path: str) -> set[int]:
    return set(TTFont(path, lazy=True).getBestCmap().keys())


def bake(name: str, with_ks: bool) -> bytes:
    src = os.path.join(ORIG_DIR, name)
    have = cmap_of(src)
    codepoints = sorted(ord(c) for c in wanted(with_ks) if ord(c) in have)

    opts = subset.Options()
    opts.layout_features = ["*"]   # 커닝·합자·조합 — 한글 조합형 기능도 여기 있다
    opts.name_IDs = ["*"]          # 이름·라이선스 표기 그대로
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    opts.glyph_names = False
    opts.hinting = True

    # recalcTimestamp=False — head.modified를 원본 그대로 두어야 다시 구워도 바이트가 같다.
    font = TTFont(src, recalcTimestamp=False)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=codepoints)
    sub.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def check() -> int:
    """게임 문구에 쓰인 글자 중 원본 폰트에 있는 것이 서브셋에도 다 있는가."""
    text = game_text_chars()
    bad = 0
    for name, _ in FONTS:
        orig = cmap_of(os.path.join(ORIG_DIR, name))
        out_path = os.path.join(OUT_DIR, name)
        if not os.path.exists(out_path):
            print(f"[실패] {name}: 서브셋이 없다 — python3 tools/gen_font_subsets.py")
            bad += 1
            continue
        got = cmap_of(out_path)
        missing = sorted(c for c in text if ord(c) in orig and ord(c) not in got)
        if missing:
            bad += 1
            shown = "".join(missing[:40])
            print(f"[실패] {name}: 게임 문구의 {len(missing)}자가 서브셋에 없다: {shown}")
            print("       python3 tools/gen_font_subsets.py 로 다시 굽고 결과를 커밋할 것")
        else:
            print(f"[통과] {name}: 문구 글자 {len([c for c in text if ord(c) in orig])}자 전부 있음")
    return 1 if bad else 0


def main() -> int:
    if "--check" in sys.argv[1:]:
        return check()

    for name, with_ks in FONTS:
        data = bake(name, with_ks)
        # 자체 검사: 다시 읽히는가, 본문 폰트는 가변 축이 살아 있는가, 바이트가 결정론적인가.
        font = TTFont(io.BytesIO(data))
        if not font.getBestCmap():
            raise SystemExit(f"{name}: 빈 cmap")
        if name.startswith("NotoSansKR"):
            if "fvar" not in font or "wght" not in [a.axisTag for a in font["fvar"].axes]:
                raise SystemExit(f"{name}: 가변 축(wght)이 사라졌다")
        if bake(name, with_ks) != data:
            raise SystemExit(f"{name}: 같은 입력에서 바이트가 다르다(비결정적)")

        out_path = os.path.join(OUT_DIR, name)
        old = open(out_path, "rb").read() if os.path.exists(out_path) else None
        src_size = os.path.getsize(os.path.join(ORIG_DIR, name))
        state = "그대로" if old == data else "갱신"
        if old != data:
            with open(out_path, "wb") as f:
                f.write(data)
        print(f"{name}: {src_size / 1e6:.2f}MB -> {len(data) / 1e6:.2f}MB, "
              f"글리프 {len(font.getGlyphOrder())}개 ({state})")

    return check()


if __name__ == "__main__":
    sys.exit(main())
