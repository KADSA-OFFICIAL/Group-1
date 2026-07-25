#!/usr/bin/env python3
"""은신처(#6)를 층 씬에 삽입한다 — 1회용 생성 스크립트.

12개를 손으로 넣으면 load_steps나 ext_resource id를 어긋나게 하기 쉬워서
스크립트로 넣는다. 좌표는 tools/verify_hiding_spots.py --suggest 로 뽑은
"벽과 겹치지 않고 계단에서 걸어서 닿는" 지점이다.

⚠️ 재실행 경고: 같은 씬에 두 번 돌리면 노드와 ext_resource가 중복된다.
이미 은신처가 있으면 아무것도 하지 않고 건너뛴다.

  python tools/add_hiding_spots.py
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

HIDING_SCRIPT = "res://scripts/interactions/hiding_spot.gd"
ZONE_SHAPE = "RectangleShape2D_key_zone"   # 48×48, 전 층에 이미 있음

# 사물함 몸체: 36×52 세로 직사각형. z_index는 Blackboard와 같게 1로 둬서
# 바닥·방 폴리곤 위에 확실히 그려지게 한다.
LOCKER_POLYGON = "PackedVector2Array(-18, -26, 18, -26, 18, 26, -18, 26)"
LOCKER_COLOR = "Color(0.3, 0.32, 0.38, 1)"

# 층 -> [(노드 이름, x, y, prompt_text, message)]
SPOTS: dict[int, list[tuple[str, int, int, str, str]]] = {
    1: [
        ("HideClass1_1", 262, 362, "사물함에 숨기",
         "1학년 1반 사물함. 낡은 체육복 냄새 사이로 몸을 접어 넣었다."),
        ("HideMusicRoom", 2238, 362, "악기함에 숨기",
         "첼로 케이스를 밀어내고 그 자리에 들어갔다. 숨소리를 죽인다."),
        ("HideEmptyRoom", 1688, 1212, "청소함에 숨기",
         "대걸레와 양동이 사이. 문틈으로 복도가 실처럼 보인다."),
    ],
    2: [
        ("HideClass1", 262, 362, "사물함에 숨기",
         "누군가의 사물함. 안쪽에 이름표가 떨어져 있다."),
        ("HideClass6", 2238, 362, "사물함에 숨기",
         "문이 헐거운 사물함. 몸을 웅크리고 숨을 참았다."),
        ("HideShower", 612, 1538, "샤워칸에 숨기",
         "샤워칸 커튼 뒤. 마른 배수구에서 쇠 냄새가 올라온다."),
    ],
    3: [
        ("HideClass2", 562, 362, "사물함에 숨기",
         "사물함 안. 어둠에 눈이 익을 때까지 기다린다."),
        ("HideClass5", 1938, 362, "사물함에 숨기",
         "빈 사물함. 등을 붙이자 철판이 서늘하다."),
        ("HideBroadcastRoom", 888, 1538, "장비함에 숨기",
         "방송 장비함. 케이블 뭉치를 껴안은 자세로 굳었다."),
    ],
    4: [
        ("HideClass1", 262, 362, "사물함에 숨기",
         "사물함 안으로 몸을 밀어 넣었다. 경첩이 작게 울었다."),
        ("HideClass6", 2238, 362, "사물함에 숨기",
         "사물함 깊숙이. 문틈으로 들어오는 빛이 전부다."),
        ("HideHistoryArchive", 888, 1538, "자료함에 숨기",
         "역사자료실 캐비닛. 곰팡이 슬은 종이 냄새가 코를 찌른다."),
    ],
}


def build_nodes(spots, ext_id: str) -> str:
    out = []
    for name, x, y, prompt, message in spots:
        out.append(f"""
[node name="{name}" type="Area2D" parent="."]
position = Vector2({x}, {y})
collision_layer = 2
collision_mask = 0
script = ExtResource("{ext_id}")
prompt_text = "{prompt}"
message = "{message}"

[node name="{name}Visual" type="Polygon2D" parent="{name}"]
z_index = 1
color = {LOCKER_COLOR}
polygon = {LOCKER_POLYGON}

[node name="{name}Zone" type="CollisionShape2D" parent="{name}"]
shape = SubResource("{ZONE_SHAPE}")
""".rstrip() + "\n")
    return "".join(out)


def patch_floor(floor: int) -> bool:
    path = ROOT / f"scenes/background/school_floor_{floor}.tscn"
    text = path.read_text(encoding="utf-8")

    if HIDING_SCRIPT in text:
        print(f"  {floor}층: 이미 은신처가 있다 — 건너뜀")
        return False

    ext_lines = list(re.finditer(r'^\[ext_resource .*\]$', text, re.M))
    if not ext_lines:
        print(f"  {floor}층: ext_resource를 찾을 수 없다", file=sys.stderr)
        return False

    # 기존 id에서 쓰이지 않은 다음 번호를 고른다
    used = {int(m.group(1)) for m in re.finditer(r'id="(\d+)_', text)}
    ext_id = f"{max(used) + 1}_hiding"

    ext_line = f'[ext_resource type="Script" path="{HIDING_SCRIPT}" id="{ext_id}"]'
    last = ext_lines[-1]
    text = text[:last.end()] + "\n" + ext_line + text[last.end():]

    # load_steps = ext_resource 수 + sub_resource 수 + 1
    ext_count = len(re.findall(r'^\[ext_resource ', text, re.M))
    sub_count = len(re.findall(r'^\[sub_resource ', text, re.M))
    want = ext_count + sub_count + 1
    text = re.sub(r'^\[gd_scene load_steps=\d+ format=3\]',
                  f'[gd_scene load_steps={want} format=3]', text, count=1)

    if not text.endswith("\n"):
        text += "\n"
    text += build_nodes(SPOTS[floor], ext_id)

    # .gitattributes가 eol=lf를 요구한다. newline을 지정하지 않으면 Windows에서
    # 파일 전체가 CRLF로 바뀌어 씬 전체가 변경된 것처럼 보인다.
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"  {floor}층: 은신처 {len(SPOTS[floor])}개 추가, "
          f"ext_resource id={ext_id}, load_steps={want}")
    return True


def main() -> int:
    print("은신처 삽입")
    changed = 0
    for floor in sorted(SPOTS):
        if patch_floor(floor):
            changed += 1
    print(f"\n{changed}개 층 수정")
    return 0


if __name__ == "__main__":
    sys.exit(main())
