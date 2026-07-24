#!/usr/bin/env python3
"""씬·스크립트 정합성 정적 검사 (Godot 없이 실행 가능).

이 환경에는 Godot 바이너리가 없어 구조적 오류가 사용자의 F5까지 흘러가곤 했다.
아래 검사는 그중 반복해서 발생한 오류 유형을 잡는다.

검사 항목
1. load_steps == ext_resource 수 + sub_resource 수 + 1
2. ExtResource/SubResource 참조가 모두 선언돼 있는지
3. ext_resource path의 파일이 실제로 존재하는지
4. node의 parent 경로가 씬 안에 존재하는지 (인스턴스 씬 내부 경로는 건너뜀)
5. 같은 부모 아래 형제 노드 이름이 중복되지 않는지
6. 씬 루트에 붙은 스크립트의 $NodePath / get_node("...")가 해석되는지
7. 벽 충돌(WC_*/RC_*)과 광원 차단체(Occ_*/LO_*)가 1:1인지 (해당 층에 차단체가 있을 때만)

사용법:  python3 tools/verify_scenes.py
종료 코드: 오류 0건이면 0, 있으면 1
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

HEADER_RE = re.compile(r'^\[(\w+)([^\]]*)\]\s*$')
ATTR_RE = re.compile(r'(\w+)=(?:"([^"]*)"|([^\s\]]+))')
EXT_REF_RE = re.compile(r'ExtResource\("([^"]+)"\)')
SUB_REF_RE = re.compile(r'SubResource\("([^"]+)"\)')
POLY_RE = re.compile(r'polygon = PackedVector2Array\(([^)]*)\)')
# 스크립트의 노드 경로 참조: $Foo/Bar, $"Foo Bar", get_node("Foo/Bar")
DOLLAR_RE = re.compile(r'\$(?:"([^"\n]+)"|([A-Za-z_][\w/]*))')
# self에 대한 호출만 검사한다 (other.get_node(...)는 대상 씬 밖이라 확인 불가)
GET_NODE_RE = re.compile(r'(?<![.\w])get_node(?:_or_null)?\("([^"\n]+)"\)')

errors: list[str] = []


def fail(scene: str, message: str) -> None:
    errors.append(f"{scene}: {message}")


def parse_attrs(raw: str) -> dict[str, str]:
    return {m.group(1): (m.group(2) if m.group(2) is not None else m.group(3))
            for m in ATTR_RE.finditer(raw)}


class Section:
    def __init__(self, kind: str, attrs: dict[str, str]) -> None:
        self.kind = kind
        self.attrs = attrs
        self.body: list[str] = []

    @property
    def text(self) -> str:
        return "\n".join(self.body)


def parse_scene(path: pathlib.Path) -> list[Section]:
    sections: list[Section] = []
    current: Section | None = None
    for line in path.read_text().splitlines():
        header = HEADER_RE.match(line)
        if header:
            current = Section(header.group(1), parse_attrs(header.group(2)))
            sections.append(current)
        elif current is not None:
            current.body.append(line)
    return sections


def check_scene(path: pathlib.Path) -> None:
    rel = str(path.relative_to(ROOT))
    sections = parse_scene(path)
    if not sections or sections[0].kind != "gd_scene":
        fail(rel, "gd_scene 헤더가 없다")
        return

    ext_ids: dict[str, dict[str, str]] = {}
    sub_ids: set[str] = set()
    nodes = [s for s in sections if s.kind == "node"]

    for s in sections:
        if s.kind == "ext_resource":
            ext_ids[s.attrs.get("id", "")] = s.attrs
        elif s.kind == "sub_resource":
            sub_ids.add(s.attrs.get("id", ""))

    # 1. load_steps
    declared = sections[0].attrs.get("load_steps")
    expected = len(ext_ids) + len(sub_ids) + 1
    if declared is None:
        if expected != 1:
            fail(rel, f"load_steps 누락 (기대 {expected})")
    elif int(declared) != expected:
        fail(rel, f"load_steps={declared} != ext {len(ext_ids)} + sub {len(sub_ids)} + 1 = {expected}")

    # 2·3. 리소스 참조 무결성 + 파일 존재
    whole = path.read_text()
    for ref in set(EXT_REF_RE.findall(whole)):
        if ref not in ext_ids:
            fail(rel, f'선언되지 않은 ExtResource("{ref}") 참조')
    for ref in set(SUB_REF_RE.findall(whole)):
        if ref not in sub_ids:
            fail(rel, f'선언되지 않은 SubResource("{ref}") 참조')
    for res_id, attrs in ext_ids.items():
        res_path = attrs.get("path", "")
        if res_path.startswith("res://"):
            target = ROOT / res_path[len("res://"):]
            if not target.exists():
                fail(rel, f'ext_resource "{res_id}" 파일 없음: {res_path}')

    # 4·5. 노드 트리 구성 검사
    declared_paths: set[str] = set()          # 루트 기준 경로("" = 루트)
    instanced_paths: set[str] = set()          # 인스턴스 씬 노드(내부는 검사 불가)
    children: dict[str, set[str]] = {}
    root_script_id: str | None = None

    for index, node in enumerate(nodes):
        name = node.attrs.get("name", "")
        parent = node.attrs.get("parent")

        if parent is None:
            if index != 0:
                fail(rel, f'노드 "{name}"에 parent가 없다 (루트가 2개?)')
            declared_paths.add("")
            children[""] = set()
            match = EXT_REF_RE.search(node.text)
            if "script = ExtResource" in node.text and match:
                root_script_id = match.group(1)
            continue

        parent_path = "" if parent == "." else parent
        # 인스턴스 씬 내부 노드 오버라이드는 정적으로 확인 불가 → 건너뜀
        inside_instance = any(
            parent_path == ip or parent_path.startswith(ip + "/")
            for ip in instanced_paths
        )
        if not inside_instance:
            if parent_path not in declared_paths:
                fail(rel, f'노드 "{name}"의 부모 경로가 없다: parent="{parent}"')
            else:
                siblings = children.setdefault(parent_path, set())
                if name in siblings:
                    fail(rel, f'형제 노드 이름 중복: "{name}" (parent="{parent}")')
                siblings.add(name)

        full = name if parent_path == "" else f"{parent_path}/{name}"
        declared_paths.add(full)
        if "instance=ExtResource" in " ".join(f"{k}={v}" for k, v in node.attrs.items()) \
                or "instance" in node.attrs:
            instanced_paths.add(full)

    # 6. 루트 스크립트의 노드 경로 해석
    if root_script_id and root_script_id in ext_ids:
        script_path = ext_ids[root_script_id].get("path", "")
        if script_path.startswith("res://"):
            script_file = ROOT / script_path[len("res://"):]
            if script_file.exists():
                check_script_paths(rel, script_file, declared_paths, instanced_paths)

    # 7. 벽 충돌 ↔ 광원 차단체 1:1 (차단체를 쓰는 씬에만 적용)
    occ_polys = {
        s.attrs.get("id", "")[len("Occ_"):]: POLY_RE.search(s.text)
        for s in sections
        if s.kind == "sub_resource"
        and s.attrs.get("type") == "OccluderPolygon2D"
        and s.attrs.get("id", "").startswith("Occ_")
    }
    if occ_polys:
        wall_polys: dict[str, str] = {}
        for node in nodes:
            name = node.attrs.get("name", "")
            if node.attrs.get("type") != "CollisionPolygon2D":
                continue
            if not (name.startswith("WC_") or name.startswith("RC_")
                    or name.endswith("BarrierCollision") or name.endswith("DoorCollision")):
                continue
            match = POLY_RE.search(node.text)
            if match:
                wall_polys[name] = match.group(1)

        missing = set(wall_polys) - set(occ_polys)
        extra = set(occ_polys) - set(wall_polys)
        if missing:
            fail(rel, f"광원 차단체 없는 벽 {len(missing)}개: {sorted(missing)[:3]}…")
        if extra:
            fail(rel, f"대응 벽이 없는 차단체 {len(extra)}개: {sorted(extra)[:3]}…")
        for name, poly in wall_polys.items():
            occ = occ_polys.get(name)
            if occ and occ.group(1).strip() != poly.strip():
                fail(rel, f"벽/차단체 폴리곤 불일치: {name}")


def check_script_paths(scene_rel: str, script_file: pathlib.Path,
                       declared: set[str], instanced: set[str]) -> None:
    """스크립트가 참조하는 노드 경로가 씬에 존재하는지 확인."""
    text = script_file.read_text()
    refs: set[str] = set()
    for match in DOLLAR_RE.finditer(text):
        refs.add(match.group(1) or match.group(2))
    for match in GET_NODE_RE.finditer(text):
        refs.add(match.group(1))

    for ref in sorted(refs):
        # 절대 경로·상위 참조·런타임 조합 경로는 정적 확인 대상에서 제외
        if ref.startswith("/") or ".." in ref or "%" in ref:
            continue
        if ref in declared:
            continue
        # 인스턴스 씬 내부 경로면 확인 불가
        if any(ref == ip or ref.startswith(ip + "/") for ip in instanced):
            continue
        fail(scene_rel, f'스크립트 {script_file.name}의 노드 경로를 찾을 수 없다: ${ref}')


def main() -> int:
    scenes = sorted(ROOT.glob("scenes/**/*.tscn"))
    if not scenes:
        print("검사할 씬이 없다", file=sys.stderr)
        return 1

    for scene in scenes:
        check_scene(scene)

    print(f"씬 {len(scenes)}개 검사")
    if errors:
        print(f"\n오류 {len(errors)}건:")
        for message in errors:
            print(f"  - {message}")
        return 1
    print("문제 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
