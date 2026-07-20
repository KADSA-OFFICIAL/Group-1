#!/usr/bin/env python3
"""각 층 .tscn의 Rooms 폴리곤을 읽어 방 둘레 벽(충돌+시각)과 문 틈을 생성해 삽입한다.

⚠️ 재실행 주의:
- RoomWalls/RoomWallVisuals 섹션을 통째로 지우고 다시 만든다.
  5층에는 수동으로 넣은 벽(미술실·빈 교실 창문, 난간 봉쇄 LedgeSeal 등)이
  RoomWalls 안에 있으므로 5층에 재실행하면 사라진다. 재실행하려면 해당 층을
  FILES에서 제외하거나 수동 벽을 다시 넣어야 한다.
- 벽을 바꾸면 광원 차단체(Occluders)와 어긋난다 — gen_occluders.py를 다시 돌릴 것
  (기존 Occluders 섹션·Occ_ sub_resource를 먼저 제거해야 함).

규약: 벽 두께 16px, 문 폭 110px(방 가로 중앙), 방 중심 y<900이면 문은 아래변/아니면 위변.
"""
import re, pathlib

T = 16        # 벽 두께
D = 110       # 문 틈 폭
CENTER_Y = 900
WALL_COLOR = "Color(1.6, 1.7, 2.1, 1)"
DOOR_COLOR = "Color(0.45, 0.32, 0.2, 1)"

FILES = [f"scenes/background/school_floor_{i}.tscn" for i in range(1, 6)]
ROOT = pathlib.Path(__file__).resolve().parent.parent

room_block_re = re.compile(
    r'\[node name="([^"]+)" type="Polygon2D" parent="Rooms"\]\s*\n'
    r'color = [^\n]*\n'
    r'polygon = PackedVector2Array\(([^)]*)\)'
)

def rect_poly(ax, ay, bx, by):
    return f"PackedVector2Array({ax}, {ay}, {bx}, {ay}, {bx}, {by}, {ax}, {by})"

def gen_for_room(name, x0, y0, x1, y1):
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    door_bottom = cy < CENTER_Y
    dl, dr = cx - D / 2.0, cx + D / 2.0

    walls = []
    walls.append(("left",  x0, y0, x0 + T, y1))
    walls.append(("right", x1 - T, y0, x1, y1))
    if door_bottom:
        walls.append(("top", x0, y0, x1, y0 + T))
        walls.append(("botL", x0, y1 - T, dl, y1))
        walls.append(("botR", dr, y1 - T, x1, y1))
        door = (dl, y1 - T, dr, y1)
    else:
        walls.append(("bot", x0, y1 - T, x1, y1))
        walls.append(("topL", x0, y0, dl, y0 + T))
        walls.append(("topR", dr, y0, x1, y0 + T))
        door = (dl, y0, dr, y0 + T)

    col, vis = [], []
    for suf, ax, ay, bx, by in walls:
        nm = f"{name}_{suf}"
        col.append(
            f'[node name="WC_{nm}" type="CollisionPolygon2D" parent="RoomWalls"]\n'
            f'polygon = {rect_poly(ax, ay, bx, by)}\n'
        )
        vis.append(
            f'[node name="WV_{nm}" type="Polygon2D" parent="RoomWallVisuals"]\n'
            f'color = {WALL_COLOR}\n'
            f'polygon = {rect_poly(ax, ay, bx, by)}\n'
        )
    ax, ay, bx, by = door
    vis.append(
        f'[node name="Door_{name}" type="Polygon2D" parent="RoomWallVisuals"]\n'
        f'color = {DOOR_COLOR}\n'
        f'polygon = {rect_poly(ax, ay, bx, by)}\n'
    )
    return col, vis

def num(s):
    f = float(s)
    return int(f) if f == int(f) else f

for rel in FILES:
    path = ROOT / rel
    text = path.read_text()

    text = re.sub(r'\n\[node name="RoomWalls".*?(?=\n\[node name="Walls")', '\n', text, flags=re.S)
    text = re.sub(r'\n\[node name="RoomWallVisuals".*?(?=\n\[node name="Walls")', '\n', text, flags=re.S)

    rooms = []
    for m in room_block_re.finditer(text):
        name = m.group(1)
        nums = [num(x.strip()) for x in m.group(2).split(",")]
        xs = nums[0::2]; ys = nums[1::2]
        rooms.append((name, min(xs), min(ys), max(xs), max(ys)))

    if not rooms:
        print(f"WARN: no rooms in {rel}")
        continue

    col_all, vis_all = [], []
    for r in rooms:
        c, v = gen_for_room(*r)
        col_all.extend(c); vis_all.extend(v)

    block = (
        '[node name="RoomWalls" type="StaticBody2D" parent="."]\n\n'
        + "\n".join(col_all)
        + '\n[node name="RoomWallVisuals" type="Node2D" parent="."]\n\n'
        + "\n".join(vis_all)
    )

    idx = text.index('[node name="Walls"')
    new_text = text[:idx] + block + "\n" + text[idx:]
    path.write_text(new_text)
    print(f"OK {rel}: {len(rooms)} rooms")
