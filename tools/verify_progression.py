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
## main.tscn의 시작 위치 — 4층 미술실 안(#405).
START_POS = (300, 700)
## 상호작용은 옆에 서서 한다 — 단서 칸에서 이만큼 떨어진 칸에 설 수 있으면 닿는다.
## 플레이어 상호작용 반경(≈40px)에 맞춘 값이다(CELL=20).
REACH_CELLS = 2
## 계단으로 내려왔을 때의 도착 지점(층 -> 자리). 창문 같은 층 통로는 자기
## `arrive_at`을 갖고 있으므로 여기 표를 안 쓴다.
## 1층 값은 `floor_manager.STAIRS[1]`(220, 800, 440x320)에서 나온다 —
## `_arrive_on`이 사각형 **위쪽** `ARRIVE_DY`(28)만큼 앞, 가로로는 가운데에서
## `ARRIVE_DX`(59)만큼 비켜선 자리다. 1층 캔버스가 3400x1500으로 줄면서
## 계단이 하단 띠(800~1480)로 올라왔다(#498).
ARRIVE = {3: (579, 692), 2: (579, 692), 1: (220 + 220 + 59, 800 - 28)}

area_re = re.compile(r'\[node name="(\w+)" type="Area2D" parent="\."\]\n'
                     r'((?:(?!\[node)[^\n]*\n)*)')


def scan(fl):
    text = (ROOT / f"scenes/background/school_floor_{fl}.tscn").read_text()
    items, locks, exits, links, flags = [], [], [], [], []
    for m in area_re.finditer(text):
        name, body = m.group(1), m.group(2)
        pos = re.search(r"position = Vector2\(([-\d.]+), ([-\d.]+)\)", body)
        if not pos:
            continue
        p = (float(pos.group(1)), float(pos.group(2)))
        got = re.search(r'\n(?:item_id|grants_item_id) = "([^"]+)"', body)
        if got:
            items.append((name, got.group(1), p))
        flag = re.search(r'\ngrants_flag = "([^"]+)"', body)
        if flag:
            flags.append((name, flag.group(1), p))
        # **계단 자물쇠만** 센다. `required_item_id`만 보면 층 통로(창문, #406)와
        # 현관까지 자물쇠로 세어, 하강 수단이 사라져도 '자물쇠는 있으니 괜찮다'로
        # 통과한다 — 실제로 창문을 지웠는데 검사가 안 걸렸다.
        is_link = "floor_link" in body or 'ExtResource("11_floorlink")' in body
        is_exit = 'ExtResource("4_exit")' in body or "exit_door" in body
        req = re.search(r'\nrequired_item_id = "([^"]+)"', body)
        if req and not is_link and not is_exit:
            locks.append((name, req.group(1), p))
        if is_exit:
            exits.append((name, p))
        # 계단이 아닌 하강 수단(#406) — 지금은 미술실 준비실 창문뿐이다.
        if is_link:
            tf = re.search(r"^target_floor = (-?\d+)$", body, re.M)
            req = re.search(r'^required_item_id = "([^"]*)"$', body, re.M)
            arr = re.search(r"^arrive_at = Vector2\(([-\d.]+), ([-\d.]+)\)$",
                            body, re.M)
            links.append((name, int(tf.group(1)) if tf else -1,
                          req.group(1) if req else "", p,
                          (float(arr.group(1)), float(arr.group(2))) if arr else None))
    return items, locks, exits, links, flags


GEN_FLOORS = ROOT / "tools/gen_floors.py"


def placement_table():
    """`gen_floors.PLACEMENT`의 (층, 오브젝트) -> 방 키."""
    text = GEN_FLOORS.read_text(encoding="utf-8")
    m = re.search(r"^PLACEMENT = \{(.*?)^\}", text, re.M | re.S)
    if m is None:
        return None
    want = {}
    for fm in re.finditer(r"^    (\d+): \[(.*?)\],?\s*$", m.group(1), re.M | re.S):
        fl = int(fm.group(1))
        for room, objs in re.findall(r'\("(\w+)", \[([^\]]*)\]\)', fm.group(2)):
            for obj in re.findall(r'"(\w+)"', objs):
                want[(fl, obj)] = room
    return want


def check_placement_rooms():
    """**단서가 `PLACEMENT`이 지정한 방 안에 실제로 떨어졌는가.**

    `POS_OVERRIDE`는 손으로 적는 절대 좌표라 방이 옮겨 가면 그대로 남는다 —
    #691에서 2·3층을 줄였을 때 **계단 열쇠 둘**(`SpareKeyHook`·`HeadKey`)이
    옛 방 자리에 남아 엉뚱한 방에 떨어졌다. 그 상태로 **검사 7종이 전부
    통과했다**: 도달성·집기 겹침·진행 사슬은 "걸어서 닿는가"만 보므로 열쇠가
    옆방에 있어도 통과한다. 그런데 단서 문구는 방을 가리키므로(#444의 교훈)
    화면과 말이 어긋나고, 방을 옮길 때마다 되풀이될 사고라 여기서 본다.
    """
    want = placement_table()
    if want is None:
        print("  ✗ gen_floors.PLACEMENT를 읽지 못했다")
        return 1
    bad = 0
    for fl in sorted({f for f, _ in want}):
        path = ROOT / f"scenes/background/school_floor_{fl}.tscn"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        _walls, rooms, _size, _ = V.parse(path)
        for (f, obj), room in sorted(want.items()):
            if f != fl:
                continue
            pat = ('\\[node name="' + obj + '" type="Area2D"[^\\]]*\\]\n'
                   r"((?:(?!\[node)[^\n]*\n)*)")
            nm = re.search(pat, text)
            if nm is None:
                continue
            pm = re.search(r"position = Vector2\(([-\d.]+), ([-\d.]+)\)", nm.group(1))
            if pm is None:
                continue
            x, y = float(pm.group(1)), float(pm.group(2))
            if room not in rooms:
                print(f"  ✗ {fl}층 {obj}: PLACEMENT가 지정한 방 {room}이 씬에 없다")
                bad += 1
                continue
            if not V.inside(rooms[room], x, y):
                actual = next((k for k, poly in rooms.items() if V.inside(poly, x, y)),
                              "어느 방도 아님")
                print(f"  ✗ {fl}층 {obj} ({x:.0f},{y:.0f}): "
                      f"지정 {room} -> 실제 {actual}  (POS_OVERRIDE를 새 방에 맞출 것)")
                bad += 1
    return bad


GAME_STATE = ROOT / "scripts/game/game_state.gd"


def gd_list(text, name):
    """`const NAME := [ "a", "b" ]`의 문자열들."""
    m = re.search(rf"^const {name} := \[(.*?)\]", text, re.M | re.S)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else None


def gd_floor_table(text, name):
    """`const NAME := { 4: [...], 3: [...] }` → {층: [플래그]}."""
    m = re.search(rf"^const {name} := \{{(.*?)^\}}", text, re.M | re.S)
    if not m:
        return None
    return {int(fl): re.findall(r'"([^"]+)"', body)
            for fl, body in re.findall(r"^\s*(\d+): \[([^\]]*)\]", m.group(1), re.M)}


def check_ending_tally(flags_at):
    """HUD의 층별 엔딩 진행도(`*_ENDING_BY_FLOOR`)가 씬과 맞는가(#665).

    상담기록부를 #411에서 3층으로 옮겼는데 표만 4층에 남아, HUD가 다시 갈 수
    없는 4층의 단서를 놓쳤다고 알렸다. 표가 손으로 적는 것이라 씬을 옮길 때마다
    어긋날 수 있다 — ① 각 플래그가 **그 층에서 걸어서 닿는** `grants_flag`로
    있는지, ② 표의 합이 판정 상수(`MISSING`+`SIWOO` / `COVERUP`)와 같은지 본다.
    ②가 없으면 판정에는 있는데 HUD에 안 뜨는(또는 그 반대) 단서를 못 잡는다.
    """
    text = GAME_STATE.read_text()
    bad = 0
    for table, judge in (("TRUE_ENDING_BY_FLOOR", ("MISSING_FLAGS", "SIWOO_FLAGS")),
                         ("REPORT_ENDING_BY_FLOOR", ("COVERUP_FLAGS",))):
        tally = gd_floor_table(text, table)
        want = [gd_list(text, j) for j in judge]
        if tally is None or None in want:
            print(f"  ✗ game_state.gd에서 {table} / {judge}를 읽지 못했다"); bad += 1
            continue
        listed = [f for fl in tally for f in tally[fl]]
        if sorted(listed) != sorted(set(listed)):
            print(f"  ✗ {table}에 같은 플래그가 두 층에 적혀 있다: {listed}"); bad += 1
        if set(listed) != {f for w in want for f in w}:
            print(f"  ✗ {table} 합 {sorted(set(listed))} ≠ "
                  f"{'+'.join(judge)} {sorted({f for w in want for f in w})}"); bad += 1
        for fl, fs in sorted(tally.items(), reverse=True):
            for f in fs:
                if f not in flags_at.get(fl, set()):
                    where = [k for k, v in sorted(flags_at.items(), reverse=True) if f in v]
                    print(f"  ✗ {table}: {f}를 {fl}층 몫으로 세지만 {fl}층에서 얻을 수 없다"
                          f" (실제: {', '.join(f'{k}층' for k in where) or '없음'})"); bad += 1
    if not bad:
        print("  층별 엔딩 진행도(HUD) ↔ 씬 단서 위치 일치")
    return bad


def main():
    inv, log, bad = set(), [], 0
    flags_at = {}  # 층 -> 그 층에서 걸어서 닿는 grants_flag
    arrive = START_POS

    for fl in range(START_FLOOR, END_FLOOR - 1, -1):
        walls, rooms, (w, h), _ = V.parse(ROOT / f"scenes/background/school_floor_{fl}.tscn")
        blocked, cols, rows = V.build_grid(walls, w, h)
        seen = V.flood(blocked, cols, rows, arrive)

        def reach(pt, _seen=seen):
            """그 자리에 **서서 손이 닿는가.** 칸 자체가 아니라 둘레를 본다.

            단서는 집기 위·벽에 붙는 것이 정상이라(#405의 도입부 단서, `Exam_`,
            `Window_`) 그 칸은 도달 격자에서 막혀 있다. 정확히 그 칸을 요구하면
            책상 위 국어책을 "얻을 수 없다"로 잡는다 — 실제로는 옆에 서서 E를
            누르면 된다.
            """
            r0, c0 = int(pt[1] // V.CELL), int(pt[0] // V.CELL)
            for dr in range(-REACH_CELLS, REACH_CELLS + 1):
                for dc in range(-REACH_CELLS, REACH_CELLS + 1):
                    if (r0 + dr, c0 + dc) in _seen:
                        return True
            return False

        items, locks, exits, links, flags = scan(fl)
        flags_at[fl] = {f for _n, f, p in flags if reach(p)}
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

        # ── 아래층으로 내려갈 수단이 **실제로** 있는가 ──────────────
        # 예전에는 계단 자물쇠의 열쇠만 확인했다. 4층에서 계단이 사라지자
        # 확인할 자물쇠가 없어져 **아무것도 검사하지 않고 통과**했다(#406) —
        # 계단이 곧 하강이라는 가정 위에 선 검사였다.
        down = [l for l in links if l[1] == fl - 1]
        if down:
            name, _tf, req, pos, arr = down[0]
            if not reach(pos):
                print(f"  ✗ {fl}층 {name}(아래층 통로)에 도달할 수 없다"); bad += 1; break
            if req and req not in inv:
                print(f"  ✗ {fl}층 {name}가 요구하는 {req}를 얻을 수 없다"); bad += 1; break
            log[-1] += f" → {name}로 {fl - 1}층"
            arrive = arr if arr else ARRIVE[fl - 1]
            continue

        if not locks:
            print(f"  ✗ {fl}층에서 {fl - 1}층으로 내려갈 수단이 없다 "
                  f"(계단 자물쇠도, 층 통로도 없다)")
            bad += 1
            break
        need = {req for _, req, _ in locks}
        missing = need - inv
        if missing:
            print(f"  ✗ {fl}층 계단 자물쇠가 요구하는 {sorted(missing)}를 얻을 수 없다")
            bad += 1
            break
        for _nm, _rq, lp in locks:
            if not reach(lp):
                print(f"  ✗ {fl}층 계단 자물쇠에 도달할 수 없다"); bad += 1
                break
        arrive = ARRIVE[fl - 1]

    bad += check_ending_tally(flags_at)
    bad += check_placement_rooms()

    print("\n".join("  " + l for l in log))
    print(f"\n진행 가능 — {START_FLOOR}층 시작에서 1층 현관 탈출까지 완주"
          if bad == 0 else f"\n진행 불가 {bad}건")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
