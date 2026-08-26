#!/usr/bin/env python3
"""층·운동장 씬을 그림 한 장으로 그려 눈으로 확인한다(SVG + PNG).

Godot을 띄우지 않고 **배치**를 보는 도구다. 씬의 `Polygon2D`를 선언 순서대로
(= 그리기 순서) 칠하고, `PointLight2D`를 방사 그라디언트로 겹친다.

**게임 화면과 같지 않다.** 없는 것이 셋이다.
  * 도트 텍스처(`Polygon2D.texture`) — 색만 칠한다.
  * 어둠(`CanvasModulate`)과 손전등 — 전부 밝은 상태로 그린다.
  * 시야 마스크(`WallFade`) — 맵 전체가 보인다.
그래서 "이렇게 보인다"가 아니라 "이렇게 놓였다"를 확인하는 데 쓴다.

    python3 tools/preview_scene.py school_yard [out.svg]

PNG은 같은 이름으로 함께 나온다(표준 라이브러리만 — zlib + struct).
"""
import pathlib
import re
import struct
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

NODE_RE = re.compile(r'\[node name="([^"]+)" type="(\w+)" parent="([^"]*)"\]'
                     r'((?:(?!\[node)[^\n]*\n)*)')
POLY_RE = re.compile(r"polygon = PackedVector2Array\(([^)]*)\)")
COLOR_RE = re.compile(r"^color = Color\(([\d.\- ,]+)\)", re.M)
POS_RE = re.compile(r"^position = Vector2\(([-\d.]+), ([-\d.]+)\)", re.M)
SIZE_RE = re.compile(r'\[sub_resource type="RectangleShape2D" id="([^"]+)"\]\n'
                     r"size = Vector2\(([\d.]+), ([\d.]+)\)")
SHAPE_RE = re.compile(r'^shape = SubResource\("([^"]+)"\)', re.M)
SCALE_RE = re.compile(r"^texture_scale = ([\d.]+)", re.M)
ENERGY_RE = re.compile(r"^energy = ([\d.]+)", re.M)

# 씬 크기를 못 찾으면 쓰는 기본값(층).
DEFAULT_SIZE = (3400, 2500)
# 광원 반지름 = 512 * texture_scale. window_light/`_yard_light`가 쓰는 그라디언트가
# 512px 반지름짜리라 그 규약을 그대로 따른다.
LIGHT_BASE = 512.0


def rgba(triplet):
    v = [float(x) for x in triplet.split(",")]
    r, g, b = (int(round(min(1.0, max(0.0, c)) * 255)) for c in v[:3])
    a = v[3] if len(v) > 3 else 1.0
    return "#%02x%02x%02x" % (r, g, b), a


def parse(path):
    text = path.read_text(encoding="utf-8")
    shapes = {sid: (float(w), float(h)) for sid, w, h in SIZE_RE.findall(text)}
    polys, lights, areas = [], [], []
    bounds = [0.0, 0.0]
    for name, kind, parent, body in NODE_RE.findall(text):
        if kind == "Polygon2D":
            m = POLY_RE.search(body)
            c = COLOR_RE.search(body)
            if not m or not c:
                continue
            nums = [float(v) for v in m.group(1).split(",")]
            pts = list(zip(nums[0::2], nums[1::2]))
            off = POS_RE.search(body)
            dx, dy = ((float(off.group(1)), float(off.group(2))) if off else (0.0, 0.0))
            pts = [(x + dx, y + dy) for x, y in pts]
            fill, alpha = rgba(c.group(1))
            polys.append((name, parent, pts, fill, alpha))
            for x, y in pts:
                bounds[0] = max(bounds[0], x)
                bounds[1] = max(bounds[1], y)
        elif kind == "PointLight2D":
            off = POS_RE.search(body)
            c = COLOR_RE.search(body)
            sc = SCALE_RE.search(body)
            en = ENERGY_RE.search(body)
            if not off or not c:
                continue
            fill, _ = rgba(c.group(1))
            lights.append((float(off.group(1)), float(off.group(2)),
                           LIGHT_BASE * (float(sc.group(1)) if sc else 1.0),
                           fill, float(en.group(1)) if en else 1.0))
        elif kind == "Area2D" and "script" in body:
            off = POS_RE.search(body)
            if off:
                areas.append((name, float(off.group(1)), float(off.group(2))))
        elif kind == "CollisionShape2D":
            sid = SHAPE_RE.search(body)
            off = POS_RE.search(body)
            if sid and off and sid.group(1) in shapes:
                w, h = shapes[sid.group(1)]
                bounds[0] = max(bounds[0], float(off.group(1)) + w / 2)
                bounds[1] = max(bounds[1], float(off.group(2)) + h / 2)
    return polys, lights, areas, bounds


def render(stem, out_path):
    path = ROOT / f"scenes/background/{stem}.tscn"
    polys, lights, areas, bounds = parse(path)
    w = max(DEFAULT_SIZE[0] if bounds[0] > DEFAULT_SIZE[0] else bounds[0], bounds[0])
    h = bounds[1]
    w, h = round(w), round(h)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
           f'width="{w}" height="{h}">',
           f'<rect width="{w}" height="{h}" fill="#07080c"/>']

    # 광원 — 방사 그라디언트. 폴리곤 **위에** screen으로 얹는다.
    out.append("<defs>")
    for i, (_x, _y, _r, fill, _e) in enumerate(lights):
        out.append(f'<radialGradient id="g{i}">'
                   f'<stop offset="0" stop-color="{fill}" stop-opacity="0.55"/>'
                   f'<stop offset="0.5" stop-color="{fill}" stop-opacity="0.2"/>'
                   f'<stop offset="1" stop-color="{fill}" stop-opacity="0"/>'
                   f"</radialGradient>")
    out.append("</defs>")

    # 선언 순서가 곧 그리기 순서다(gen_floors.py의 규약).
    for _name, _parent, pts, fill, alpha in polys:
        d = " ".join(f"{x:.0f},{y:.0f}" for x, y in pts)
        op = f' fill-opacity="{alpha:.2f}"' if alpha < 1.0 else ""
        out.append(f'<polygon points="{d}" fill="{fill}"{op}/>')

    out.append('<g style="mix-blend-mode:screen">')
    for i, (x, y, r, _fill, _e) in enumerate(lights):
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="url(#g{i})"/>')
    out.append("</g>")
    out.append("</svg>")

    out_path.write_text("\n".join(out), encoding="utf-8")
    return len(polys), len(lights), len(areas), (w, h)


# 축소 배율. 3400px를 그대로 쓰면 PNG이 커지고 볼 때도 불편하다.
PNG_DIV = 1


def _fill(buf, w, h, pts, rgb, alpha):
    """스캔라인 폴리곤 채우기. 반투명은 그 자리 색과 섞는다."""
    ys = [y for _x, y in pts]
    y0, y1 = max(0, int(min(ys))), min(h - 1, int(max(ys)))
    for y in range(y0, y1 + 1):
        cy = y + 0.5
        xs = []
        for i in range(len(pts)):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % len(pts)]
            if (ay > cy) != (by > cy):
                xs.append(ax + (cy - ay) * (bx - ax) / (by - ay))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            xa, xb = max(0, int(xs[i])), min(w - 1, int(xs[i + 1]))
            for x in range(xa, xb + 1):
                k = (y * w + x) * 4
                if alpha >= 1.0:
                    buf[k:k + 3] = rgb
                else:
                    for c in range(3):
                        buf[k + c] = int(buf[k + c] * (1 - alpha) + rgb[c] * alpha)
                buf[k + 3] = 255


def _glow(buf, w, h, cx, cy, r, rgb, gain):
    """가로등 — 가운데가 밝고 가장자리로 사라지는 원. 더하기로 얹는다."""
    x0, x1 = max(0, int(cx - r)), min(w - 1, int(cx + r))
    y0, y1 = max(0, int(cy - r)), min(h - 1, int(cy + r))
    rr = r * r
    for y in range(y0, y1 + 1):
        dy = y - cy
        for x in range(x0, x1 + 1):
            d2 = (x - cx) ** 2 + dy * dy
            if d2 >= rr:
                continue
            t = (1.0 - (d2 / rr) ** 0.5) ** 2 * gain
            k = (y * w + x) * 4
            for c in range(3):
                buf[k + c] = min(255, int(buf[k + c] + rgb[c] * t))


def write_png(path, w, h, buf):
    """8비트 RGBA PNG(표준 라이브러리만). gen_tiles.py의 것과 같은 방식이다."""
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += buf[y * w * 4:(y + 1) * w * 4]

    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    out += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    out += chunk(b"IEND", b"")
    path.write_bytes(out)


def render_png(polys, lights, size, out_path):
    w, h = size[0] // PNG_DIV, size[1] // PNG_DIV
    buf = bytearray([7, 8, 12, 255] * (w * h))
    for _name, _parent, pts, fill, alpha in polys:
        rgb = [int(fill[i:i + 2], 16) for i in (1, 3, 5)]
        _fill(buf, w, h, [(x / PNG_DIV, y / PNG_DIV) for x, y in pts], rgb, alpha)
    for x, y, r, fill, energy in lights:
        rgb = [int(fill[i:i + 2], 16) for i in (1, 3, 5)]
        _glow(buf, w, h, x / PNG_DIV, y / PNG_DIV, r / PNG_DIV, rgb, 0.5 * energy)
    write_png(out_path, w, h, buf)
    return w, h


if __name__ == "__main__":
    stem = sys.argv[1] if len(sys.argv) > 1 else "school_yard"
    dest = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / f"{stem}_preview.svg"
    p, l, a, size = render(stem, dest)
    polys, lights, _areas, _b = parse(ROOT / f"scenes/background/{stem}.tscn")
    png = dest.with_suffix(".png")
    pw, ph = render_png(polys, lights, size, png)
    print(f"{stem}: {size[0]}x{size[1]}  폴리곤 {p}개, 광원 {l}개, Area2D {a}개")
    print(f"  -> {dest}")
    print(f"  -> {png} ({pw}x{ph})")
