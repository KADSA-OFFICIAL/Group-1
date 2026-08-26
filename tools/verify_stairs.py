#!/usr/bin/env python3
"""floor_manager.gd의 계단 좌표가 실제 층 씬과 맞는지 대조한다 (#159 P2).

계단실 좌표가 층마다 다르므로(1층은 1곳·위치도 다름) 상수와 씬이 어긋나면
플레이어가 층 전환 존을 밟지 못하거나 벽 속에 도착한다. 이 검사는
- STAIRS의 사각형이 씬의 Slab_Stair* 폴리곤과 일치하는지
- 파생된 트리거 존이 계단실 안(반쪽별)에 들어가는지
- 도착 지점이 벽·방 안이 아닌 통행 가능한 곳인지
를 Godot 없이 확인한다.
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
GD = ROOT / "scripts/game/floor_manager.gd"

WALL_T, RAIL_HALF, ZONE_H, ARRIVE_DY, ARRIVE_DX = 16.0, 8.0, 54.0, 28.0, 59.0

errors = []


def fail(msg):
    errors.append(msg)


def parse_rects():
    """STAIRS = {층: [Rect2(...), ...]} 를 GDScript에서 읽는다."""
    text = GD.read_text()
    named = dict(re.findall(r"const (STAIR_[AB]) := Rect2\(([^)]*)\)", text))
    named = {k: [float(v) for v in v.split(",")] for k, v in named.items()}

    block = re.search(r"const STAIRS := \{(.*?)\n\}", text, re.S)
    if not block:
        fail("floor_manager.gd에서 STAIRS를 찾지 못했다")
        return {}
    out = {}
    for line in block.group(1).splitlines():
        m = re.match(r"\s*(\d+):\s*\[(.*)\],", line)
        if not m:
            continue
        rects = []
        for item in re.findall(r"STAIR_[AB]|Rect2\([^)]*\)", m.group(2)):
            if item.startswith("STAIR_"):
                rects.append(named[item])
            else:
                rects.append([float(v) for v in item[6:-1].split(",")])
        out[int(m.group(1))] = rects
    return out


def scene_slabs(fl):
    """씬의 Slab_Stair* 폴리곤 → (x,y,w,h) 목록."""
    t = (ROOT / f"scenes/background/school_floor_{fl}.tscn").read_text()
    out = []
    for m in re.finditer(
            r'name="Slab_(Stair\w*)" type="Polygon2D"[^\[]*?polygon = PackedVector2Array\(([^)]*)\)',
            t, re.S):
        v = [float(x) for x in m.group(2).split(",")]
        xs, ys = v[0::2], v[1::2]
        out.append((m.group(1), min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
    return sorted(out, key=lambda s: (s[2], s[1]))


def walls(fl):
    t = (ROOT / f"scenes/background/school_floor_{fl}.tscn").read_text()
    out = []
    for m in re.finditer(
            r'name="(?:WC_|RC_)\w+" type="CollisionPolygon2D"[^\[]*?polygon = PackedVector2Array\(([^)]*)\)',
            t, re.S):
        v = [float(x) for x in m.group(1).split(",")]
        xs, ys = v[0::2], v[1::2]
        out.append((min(xs), min(ys), max(xs), max(ys)))
    return out


def _check_yard(fail):
    """운동장(#356) — floor_manager의 상수가 생성기·씬과 맞는지 본다.

    운동장은 층과 크기가 다르다(3400x1700). `FLOOR_BOUNDS`와 `YARD_ARRIVE`가
    어긋나면 카메라가 씬 밖을 비추거나 플레이어가 벽 속에 등장한다 — 둘 다
    실행해 봐야만 보이는 종류라 여기서 정적으로 잡는다.
    """
    import re as _re
    gen = (ROOT / "tools/gen_floors.py").read_text(encoding="utf-8")
    m = _re.search(r"^YW, YH = (\d+), (\d+)", gen, _re.M)
    a = _re.search(r"^YARD_ARRIVE = \(([\d.]+), ([\d.]+)\)", gen, _re.M)
    if m is None or a is None:
        fail("gen_floors.py에서 YW/YH 또는 YARD_ARRIVE를 못 찾았다")
        return
    yw, yh = int(m.group(1)), int(m.group(2))
    ax, ay = float(a.group(1)), float(a.group(2))

    fm = (ROOT / "scripts/game/floor_manager.gd").read_text(encoding="utf-8")
    b = _re.search(r"0: Rect2\(0, 0, (\d+), (\d+)\)", fm)
    if b is None:
        fail("floor_manager.gd에서 운동장 FLOOR_BOUNDS를 못 찾았다")
    elif (int(b.group(1)), int(b.group(2))) != (yw, yh):
        fail(f"운동장 카메라 한계 {b.group(1)}x{b.group(2)} != 씬 {yw}x{yh}")
    v = _re.search(r"const YARD_ARRIVE := Vector2\(([\d.]+), ([\d.]+)\)", fm)
    if v is None:
        fail("floor_manager.gd에서 YARD_ARRIVE를 못 찾았다")
    elif (float(v.group(1)), float(v.group(2))) != (ax, ay):
        fail(f"운동장 등장 지점 {v.group(1)},{v.group(2)} != 생성기 {ax},{ay}")

    # 옆문 등장 지점(#393)은 floor_manager가 아니라 **문 노드가 들고 있다**
    # (`exit_door.gd`의 arrive_at). 상수를 한 벌 더 두는 대신 씬 값과 대조한다.
    side = _re.search(r"^YARD_SIDE_ARRIVE = \(([\d.]+), ([\d.]+)\)", gen, _re.M)
    if side is None:
        fail("gen_floors.py에서 YARD_SIDE_ARRIVE를 못 찾았다")
        return
    sx, sy = float(side.group(1)), float(side.group(2))
    f1 = (ROOT / "scenes/background/school_floor_1.tscn").read_text(encoding="utf-8")
    d = _re.search(r'name="YardGateDoor"[^\[]*?arrive_at = Vector2\(([-\d.]+), ([-\d.]+)\)',
                   f1, _re.S)
    if d is None:
        fail("1층에 운동장 출입구 문(YardGateDoor)의 arrive_at이 없다")
    elif (float(d.group(1)), float(d.group(2))) != (sx, sy):
        fail(f"옆문 등장 지점 {d.group(1)},{d.group(2)} != 생성기 {sx},{sy}")

    path = ROOT / "scenes/background/school_yard.tscn"
    if not path.exists():
        fail("school_yard.tscn이 없다 — gen_floors.py를 다시 돌려야 한다")
        return
    text = path.read_text(encoding="utf-8")
    if '[node name="FrontGate" type="Area2D"' not in text:
        fail("운동장에 정문(FrontGate)이 없다")
    # 문 자리는 둘이다(#393). 둘 다 나온 뒤에는 벽으로 막혀 있어야 한다.
    for seal in ("WC_PorchSeal", "WC_SideSeal"):
        if f'name="{seal}"' not in text:
            fail(f"운동장 정면에 {seal}이 없다 — 나온 문이 뚫린 채로 남는다")

    # 등장 지점이 집기 안이면 플레이어가 끼인 채로 씬이 시작된다. 운동장 집기는
    # `add_props()`를 안 타서 서로도 등장 지점도 피해 주지 않는다(#361과 같은
    # 이유) — 그래서 여기서 본다. 여유는 충돌 캡슐 반경(8)에 슬랙을 얹은 값.
    pad = 12.0
    props = []
    for pm in _re.finditer(
            r'name="(PC_\w+)" type="CollisionPolygon2D"[^\[]*?'
            r'polygon = PackedVector2Array\(([^)]*)\)', text, _re.S):
        nums = [float(x) for x in pm.group(2).split(",")]
        xs, ys = nums[0::2], nums[1::2]
        props.append((pm.group(1), min(xs), min(ys), max(xs), max(ys)))
    for label, (px, py) in (("현관", (ax, ay)), ("옆문", (sx, sy))):
        if not (0 < px < yw and 0 < py < yh):
            fail(f"{label} 등장 지점 {px},{py}이 운동장(0,0~{yw},{yh}) 밖이다")
        for nm, x0, y0, x1, y1 in props:
            if x0 - pad < px < x1 + pad and y0 - pad < py < y1 + pad:
                fail(f"{label} 등장 지점 {px},{py}이 집기 {nm} 안이다")


def main():
    stairs = parse_rects()
    if not stairs:
        print("\n".join(errors)); return 1

    for fl in (1, 2, 3, 4, 5):
        declared = stairs.get(fl, [])
        actual = scene_slabs(fl)
        if len(declared) != len(actual):
            fail(f"floor{fl}: STAIRS {len(declared)}개 vs 씬 계단실 {len(actual)}개")
            continue
        for (name, sx, sy, sw, sh), d in zip(actual, declared):
            if [sx, sy, sw, sh] != d:
                fail(f"floor{fl} {name}: 씬 {[sx,sy,sw,sh]} vs STAIRS {d}")

        ws = walls(fl)
        for i, d in enumerate(declared):
            x, y, w, h = d
            mid = x + w / 2.0
            y_end = y + h - WALL_T
            zones = {
                "up": (x + WALL_T, y_end - ZONE_H, mid - RAIL_HALF, y_end),
                "down": (mid + RAIL_HALF, y_end - ZONE_H, x + w - WALL_T, y_end),
            }
            for tag, (zx0, zy0, zx1, zy1) in zones.items():
                if zx1 <= zx0 or zy1 <= zy0:
                    fail(f"floor{fl} 계단{i} {tag} 존 크기가 0 이하")
                for wx0, wy0, wx1, wy1 in ws:
                    if zx0 < wx1 and wx0 < zx1 and zy0 < wy1 and wy0 < zy1:
                        fail(f"floor{fl} 계단{i} {tag} 존이 벽과 겹친다")
                        break
            # 도착 지점(이 층으로 올라온/내려온 경우 모두)이 벽 속이 아닌지
            for up in (True, False):
                ax = mid + (ARRIVE_DX if up else -ARRIVE_DX)
                ay = y - ARRIVE_DY
                for wx0, wy0, wx1, wy1 in ws:
                    if wx0 <= ax <= wx1 and wy0 <= ay <= wy1:
                        fail(f"floor{fl} 계단{i} 도착지점({ax:.0f},{ay:.0f})이 벽 안")
                        break

    _check_yard(fail)

    print(f"계단 검사: 5개 층 + 운동장")
    if errors:
        print(f"\n오류 {len(errors)}건:")
        for e in errors:
            print("  -", e)
        return 1
    print("문제 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
