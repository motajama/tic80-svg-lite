#!/usr/bin/env python3
"""
svg2ticvec.py

Convert a deliberately small, TIC-80-friendly SVG subset into Lua vector tables.

Supported SVG:
- <path d="..."> with commands:
  M/m, L/l, H/h, V/v, C/c, Q/q, Z/z
- <rect x="" y="" width="" height="" rx="" ry="">
- <circle cx="" cy="" r="">
- <polyline points="">
- <polygon points="">

Unsupported by design:
- gradients, text, filters, clipping, masks, transforms, stylesheets
- arcs A/a
- stroke width and fills are not faithfully preserved

Bezier curves are approximated as line segments.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from typing import List, Optional, Sequence, Tuple, Union


Command = Tuple
Matrix = Tuple[float, float, float, float, float, float]
ColorRef = Union[int, str]


TOKEN_RE = re.compile(
    r"[AaCcHhLlMmQqSsTtVvZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"
)


def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def num(value: Optional[str], default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    # tolerate simple px units
    value = value.strip().replace("px", "")
    return float(value)


def fmt_number(value: float, decimals: int) -> str:
    if abs(value) < 1e-9:
        value = 0.0
    rounded = round(value, decimals)
    if rounded == int(rounded):
        return str(int(rounded))
    s = f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")
    return s


def parse_style_attr(style: str) -> dict:
    out = {}
    for part in (style or "").split(";"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        out[key.strip()] = value.strip()
    return out


def get_paint_attr(elem: ET.Element, name: str) -> Optional[str]:
    if name in elem.attrib:
        return elem.attrib[name]
    style = elem.attrib.get("style")
    if style:
        return parse_style_attr(style).get(name)
    return None


def get_color_role(elem: ET.Element) -> Optional[str]:
    for key, value in elem.attrib.items():
        if key == "{http://www.inkscape.org/namespaces/inkscape}label" and value:
            return value.strip() or None
    return None


def has_fill(elem: ET.Element) -> bool:
    fill = get_paint_attr(elem, "fill")
    return fill is not None and fill.lower() != "none"


def has_stroke(elem: ET.Element) -> bool:
    stroke = get_paint_attr(elem, "stroke")
    return stroke is not None and stroke.lower() != "none"


def get_stroke_width(elem: ET.Element) -> float:
    value = get_paint_attr(elem, "stroke-width")
    if value is None:
        return 1.0
    return max(1.0, num(value, 1.0))


def identity_matrix() -> Matrix:
    return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def multiply_matrix(left: Matrix, right: Matrix) -> Matrix:
    la, lb, lc, ld, le, lf = left
    ra, rb, rc, rd, re, rf = right
    return (
        la * ra + lc * rb,
        lb * ra + ld * rb,
        la * rc + lc * rd,
        lb * rc + ld * rd,
        la * re + lc * rf + le,
        lb * re + ld * rf + lf,
    )


def apply_matrix_point(matrix: Matrix, x: float, y: float) -> Tuple[float, float]:
    a, b, c, d, e, f = matrix
    return (a * x + c * y + e, b * x + d * y + f)


def parse_transform(transform: Optional[str]) -> Matrix:
    if not transform:
        return identity_matrix()

    result = identity_matrix()
    for name, raw_args in re.findall(r"([A-Za-z]+)\s*\(([^)]*)\)", transform):
        values = [
            float(v)
            for v in re.findall(
                r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", raw_args
            )
        ]

        if name == "matrix":
            if len(values) != 6:
                raise ValueError("matrix() transform requires 6 values")
            op = tuple(values)
        elif name == "translate":
            if len(values) not in (1, 2):
                raise ValueError("translate() transform requires 1 or 2 values")
            tx = values[0]
            ty = values[1] if len(values) == 2 else 0.0
            op = (1.0, 0.0, 0.0, 1.0, tx, ty)
        elif name == "scale":
            if len(values) not in (1, 2):
                raise ValueError("scale() transform requires 1 or 2 values")
            sx = values[0]
            sy = values[1] if len(values) == 2 else sx
            op = (sx, 0.0, 0.0, sy, 0.0, 0.0)
        elif name == "rotate":
            if len(values) not in (1, 3):
                raise ValueError("rotate() transform requires 1 or 3 values")
            angle = math.radians(values[0])
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            rotate_only = (cos_a, sin_a, -sin_a, cos_a, 0.0, 0.0)
            if len(values) == 3:
                cx, cy = values[1], values[2]
                op = multiply_matrix(
                    multiply_matrix((1.0, 0.0, 0.0, 1.0, cx, cy), rotate_only),
                    (1.0, 0.0, 0.0, 1.0, -cx, -cy),
                )
            else:
                op = rotate_only
        elif name == "skewX":
            if len(values) != 1:
                raise ValueError("skewX() transform requires 1 value")
            op = (1.0, 0.0, math.tan(math.radians(values[0])), 1.0, 0.0, 0.0)
        elif name == "skewY":
            if len(values) != 1:
                raise ValueError("skewY() transform requires 1 value")
            op = (1.0, math.tan(math.radians(values[0])), 0.0, 1.0, 0.0, 0.0)
        else:
            raise NotImplementedError(f"Unsupported transform function: {name}")

        result = multiply_matrix(result, op)

    return result


def is_identity_matrix(matrix: Matrix) -> bool:
    return all(abs(a - b) < 1e-9 for a, b in zip(matrix, identity_matrix()))


def is_axis_aligned_rect_matrix(matrix: Matrix) -> bool:
    a, b, c, d, _, _ = matrix
    return abs(b) < 1e-9 and abs(c) < 1e-9


def is_uniform_circle_matrix(matrix: Matrix) -> bool:
    a, b, c, d, _, _ = matrix
    sx = math.hypot(a, b)
    sy = math.hypot(c, d)
    dot = a * c + b * d
    return abs(sx - sy) < 1e-9 and abs(dot) < 1e-9


def transform_commands(cmds: Sequence[Command], matrix: Matrix) -> List[Command]:
    if is_identity_matrix(matrix):
        return list(cmds)

    out: List[Command] = []
    for cmd in cmds:
        op = cmd[0]
        if op in ("m", "l"):
            x, y = apply_matrix_point(matrix, cmd[1], cmd[2])
            out.append((op, x, y))
        elif op == "z":
            out.append(cmd)
        else:
            raise NotImplementedError(f"Cannot transform command {op!r} directly")
    return out


def rect_as_path_commands(
    x: float,
    y: float,
    w: float,
    h: float,
    matrix: Matrix,
) -> List[Command]:
    points = [
        apply_matrix_point(matrix, x, y),
        apply_matrix_point(matrix, x + w, y),
        apply_matrix_point(matrix, x + w, y + h),
        apply_matrix_point(matrix, x, y + h),
    ]
    cmds: List[Command] = [("m", points[0][0], points[0][1])]
    cmds.extend(("l", px, py) for px, py in points[1:])
    cmds.append(("z",))
    return cmds


def circle_as_path_commands(
    cx: float,
    cy: float,
    r: float,
    matrix: Matrix,
    segments: int,
) -> List[Command]:
    points = []
    for step in range(segments):
        angle = (2 * math.pi * step) / segments
        px = cx + math.cos(angle) * r
        py = cy + math.sin(angle) * r
        points.append(apply_matrix_point(matrix, px, py))
    cmds: List[Command] = [("m", points[0][0], points[0][1])]
    cmds.extend(("l", px, py) for px, py in points[1:])
    cmds.append(("z",))
    return cmds


def commands_to_subpaths(cmds: Sequence[Command]) -> List[List[Tuple[float, float]]]:
    subpaths: List[List[Tuple[float, float]]] = []
    current: Optional[List[Tuple[float, float]]] = None

    for cmd in cmds:
        op = cmd[0]
        if op == "m":
            current = [(cmd[1], cmd[2])]
            subpaths.append(current)
        elif op == "l":
            if current is None:
                raise ValueError("Line command without an active subpath")
            current.append((cmd[1], cmd[2]))
        elif op == "z":
            current = None
        else:
            raise ValueError(f"Unsupported drawing command in subpath conversion: {op!r}")

    return subpaths


def subpaths_to_fill_commands(subpaths: Sequence[Sequence[Tuple[float, float]]]) -> List[Command]:
    cmds: List[Command] = []
    for points in subpaths:
        if len(points) < 3:
            continue
        flat: List[float] = []
        for x, y in points:
            flat.extend((x, y))
        cmds.append(tuple(["p", *flat]))
    return cmds


def with_stroke_width(cmds: Sequence[Command], stroke_width: float) -> List[Command]:
    if not cmds:
        return []
    if abs(stroke_width - 1.0) < 1e-9:
        return list(cmds)
    return [("w", stroke_width), *cmds, ("w", 1.0)]


def parse_points(points: str) -> List[Tuple[float, float]]:
    values = re.findall(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", points or "")
    nums = [float(v) for v in values]
    if len(nums) % 2:
        raise ValueError(f"Odd number of coordinates in points attribute: {points!r}")
    return list(zip(nums[0::2], nums[1::2]))


def cubic_point(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    t: float,
) -> Tuple[float, float]:
    mt = 1 - t
    x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
    y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
    return x, y


def quad_point(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    t: float,
) -> Tuple[float, float]:
    mt = 1 - t
    x = mt**2 * p0[0] + 2 * mt * t * p1[0] + t**2 * p2[0]
    y = mt**2 * p0[1] + 2 * mt * t * p1[1] + t**2 * p2[1]
    return x, y


class PathParser:
    def __init__(self, d: str, curve_segments: int = 8):
        self.tokens = TOKEN_RE.findall(d or "")
        self.i = 0
        self.curve_segments = max(1, curve_segments)
        self.commands: List[Command] = []
        self.x = 0.0
        self.y = 0.0
        self.start_x = 0.0
        self.start_y = 0.0

    def has_more(self) -> bool:
        return self.i < len(self.tokens)

    def peek(self) -> Optional[str]:
        return self.tokens[self.i] if self.has_more() else None

    def is_cmd(self, token: Optional[str]) -> bool:
        return bool(token and re.fullmatch(r"[AaCcHhLlMmQqSsTtVvZz]", token))

    def read_num(self) -> float:
        if not self.has_more():
            raise ValueError("Unexpected end of path data")
        tok = self.tokens[self.i]
        if self.is_cmd(tok):
            raise ValueError(f"Expected number, got command {tok!r}")
        self.i += 1
        return float(tok)

    def add_move(self, x: float, y: float):
        self.commands.append(("m", x, y))
        self.x, self.y = x, y
        self.start_x, self.start_y = x, y

    def add_line(self, x: float, y: float):
        self.commands.append(("l", x, y))
        self.x, self.y = x, y

    def parse(self) -> List[Command]:
        cmd: Optional[str] = None

        while self.has_more():
            tok = self.peek()
            if self.is_cmd(tok):
                cmd = tok
                self.i += 1
            elif cmd is None:
                raise ValueError(f"Path data starts with a number: {tok!r}")

            if cmd in ("Z", "z"):
                self.commands.append(("z",))
                self.x, self.y = self.start_x, self.start_y
                cmd = None
                continue

            if cmd in ("M", "m"):
                # first pair is move, following implicit pairs are line commands
                first = True
                while self.has_more() and not self.is_cmd(self.peek()):
                    x = self.read_num()
                    y = self.read_num()
                    if cmd == "m":
                        x += self.x
                        y += self.y
                    if first:
                        self.add_move(x, y)
                        first = False
                    else:
                        self.add_line(x, y)
                continue

            if cmd in ("L", "l"):
                while self.has_more() and not self.is_cmd(self.peek()):
                    x = self.read_num()
                    y = self.read_num()
                    if cmd == "l":
                        x += self.x
                        y += self.y
                    self.add_line(x, y)
                continue

            if cmd in ("H", "h"):
                while self.has_more() and not self.is_cmd(self.peek()):
                    x = self.read_num()
                    if cmd == "h":
                        x += self.x
                    self.add_line(x, self.y)
                continue

            if cmd in ("V", "v"):
                while self.has_more() and not self.is_cmd(self.peek()):
                    y = self.read_num()
                    if cmd == "v":
                        y += self.y
                    self.add_line(self.x, y)
                continue

            if cmd in ("C", "c"):
                while self.has_more() and not self.is_cmd(self.peek()):
                    x1, y1 = self.read_num(), self.read_num()
                    x2, y2 = self.read_num(), self.read_num()
                    x3, y3 = self.read_num(), self.read_num()
                    if cmd == "c":
                        x1, y1 = x1 + self.x, y1 + self.y
                        x2, y2 = x2 + self.x, y2 + self.y
                        x3, y3 = x3 + self.x, y3 + self.y
                    p0 = (self.x, self.y)
                    p1 = (x1, y1)
                    p2 = (x2, y2)
                    p3 = (x3, y3)
                    for step in range(1, self.curve_segments + 1):
                        t = step / self.curve_segments
                        x, y = cubic_point(p0, p1, p2, p3, t)
                        self.add_line(x, y)
                continue

            if cmd in ("Q", "q"):
                while self.has_more() and not self.is_cmd(self.peek()):
                    x1, y1 = self.read_num(), self.read_num()
                    x2, y2 = self.read_num(), self.read_num()
                    if cmd == "q":
                        x1, y1 = x1 + self.x, y1 + self.y
                        x2, y2 = x2 + self.x, y2 + self.y
                    p0 = (self.x, self.y)
                    p1 = (x1, y1)
                    p2 = (x2, y2)
                    for step in range(1, self.curve_segments + 1):
                        t = step / self.curve_segments
                        x, y = quad_point(p0, p1, p2, t)
                        self.add_line(x, y)
                continue

            if cmd in ("S", "s", "T", "t"):
                raise NotImplementedError(
                    f"SVG path command {cmd} is not supported."
                )

            if cmd in ("A", "a"):
                raise NotImplementedError(
                    "SVG arc commands A/a are not supported. Convert arcs to "
                    "paths/lines in Inkscape first."
                )

            raise ValueError(f"Unsupported path command: {cmd!r}")

        return self.commands


def rect_commands(elem: ET.Element, rounded_segments: int = 4) -> List[Command]:
    x = num(elem.attrib.get("x"), 0)
    y = num(elem.attrib.get("y"), 0)
    w = num(elem.attrib.get("width"), 0)
    h = num(elem.attrib.get("height"), 0)
    rx = num(elem.attrib.get("rx"), 0)
    ry = num(elem.attrib.get("ry"), rx)

    if rx <= 0 and ry <= 0:
        return [("r", x, y, w, h)]

    # Approximate rounded rectangles with lines.
    rx = min(rx, w / 2)
    ry = min(ry, h / 2)
    cmds: List[Command] = [("m", x + rx, y), ("l", x + w - rx, y)]

    # quarter ellipse helper
    def arc(cx, cy, a0, a1):
        for step in range(1, rounded_segments + 1):
            t = step / rounded_segments
            a = a0 + (a1 - a0) * t
            cmds.append(("l", cx + math.cos(a) * rx, cy + math.sin(a) * ry))

    arc(x + w - rx, y + ry, -math.pi / 2, 0)
    cmds.append(("l", x + w, y + h - ry))
    arc(x + w - rx, y + h - ry, 0, math.pi / 2)
    cmds.append(("l", x + rx, y + h))
    arc(x + rx, y + h - ry, math.pi / 2, math.pi)
    cmds.append(("l", x, y + ry))
    arc(x + rx, y + ry, math.pi, 3 * math.pi / 2)
    cmds.append(("z",))
    return cmds


def element_commands(
    elem: ET.Element, curve_segments: int, transform: Matrix
) -> List[Command]:
    tag = strip_ns(elem.tag)

    if tag == "path":
        path_cmds = PathParser(
            elem.attrib.get("d", ""), curve_segments=curve_segments
        ).parse()
        path_cmds = transform_commands(path_cmds, transform)
        fill = has_fill(elem)
        stroke = has_stroke(elem)
        stroke_width = get_stroke_width(elem)
        if not fill and not stroke:
            return with_stroke_width(path_cmds, stroke_width)

        cmds: List[Command] = []
        if fill:
            cmds.extend(subpaths_to_fill_commands(commands_to_subpaths(path_cmds)))
        if stroke:
            cmds.extend(with_stroke_width(path_cmds, stroke_width))
        return cmds

    if tag == "rect":
        x = num(elem.attrib.get("x"), 0)
        y = num(elem.attrib.get("y"), 0)
        w = num(elem.attrib.get("width"), 0)
        h = num(elem.attrib.get("height"), 0)
        rx = num(elem.attrib.get("rx"), 0)
        ry = num(elem.attrib.get("ry"), rx)
        fill = has_fill(elem)
        stroke = has_stroke(elem)
        stroke_width = get_stroke_width(elem)

        if rx > 0 or ry > 0:
            rect_path = transform_commands(rect_commands(elem), transform)
            if not fill and not stroke:
                return with_stroke_width(rect_path, stroke_width)
            cmds: List[Command] = []
            if fill:
                cmds.extend(subpaths_to_fill_commands(commands_to_subpaths(rect_path)))
            if stroke:
                cmds.extend(with_stroke_width(rect_path, stroke_width))
            return cmds

        if not fill and not stroke:
            if is_identity_matrix(transform) or is_axis_aligned_rect_matrix(transform):
                x0, y0 = apply_matrix_point(transform, x, y)
                x1, y1 = apply_matrix_point(transform, x + w, y + h)
                rect_cmds = [("r", min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))]
                return with_stroke_width(rect_cmds, stroke_width)
            return with_stroke_width(rect_as_path_commands(x, y, w, h, transform), stroke_width)

        cmds: List[Command] = []
        if fill:
            if is_identity_matrix(transform) or is_axis_aligned_rect_matrix(transform):
                x0, y0 = apply_matrix_point(transform, x, y)
                x1, y1 = apply_matrix_point(transform, x + w, y + h)
                cmds.append(("b", min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)))
            else:
                cmds.extend(
                    subpaths_to_fill_commands(
                        commands_to_subpaths(rect_as_path_commands(x, y, w, h, transform))
                    )
                )
        if stroke:
            if is_identity_matrix(transform) or is_axis_aligned_rect_matrix(transform):
                x0, y0 = apply_matrix_point(transform, x, y)
                x1, y1 = apply_matrix_point(transform, x + w, y + h)
                cmds.extend(with_stroke_width(
                    [("r", min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))],
                    stroke_width,
                )
                )
            else:
                cmds.extend(
                    with_stroke_width(rect_as_path_commands(x, y, w, h, transform), stroke_width)
                )
        return cmds

    if tag == "circle":
        cx = num(elem.attrib.get("cx"), 0)
        cy = num(elem.attrib.get("cy"), 0)
        r = num(elem.attrib.get("r"), 0)
        fill = has_fill(elem)
        stroke = has_stroke(elem)
        stroke_width = get_stroke_width(elem)

        if not fill and not stroke:
            if is_identity_matrix(transform) or is_uniform_circle_matrix(transform):
                pcx, pcy = apply_matrix_point(transform, cx, cy)
                radius = math.hypot(transform[0], transform[1]) * r
                return with_stroke_width([("o", pcx, pcy, radius)], stroke_width)
            return with_stroke_width(
                circle_as_path_commands(cx, cy, r, transform, curve_segments * 4),
                stroke_width,
            )

        cmds: List[Command] = []
        if fill:
            if is_identity_matrix(transform) or is_uniform_circle_matrix(transform):
                pcx, pcy = apply_matrix_point(transform, cx, cy)
                radius = math.hypot(transform[0], transform[1]) * r
                cmds.append(("f", pcx, pcy, radius))
            else:
                cmds.extend(
                    subpaths_to_fill_commands(
                        commands_to_subpaths(
                            circle_as_path_commands(cx, cy, r, transform, curve_segments * 4)
                        )
                    )
                )
        if stroke:
            if is_identity_matrix(transform) or is_uniform_circle_matrix(transform):
                pcx, pcy = apply_matrix_point(transform, cx, cy)
                radius = math.hypot(transform[0], transform[1]) * r
                cmds.extend(with_stroke_width([("o", pcx, pcy, radius)], stroke_width))
            else:
                cmds.extend(
                    with_stroke_width(
                        circle_as_path_commands(cx, cy, r, transform, curve_segments * 4),
                        stroke_width,
                    )
                )
        return cmds

    if tag == "polyline":
        pts = parse_points(elem.attrib.get("points", ""))
        if not pts:
            return []
        cmds: List[Command] = [("m", pts[0][0], pts[0][1])]
        cmds.extend(("l", x, y) for x, y in pts[1:])
        cmds = transform_commands(cmds, transform)
        if has_fill(elem):
            raise NotImplementedError("Filled polylines are not supported.")
        return with_stroke_width(cmds, get_stroke_width(elem))

    if tag == "polygon":
        pts = parse_points(elem.attrib.get("points", ""))
        if not pts:
            return []
        cmds = [("m", pts[0][0], pts[0][1])]
        cmds.extend(("l", x, y) for x, y in pts[1:])
        cmds.append(("z",))
        cmds = transform_commands(cmds, transform)
        fill = has_fill(elem)
        stroke = has_stroke(elem)
        stroke_width = get_stroke_width(elem)
        if not fill and not stroke:
            return with_stroke_width(cmds, stroke_width)
        out: List[Command] = []
        if fill:
            out.extend(subpaths_to_fill_commands(commands_to_subpaths(cmds)))
        if stroke:
            out.extend(with_stroke_width(cmds, stroke_width))
        return out

    return []


def convert(svg_file: str, curve_segments: int = 8) -> List[Command]:
    tree = ET.parse(svg_file)
    root = tree.getroot()
    cmds: List[Command] = []
    current_color: ColorRef = 12

    # Default color. User can edit or script color later.
    cmds.append(("c", 12))

    def walk(elem: ET.Element, inherited_transform: Matrix):
        nonlocal current_color
        local_transform = parse_transform(elem.attrib.get("transform"))
        current_transform = multiply_matrix(inherited_transform, local_transform)
        tag = strip_ns(elem.tag)

        if tag in {"path", "rect", "circle", "polyline", "polygon"}:
            target_color: ColorRef = get_color_role(elem) or 12
            element_cmds = element_commands(
                elem,
                curve_segments=curve_segments,
                transform=current_transform,
            )
            if element_cmds and target_color != current_color:
                cmds.append(("c", target_color))
                current_color = target_color
            cmds.extend(
                element_cmds
            )

        for child in elem:
            walk(child, current_transform)

    walk(root, identity_matrix())

    return cmds


def to_lua(cmds: Sequence[Command], name: str, decimals: int = 2, compact: bool = False) -> str:
    def format_arg(value) -> str:
        if isinstance(value, str):
            return f'"{value}"'
        return fmt_number(float(value), decimals)

    if compact:
        lines = [f"{name}={{"]
        for cmd in cmds:
            args = [f'"{cmd[0]}"'] + [format_arg(v) for v in cmd[1:]]
            lines.append("{" + ",".join(args) + "},")
        lines.append("}")
        return "\n".join(lines)

    lines = [f"{name} = {{"]
    for cmd in cmds:
        args = [f'"{cmd[0]}"'] + [format_arg(v) for v in cmd[1:]]
        lines.append("  {" + ", ".join(args) + "},")
    lines.append("}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Convert simple SVG into a TIC-80 Lua vector table."
    )
    ap.add_argument("input", help="input SVG file")
    ap.add_argument("-o", "--output", default="out.lua", help="output Lua file")
    ap.add_argument("-n", "--name", default="icon", help="Lua table name")
    ap.add_argument(
        "--curve-segments",
        type=int,
        default=8,
        help="number of line segments per Bezier curve",
    )
    ap.add_argument(
        "--decimals",
        type=int,
        default=2,
        help="number of decimal places in Lua output",
    )
    ap.add_argument(
        "--compact",
        action="store_true",
        help="write more compact Lua output",
    )

    args = ap.parse_args(argv)

    try:
        cmds = convert(args.input, curve_segments=args.curve_segments)
        lua = to_lua(cmds, args.name, decimals=args.decimals, compact=args.compact)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(lua)
            f.write("\n")
    except Exception as exc:
        print(f"svg2ticvec: error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
