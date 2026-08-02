#!/usr/bin/env python3
"""층 씬의 도달성 검사 (#159).

충돌 폴리곤(WC_*/RC_*)과 외벽을 격자에 래스터화한 뒤 BFS로,
- 시작 지점에서 각 방(Rooms 폴리곤 중심)에 닿는지
- 막힌 공간(Blocked*)과 건물 밖 공백이 정말 닫혀 있는지
를 확인한다. Godot 없이 도는 정적 검사.
"""
import re, sys, pathlib, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
CELL = 20
PLAYER_R = 10       # 플레이어 캡슐 반경 — 벽을 이만큼 부풀려 통과 가능성을 보수적으로 본다

node_re = re.compile(
    r'\[node name="([^"]+)" type="(CollisionPolygon2D|Polygon2D)" parent="([^"]*)"\]\n'
    r'(?:[^\[]*?)polygon = PackedVector2Array\(([^)]*)\)', re.S)


def parse(path):
    text = path.read_text()
    walls, rooms = [], {}
    for m in node_re.finditer(text):
        name, ntype, parent, nums = m.group(1), m.group(2), m.group(3), m.group(4)
        pts = [float(v) for v in nums.split(",")]
        poly = list(zip(pts[0::2], pts[1::2]))
        if ntype == "CollisionPolygon2D" and (name.startswith("WC_") or name.startswith("RC_")):
            walls.append(poly)
        elif ntype == "Polygon2D" and parent == "Rooms":
            rooms[name] = poly
    size = re.search(r'name="Floor".*?polygon = PackedVector2Array\(([^)]*)\)', text, re.S)
    fp = [float(v) for v in size.group(1).split(",")]
    return walls, rooms, (max(fp[0::2]), max(fp[1::2]))


def inside(poly, x, y):
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


def bbox(poly, pad=0.0):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def build_grid(walls, w, h):
    cols, rows = int(w // CELL) + 1, int(h // CELL) + 1
    blocked = [[False] * cols for _ in range(rows)]
    for poly in walls:
        bx0, by0, bx1, by1 = bbox(poly, PLAYER_R)
        for r in range(max(0, int(by0 // CELL)), min(rows, int(by1 // CELL) + 1)):
            for c in range(max(0, int(bx0 // CELL)), min(cols, int(bx1 // CELL) + 1)):
                if blocked[r][c]:
                    continue
                cx, cy = c * CELL + CELL / 2, r * CELL + CELL / 2
                # 부풀린 벽: 셀 중심이 폴리곤 안이거나 경계에서 PLAYER_R 이내면 막힘
                if inside(poly, cx, cy) or (bx0 <= cx <= bx1 and by0 <= cy <= by1
                                            and _near(poly, cx, cy, PLAYER_R)):
                    blocked[r][c] = True
    # 바깥 테두리는 외벽
    for r in range(rows):
        blocked[r][0] = blocked[r][cols - 1] = True
    for c in range(cols):
        blocked[0][c] = blocked[rows - 1][c] = True
    return blocked, cols, rows


def _near(poly, x, y, d):
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / L2))
        px, py = x0 + t * dx, y0 + t * dy
        if (px - x) ** 2 + (py - y) ** 2 <= d * d:
            return True
    return False


def flood(blocked, cols, rows, start):
    sc, sr = int(start[0] // CELL), int(start[1] // CELL)
    if blocked[sr][sc]:
        # 시작점이 벽이면 근처 빈 칸 탐색
        found = None
        for rad in range(1, 25):
            for dr in range(-rad, rad + 1):
                for dc in range(-rad, rad + 1):
                    r, c = sr + dr, sc + dc
                    if 0 <= r < rows and 0 <= c < cols and not blocked[r][c]:
                        found = (r, c); break
                if found: break
            if found: break
        if not found:
            return set()
        sr, sc = found
    seen = {(sr, sc)}
    q = collections.deque([(sr, sc)])
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and not blocked[nr][nc] and (nr, nc) not in seen:
                seen.add((nr, nc)); q.append((nr, nc))
    return seen


def main():
    bad = 0
    for fl in (1, 2, 3, 4, 5):
        path = ROOT / f"scenes/background/school_floor_{fl}.tscn"
        walls, rooms, (w, h) = parse(path)
        blocked, cols, rows = build_grid(walls, w, h)
        # 시작: 북쪽 복도 한가운데(1층은 상단 복도)
        start = (200, 700) if fl != 1 else (200, 1700)
        seen = flood(blocked, cols, rows, start)
        print(f"floor{fl}: 벽 {len(walls)}개, 도달 셀 {len(seen)}/{cols*rows}")

        for name, poly in sorted(rooms.items()):
            cx = sum(p[0] for p in poly) / len(poly)
            cy = sum(p[1] for p in poly) / len(poly)
            r, c = int(cy // CELL), int(cx // CELL)
            reach = (r, c) in seen
            want_closed = name.startswith("Blocked") or name == "YardExit"
            if want_closed and reach:
                print(f"   ✗ {name}: 막혀 있어야 하는데 도달됨"); bad += 1
            elif not want_closed and not reach:
                print(f"   ✗ {name}: 도달 불가"); bad += 1
    print("\n문제 없음" if bad == 0 else f"\n문제 {bad}건")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
