#!/usr/bin/env python3
"""진행 사슬 검사 (#159 P3).

4층 시작 → 계단 열쇠로 하강 → 1층 현관 탈출까지 실제로 완주 가능한지
정적으로 시뮬레이션한다. 각 층에서
  1) 도착 지점에서 걸어갈 수 있는 범위(격자 BFS, 자물쇠 배리어 포함)를 구하고
  2) 그 범위 안의 아이템 소스(item_id / grants_item_id)를 인벤토리에 넣고
  3) 그 층 계단 자물쇠가 요구하는 열쇠를 갖고 있는지 확인한 뒤
  4) 다음 층으로 내려간다.
열쇠가 없으면 그 지점에서 진행 불가로 실패한다.
"""
import re, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import verify_floor_reach as V

ROOT = V.ROOT
START_FLOOR, END_FLOOR = 4, 1

area_re = re.compile(r'\[node name="(\w+)" type="Area2D" parent="\."\]\n'
                     r'((?:(?!\[node)[^\n]*\n)*)')


def scan(fl):
    text = (ROOT / f"scenes/background/school_floor_{fl}.tscn").read_text()
    items, locks, exits = [], [], []
    for m in area_re.finditer(text):
        name, body = m.group(1), m.group(2)
        pos = re.search(r"position = Vector2\(([-\d.]+), ([-\d.]+)\)", body)
        if not pos:
            continue
        p = (float(pos.group(1)), float(pos.group(2)))
        got = re.search(r'\n(?:item_id|grants_item_id) = "([^"]+)"', body)
        if got:
            items.append((name, got.group(1), p))
        req = re.search(r'\nrequired_item_id = "([^"]+)"', body)
        if req:
            locks.append((name, req.group(1), p))
        if 'ExtResource("4_exit")' in body or "exit_door" in body:
            exits.append((name, p))
    return items, locks, exits


def main():
    inv, log, bad = set(), [], 0
    arrive = (579, 692)   # main.tscn의 4층 시작 위치

    for fl in range(START_FLOOR, END_FLOOR - 1, -1):
        walls, rooms, (w, h), _ = V.parse(ROOT / f"scenes/background/school_floor_{fl}.tscn")
        blocked, cols, rows = V.build_grid(walls, w, h)
        seen = V.flood(blocked, cols, rows, arrive)
        reach = lambda p: (int(p[1] // V.CELL), int(p[0] // V.CELL)) in seen

        items, locks, exits = scan(fl)
        picked = []
        for name, item, p in items:
            if reach(p):
                inv.add(item)
                picked.append(f"{name}({item})")
        log.append(f"{fl}층: 획득 {', '.join(picked) if picked else '없음'}")

        if fl == END_FLOOR:
            if not exits:
                print(f"  ✗ {fl}층에 현관(exit_door)이 없다"); bad += 1
            elif not reach(exits[0][1]):
                print(f"  ✗ {fl}층 현관에 도달할 수 없다"); bad += 1
            elif "front_gate_key" not in inv:
                print("  ✗ 현관 열쇠(front_gate_key)를 얻지 못했다"); bad += 1
            break

        need = {req for _, req, _ in locks}
        missing = need - inv
        if missing:
            print(f"  ✗ {fl}층 계단 자물쇠가 요구하는 {sorted(missing)}를 얻을 수 없다")
            bad += 1
            break
        # 열쇠를 썼다고 보고 다음 층 도착 지점으로
        arrive = (579, 692) if fl - 1 != 1 else (440 + 59, 2120 - 28)

    print("\n".join("  " + l for l in log))
    print("\n진행 가능 — 4층 시작에서 1층 현관 탈출까지 완주" if bad == 0
          else f"\n진행 불가 {bad}건")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
