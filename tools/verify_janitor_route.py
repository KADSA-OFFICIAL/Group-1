#!/usr/bin/env python3
"""수위 순찰 루트(#141) 검증 — Godot 없이 루트가 실제로 걸을 수 있는지 대조한다.

janitor.gd는 층 씬의 문(Structures/Door_<방>)에서 "문 앞 대기
지점"을 뽑아 최근접 이웃으로 이어 고정 순찰 루트를 만든다. 이 환경에는 Godot
바이너리가 없어 F5로 확인할 수 없으므로, 같은 규칙을 파이썬으로 재현해서
확인한다.

  1. 문마다 방 폴리곤을 찾을 수 있는가(Door_<방> ↔ Rooms/<방> 이름 규약)
  2. 대기 지점이 벽 안에 박히지 않는가(_is_free_point와 같은 판정)
  3. 대기 지점이 계단 도착 지점에서 걸어서 닿는가(격자 연결성)
  4. 루트가 층의 방을 실제로 도는가(연속 구간이 지나치게 길지 않은가)
  5. 스폰·순찰이 복도로 한정되는가(#313) — 복도망(복도 칸의 가장 큰 연결 성분)에
     계단실·방 안쪽 칸이 없고, 모든 대기 지점이 그 안에 있는가

격자·몸통·벽 수집 규칙은 scripts/npc/janitor.gd와 같게 맞췄다. 격자 크기는
janitor.gd처럼 Floor 폴리곤에서 계산한다 — 상수로 박아 두면 맵이 커졌을 때
(#159로 3400×2500) 바깥 구역이 통째로 검사에서 빠진다.

  python tools/verify_janitor_route.py          # 검증
  python tools/verify_janitor_route.py --list   # 층별 루트 순서 출력

한국어 Windows에서는 UTF-8 강제가 필요하다: PYTHONUTF8=1 python ...
"""

from __future__ import annotations

import collections
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FLOOR_MANAGER = ROOT / "scripts/game/floor_manager.gd"
JANITOR = ROOT / "scripts/npc/janitor.gd"

# janitor.gd와 같은 값(아래 read_janitor_constants가 실제 값과 대조한다)
BODY_HALF_WIDTH = 9.0
BODY_HALF_HEIGHT = 15.0
CELL = 25.0
DOOR_APPROACH = 46.0

# floor_manager.gd
WALL_T, ARRIVE_DY, ARRIVE_DX = 16.0, 28.0, 59.0

# 문과 문 사이가 이보다 멀면 순찰이 아니라 맵 횡단이다 — 루트 순서를 의심한다.
# 맵 대각선(3400×2500)의 절반 정도.
MAX_LEG = 2100.0

errors: list[str] = []
warnings: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def warn(message: str) -> None:
    warnings.append(message)


def scene_text(floor: int) -> str:
    return (ROOT / f"scenes/background/school_floor_{floor}.tscn").read_text(
        encoding="utf-8")


def patrolled_floors() -> list[int]:
    """floor_manager의 MIN/MAX_FLOOR와 JANITOR_FREE_FLOOR에서 순찰 층을 읽는다."""
    text = FLOOR_MANAGER.read_text(encoding="utf-8")

    def const(name: str) -> int:
        match = re.search(rf"const {name} := (\d+)", text)
        if not match:
            fail(f"floor_manager.gd에서 {name}을 찾지 못했다")
            return 0
        return int(match.group(1))

    low, high, free = const("MIN_FLOOR"), const("MAX_FLOOR"), const("JANITOR_FREE_FLOOR")
    return [f for f in range(low, high + 1) if f != free]


def read_janitor_constants() -> None:
    """이 스크립트가 베껴 둔 상수가 janitor.gd와 어긋나면 검증이 거짓말을 한다."""
    text = JANITOR.read_text(encoding="utf-8")
    expected = {
        "BODY_HALF_WIDTH": BODY_HALF_WIDTH,
        "BODY_HALF_HEIGHT": BODY_HALF_HEIGHT,
        "CELL": CELL,
        "DOOR_APPROACH": DOOR_APPROACH,
    }
    for name, value in expected.items():
        match = re.search(rf"const {name} := ([\d.]+)", text)
        if not match:
            fail(f"janitor.gd에서 {name}을 찾지 못했다")
            continue
        if not math.isclose(float(match.group(1)), value):
            fail(f"상수 불일치: janitor.gd {name} = {match.group(1)}, "
                 f"이 스크립트 = {value}")


def stair_rects() -> dict[int, list[list[float]]]:
    """floor_manager.gd의 STAIRS = {층: [Rect2(...)]}."""
    text = FLOOR_MANAGER.read_text(encoding="utf-8")
    named = {
        key: [float(v) for v in value.split(",")]
        for key, value in re.findall(r"const (STAIR_[AB]) := Rect2\(([^)]*)\)", text)
    }
    block = re.search(r"const STAIRS := \{(.*?)\n\}", text, re.S)
    if not block:
        fail("floor_manager.gd에서 STAIRS를 찾지 못했다")
        return {}

    out: dict[int, list[list[float]]] = {}
    for line in block.group(1).splitlines():
        match = re.match(r"\s*(\d+):\s*\[(.*)\],", line)
        if not match:
            continue
        rects = []
        for item in re.findall(r"STAIR_[AB]|Rect2\([^)]*\)", match.group(2)):
            rects.append(named[item] if item.startswith("STAIR_")
                         else [float(v) for v in item[6:-1].split(",")])
        out[int(match.group(1))] = rects
    return out


def arrive_points(floor: int, stairs: dict[int, list[list[float]]]) -> list[tuple[float, float]]:
    """floor_manager._arrive_on과 같은 계산 — 층 도착 지점(연결성 시드)."""
    out = []
    for x, y, width, _height in stairs.get(floor, []):
        mid = x + width / 2.0
        out.append((mid + ARRIVE_DX, y - ARRIVE_DY))
        out.append((mid - ARRIVE_DX, y - ARRIVE_DY))
    return out


def polygon_rect(raw: str) -> tuple[float, float, float, float]:
    nums = [float(v) for v in raw.split(",")]
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def floor_extent(floor: int) -> tuple[float, float]:
    """Floor 폴리곤에서 맵 크기 — janitor._grid_size_for와 같은 계산."""
    match = re.search(
        r'\[node name="Floor" type="Polygon2D" parent="\."\]\s*\n'
        r'(?:[a-z_].*\n)*?polygon = PackedVector2Array\(([^)]*)\)',
        scene_text(floor))
    if not match:
        fail(f"{floor}층: Floor 폴리곤을 찾지 못했다")
        return 2800.0, 1800.0
    _x0, _y0, x1, y1 = polygon_rect(match.group(1))
    return x1, y1


def load_blockers(floor: int) -> list[tuple[float, float, float, float]]:
    """StaticBody2D 하위 충돌 도형만 모은다(janitor._collect_blockers와 같음)."""
    text = scene_text(floor)
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
        # 미닫이 교실문은 수위가 밀고 지나간다 — 장애물로 세지 않는다
        # (janitor._collect_blockers도 같은 이름 규칙으로 건너뛴다).
        if "SDPanel" in parent:
            continue
        if kind == "CollisionPolygon2D":
            poly = re.search(r'polygon = PackedVector2Array\(([^)]*)\)', body)
            if poly:
                out.append(polygon_rect(poly.group(1)))
        elif kind == "CollisionShape2D":
            pos = re.search(r'position = Vector2\(([^)]*)\)', body)
            shape = re.search(r'shape = SubResource\("([^"]+)"\)', body)
            if not (shape and shape.group(1) in shapes):
                continue
            cx, cy = ([float(v) for v in pos.group(1).split(",")]
                      if pos else [0.0, 0.0])
            width, height = shapes[shape.group(1)]
            out.append((cx - width / 2, cy - height / 2,
                        cx + width / 2, cy + height / 2))
    return out


def load_polygons(floor: int, parent: str) -> dict[str, tuple[float, float, float, float]]:
    """parent 아래 Polygon2D 노드의 이름 → 전역 사각형."""
    out = {}
    pattern = re.compile(
        r'\[node name="([^"]+)" type="Polygon2D" parent="' + re.escape(parent)
        + r'"\]\s*\n((?:[a-z_].*\n)*)', re.M)
    for match in pattern.finditer(scene_text(floor)):
        poly = re.search(r'polygon = PackedVector2Array\(([^)]*)\)', match.group(2))
        if poly:
            out[match.group(1)] = polygon_rect(poly.group(1))
    return out


def outward(door: tuple[float, float, float, float],
            room: tuple[float, float, float, float]) -> tuple[float, float]:
    """janitor._outward — 문이 붙은 벽면의 복도 쪽 방향."""
    dcx, dcy = (door[0] + door[2]) / 2, (door[1] + door[3]) / 2
    rcx, rcy = (room[0] + room[2]) / 2, (room[1] + room[3]) / 2
    if (door[2] - door[0]) >= (door[3] - door[1]):
        return 0.0, (1.0 if dcy >= rcy else -1.0)
    return (1.0 if dcx >= rcx else -1.0), 0.0


def cell_of(x: float, y: float) -> tuple[int, int]:
    return int(x // CELL), int(y // CELL)


def cell_center(cx: int, cy: int) -> tuple[float, float]:
    return cx * CELL + CELL / 2, cy * CELL + CELL / 2


def build_solid(rects, grid_w: int, grid_h: int) -> set[tuple[int, int]]:
    """janitor._rebuild_grid와 같은 규칙으로 통행 불가 칸을 표시한다."""
    solid: set[tuple[int, int]] = set()
    for wx0, wy0, wx1, wy1 in rects:
        gx0, gy0 = wx0 - BODY_HALF_WIDTH, wy0 - BODY_HALF_HEIGHT
        gx1, gy1 = wx1 + BODY_HALF_WIDTH, wy1 + BODY_HALF_HEIGHT
        for cx in range(max(int(gx0 // CELL), 0), min(int(gx1 // CELL), grid_w - 1) + 1):
            for cy in range(max(int(gy0 // CELL), 0), min(int(gy1 // CELL), grid_h - 1) + 1):
                px, py = cell_center(cx, cy)
                if gx0 <= px <= gx1 and gy0 <= py <= gy1:
                    solid.add((cx, cy))
    return solid


def reachable_cells(solid, seeds, grid_w: int, grid_h: int) -> set[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    queue: collections.deque = collections.deque()
    for px, py in seeds:
        start = cell_of(px, py)
        if (0 <= start[0] < grid_w and 0 <= start[1] < grid_h
                and start not in solid and start not in seen):
            seen.add(start)
            queue.append(start)

    while queue:
        cx, cy = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (cx + dx, cy + dy)
            if not (0 <= nxt[0] < grid_w and 0 <= nxt[1] < grid_h):
                continue
            if nxt in solid or nxt in seen:
                continue
            seen.add(nxt)
            queue.append(nxt)
    return seen


def build_route(floor: int, solid, grid_w: int, grid_h: int):
    """janitor._build_route를 그대로 재현한다.

    반환: (루트, 건너뛴 문). 루트 항목 = (방 이름, 대기 지점, 문 중심).
    """
    doors = load_polygons(floor, "Structures")
    rooms = load_polygons(floor, "Rooms")

    stops = []
    skipped = []
    for name, rect in doors.items():
        if not name.startswith("Door_"):
            continue
        room_name = name[len("Door_"):]
        room = rooms.get(room_name)
        if room is None:
            # 현관(Door_FrontGate)처럼 방이 아닌 외부 문은 정상적으로 여기 걸린다.
            # 오타로 이름이 어긋난 경우와 구분이 안 되므로 경고로 남긴다.
            warn(f"{floor}층 {name}: Rooms/{room_name}이 없어 루트에서 제외된다 "
                 f"(현관 등 외부 문이면 정상)")
            continue

        dcx, dcy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
        ox, oy = outward(rect, room)
        stop = (dcx + ox * DOOR_APPROACH, dcy + oy * DOOR_APPROACH)
        cell = cell_of(*stop)
        free = (0 <= cell[0] < grid_w and 0 <= cell[1] < grid_h
                and cell not in solid)
        if not free:
            skipped.append((room_name, stop))
            continue
        stops.append((room_name, stop, (dcx, dcy)))

    if not stops:
        return [], skipped

    # 최근접 이웃 — janitor.gd와 같은 순서(씬 순서의 첫 문에서 시작)
    remaining = list(range(len(stops)))
    current = remaining.pop(0)
    route = [stops[current]]
    while remaining:
        best_slot = min(
            range(len(remaining)),
            key=lambda slot: (
                (stops[remaining[slot]][1][0] - stops[current][1][0]) ** 2
                + (stops[remaining[slot]][1][1] - stops[current][1][1]) ** 2))
        current = remaining.pop(best_slot)
        route.append(stops[current])
    return route, skipped


def corridor_pool(floor: int, solid, grid_w: int, grid_h: int):
    """janitor._collect_patrol_cells 재현 — 복도 칸의 가장 큰 연결 성분.

    복도 칸 = 통행 가능한 칸 − (Rooms ∪ Stairwells) 안쪽. 계단실을 빼는 것이
    #313의 핵심이다 — 계단실 바닥은 Rooms에 없어서 예전에는 복도로 분류됐고,
    잠긴 계단은 닫힌 상자라 거기서 스폰된 수위가 갇혔다.

    반환: (복도망, 복도 칸 전체, 실내 사각형, 계단실 사각형)
    """
    indoor = list(load_polygons(floor, "Rooms").values())
    stairwells = list(load_polygons(floor, "Stairwells").values())
    indoor += stairwells

    corridor: set[tuple[int, int]] = set()
    for cx in range(grid_w):
        for cy in range(grid_h):
            cell = (cx, cy)
            if cell in solid:
                continue
            px, py = cell_center(cx, cy)
            if any(x0 <= px <= x1 and y0 <= py <= y1 for x0, y0, x1, y1 in indoor):
                continue
            corridor.add(cell)

    seen: set[tuple[int, int]] = set()
    best: set[tuple[int, int]] = set()
    for start in corridor:
        if start in seen:
            continue
        component: set[tuple[int, int]] = {start}
        queue = collections.deque([start])
        seen.add(start)
        while queue:
            cx, cy = queue.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (cx + dx, cy + dy)
                if nxt in seen or nxt not in corridor:
                    continue
                seen.add(nxt)
                component.add(nxt)
                queue.append(nxt)
        if len(component) > len(best):
            best = component
    return best, corridor, indoor, stairwells


def check_corridor(floor: int, solid, grid_w: int, grid_h: int, route) -> None:
    """스폰·순찰이 복도로 한정되는지(#313)."""
    pool, corridor, indoor, stairwells = corridor_pool(floor, solid, grid_w, grid_h)

    if not pool:
        fail(f"{floor}층: 복도망이 비었다 — 수위가 스폰할 자리가 없다")
        return

    inside = [cell for cell in pool
              if any(x0 <= cell_center(*cell)[0] <= x1 and y0 <= cell_center(*cell)[1] <= y1
                     for x0, y0, x1, y1 in indoor)]
    if inside:
        fail(f"{floor}층: 스폰 후보에 실내 칸 {len(inside)}개가 섞였다")

    # 계단실 칸이 후보에 남아 있으면 갇힘이 재발한다.
    stair_cells = [cell for cell in pool
                   if any(x0 <= cell_center(*cell)[0] <= x1 and y0 <= cell_center(*cell)[1] <= y1
                          for x0, y0, x1, y1 in stairwells)]
    if stair_cells:
        fail(f"{floor}층: 스폰 후보에 계단실 칸 {len(stair_cells)}개 — 갇힌다")

    outside = [name for name, stop, _door in route if cell_of(*stop) not in pool]
    if outside:
        fail(f"{floor}층: 복도망에서 닿지 않는 대기 지점 {len(outside)}개 "
             f"— {', '.join(outside)}")

    pockets = len(corridor) - len(pool)
    print(f"        복도망 {len(pool)}칸 (스폰 후보), 떨어진 복도 칸 {pockets}개, "
          f"계단실 제외 {sum(1 for cx in range(grid_w) for cy in range(grid_h) if (cx, cy) not in solid and any(x0 <= cell_center(cx, cy)[0] <= x1 and y0 <= cell_center(cx, cy)[1] <= y1 for x0, y0, x1, y1 in stairwells))}칸")


def check_floor(floor: int, stairs, show_list: bool) -> None:
    extent_x, extent_y = floor_extent(floor)
    grid_w = int(math.ceil(extent_x / CELL))
    grid_h = int(math.ceil(extent_y / CELL))

    rects = load_blockers(floor)
    solid = build_solid(rects, grid_w, grid_h)
    seeds = arrive_points(floor, stairs)
    reach = reachable_cells(solid, seeds, grid_w, grid_h)

    route, skipped = build_route(floor, solid, grid_w, grid_h)

    if not route:
        fail(f"{floor}층: 순찰 루트가 비었다 — 수위가 무작위 배회로 폴백한다")
        return

    unreachable = [name for name, stop, _door in route
                   if cell_of(*stop) not in reach]
    if unreachable:
        fail(f"{floor}층: 계단에서 걸어서 닿지 않는 대기 지점 "
             f"{len(unreachable)}개 — {', '.join(unreachable)}")

    # 루트는 순환이 아니라 왕복이다(janitor._advance_route) — 끝 문에서 첫 문으로
    # 건너뛰는 구간이 없으므로 인접 쌍만 잰다.
    total = 0.0
    longest = 0.0
    longest_pair = ""
    for i in range(len(route) - 1):
        leg = math.dist(route[i][1], route[i + 1][1])
        total += leg
        if leg > longest:
            longest = leg
            longest_pair = f"{route[i][0]} → {route[i + 1][0]}"
    if longest > MAX_LEG:
        warn(f"{floor}층: 가장 긴 구간이 {longest:.0f}px ({longest_pair}) "
             f"— 순찰이 맵을 가로지른다")

    round_trip = total * 2.0
    print(f"  {floor}층: 문 {len(route)}개, 왕복 {round_trip:.0f}px "
          f"(순찰 속도 130 + 방 확인 1.8초 기준 "
          f"{round_trip / 130.0 + len(route) * 2 * 1.8:.0f}초), "
          f"가장 긴 구간 {longest:.0f}px, 건너뛴 문 {len(skipped)}개")
    if skipped:
        print("        건너뜀: "
              + ", ".join(f"{n}({x:.0f},{y:.0f})" for n, (x, y) in skipped))
    check_corridor(floor, solid, grid_w, grid_h, route)

    if show_list:
        for i, (name, stop, _door) in enumerate(route):
            print(f"        {i + 1:2d}. {name:20s} ({stop[0]:7.0f},{stop[1]:7.0f})")


def main() -> int:
    show_list = "--list" in sys.argv

    read_janitor_constants()
    stairs = stair_rects()
    floors = patrolled_floors()
    print(f"순찰 층: {', '.join(f'{f}층' for f in floors)}")

    for floor in floors:
        check_floor(floor, stairs, show_list)

    if warnings:
        print(f"\n경고 {len(warnings)}건:")
        for message in warnings:
            print(f"  - {message}")

    if errors:
        print(f"\n오류 {len(errors)}건:")
        for message in errors:
            print(f"  - {message}")
        return 1

    print("문제 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
