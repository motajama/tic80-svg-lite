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
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple


Number = float
Command = Tuple


TOKEN_RE = re.compile(
    r"[AaCcHhLlMmQqVvZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?"
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
        self.last_cmd: Optional[str] = None

    def has_more(self) -> bool:
        return self.i < len(self.tokens)

    def peek(self) -> Optional[str]:
        return self.tokens[self.i] if self.has_more() else None

    def is_cmd(self, token: Optional[str]) -> bool:
        return bool(token and re.fullmatch(r"[AaCcHhLlMmQqVvZz]", token))

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
                self.last_cmd = cmd
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
                self.last_cmd = cmd
                continue

            if cmd in ("L", "l"):
                while self.has_more() and not self.is_cmd(self.peek()):
                    x = self.read_num()
                    y = self.read_num()
                    if cmd == "l":
                        x += self.x
                        y += self.y
                    self.add_line(x, y)
                self.last_cmd = cmd
                continue

            if cmd in ("H", "h"):
                while self.has_more() and not self.is_cmd(self.peek()):
                    x = self.read_num()
                    if cmd == "h":
                        x += self.x
                    self.add_line(x, self.y)
                self.last_cmd = cmd
                continue

            if cmd in ("V", "v"):
                while self.has_more() and not self.is_cmd(self.peek()):
                    y = self.read_num()
                    if cmd == "v":
                        y += self.y
                    self.add_line(self.x, y)
                self.last_cmd = cmd
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
                self.last_cmd = cmd
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
                self.last_cmd = cmd
                continue

            if cmd in ("A", "a"):
                raise NotImplementedError("SVG arc commands A/a are not supported. Convert arcs to paths/lines in Inkscape first.")

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


def element_commands(elem: ET.Element, curve_segments: int) -> List[Command]:
    tag = strip_ns(elem.tag)

    if tag == "path":
        return PathParser(elem.attrib.get("d", ""), curve_segments=curve_segments).parse()

    if tag == "rect":
        return rect_commands(elem)

    if tag == "circle":
        cx = num(elem.attrib.get("cx"), 0)
        cy = num(elem.attrib.get("cy"), 0)
        r = num(elem.attrib.get("r"), 0)
        return [("o", cx, cy, r)]

    if tag == "polyline":
        pts = parse_points(elem.attrib.get("points", ""))
        if not pts:
            return []
        cmds: List[Command] = [("m", pts[0][0], pts[0][1])]
        cmds.extend(("l", x, y) for x, y in pts[1:])
        return cmds

    if tag == "polygon":
        pts = parse_points(elem.attrib.get("points", ""))
        if not pts:
            return []
        cmds = [("m", pts[0][0], pts[0][1])]
        cmds.extend(("l", x, y) for x, y in pts[1:])
        cmds.append(("z",))
        return cmds

    return []


def convert(svg_file: str, curve_segments: int = 8) -> List[Command]:
    tree = ET.parse(svg_file)
    root = tree.getroot()
    cmds: List[Command] = []

    # Default color. User can edit or script color later.
    cmds.append(("c", 12))

    for elem in root.iter():
        tag = strip_ns(elem.tag)
        if tag in {"path", "rect", "circle", "polyline", "polygon"}:
            cmds.extend(element_commands(elem, curve_segments=curve_segments))

    return cmds


def to_lua(cmds: Sequence[Command], name: str, decimals: int = 2, compact: bool = False) -> str:
    if compact:
        lines = [f"{name}={{"]
        for cmd in cmds:
            args = [f'"{cmd[0]}"'] + [fmt_number(float(v), decimals) for v in cmd[1:]]
            lines.append("{" + ",".join(args) + "},")
        lines.append("}")
        return "\n".join(lines)

    lines = [f"{name} = {{"]
    for cmd in cmds:
        args = [f'"{cmd[0]}"'] + [fmt_number(float(v), decimals) for v in cmd[1:]]
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
