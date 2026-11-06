#!/usr/bin/env python3
"""판마다 바뀌는 단서·열쇠 자리 검사 (#794).

`gen_floors.CLUE_SITES`의 후보는 런타임(`clue_shuffle.gd`)이 고르므로 씬에는
기본 자리(첫 후보) 하나만 구워진다. 다른 후보는 검사 7종이 한 번도 안 본다 —
그래서 여기서 **후보 번호마다 씬을 다시 굽고 검사 7종을 돌린다.** 집기는 모든
후보를 피하게 깔리므로(`sc.clue_pts`) 후보 번호가 달라도 바뀌는 것은 단서
노드와 표시뿐이다.

검사 7종이 못 보는 것 둘을 더 본다.
  1. **다른 묶음끼리 상호작용 존이 겹치는가**(`verify_props.CLUE_GAP`). 변형
     번호마다 묶음이 같은 번호의 후보를 쓰므로, 런타임에 나올 수 있는 조합
     (예: 1번 묶음은 0번 후보, 2번 묶음은 2번 후보)은 변형만으로 다 안 나온다.
     자리는 서로 독립이니 **모든 후보 쌍**을 직접 본다(고정 단서 포함).
  2. **강제 동선에서 얼마나 우회하는가**(#350) — 도착 지점 → 단서 → 그 층
     출구의 도보 거리에서 도착 → 출구를 뺀 값. 보고만 하고 실패로 치지 않는다
     (숫자를 보고 후보를 고르라는 것이다). 닿지 않으면 실패다.

끝나면 `CLUE_SITE=0`으로 다시 구워 저장소를 기본 상태로 되돌린다 —
결정론적이라 `git diff`가 비어야 한다.

    python3 tools/verify_clue_sites.py          # 전부
    python3 tools/verify_clue_sites.py --quick  # 1·2만(다시 굽지 않음)
"""
import collections
import os
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import gen_floors as G  # noqa: E402
import verify_floor_reach as V  # noqa: E402
import verify_progression as VP  # noqa: E402
import verify_props as VPR  # noqa: E402

ROOT = TOOLS.parent
CHECKS = ["verify_scenes", "verify_floor_reach", "verify_stairs", "verify_progression",
          "verify_props", "verify_hiding_spots", "verify_janitor_route"]


def regen(k):
    env = dict(os.environ, CLUE_SITE=str(k))
    r = subprocess.run([sys.executable, str(TOOLS / "gen_floors.py")], env=env,
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit(f"gen_floors.py 실패 (CLUE_SITE={k})")


def run_checks(k):
    bad = 0
    # 검사기도 후보 번호를 알아야 한다 — `verify_progression`이 단서가 **그 후보의
    # 방**에 떨어졌는지 본다.
    env = dict(os.environ, CLUE_SITE=str(k))
    for name in CHECKS:
        r = subprocess.run([sys.executable, str(TOOLS / f"{name}.py")], env=env,
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode != 0:
            bad += 1
            lines = [ln for ln in (r.stdout + r.stderr).splitlines()
                     if "✗" in ln or "ERROR" in ln or "error" in ln.lower()]
            print(f"  ✗ 후보 {k}: {name} 실패")
            for ln in (lines or (r.stdout + r.stderr).splitlines()[-8:])[:12]:
                print(f"      {ln.strip()}")
    return bad


def fixed_clues(fl):
    """고정 단서(`PLACEMENT`) 자리 — 씬에서 읽는다."""
    names = {nm for _room, ns in G.PLACEMENT.get(fl, []) for nm in ns}
    items, _locks, exits, _links, flags = VP.scan(fl)
    out = {}
    for nm, _x, p in items + flags:
        if nm in names:
            out[nm] = p
    for nm, p in exits:
        out[nm] = p
    return out


def check_gaps():
    bad = 0
    for fl, groups in sorted(G.CLUE_SITES.items()):
        pts = [(f"고정 {nm}", nm, p) for nm, p in fixed_clues(fl).items()]
        for gi, (names, sites) in enumerate(groups):
            for si, (room, ps, _h) in enumerate(sites):
                for nm, p in zip(names, ps):
                    pts.append((f"묶음{gi}", f"{nm}@{room}", p))
            # 같은 묶음 안의 노드끼리도(열쇠 보관함 ↔ 고리) 떨어져 있어야 한다.
            for room, ps, _h in sites:
                for i in range(len(ps)):
                    for j in range(i + 1, len(ps)):
                        d = ((ps[i][0] - ps[j][0]) ** 2 + (ps[i][1] - ps[j][1]) ** 2) ** 0.5
                        if d < VPR.CLUE_GAP:
                            print(f"  ✗ {fl}층 {names[i]}·{names[j]}@{room}: {d:.0f}px "
                                  f"< {VPR.CLUE_GAP}")
                            bad += 1
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                gi, ni, pi = pts[i]
                gj, nj, pj = pts[j]
                if gi == gj:
                    continue
                d = ((pi[0] - pj[0]) ** 2 + (pi[1] - pj[1]) ** 2) ** 0.5
                if d < VPR.CLUE_GAP:
                    print(f"  ✗ {fl}층 {ni} ↔ {nj}: {d:.0f}px < {VPR.CLUE_GAP} "
                          f"(상호작용 존이 겹친다)")
                    bad += 1
    print(f"  후보 간격: {'문제 없음' if bad == 0 else f'{bad}건'}")
    return bad


def bfs(blocked, cols, rows, start):
    sr, sc = int(start[1] // V.CELL), int(start[0] // V.CELL)
    if blocked[sr][sc]:
        # 도착 지점·계단 자물쇠는 벽·배리어에 붙어 있어 칸이 막혀 있을 수 있다 —
        # 가장 가까운 빈 칸에서 시작한다(`verify_floor_reach.flood`와 같은 방식).
        sr, sc = min(((r, c) for r in range(max(0, sr - 4), min(rows, sr + 5))
                      for c in range(max(0, sc - 4), min(cols, sc + 5)) if not blocked[r][c]),
                     key=lambda rc: abs(rc[0] - sr) + abs(rc[1] - sc))
    dist = {(sr, sc): 0}
    q = collections.deque([(sr, sc)])
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if (0 <= nr < rows and 0 <= nc < cols and not blocked[nr][nc]
                    and (nr, nc) not in dist):
                dist[(nr, nc)] = dist[(r, c)] + 1
                q.append((nr, nc))
    return dist


def near(dist, p):
    """그 자리에 서서 손이 닿는 칸 중 가장 가까운 거리(px). 없으면 None."""
    r0, c0 = int(p[1] // V.CELL), int(p[0] // V.CELL)
    best = None
    k = VP.REACH_CELLS
    for dr in range(-k, k + 1):
        for dc in range(-k, k + 1):
            d = dist.get((r0 + dr, c0 + dc))
            if d is not None and (best is None or d < best):
                best = d
    return None if best is None else best * V.CELL


def route_ends(fl):
    """(도착 지점, 출구) — 3층 도착은 4층 창문의 `arrive_at`이다."""
    if fl == 3:
        link = next(l for l in VP.scan(4)[3] if l[1] == 3)
        arrive = link[4]
    else:
        arrive = VP.ARRIVE[fl]
    _items, locks, exits, _links, _flags = VP.scan(fl)
    end = exits[0][1] if fl == 1 else locks[0][2]
    return arrive, end


def check_detours():
    bad = 0
    for fl, groups in sorted(G.CLUE_SITES.items(), reverse=True):
        walls, _rooms, (w, h), _ = V.parse(ROOT / f"scenes/background/school_floor_{fl}.tscn")
        blocked, cols, rows = V.build_grid(walls, w, h)
        arrive, end = route_ends(fl)
        d_arr = bfs(blocked, cols, rows, arrive)
        d_end = bfs(blocked, cols, rows, end)
        base = near(d_arr, end)
        print(f"  {fl}층 도착→출구 {base}px")
        for names, sites in groups:
            row = []
            for room, ps, _h in sites:
                a, b = near(d_arr, ps[0]), near(d_end, ps[0])
                if a is None or b is None:
                    print(f"  ✗ {fl}층 {names[0]}@{room} {ps[0]}: 걸어서 닿지 않는다")
                    bad += 1
                    continue
                row.append(f"{room} +{a + b - base}")
            print(f"     {names[0]:<16} " + " / ".join(row))
    return bad


def main():
    quick = "--quick" in sys.argv
    if not quick:
        regen(0)  # 우회 거리는 지금 표로 구운 씬에서 잰다 — 남아 있던 씬은 낡았을 수 있다
    bad = check_gaps() + check_detours()
    if not quick:
        count = max(len(s) for groups in G.CLUE_SITES.values() for _n, s in groups)
        try:
            for k in range(count):
                regen(k)
                b = run_checks(k)
                print(f"  후보 {k}: 검사 {len(CHECKS)}종 {'통과' if b == 0 else f'{b}종 실패'}")
                bad += b
        finally:
            regen(0)
    print("\n문제 없음" if bad == 0 else f"\n문제 {bad}건")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
