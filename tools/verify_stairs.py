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

    print(f"계단 검사: 5개 층")
    if errors:
        print(f"\n오류 {len(errors)}건:")
        for e in errors:
            print("  -", e)
        return 1
    print("문제 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
