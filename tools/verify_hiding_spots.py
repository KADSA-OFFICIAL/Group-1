#!/usr/bin/env python3
"""은신처(#6) 배치 검증 — Godot 없이 좌표가 실제로 쓸 만한지 대조한다.

이 환경에는 Godot 바이너리가 없어 F5로 확인할 수 없다. 은신처를 눈대중으로
찍으면 벽 안에 박히거나 닿을 수 없는 칸에 놓일 수 있으므로, 층 씬의 벽을
직접 파싱해서 두 가지를 확인한다.

  1. 플레이어 몸통이 그 자리에 들어가는가(벽과 겹치지 않는가)
  2. 계단 도착 지점에서 걸어서 닿을 수 있는가(격자 연결성)

벽 수집 규칙과 격자 구성은 scripts/npc/janitor.gd의 _collect_blockers /
_rebuild_grid와 같게 맞췄다(sim_janitor_chase.py와 동일한 방식).

  python tools/verify_hiding_spots.py            # 배치 검증
  python tools/verify_hiding_spots.py --suggest   # 방 라벨별 후보 좌표 제안

한국어 Windows에서는 UTF-8 강제가 필요하다: PYTHONUTF8=1 python ...
"""

from __future__ import annotations

import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 수위아저씨가 순찰하는 층(floor_manager.JANITOR_FREE_FLOOR = 5 제외).
# 좌표는 씬에서 직접 읽는다 — 여기에 베껴 두면 씬과 어긋나도 통과해버린다.
PATROLLED_FLOORS = [1, 2, 3, 4]

HIDING_SCRIPT = "res://scripts/interactions/hiding_spot.gd"

# janitor.gd와 같은 값
BODY_HALF_WIDTH = 9.0
BODY_HALF_HEIGHT = 15.0
CELL = 25.0
GRID_WIDTH = 112
GRID_HEIGHT = 72

# floor_manager.gd ARRIVE_AFTER_DOWN — 전 층 공통 복도 지점(연결성 시드)
ARRIVE_POINTS = [(281.0, 692.0), (1311.0, 1372.0)]

# 은신처가 벽에 너무 붙으면 들어가고 나올 때 끼일 수 있어 여유를 둔다
CLEARANCE_MARGIN = 3.0

errors: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def load_blockers(floor: int) -> list[tuple[float, float, float, float]]:
    """층 씬에서 StaticBody2D 하위 충돌 도형만 모은다(Area2D 상호작용 존 제외)."""
    text = (ROOT / f"scenes/background/school_floor_{floor}.tscn").read_text(
        encoding="utf-8")
    shapes = {
        m.group(1): [float(v) for v in m.group(2).split(",")]
        for m in re.finditer(
            r'\[sub_resource type="RectangleShape2D" id="([^"]+)"\]\s*\n'
            r'size = Vector2\(([^)]*)\)', text)
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
        kind, parent, body = match.group(2), match.group(3) or "", match.group(4)
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
            cx, cy = ([float(v) for v in pos.group(1).split(",")]
                      if pos else [0.0, 0.0])
            w, h = shapes[shp.group(1)]
            out.append((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
    return out


def load_room_labels(floor: int) -> list[tuple[str, float, float]]:
    """방 라벨(이름, 중심 x, 중심 y). --suggest에서 후보를 찾는 기준점."""
    text = (ROOT / f"scenes/background/school_floor_{floor}.tscn").read_text(
        encoding="utf-8")
    out = []
    for m in re.finditer(
            r'\[node name="([^"]+)" type="Label" parent="Labels"\]\s*\n'
            r'((?:[a-z_].*\n)*)', text):
        body = m.group(2)
        left = re.search(r'offset_left = ([\d.-]+)', body)
        top = re.search(r'offset_top = ([\d.-]+)', body)
        right = re.search(r'offset_right = ([\d.-]+)', body)
        bottom = re.search(r'offset_bottom = ([\d.-]+)', body)
        text_m = re.search(r'text = "([^"]*)"', body)
        if not (left and top and right and bottom):
            continue
        cx = (float(left.group(1)) + float(right.group(1))) / 2
        cy = (float(top.group(1)) + float(bottom.group(1))) / 2
        out.append((text_m.group(1) if text_m else m.group(1), cx, cy))
    return out


def load_hiding_spots(floor: int) -> list[tuple[str, float, float]]:
    """씬에 실제로 들어 있는 은신처(hiding_spot.gd가 붙은 Area2D)를 읽는다."""
    text = (ROOT / f"scenes/background/school_floor_{floor}.tscn").read_text(
        encoding="utf-8")

    ext_id = re.search(
        r'\[ext_resource type="Script" path="' + re.escape(HIDING_SCRIPT)
        + r'" id="([^"]+)"\]', text)
    if not ext_id:
        return []

    out = []
    for m in re.finditer(
            r'\[node name="([^"]+)" type="Area2D" parent="\."\]\s*\n'
            r'((?:[a-z_].*\n)*)', text):
        body = m.group(2)
        if f'script = ExtResource("{ext_id.group(1)}")' not in body:
            continue
        pos = re.search(r'position = Vector2\(([^)]*)\)', body)
        if not pos:
            continue
        x, y = [float(v) for v in pos.group(1).split(",")]
        out.append((m.group(1), x, y))
    return out


def body_free(x: float, y: float, rects, margin: float = CLEARANCE_MARGIN) -> bool:
    """플레이어 몸통(+여유)이 벽과 겹치지 않는가."""
    ax = x - BODY_HALF_WIDTH - margin
    ay = y - BODY_HALF_HEIGHT - margin
    bx = x + BODY_HALF_WIDTH + margin
    by = y + BODY_HALF_HEIGHT + margin
    for wx0, wy0, wx1, wy1 in rects:
        if ax < wx1 and bx > wx0 and ay < wy1 and by > wy0:
            return False
    return True


def cell_of(x: float, y: float) -> tuple[int, int]:
    return int(x // CELL), int(y // CELL)


def cell_center(cx: int, cy: int) -> tuple[float, float]:
    return cx * CELL + CELL / 2, cy * CELL + CELL / 2


def build_solid(rects) -> set[tuple[int, int]]:
    """janitor.gd _rebuild_grid와 같은 규칙으로 통행 불가 칸을 표시한다."""
    solid: set[tuple[int, int]] = set()
    for wx0, wy0, wx1, wy1 in rects:
        gx0, gy0 = wx0 - BODY_HALF_WIDTH, wy0 - BODY_HALF_HEIGHT
        gx1, gy1 = wx1 + BODY_HALF_WIDTH, wy1 + BODY_HALF_HEIGHT
        for cx in range(max(int(gx0 // CELL), 0),
                        min(int(gx1 // CELL), GRID_WIDTH - 1) + 1):
            for cy in range(max(int(gy0 // CELL), 0),
                            min(int(gy1 // CELL), GRID_HEIGHT - 1) + 1):
                px, py = cell_center(cx, cy)
                if gx0 <= px <= gx1 and gy0 <= py <= gy1:
                    solid.add((cx, cy))
    return solid


def reachable_cells(solid: set[tuple[int, int]]) -> set[tuple[int, int]]:
    """계단 도착 지점들에서 걸어서 닿는 칸(4방향 BFS)."""
    seen: set[tuple[int, int]] = set()
    queue: collections.deque = collections.deque()

    for px, py in ARRIVE_POINTS:
        start = cell_of(px, py)
        if start not in solid and start not in seen:
            seen.add(start)
            queue.append(start)

    while queue:
        cx, cy = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
                continue
            if (nx, ny) in solid or (nx, ny) in seen:
                continue
            seen.add((nx, ny))
            queue.append((nx, ny))
    return seen


def suggest(floor: int) -> None:
    rects = load_blockers(floor)
    solid = build_solid(rects)
    reach = reachable_cells(solid)

    print(f"\n=== {floor}층 후보 (방 라벨에서 가장 가까운 통행 가능 지점) ===")
    for name, lx, ly in load_room_labels(floor):
        best = None
        best_distance = float("inf")
        for cx, cy in reach:
            px, py = cell_center(cx, cy)
            if not body_free(px, py, rects):
                continue
            distance = (px - lx) ** 2 + (py - ly) ** 2
            if distance < best_distance:
                best_distance = distance
                best = (px, py)
        if best is None:
            print(f"  {name:16s} 후보 없음")
        else:
            print(f"  {name:16s} ({best[0]:7.0f},{best[1]:7.0f})"
                  f"  라벨에서 {best_distance ** 0.5:5.0f}px")


def verify() -> None:
    total = 0
    for floor in PATROLLED_FLOORS:
        rects = load_blockers(floor)
        solid = build_solid(rects)
        reach = reachable_cells(solid)
        spots = load_hiding_spots(floor)

        if not spots:
            fail(f"{floor}층: 은신처가 없다 — 수위아저씨가 순찰하는 층에는 "
                 f"회피 수단이 있어야 한다")
            continue

        for name, x, y in spots:
            total += 1
            if not body_free(x, y, rects):
                fail(f"{floor}층 {name} ({x:.0f},{y:.0f}): 벽과 겹친다 "
                     f"— 플레이어 몸통이 들어가지 않는다")
                continue
            if cell_of(x, y) not in reach:
                fail(f"{floor}층 {name} ({x:.0f},{y:.0f}): 계단 도착 지점에서 "
                     f"걸어서 닿을 수 없다")

        print(f"  {floor}층: 은신처 {len(spots)}개 "
              f"({', '.join(n for n, _, _ in spots)})")

    print(f"은신처 {total}개 검사")


def main() -> int:
    if "--suggest" in sys.argv:
        for floor in PATROLLED_FLOORS:
            suggest(floor)
        return 0

    verify()
    if errors:
        print(f"\n오류 {len(errors)}건:")
        for message in errors:
            print(f"  - {message}")
        return 1

    print("문제 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
