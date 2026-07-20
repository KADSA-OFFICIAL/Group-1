#!/usr/bin/env python3
"""#108: 전 층 벽에 LightOccluder2D 생성 — 벽 너머 조명 차단.
- 정적 벽(RoomWalls WC_*, StairWalls RC_*): 루트의 Occluders 그룹에 배치
- 동적 배리어(StairLocks SU/SDBarrier, ArtRoomDoor): 해당 StaticBody2D의 자식으로
  배치해 개방(queue_free) 시 함께 제거되게 함
- OccluderPolygon2D는 sub_resource로 추가, load_steps 갱신
주의: gen_walls.py를 재실행하면 벽과 차단체가 어긋남 — 벽 변경 시 이 스크립트 재실행 필요.
"""
import re, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / "scenes/background"

# 동적 배리어: (충돌 노드명, 부모 StaticBody2D 경로)
DYNAMIC = {
    "SUBarrierCollision": "StairLocks/SUBarrier",
    "SDBarrierCollision": "StairLocks/SDBarrier",
    "ArtRoomDoorCollision": "ArtRoomDoor",
}

col_re = re.compile(
    r'\[node name="((?:WC_|RC_)[^"]+|SUBarrierCollision|SDBarrierCollision|ArtRoomDoorCollision)"'
    r' type="CollisionPolygon2D" parent="([^"]+)"\]\s*\n'
    r'polygon = PackedVector2Array\(([^)]*)\)'
)

for fl in range(1, 6):
    p = ROOT / f"school_floor_{fl}.tscn"
    t = p.read_text()
    if 'name="Occluders"' in t:
        sys.exit(f"ABORT floor{fl}: Occluders 이미 존재")

    cols = [(m.group(1), m.group(2), m.group(3)) for m in col_re.finditer(t)]
    if not cols:
        sys.exit(f"ABORT floor{fl}: 충돌 폴리곤 없음")

    subs, static_nodes, dynamic_blocks = [], [], {}
    for name, parent, poly in cols:
        occ_id = f"Occ_{name}"
        subs.append(f'[sub_resource type="OccluderPolygon2D" id="{occ_id}"]\n'
                    f'polygon = PackedVector2Array({poly})\n\n')
        if name in DYNAMIC:
            dynamic_blocks[name] = (
                f'[node name="LO_{name}" type="LightOccluder2D" parent="{DYNAMIC[name]}"]\n'
                f'occluder = SubResource("{occ_id}")\n\n')
        else:
            static_nodes.append(
                f'[node name="LO_{name}" type="LightOccluder2D" parent="Occluders"]\n'
                f'occluder = SubResource("{occ_id}")\n\n')

    # load_steps 갱신
    ls = int(re.search(r"load_steps=(\d+)", t).group(1))
    t = t.replace(f"load_steps={ls}", f"load_steps={ls + len(subs)}", 1)

    # sub_resource 삽입: 첫 [node 앞
    first_node = t.index("[node name=")
    t = t[:first_node] + "".join(subs) + t[first_node:]

    # 동적 배리어 차단체: 해당 충돌 노드 블록 바로 뒤에 삽입
    for name, block in dynamic_blocks.items():
        m = re.search(r'\[node name="' + re.escape(name) + r'"[^\]]*\]\s*\npolygon = PackedVector2Array\([^)]*\)\n', t)
        if not m: sys.exit(f"ABORT floor{fl}: {name} 블록 못 찾음")
        t = t[:m.end()] + "\n" + block + t[m.end():]

    # 정적 차단체 그룹: Labels 앞 (gen_walls 재생성 구간 밖)
    anchor = '[node name="Labels" type="Node2D" parent="."]'
    if anchor not in t: sys.exit(f"ABORT floor{fl}: Labels 앵커 없음")
    t = t.replace(anchor, '[node name="Occluders" type="Node2D" parent="."]\n\n'
                  + "".join(static_nodes) + anchor, 1)

    p.write_text(t)
    print(f"OK floor{fl}: 차단체 {len(cols)}개 (동적 {len(dynamic_blocks)})")
