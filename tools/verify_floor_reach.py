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
        # 벽(WC_/RC_)뿐 아니라 계단 자물쇠 배리어(SUBarrierCollision 등) 같은
        # 모든 정적 충돌 폴리곤을 막힌 것으로 본다. 접두사만 보면 배리어를 놓쳐
        # "잠긴 계단도 도달 가능"으로 잘못 통과한다(#159 P3에서 발견).
        # 미닫이 교실문(SDPanel*)은 다가오면 열리므로 막힌 것으로 보지 않는다.
        # 이 이름 규칙은 scripts/interactions/sliding_door.gd·janitor.gd·
        # verify_janitor_route.py와 공유한다.
        if ntype == "CollisionPolygon2D" and "SDPanel" not in parent:
            walls.append(poly)
        elif ntype == "Polygon2D" and parent == "Rooms":
            rooms[name] = poly
    size = re.search(r'name="Floor".*?polygon = PackedVector2Array\(([^)]*)\)', text, re.S)
    fp = [float(v) for v in size.group(1).split(",")]
    return walls, rooms, (max(fp[0::2]), max(fp[1::2])), windows(text)


window_re = re.compile(
    r'\[node name="(Window_[^"]+)" type="Area2D" parent="\."\]\n'
    r'position = Vector2\(([-\d.]+), ([-\d.]+)\)')


def windows(text):
    """창가 조사(#274)의 위치. 벽에 붙어 있어 verify_props의 여유 검사에서
    빠지는 대신, 여기서 도달 격자로 실제로 다가갈 수 있는지 본다."""
    return [(m.group(1), float(m.group(2)), float(m.group(3)))
            for m in window_re.finditer(text)]


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


# 도입부 4층(#405)의 시드 — 미술실 안. main.tscn의 시작 위치와 같다.
INTRO_START = (300, 700)


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


def check_camera(sizes):
    """카메라 한계가 맵 캔버스와 맞는지. 어긋나면 맵 끝에서 카메라가 밖을 비춘다.

    한계는 두 곳에서 온다 — `player.tscn`의 기본값과, 층마다 그것을 덮어쓰는
    `floor_manager`의 `FLOOR_BOUNDS`(#356). 크기가 다른 층(운동장 3400x1700,
    도입부 1800x1000)은 후자에 적혀 있어야 한다.
    """
    text = (ROOT / "scenes/player/player.tscn").read_text(encoding="utf-8")
    lim = {}
    for key in ("limit_left", "limit_top", "limit_right", "limit_bottom"):
        m = re.search(rf"^{key} = (-?\d+)$", text, re.M)
        if m:
            lim[key] = int(m.group(1))
    if len(lim) != 4:
        print("   ✗ player.tscn에서 카메라 limit_*를 찾지 못했다")
        return 1
    default = (lim["limit_right"], lim["limit_bottom"])

    fm = (ROOT / "scripts/game/floor_manager.gd").read_text(encoding="utf-8")
    bounds = {}
    blk = re.search(r"const FLOOR_BOUNDS := \{(.*?)\}", fm, re.S)
    if blk:
        for fl, w, h in re.findall(r"(\d+)\s*:\s*Rect2\(0,\s*0,\s*(\d+),\s*(\d+)\)",
                                   blk.group(1)):
            bounds[int(fl)] = (int(w), int(h))

    bad = 0
    if (lim["limit_left"], lim["limit_top"]) != (0, 0):
        print(f"   ✗ 카메라 원점이 0,0이 아니다 ({lim['limit_left']},{lim['limit_top']})")
        bad += 1
    for fl, (w, h) in sizes.items():
        want = bounds.get(fl, default)
        if want != (int(w), int(h)):
            where = f"FLOOR_BOUNDS[{fl}]" if fl in bounds else "player.tscn 기본값"
            print(f"   ✗ floor{fl} 카메라 한계 {want[0]}x{want[1]}({where}) "
                  f"≠ 맵 {int(w)}x{int(h)}")
            bad += 1
    return bad


def main():
    bad = 0
    sizes = {}
    for fl in (1, 2, 3, 4):
        path = ROOT / f"scenes/background/school_floor_{fl}.tscn"
        walls, rooms, (w, h), wins = parse(path)
        sizes[fl] = (w, h)
        blocked, cols, rows = build_grid(walls, w, h)
        # 시작: 북쪽 복도 한가운데(1층은 상단 복도)
        # 시드는 그 층에서 확실히 걸을 수 있는 자리. 1층 시드는 복도 안이다 —
        # 캔버스가 3400x1500으로 줄고(#498) 복도가 620~800으로 올라왔다.
        # 710이 그 한가운데다(#479 1800 → #495 1940 → #498 620~800).
        # 1층은 아래쪽 절반만
        # 건물이고, 4층은 도입부라 캔버스 자체가 작다(#405).
        start = {1: (200, 710), 4: INTRO_START}.get(fl, (200, 700))
        seen = flood(blocked, cols, rows, start)
        print(f"floor{fl}: 벽 {len(walls)}개, 도달 셀 {len(seen)}/{cols*rows}")

        for name, poly in sorted(rooms.items()):
            cx = sum(p[0] for p in poly) / len(poly)
            cy = sum(p[1] for p in poly) / len(poly)
            r, c = int(cy // CELL), int(cx // CELL)
            reach = (r, c) in seen
            # 운동장 출입구는 #393에서 열렸다 — 두 번째 탈출 루트라
            # 복도에서 걸어 들어갈 수 있어야 한다. 이제 막힌 방은
            # 이름 없는 Blocked* 뿐이다.
            want_closed = name.startswith("Blocked")
            if want_closed and reach:
                print(f"   ✗ {name}: 막혀 있어야 하는데 도달됨"); bad += 1
            elif not want_closed and not reach:
                print(f"   ✗ {name}: 도달 불가"); bad += 1

        # 창가 조사(#274)에 다가갈 수 있는가. 플레이어의 InteractionArea는
        # 24x24, 창가 조사 범위는 170x52 — 중심 간 거리가 (12+85, 12+26)
        # 안이면 겹친다. 도달 가능한 셀 하나라도 그 안에 있으면 된다.
        for name, px, py in wins:
            if not any(abs((c + 0.5) * CELL - px) < 97
                       and abs((r + 0.5) * CELL - py) < 38 for r, c in seen):
                print(f"   ✗ {name}: 창가에 다가갈 수 없다 ({px:.0f},{py:.0f})")
                bad += 1
    bad += check_camera(sizes)
    print("\n문제 없음" if bad == 0 else f"\n문제 {bad}건")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
