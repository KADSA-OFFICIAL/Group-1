#!/usr/bin/env python3
"""방 안 집기(PC_/PV_) 검사.

gen_floors.py의 add_props가 놓은 집기가 방 밖으로 나가거나, 벽·다른 집기와
겹치거나, 단서·은신처를 덮지 않는지 본다. 도달성 자체는 verify_floor_reach가
보므로 여기서는 "조사할 수 있는가"와 "겹치지 않는가"를 맡는다.

Godot 없이 도는 정적 검사.
  python3 tools/verify_props.py
종료 코드: 오류 0건이면 0, 있으면 1
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 단서·은신처 Area2D 중심에서 이만큼은 집기가 없어야 상호작용 존(48×48)이 열린다.
CLUE_CLEAR = 30

NODE_RE = re.compile(
    r'\[node name="([^"]+)" type="(\w+)" parent="([^"]*)"\]\n(.*?)(?=\n\[node|\Z)', re.S)
POLY_RE = re.compile(r'polygon = PackedVector2Array\(([^)]*)\)')
POS_RE = re.compile(r'^position = Vector2\(([-\d.]+), ([-\d.]+)\)', re.M)

errors: list[str] = []
warnings: list[str] = []


def pts(raw: str) -> list[tuple[float, float]]:
    v = [float(x) for x in raw.split(",")]
    return list(zip(v[0::2], v[1::2]))


def bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def overlap(a, b, eps: float = 0.5) -> bool:
    return not (a[2] - eps <= b[0] or b[2] - eps <= a[0]
                or a[3] - eps <= b[1] or b[3] - eps <= a[1])


def sat_overlap(a, b, eps: float = 0.5) -> bool:
    """볼록 폴리곤 두 개의 겹침(분리축 정리).

    벽은 사선(평행사변형)이 섞여 있어 경계상자로 비교하면 교무실·사선 화장실이
    통째로 겹친 것처럼 나온다. eps만큼 줄여 맞닿은 경우는 겹침으로 보지 않는다.
    """
    for poly in (a, b):
        n = len(poly)
        for i in range(n):
            x0, y0 = poly[i]
            x1, y1 = poly[(i + 1) % n]
            ax, ay = -(y1 - y0), x1 - x0
            length = (ax * ax + ay * ay) ** 0.5
            if length == 0:
                continue
            ax, ay = ax / length, ay / length
            pa = [ax * px + ay * py for px, py in a]
            pb = [ax * px + ay * py for px, py in b]
            if min(pa) >= max(pb) - eps or min(pb) >= max(pa) - eps:
                return False
    return True


def inside(poly, x, y) -> bool:
    c = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xin = (x1 - x0) * (y - y0) / (y1 - y0) + x0
            if x < xin:
                c = not c
    return c


def check(fl: int) -> None:
    path = ROOT / f"scenes/background/school_floor_{fl}.tscn"
    text = path.read_text(encoding="utf-8")
    tag = f"floor{fl}"

    props: dict[str, tuple] = {}      # PC_ 이름 -> bbox
    visuals: dict[str, str] = {}      # PV_ 이름 -> polygon 원문
    prop_polys: dict[str, str] = {}
    walls: list[list] = []
    rooms: dict[str, list] = {}
    clues: list[tuple[str, float, float]] = []

    for name, ntype, parent, body in NODE_RE.findall(text):
        poly_m = POLY_RE.search(body)
        if ntype == "CollisionPolygon2D" and parent == "PropBodies":
            props[name[3:]] = bbox(pts(poly_m.group(1)))
            prop_polys[name[3:]] = poly_m.group(1).strip()
        elif ntype == "Polygon2D" and parent == "Props":
            visuals[name[3:]] = poly_m.group(1).strip()
        elif ntype == "CollisionPolygon2D" and parent != "PropBodies" and poly_m:
            walls.append(pts(poly_m.group(1)))
        elif ntype == "Polygon2D" and parent == "Rooms" and poly_m:
            rooms[name] = pts(poly_m.group(1))
        elif ntype == "Area2D" and parent == "." and "script" in body:
            pos = POS_RE.search(body)
            if pos:
                clues.append((name, float(pos.group(1)), float(pos.group(2))))

    # 1. 충돌 PC_ ↔ 시각 PV_ 1:1, 폴리곤 동일
    for key in sorted(set(props) | set(visuals)):
        if key not in visuals:
            errors.append(f"{tag}: PC_{key}에 대응하는 PV_{key}가 없다")
        elif key not in props:
            errors.append(f"{tag}: PV_{key}에 대응하는 PC_{key}가 없다")
        elif prop_polys[key] != visuals[key]:
            errors.append(f"{tag}: PC_{key}와 PV_{key}의 폴리곤이 다르다")

    # 2. 집기는 어느 방 안에 온전히 들어가야 한다
    for key, (x0, y0, x1, y1) in sorted(props.items()):
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        if not any(all(inside(poly, cx, cy) for cx, cy in corners)
                   for poly in rooms.values()):
            errors.append(f"{tag}: 집기 {key}가 방 안에 온전히 들어 있지 않다 "
                          f"({x0:.0f},{y0:.0f})")

    # 3. 벽과 겹치지 않는다 (사선 벽이 있어 분리축으로 본다)
    for key, (x0, y0, x1, y1) in sorted(props.items()):
        quad = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        for w in walls:
            if sat_overlap(quad, w):
                errors.append(f"{tag}: 집기 {key}가 벽과 겹친다 "
                              f"({x0:.0f},{y0:.0f})")
                break

    # 4. 집기끼리 겹치지 않는다
    items = sorted(props.items())
    for i, (ka, a) in enumerate(items):
        for kb, b in items[i + 1:]:
            if overlap(a, b):
                errors.append(f"{tag}: 집기 {ka}와 {kb}가 겹친다")

    # 5. 단서·은신처를 덮지 않는다
    for name, px, py in clues:
        for key, (x0, y0, x1, y1) in sorted(props.items()):
            if (x0 - CLUE_CLEAR < px < x1 + CLUE_CLEAR
                    and y0 - CLUE_CLEAR < py < y1 + CLUE_CLEAR):
                errors.append(f"{tag}: 집기 {key}가 {name}({px:.0f},{py:.0f})를 덮는다")

    # 6. 커버리지 — 집기가 하나도 없는 방(경고)
    have = set()
    for key, (x0, y0, x1, y1) in props.items():
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for rname, poly in rooms.items():
            if inside(poly, cx, cy):
                have.add(rname)
                break
    bare = sorted(set(rooms) - have)
    print(f"  {tag}: 집기 {len(props)}개, 방 {len(rooms)}개 중 {len(have)}개에 배치")
    if bare:
        warnings.append(f"{tag}: 집기 없는 방 {len(bare)}개 — {', '.join(bare)}")


def main() -> int:
    print("집기 검사: 5개 층")
    for fl in (1, 2, 3, 4, 5):
        check(fl)
    if warnings:
        print("\n경고 " + str(len(warnings)) + "건:")
        for w in warnings:
            print(f"  - {w}")
    if errors:
        print("\n오류 " + str(len(errors)) + "건:")
        for e in errors[:30]:
            print(f"  - {e}")
        if len(errors) > 30:
            print(f"  … 외 {len(errors) - 30}건")
        return 1
    print("\n문제 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
