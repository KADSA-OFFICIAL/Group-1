#!/usr/bin/env python3
"""방·복도 집기(PC_/PV_)와 장식(PD_) 검사.

gen_floors.py의 add_props가 놓은 집기가 제자리를 벗어나거나, 벽·다른 집기와
겹치거나, 단서·은신처를 덮지 않는지 본다. 도달성 자체는 verify_floor_reach가
보므로 여기서는 "조사할 수 있는가"와 "겹치지 않는가"를 맡는다.

집기는 두 갈래다. 방 집기는 방 폴리곤 안에 온전히 들어가야 하고, 복도 집기
(Corr_*)는 반대로 어느 방에도 걸치지 않아야 한다 — 복도 벽에 붙는 사물함이라
방 안으로 파고들면 방이 좁아지고 문 앞을 막는다.
장식(PD_)은 충돌체가 없으므로 짝 검사에서 빼되, 벽·집기와 겹치는지는 본다.
집기 위 소품(PT_ — 책상 위 교과서, 선반의 책)은 반대로 어느 집기 안에 온전히
들어가야 한다. 미닫이 교실문(SDPanel*)은 닫힌 자리뿐 아니라 **열린 자리**도
본다 — 열렸을 때 사물함이나 집기에 겹치면 문이 가구를 뚫고 들어간다.

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

# 미닫이 교실문이 밀려나는 거리·방향은 씬의 travel 값에서 읽는다. 상수로 박으면
# 한 짝/두 짝, 미는 방향이 바뀔 때마다 조용히 어긋난다.
TRAVEL_RE = re.compile(
    r'\[node name="(SlideDoor_[^"]+)"[^\]]*\]\n(?:[^\[]*?)^travel = (-?[\d.]+)',
    re.M | re.S)

# 사선 벽 문은 세로로도 밀린다(#252). 축정렬 문에는 이 줄이 없어 0으로 본다.
TRAVEL_Y_RE = re.compile(
    r'\[node name="(SlideDoor_[^"]+)"[^\]]*\]\n(?:[^\[]*?)^travel_y = (-?[\d.]+)',
    re.M | re.S)

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
    decors: dict[str, tuple] = {}     # PD_ 이름 -> bbox (충돌 없는 장식)
    tops: dict[str, tuple] = {}       # PT_ 이름 -> bbox (집기 위 소품)
    panels: dict[str, list] = {}      # 미닫이 문짝 -> 폴리곤(사선이라 경계상자로 보면 안 된다)
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
            if name.startswith("PD_"):
                decors[name[3:]] = bbox(pts(poly_m.group(1)))
            elif name.startswith("PT_"):
                tops[name[3:]] = bbox(pts(poly_m.group(1)))
            else:
                visuals[name[3:]] = poly_m.group(1).strip()
        elif ntype == "CollisionPolygon2D" and parent != "PropBodies" and poly_m:
            if "SDPanel" in parent:
                panels[parent] = pts(poly_m.group(1))
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

    # 2. 방 집기는 방 안에, 복도 집기(Corr_*)는 방 밖에 있어야 한다
    for key, (x0, y0, x1, y1) in sorted(props.items()):
        # 1px 안쪽으로 재서 "벽면에 맞닿음"과 "방 안으로 침범"을 구분한다.
        # 점-다각형 판정은 경계를 안쪽으로 세므로, 복도 사물함의 아래 변이 방
        # 위 변과 같은 y면 그대로는 침범으로 잡힌다.
        e = 1.0
        corners = [(x0 + e, y0 + e), (x1 - e, y0 + e),
                   (x1 - e, y1 - e), (x0 + e, y1 - e)]
        in_room = any(all(inside(poly, cx, cy) for cx, cy in corners)
                      for poly in rooms.values())
        touches = any(any(inside(poly, cx, cy) for cx, cy in corners)
                      for poly in rooms.values())
        if key.startswith("Corr_"):
            if touches:
                errors.append(f"{tag}: 복도 집기 {key}가 방 안으로 들어갔다 "
                              f"({x0:.0f},{y0:.0f})")
        elif not in_room:
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
    #
    # 창가 조사(Window_*)는 뺀다(#274). 이 검사는 '걸어가서 조사할 수 있게
    # 집기에서 CLUE_CLEAR만큼 떨어져 있어라'는 뜻인데, 창가 조사는 **벽에 붙어
    # 있는 것이 정상**이다. 교실 창가는 원래 책상이 벽까지 들어차 있어
    # 어떤 좌표를 골라도 이 여유를 못 만든다.
    # 대신 실제로 다가갈 수 있는지는 verify_floor_reach가 도달 격자로 본다.
    for name, px, py in clues:
        # 집기 조사(Exam_, #301)도 뺀다 — **집기 위에 있는 것이 정상**이다.
        # 그 집기를 조사하라고 붙인 것이라 떨어져 있으면 오히려 이상하다.
        if name.startswith(("Window_", "Exam_")):
            continue
        for key, (x0, y0, x1, y1) in sorted(props.items()):
            if (x0 - CLUE_CLEAR < px < x1 + CLUE_CLEAR
                    and y0 - CLUE_CLEAR < py < y1 + CLUE_CLEAR):
                errors.append(f"{tag}: 집기 {key}가 {name}({px:.0f},{py:.0f})를 덮는다")

    # 6. 장식(PD_)은 충돌체가 없지만 벽·집기와 겹쳐 보이면 안 된다
    for key, (x0, y0, x1, y1) in sorted(decors.items()):
        quad = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        if any(sat_overlap(quad, w) for w in walls):
            errors.append(f"{tag}: 장식 {key}가 벽과 겹친다 ({x0:.0f},{y0:.0f})")
            continue
        for pkey, box in props.items():
            if overlap((x0, y0, x1, y1), box):
                errors.append(f"{tag}: 장식 {key}가 집기 {pkey}와 겹친다")
                break

    # 7. 집기 위 소품(PT_)은 어느 집기 안에 온전히 들어가야 한다
    for key, (x0, y0, x1, y1) in sorted(tops.items()):
        if not any(px0 - 0.5 <= x0 and x1 <= px1 + 0.5
                   and py0 - 0.5 <= y0 and y1 <= py1 + 0.5
                   for px0, py0, px1, py1 in props.values()):
            errors.append(f"{tag}: 소품 {key}가 어느 집기 위에도 없다 "
                          f"({x0:.0f},{y0:.0f})")

    # 8. 미닫이문이 열린 자리에서 집기와 겹치지 않는지
    travels = {m.group(1): float(m.group(2)) for m in TRAVEL_RE.finditer(text)}
    travel_ys = {m.group(1): float(m.group(2)) for m in TRAVEL_Y_RE.finditer(text)}
    for parent, panel in sorted(panels.items()):
        root = parent.split("/")[0]
        step = travels.get(root)
        if step is None:
            errors.append(f"{tag}: {root}에 travel 값이 없다")
            continue
        # 사선 벽 문짝은 평행사변형이다 — 경계상자로 보면 벽 아래 집기가 전부
        # 걸린 것처럼 나온다(#252). 벽 검사와 같은 분리축으로 본다.
        sy = travel_ys.get(root, 0.0)
        moved = [(x + step, y + sy) for x, y in panel]
        for pkey, raw in prop_polys.items():
            if sat_overlap(moved, pts(raw)):
                errors.append(f"{tag}: 열린 문 {parent}가 집기 {pkey}와 겹친다")
                break

    # 9. 커버리지 — 집기가 하나도 없는 방(경고)
    have = set()
    for key, (x0, y0, x1, y1) in props.items():
        if key.startswith("Corr_"):
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        for rname, poly in rooms.items():
            if inside(poly, cx, cy):
                have.add(rname)
                break
    bare = sorted(set(rooms) - have)
    corr = sum(1 for k in props if k.startswith("Corr_"))
    print(f"  {tag}: 집기 {len(props)}개(복도 {corr}) · 장식 {len(decors)}개, "
          f"방 {len(rooms)}개 중 {len(have)}개에 배치")
    if bare:
        warnings.append(f"{tag}: 집기 없는 방 {len(bare)}개 — {', '.join(bare)}")


def check_yard() -> None:
    """운동장(#356)은 방·복도가 없어 check()를 못 쓴다 — **집기끼리 겹치는지만** 본다.

    `build_yard()`가 소품마다 독립적인 루프로 좌표를 잡고 서로 확인하지 않아
    스탠드·나무·가로등·벤치가 세 쌍이나 파고들어 있었다(#361). 층 쪽은
    `add_props()`가 `sc.prop_rects`를 보며 피하지만 운동장은 그 경로를 안 탄다.
    """
    path = ROOT / "scenes/background/school_yard.tscn"
    if not path.exists():
        errors.append("school_yard.tscn이 없다 — gen_floors.py를 다시 돌려야 한다")
        return
    text = path.read_text(encoding="utf-8")
    pat = re.compile(r'\[node name="PC_(\w+)" type="CollisionPolygon2D" '
                     r'parent="PropBodies"\]\npolygon = PackedVector2Array\(([^)]*)\)')
    boxes = []
    for m in pat.finditer(text):
        nums = [float(v) for v in m.group(2).split(",")]
        xs, ys = nums[0::2], nums[1::2]
        boxes.append((m.group(1), min(xs), min(ys), max(xs), max(ys)))

    hits = 0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]:
                ox = min(a[3], b[3]) - max(a[1], b[1])
                oy = min(a[4], b[4]) - max(a[2], b[2])
                errors.append(f"운동장: {a[0]}와 {b[0]}가 겹친다 ({ox:.0f}x{oy:.0f}px)")
                hits += 1
    print(f"  운동장: 집기 {len(boxes)}개, 겹침 {hits}쌍")


def main() -> int:
    print("집기 검사: 5개 층 + 운동장")
    for fl in (1, 2, 3, 4, 5):
        check(fl)
    check_yard()
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
