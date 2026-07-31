#!/usr/bin/env python3
"""층 씬의 상호작용 오브젝트 배치·진행 가능성을 정적으로 검사한다(#140).

검사 항목:
1. 조사/획득 오브젝트(interactable·pickup_item·locked_door 제외한 Area2D)가
   어떤 방 내부에 있는지 — 벽 두께(16)와 여유(CLEARANCE)를 뺀 안쪽 사각형 기준.
2. 문 틈(방 가로 중앙 110px) 앞을 막지 않는지.
3. 오브젝트끼리, 그리고 은신처와 겹치지 않는지(중심 간 MIN_GAP).
4. 계단 열쇠 진행: 각 층에서 그 층을 벗어나는 데 필요한 열쇠를
   같은 층 또는 그 이전 층에서 얻을 수 있는지(막힘 없음).

Godot 없이 수초 만에 끝난다. 실패하면 종료 코드 1.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FLOORS = [1, 2, 3, 4]

T = 16          # 벽 두께(gen_walls.py와 동일)
DOOR_W = 110    # 문 틈 폭
CENTER_Y = 900  # 방 중심 y < CENTER_Y 이면 문은 아래변
CLEARANCE = 24  # 벽 안쪽에서 오브젝트 중심까지 최소 여유
MIN_GAP = 56    # 오브젝트 중심 간 최소 거리(상호작용 존 48px 기준)

ROOM_RE = re.compile(
    r'\[node name="([^"]+)" type="Polygon2D" parent="Rooms"\]\s*\n'
    r'color = [^\n]*\n'
    r'polygon = PackedVector2Array\(([^)]*)\)'
)
NODE_RE = re.compile(r'\[node name="([^"]+)" type="Area2D" parent="\."\]\n(.*?)(?=\n\[node )', re.S)

# 계단을 여는 열쇠는 소모형이므로, 층을 벗어나려면 그 층까지 오는 동안 얻을 수 있어야 한다.
KEY_SCRIPTS = ("pickup_item.gd", "interactable.gd")


def parse_floor(floor):
    text = (ROOT / f"scenes/background/school_floor_{floor}.tscn").read_text()

    ext = dict(re.findall(r'\[ext_resource type="Script" path="res://scripts/interactions/([^"]+)" id="([^"]+)"\]', text))
    script_of = {v: k for k, v in ext.items()}

    rooms = []
    for m in ROOM_RE.finditer(text):
        nums = [float(x) for x in m.group(2).split(",")]
        xs, ys = nums[0::2], nums[1::2]
        rooms.append((m.group(1), min(xs), min(ys), max(xs), max(ys)))

    objects = []
    for m in NODE_RE.finditer(text):
        name, body = m.group(1), m.group(2)
        sm = re.search(r'script = ExtResource\("([^"]+)"\)', body)
        pm = re.search(r'^position = Vector2\(([-\d.]+), ([-\d.]+)\)', body, re.M)
        if not (sm and pm):
            continue
        script = script_of.get(sm.group(1), "?")
        item = re.search(r'^(?:grants_)?item_id = "([^"]*)"', body, re.M)
        objects.append({
            "name": name,
            "script": script,
            "pos": (float(pm.group(1)), float(pm.group(2))),
            "item": item.group(1) if item else "",
        })
    return rooms, objects


def door_gap(x0, y0, x1, y1):
    """문 틈 사각형(벽 두께만큼 안쪽으로 파고든 통로)."""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    dl, dr = cx - DOOR_W / 2, cx + DOOR_W / 2
    if cy < CENTER_Y:
        return (dl, y1 - T - CLEARANCE, dr, y1)
    return (dl, y0, dr, y0 + T + CLEARANCE)


def main():
    errors = []
    key_sources = {}   # item_id -> 얻을 수 있는 최소 층수 대신 "그 층에 있다"는 집합
    for floor in FLOORS:
        rooms, objects = parse_floor(floor)
        placed = []

        for obj in objects:
            # 계단 자물쇠·탈출구는 복도/계단실에 있으므로 배치 검사 대상이 아니다
            if obj["script"] in ("locked_door.gd", "exit_door.gd", "hiding_spot.gd"):
                if obj["script"] == "hiding_spot.gd":
                    placed.append(obj)   # 겹침 검사에는 포함
                continue

            x, y = obj["pos"]
            inside = None
            for name, x0, y0, x1, y1 in rooms:
                if x0 + T + CLEARANCE <= x <= x1 - T - CLEARANCE and y0 + T + CLEARANCE <= y <= y1 - T - CLEARANCE:
                    inside = (name, x0, y0, x1, y1)
                    break
            if inside is None:
                errors.append(f"{floor}층 {obj['name']} {obj['pos']}: 어떤 방 안쪽에도 없음(벽/복도와 겹칠 수 있음)")
                continue

            gx0, gy0, gx1, gy1 = door_gap(*inside[1:])
            if gx0 <= x <= gx1 and gy0 <= y <= gy1:
                errors.append(f"{floor}층 {obj['name']} {obj['pos']}: {inside[0]} 문 틈을 막음")

            for other in placed:
                ox, oy = other["pos"]
                if abs(ox - x) < MIN_GAP and abs(oy - y) < MIN_GAP:
                    errors.append(f"{floor}층 {obj['name']}와 {other['name']}가 너무 가까움({obj['pos']} / {other['pos']})")
            placed.append(obj)

            if obj["item"].startswith("stair_key_") or obj["item"] == "front_gate_key":
                key_sources.setdefault(obj["item"], []).append((floor, obj["name"]))

        print(f"{floor}층: 방 {len(rooms)}개, 오브젝트 {len(objects)}개 검사")

    # 진행 검사: 4층에서 시작해 아래로 내려간다. N층을 벗어나려면 stair_key_N이 필요하고,
    # 그 열쇠는 N층 또는 그 위(먼저 지나온 층)에서 얻을 수 있어야 한다.
    print()
    for floor in (4, 3, 2):
        key = f"stair_key_{floor}"
        sources = key_sources.get(key, [])
        reachable = [s for s in sources if s[0] >= floor]
        where = ", ".join(f"{f}층 {n}" for f, n in sources) or "없음"
        print(f"{key}: {where}")
        if not reachable:
            errors.append(f"{key}를 {floor}층 이상에서 얻을 수 없음 — {floor}층에서 막힌다")
    front = key_sources.get("front_gate_key", [])
    print(f"front_gate_key: {', '.join(f'{f}층 {n}' for f, n in front) or '없음'}")
    if not front:
        errors.append("front_gate_key 출처가 없음 — 탈출 불가")

    if errors:
        print("\n문제:")
        for e in errors:
            print(" -", e)
        return 1
    print("\n배치·진행 문제 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
