#!/usr/bin/env python3
"""수위아저씨 추격 제어 루프를 실제 층 지오메트리 위에서 시간축 시뮬레이션한다.

이 맥에는 Godot 바이너리가 없어 F5 검증을 개발자가 할 수 없다. 추격 로직은
"정적으로는 맞아 보이는데 실제로는 어긋나는" 실패를 여러 번 냈기 때문에,
제어 루프를 프레임 단위로 돌려 도달률과 뒤로 가는 시간을 수치로 비교한다.

사용법:
    python3 tools/sim_janitor_chase.py [층번호 ...]      # 기본: 2 3

무엇을 재현하는가
- janitor.gd의 _clear_line(중심 + 진행방향 수직 ±몸통반폭, hit_from_inside 없음)
- 격자 A*: 벽 AABB를 몸통 반폭만큼 부풀려 칸 중심이 그 안이면 통행 불가,
  대각선은 양옆이 뚫린 경우만, 경로 지점은 칸 중심
- 경로 다듬기: 앞쪽 PATH_LOOKAHEAD개 중 시야가 트인 가장 먼 지점으로 건너뜀
- move_and_slide: 축분리 이동(FLOATING 모드의 벽 슬라이드 근사)

근사(주의)
- 콜리전 캡슐(18×30)을 AABB로 다룬다 — 모서리에서 실제와 미세하게 다르다.
- 플레이어는 정지 상태로 둔다(결정론 확보). 실제 추격은 움직이는 표적이다.
"""
from __future__ import annotations   # 사용자 맥의 python 3.9에서 `float | None` 표기 허용

import heapq
import math
import pathlib
import random
import re
import sys

DT = 1.0 / 60.0
CHASE_SPEED = 220.0
ARRIVE = 6.0
STUCK_SECONDS = 0.6
PROGRESS_RATIO = 0.3
REPATH = 0.3
CONTACT = 30.0
HALF_W, HALF_H, PROBE_MARGIN = 9.0, 15.0, 1.0
CELL = 25.0
GRID_W, GRID_H = 112, 72
LOOKAHEAD = 12
PATROL_SPEED = 110.0
SIGHT_RANGE = 320.0     # 플레이어 손전등이 닿는 거리
REVEAL_DELAY = 1.0      # 시야 노출 후 추적 시작까지
LOSE_SIGHT = 1.5        # 시야 상실 후 추적 유지

# 교체 전 구현(웨이포인트 8노드 + direct_block_time) — 비교 기준
OLD_WAYPOINTS = {
    "stair_top_w": (170, 670), "stair_top_e": (620, 670), "main_w": (620, 940),
    "main_mid": (1325, 940), "main_e": (2600, 940), "lower_mid": (1325, 1360),
    "lower_w": (170, 1360), "lower_e": (2600, 1360),
}
OLD_NEIGHBORS = {
    "stair_top_w": ["stair_top_e"], "stair_top_e": ["stair_top_w", "main_w"],
    "main_w": ["stair_top_e", "main_mid"], "main_mid": ["main_w", "main_e", "lower_mid"],
    "main_e": ["main_mid"], "lower_mid": ["main_mid", "lower_w", "lower_e"],
    "lower_w": ["lower_mid"], "lower_e": ["lower_mid"],
}
OLD_DIRECT_BLOCK = 1.0

ROOT = pathlib.Path(__file__).resolve().parent.parent


# ── 층 씬에서 벽 수집 (janitor.gd _collect_blockers와 같은 규칙) ──────────

def load_blockers(floor: int) -> list[tuple[float, float, float, float]]:
    text = (ROOT / f"scenes/background/school_floor_{floor}.tscn").read_text()
    shapes = {
        m.group(1): [float(v) for v in m.group(2).split(",")]
        for m in re.finditer(
            r'\[sub_resource type="RectangleShape2D" id="([^"]+)"\]\s*\nsize = Vector2\(([^)]*)\)',
            text)
    }
    static_bodies = {
        m.group(1) for m in re.finditer(
            r'\[node name="([^"]+)" type="StaticBody2D"', text)
    }
    node_re = re.compile(
        r'\[node name="([^"]+)" type="([^"]+)"(?: parent="([^"]+)")?\]\s*\n'
        r'((?:[a-z_].*\n)*)', re.M)

    out = []
    for match in node_re.finditer(text):
        name, kind, parent, body = (match.group(1), match.group(2),
                                    match.group(3) or "", match.group(4))
        # 부모가 StaticBody2D인 도형만 (Area2D 상호작용 존 제외)
        if parent.split("/")[-1] not in static_bodies:
            continue
        if kind == "CollisionPolygon2D":
            poly = re.search(r'polygon = PackedVector2Array\(([^)]*)\)', body)
            if not poly:
                continue
            nums = [float(v) for v in poly.group(1).split(",")]
            xs, ys = nums[0::2], nums[1::2]
            out.append((min(xs), min(ys), max(xs), max(ys)))
        elif kind == "CollisionShape2D":
            pos = re.search(r'position = Vector2\(([^)]*)\)', body)
            shp = re.search(r'shape = SubResource\("([^"]+)"\)', body)
            if not (shp and shp.group(1) in shapes):
                continue
            cx, cy = ([float(v) for v in pos.group(1).split(",")] if pos else [0.0, 0.0])
            w, h = shapes[shp.group(1)]
            out.append((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
    return out


# ── 시야 판정 (_clear_line) ───────────────────────────────────────────────

def _ray_hits(a, b, rect) -> bool:
    x0, y0, x1, y1 = rect
    ax, ay = a
    if x0 <= ax <= x1 and y0 <= ay <= y1:
        return False                      # hit_from_inside = false
    dx, dy = b[0] - ax, b[1] - ay
    tmin, tmax = 0.0, 1.0
    for p, d, lo, hi in ((ax, dx, x0, x1), (ay, dy, y0, y1)):
        if abs(d) < 1e-12:
            if p < lo or p > hi:
                return False
            continue
        t1, t2 = (lo - p) / d, (hi - p) / d
        if t1 > t2:
            t1, t2 = t2, t1
        tmin, tmax = max(tmin, t1), min(tmax, t2)
        if tmin > tmax:
            return False
    return True


def clear_ray(a, b, rects) -> bool:
    return not any(_ray_hits(a, b, r) for r in rects)


def clear_line(a, b, rects) -> bool:
    length = math.dist(a, b)
    if length < 1e-9:
        return True
    if not clear_ray(a, b, rects):
        return False
    dx, dy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    px, py = dy, -dx                       # Vector2.orthogonal()
    extent = max(abs(px) * HALF_W + abs(py) * HALF_H - PROBE_MARGIN, 0.0)
    ox, oy = px * extent, py * extent
    return (clear_ray((a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy), rects)
            and clear_ray((a[0] - ox, a[1] - oy), (b[0] - ox, b[1] - oy), rects))


# ── 물리 근사 ────────────────────────────────────────────────────────────

def body_blocked(pos, rects) -> bool:
    x0, y0 = pos[0] - HALF_W, pos[1] - HALF_H
    x1, y1 = pos[0] + HALF_W, pos[1] + HALF_H
    return any(x0 < r[2] and r[0] < x1 and y0 < r[3] and r[1] < y1 for r in rects)


def move_and_slide(pos, vel, rects):
    nx = pos[0] + vel[0] * DT
    if body_blocked((nx, pos[1]), rects):
        nx = pos[0]
    ny = pos[1] + vel[1] * DT
    if body_blocked((nx, ny), rects):
        ny = pos[1]
    return (nx, ny)


# ── 격자 A* (교체 후 구현) ───────────────────────────────────────────────

def cell_of(p):
    return (int(math.floor(p[0] / CELL)), int(math.floor(p[1] / CELL)))


def cell_center(c):
    return (c[0] * CELL + CELL / 2, c[1] * CELL + CELL / 2)


def build_grid(rects):
    solid = [[False] * GRID_H for _ in range(GRID_W)]
    for x0, y0, x1, y1 in rects:
        gx0, gy0 = x0 - HALF_W, y0 - HALF_H
        gx1, gy1 = x1 + HALF_W, y1 + HALF_H
        c0, c1 = cell_of((gx0, gy0)), cell_of((gx1, gy1))
        for cx in range(max(c0[0], 0), min(c1[0], GRID_W - 1) + 1):
            for cy in range(max(c0[1], 0), min(c1[1], GRID_H - 1) + 1):
                px, py = cell_center((cx, cy))
                if gx0 <= px <= gx1 and gy0 <= py <= gy1:
                    solid[cx][cy] = True
    return solid


def nearest_free(solid, point):
    c = cell_of(point)
    c = (min(max(c[0], 0), GRID_W - 1), min(max(c[1], 0), GRID_H - 1))
    if not solid[c[0]][c[1]]:
        return c
    for radius in range(1, 8):
        best, best_d = None, float("inf")
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if abs(dx) != radius and abs(dy) != radius:
                    continue
                p = (c[0] + dx, c[1] + dy)
                if not (0 <= p[0] < GRID_W and 0 <= p[1] < GRID_H) or solid[p[0]][p[1]]:
                    continue
                d = math.dist(cell_center(p), point)
                if d < best_d:
                    best_d, best = d, p
        if best:
            return best
    return c


NBR8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def astar(solid, start, goal):
    if solid[start[0]][start[1]] or solid[goal[0]][goal[1]]:
        return []
    openh = [(math.dist(start, goal), 0.0, start)]
    came, gscore = {start: None}, {start: 0.0}
    while openh:
        _, g, cur = heapq.heappop(openh)
        if cur == goal:
            break
        if g > gscore.get(cur, 1e18):
            continue
        for dx, dy in NBR8:
            n = (cur[0] + dx, cur[1] + dy)
            if not (0 <= n[0] < GRID_W and 0 <= n[1] < GRID_H) or solid[n[0]][n[1]]:
                continue
            # DIAGONAL_MODE_ONLY_IF_NO_OBSTACLES
            if dx and dy and (solid[cur[0] + dx][cur[1]] or solid[cur[0]][cur[1] + dy]):
                continue
            ng = g + math.hypot(dx, dy)
            if ng < gscore.get(n, 1e18):
                gscore[n] = ng
                came[n] = cur
                heapq.heappush(openh, (ng + math.dist(n, goal), ng, n))
    if goal not in came:
        return []
    path, c = [], goal
    while c:
        path.append(cell_center(c))
        c = came[c]
    return path[::-1]


def next_point(pos, path, rects, fallback):
    if not path:
        return fallback, path
    limit = min(len(path), LOOKAHEAD)
    index = 0
    for i in range(limit - 1, -1, -1):
        if clear_line(pos, path[i], rects):
            index = i
            break
    while index > 0 and len(path) > 1:
        path.pop(0)
        index -= 1
    if len(path) > 1 and math.dist(pos, path[0]) <= ARRIVE:
        path.pop(0)
    return path[0], path


def run_grid(pos, player, rects, solid, seconds):
    path, repath, stuck, backward, reached = [], 0.0, 0.0, 0, None
    for frame in range(int(seconds / DT)):
        if math.dist(pos, player) <= CONTACT:
            reached = frame * DT
            break
        repath -= DT
        if repath <= 0.0 or stuck >= STUCK_SECONDS:
            repath, stuck = REPATH, 0.0
            if clear_line(pos, player, rects):
                path = []
            else:
                path = astar(solid, nearest_free(solid, pos), nearest_free(solid, player))
        target, path = next_point(pos, path, rects, player)
        length = math.dist(pos, target)
        if length < 1e-9:
            continue
        d = ((target[0] - pos[0]) / length, (target[1] - pos[1]) / length)
        before = pos
        pos = move_and_slide(pos, (d[0] * CHASE_SPEED, d[1] * CHASE_SPEED), rects)
        adv = (pos[0] - before[0]) * d[0] + (pos[1] - before[1]) * d[1]
        stuck = stuck + DT if adv < CHASE_SPEED * DT * PROGRESS_RATIO else 0.0
        if math.dist(pos, player) - math.dist(before, player) > 0.05:
            backward += 1
    return {"reached": reached, "backward": backward * DT,
            "dist": math.dist(pos, player)}


# ── 교체 전 구현 (비교 기준) ─────────────────────────────────────────────

def _old_bfs(a, b):
    came, queue = {a: None}, [a]
    while queue:
        cur = queue.pop(0)
        if cur == b:
            break
        for n in OLD_NEIGHBORS[cur]:
            if n not in came:
                came[n] = cur
                queue.append(n)
    if b not in came:
        return []
    out, c = [], b
    while c:
        out.append(c)
        c = came[c]
    return out[::-1]


_OLD_PATHS = {(a, b): _old_bfs(a, b) for a in OLD_WAYPOINTS for b in OLD_WAYPOINTS}


def _old_reachable(point, rects):
    out = [n for n in OLD_WAYPOINTS if clear_line(point, OLD_WAYPOINTS[n], rects)]
    if out:
        return out
    return [min(OLD_WAYPOINTS, key=lambda n: math.dist(point, OLD_WAYPOINTS[n]))]


def _old_build(pos, player, rects):
    best, best_cost = [], float("inf")
    for s in _old_reachable(pos, rects):
        d0 = math.dist(pos, OLD_WAYPOINTS[s])
        for e in _old_reachable(player, rects):
            p = _OLD_PATHS[(s, e)]
            cost = (d0 + sum(math.dist(OLD_WAYPOINTS[p[i - 1]], OLD_WAYPOINTS[p[i]])
                             for i in range(1, len(p)))
                    + math.dist(OLD_WAYPOINTS[e], player))
            if cost < best_cost:
                best_cost, best = cost, p
    return list(best)


def run_old(pos, player, rects, seconds):
    path, repath, block, stuck, backward, reached = [], 0.0, 0.0, 0.0, 0, None
    for frame in range(int(seconds / DT)):
        to_player = math.dist(pos, player)
        if to_player <= CONTACT:
            reached = frame * DT
            break
        block = max(block - DT, 0.0)
        repath -= DT
        if repath <= 0.0:
            repath = REPATH
            if block <= 0.0 and clear_line(pos, player, rects):
                path = []
            else:
                prev = path[0] if path else ""
                path = _old_build(pos, player, rects)
                if not path or path[0] != prev:
                    stuck = 0.0
        goal = player
        if path:
            goal = OLD_WAYPOINTS[path[0]]
            if math.dist(pos, goal) <= ARRIVE:
                path.pop(0)
                stuck = 0.0
                continue
        length = math.dist(pos, goal)
        if length < 1e-9:
            continue
        d = ((goal[0] - pos[0]) / length, (goal[1] - pos[1]) / length)
        before = pos
        pos = move_and_slide(pos, (d[0] * CHASE_SPEED, d[1] * CHASE_SPEED), rects)
        adv = (pos[0] - before[0]) * d[0] + (pos[1] - before[1]) * d[1]
        stuck = stuck + DT if adv < CHASE_SPEED * DT * PROGRESS_RATIO else 0.0
        if stuck >= STUCK_SECONDS and to_player > CONTACT * 2.0:
            block = OLD_DIRECT_BLOCK
            path = _old_build(pos, player, rects)
            repath, stuck = REPATH, 0.0
        if math.dist(pos, player) - math.dist(before, player) > 0.05:
            backward += 1
    return {"reached": reached, "backward": backward * DT,
            "dist": math.dist(pos, player)}


# ── 평가 ─────────────────────────────────────────────────────────────────

def evaluate(floor: int, seed: int = 11) -> bool:
    rects = load_blockers(floor)
    solid = build_grid(rects)
    free = sum(1 for x in range(GRID_W) for y in range(GRID_H) if not solid[x][y])
    print(f"\n=== {floor}층 · 벽 {len(rects)}개 · 격자 {GRID_W}×{GRID_H} "
          f"(통행 가능 {free}칸) ===")

    random.seed(seed)
    spots = [(x, y) for x in range(60, 2760, 50) for y in range(60, 1760, 50)
             if not body_blocked((x, y), rects)]
    random.shuffle(spots)

    all_ok = True
    for label, lo, hi, count in (("근거리 80~350px", 80, 350, 90),
                                 ("원거리 600~1500px", 600, 1500, 45)):
        pairs = []
        for start in spots:
            near = [p for p in spots if lo <= math.dist(start, p) <= hi]
            if near:
                pairs.append((start, random.choice(near)))
                if len(pairs) >= count:
                    break

        old_fail = new_fail = skipped = tested = 0
        old_back = new_back = 0.0
        for start, target in pairs:
            path = astar(solid, nearest_free(solid, start), nearest_free(solid, target))
            if not path:
                skipped += 1          # 실제로 도달 불가(잠긴 계단실 등)
                continue
            length = sum(math.dist(path[i - 1], path[i]) for i in range(1, len(path)))
            budget = max(4.0, 2.5 * length / CHASE_SPEED + 2.0)
            tested += 1
            old = run_old(start, target, rects, budget)
            new = run_grid(start, target, rects, solid, budget)
            old_fail += old["reached"] is None
            new_fail += new["reached"] is None
            old_back += old["backward"]
            new_back += new["backward"]

        if not tested:
            continue
        print(f"  [{label}] 검사 {tested}건 (도달불가 제외 {skipped}건)")
        print(f"     교체 전(웨이포인트) 실패 {old_fail:>3}건 "
              f"({old_fail / tested * 100:4.0f}%)  평균 뒤로 {old_back / tested:.2f}s")
        print(f"     교체 후(격자 A*)    실패 {new_fail:>3}건 "
              f"({new_fail / tested * 100:4.0f}%)  평균 뒤로 {new_back / tested:.2f}s")
        if new_fail / tested > 0.10:
            print("     ⚠ 목표(10% 이하) 미달")
            all_ok = False
    return all_ok


# ── 시야 기반 추적 게이트 (#153) ─────────────────────────────────────────

def can_be_seen(pos, player, rects) -> bool:
    """janitor.gd _can_be_seen: 손전등 거리 안 + 벽에 안 가림(중심선 1발)."""
    if math.dist(pos, player) > SIGHT_RANGE:
        return False
    return clear_ray(pos, player, rects)


def run_sighted(pos, player, rects, solid, seconds, patrol_target=None):
    """시야 게이트를 포함한 루프. 추적 시작 시각과 최소 거리를 돌려준다."""
    path, repath, stuck, seen, hold = [], 0.0, 0.0, 0.0, 0.0
    chase_started, closest, caught = None, math.dist(pos, player), None
    for frame in range(int(seconds / DT)):
        # _update_awareness와 동일: 최초 발각은 유예 필요, 이후 시야 상실은 유지 시간
        if can_be_seen(pos, player, rects):
            seen += DT
            if seen >= REVEAL_DELAY or hold > 0.0:
                hold = LOSE_SIGHT
        else:
            seen = 0.0
            hold = max(hold - DT, 0.0)
        chasing = hold > 0.0
        if chasing and chase_started is None:
            chase_started = frame * DT

        if chasing:
            if math.dist(pos, player) <= CONTACT:
                caught = frame * DT
                break
            repath -= DT
            if repath <= 0.0 or stuck >= STUCK_SECONDS:
                repath, stuck = REPATH, 0.0
                if clear_line(pos, player, rects):
                    path = []
                else:
                    path = astar(solid, nearest_free(solid, pos),
                                 nearest_free(solid, player))
            target, path = next_point(pos, path, rects, player)
            speed = CHASE_SPEED
        else:
            if not path or math.dist(pos, patrol_target) <= ARRIVE:
                path = astar(solid, nearest_free(solid, pos),
                             nearest_free(solid, patrol_target))
            target, path = next_point(pos, path, rects, patrol_target)
            speed = PATROL_SPEED

        length = math.dist(pos, target)
        if length < 1e-9:
            continue
        d = ((target[0] - pos[0]) / length, (target[1] - pos[1]) / length)
        before = pos
        pos = move_and_slide(pos, (d[0] * speed, d[1] * speed), rects)
        adv = (pos[0] - before[0]) * d[0] + (pos[1] - before[1]) * d[1]
        stuck = stuck + DT if adv < speed * DT * PROGRESS_RATIO else 0.0
        closest = min(closest, math.dist(pos, player))
    return {"chase_started": chase_started, "closest": closest, "caught": caught}


def check_sight_gate(floor: int) -> bool:
    rects = load_blockers(floor)
    solid = build_grid(rects)
    ok = True
    print(f"\n=== {floor}층 · 시야 기반 추적 게이트 (#153) ===")

    # 1) 시야 거리 밖: 추적이 시작되지 않고 플레이어에게 접근하지 않아야 한다
    player = (1325, 940)
    far = (1325 + 600, 940)
    if solid[cell_of(far)[0]][cell_of(far)[1]]:
        far = (1325 + 550, 940)
    start_gap = math.dist(far, player)
    r = run_sighted(far, player, rects, solid, 6.0, patrol_target=(2600, 1360))
    passed = r["chase_started"] is None and r["closest"] > SIGHT_RANGE
    ok = ok and passed
    print(f"  시야 밖({start_gap:.0f}px) → 추적 시작 {r['chase_started']}, "
          f"최근접 {r['closest']:.0f}px  [{'OK' if passed else 'FAIL'}]")

    # 2) 벽에 가린 근거리: 거리는 시야 안이지만 차폐되어 추적이 시작되지 않아야 한다
    blocked = None
    for cx in range(GRID_W):
        for cy in range(GRID_H):
            if solid[cx][cy]:
                continue
            p = cell_center((cx, cy))
            if math.dist(p, player) < SIGHT_RANGE and not clear_ray(p, player, rects):
                blocked = p
                break
        if blocked:
            break
    if blocked:
        r = run_sighted(blocked, player, rects, solid, 3.0, patrol_target=(170, 1360))
        passed = r["chase_started"] is None
        ok = ok and passed
        print(f"  시야 내 거리이나 벽에 가림 {tuple(int(v) for v in blocked)} "
              f"({math.dist(blocked, player):.0f}px) → 추적 시작 {r['chase_started']}  "
              f"[{'OK' if passed else 'FAIL'}]")

    # 3) 시야 안 + 트임: 정확히 REVEAL_DELAY 후 추적이 시작되어야 한다
    visible = None
    for cx in range(GRID_W):
        for cy in range(GRID_H):
            if solid[cx][cy]:
                continue
            p = cell_center((cx, cy))
            gap = math.dist(p, player)
            if 150 < gap < SIGHT_RANGE - 40 and clear_ray(p, player, rects):
                visible = p
                break
        if visible:
            break
    if visible:
        # 유예 타이밍은 정지 상태로 검증한다(순찰 목표 = 자기 위치).
        # 순찰로 움직이면 1초 안에 시야를 벗어날 수 있어 타이밍이 흔들린다.
        r = run_sighted(visible, player, rects, solid, 6.0, patrol_target=visible)
        started = r["chase_started"]
        passed = started is not None and abs(started - REVEAL_DELAY) <= DT * 1.5
        ok = ok and passed
        shown = f"{started:.3f}s" if started is not None else "없음"
        print(f"  시야 내 + 트임(정지) {tuple(int(v) for v in visible)} "
              f"({math.dist(visible, player):.0f}px) → 추적 시작 {shown} "
              f"(기대 {REVEAL_DELAY:.3f}s)  [{'OK' if passed else 'FAIL'}]")
        print(f"     이후 접촉까지 {r['caught']:.1f}s" if r["caught"]
              else "     접촉 미도달")

        # 순찰 중 노출: 유예 1초 사이에 순찰이 시야를 끊으면 발각이 초기화된다.
        # 사양상 허용되는 동작이므로 단정하지 않고 관찰값만 남긴다.
        moving = run_sighted(visible, player, rects, solid, 6.0,
                             patrol_target=(170, 1360))
        note = (f"{moving['chase_started']:.2f}s"
                if moving["chase_started"] is not None else "미발동")
        print(f"     (참고) 같은 지점에서 순찰 이동 중이면 추적 시작 {note} "
              f"— 유예 중 이동으로 시야가 끊기면 누적이 초기화된다")

    # 4) 순찰 목표는 복도만 — 방 폴리곤 내부 칸이 제외되는지
    rooms = load_room_rects(floor)
    corridor = [c for c in ((x, y) for x in range(GRID_W) for y in range(GRID_H))
                if not solid[c[0]][c[1]]
                and not any(r[0] <= cell_center(c)[0] <= r[2]
                            and r[1] <= cell_center(c)[1] <= r[3] for r in rooms)]
    walkable = sum(1 for x in range(GRID_W) for y in range(GRID_H) if not solid[x][y])
    in_room = [c for c in corridor
               if any(r[0] <= cell_center(c)[0] <= r[2]
                      and r[1] <= cell_center(c)[1] <= r[3] for r in rooms)]
    passed = len(corridor) > 0 and not in_room and len(corridor) < walkable
    ok = ok and passed
    print(f"  복도 칸 {len(corridor)} / 통행 가능 {walkable} "
          f"(방 내부 포함 {len(in_room)}개)  [{'OK' if passed else 'FAIL'}]")
    return ok


def awareness_timeline(steps: list[tuple[bool, bool]]) -> list[bool]:
    """janitor.gd _update_awareness를 그대로 재현.

    steps: 프레임별 (보임, 은신) → 프레임별 추적 여부.
    """
    seen, hold, out = 0.0, 0.0, []
    for visible, hiding in steps:
        if hiding:
            seen, hold = 0.0, 0.0
        elif visible:
            seen += DT
            if seen >= REVEAL_DELAY or hold > 0.0:
                hold = LOSE_SIGHT
        else:
            seen = 0.0
            hold = max(hold - DT, 0.0)
        out.append(hold > 0.0)
    return out


def _first_true(flags: list[bool]) -> float | None:
    for i, v in enumerate(flags):
        if v:
            return i * DT
    return None


def _first_false_after(flags: list[bool], start_frame: int) -> float | None:
    for i in range(start_frame, len(flags)):
        if not flags[i]:
            return i * DT
    return None


def check_awareness() -> bool:
    """발각 타이머 상태기계 검증(지오메트리 없이 타이밍만)."""
    print("\n=== 발각/추적 유지 타이머 (#153) ===")
    ok = True
    frames = lambda s: int(round(s / DT))

    # 1) 계속 보임 → REVEAL_DELAY에 추적 시작
    t = awareness_timeline([(True, False)] * frames(3.0))
    start = _first_true(t)
    passed = start is not None and abs(start - REVEAL_DELAY) <= DT * 1.5
    ok &= passed
    print(f"  계속 보임 → 시작 {start:.3f}s (기대 {REVEAL_DELAY})  "
          f"[{'OK' if passed else 'FAIL'}]")

    # 2) 1.0초 노출 뒤 시야 상실 → LOSE_SIGHT 동안 유지되고 그 뒤 해제
    seq = [(True, False)] * frames(1.2) + [(False, False)] * frames(3.0)
    t = awareness_timeline(seq)
    start = _first_true(t)
    stop = _first_false_after(t, frames(1.2))
    held = stop - frames(1.2) * DT if stop is not None else None
    passed = held is not None and abs(held - LOSE_SIGHT) <= DT * 2
    ok &= passed
    print(f"  1.2초 노출 후 시야 상실 → 유지 {held:.3f}s (기대 {LOSE_SIGHT})  "
          f"[{'OK' if passed else 'FAIL'}]")

    # 3) 유지 중 재노출 → 끊김 없이 이어져야 한다(깜빡임 없음)
    seq = ([(True, False)] * frames(1.2) + [(False, False)] * frames(0.8)
           + [(True, False)] * frames(0.5) + [(False, False)] * frames(3.0))
    t = awareness_timeline(seq)
    engaged = t[frames(1.2):frames(2.5)]
    passed = all(engaged)
    ok &= passed
    print(f"  유지 중 재노출 → 구간 내 추적 연속 {passed}  "
          f"[{'OK' if passed else 'FAIL'}]")

    # 4) 재노출로 유지가 갱신되어 마지막 노출 시점부터 다시 1.5초
    stop = _first_false_after(t, frames(2.5))
    expected = (frames(1.2) + frames(0.8) + frames(0.5)) * DT + LOSE_SIGHT
    passed = stop is not None and abs(stop - expected) <= DT * 2
    ok &= passed
    print(f"  재노출 후 해제 {stop:.3f}s (기대 {expected:.3f}s)  "
          f"[{'OK' if passed else 'FAIL'}]")

    # 5) 은신은 즉시 끊는다 — 유지 시간을 주지 않는다(캐비넷 안 붙잡힘 방지)
    seq = [(True, False)] * frames(1.2) + [(True, True)] * frames(1.0)
    t = awareness_timeline(seq)
    stop = _first_false_after(t, frames(1.2))
    passed = stop is not None and stop - frames(1.2) * DT <= DT * 1.5
    ok &= passed
    print(f"  은신 시작 → 즉시 해제(경과 {stop - frames(1.2) * DT:.3f}s)  "
          f"[{'OK' if passed else 'FAIL'}]")

    # 6) 유예 미달 노출은 추적을 만들지 않는다
    seq = [(True, False)] * frames(0.8) + [(False, False)] * frames(1.0)
    t = awareness_timeline(seq)
    passed = not any(t)
    ok &= passed
    print(f"  0.8초만 노출(유예 미달) → 추적 없음 {passed}  "
          f"[{'OK' if passed else 'FAIL'}]")
    return ok


def load_room_rects(floor: int) -> list[tuple[float, float, float, float]]:
    """층 씬 Rooms 아래 방 폴리곤 영역(순찰 제외 대상)."""
    text = (ROOT / f"scenes/background/school_floor_{floor}.tscn").read_text()
    out = []
    for m in re.finditer(
            r'\[node name="[^"]+" type="Polygon2D" parent="Rooms"\]\s*\n'
            r'(?:[a-z_].*\n)*?polygon = PackedVector2Array\(([^)]*)\)', text):
        nums = [float(v) for v in m.group(1).split(",")]
        xs, ys = nums[0::2], nums[1::2]
        out.append((min(xs), min(ys), max(xs), max(ys)))
    return out


def main() -> int:
    floors = [int(a) for a in sys.argv[1:]] or [2, 3]
    ok = True
    for floor in floors:
        ok = evaluate(floor) and ok
    for floor in floors:
        ok = check_sight_gate(floor) and ok
    ok = check_awareness() and ok
    print("\n전체:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
