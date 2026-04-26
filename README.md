# TIC-80 SVG Lite

A tiny SVG-like vector pipeline for [TIC-80](https://tic80.com/) Lua games.

It is **not** a full SVG renderer. It is a small converter + runtime intended for icons, line art, UI symbols, simple map signs, and small vector illustrations.

```text
SVG file → svg2ticvec.py → Lua table → drawvec() in TIC-80
```

## Why?

TIC-80 is small and fast. Parsing real SVG at runtime is too heavy and unnecessary for most fantasy-console game assets. This project converts a safe SVG subset into a compact Lua table that TIC-80 can draw using built-in primitives such as `line`, `rectb`, `circb`, and a tiny scanline polygon filler.

## Supported SVG subset

### Elements

- `path`
- `rect`
- `circle`
- `polyline`
- `polygon`

### Path commands

- `M`, `m` — move to
- `L`, `l` — line to
- `H`, `h` — horizontal line
- `V`, `v` — vertical line
- `C`, `c` — cubic Bézier, approximated as lines
- `Q`, `q` — quadratic Bézier, approximated as lines
- `Z`, `z` — close path

### Not supported

- SVG arcs `A/a`
- gradients
- text
- filters
- masks
- clipping
- external CSS
- full SVG fill rules, holes, and compound-path semantics

### Supported transforms

- `translate(...)`
- `scale(...)`
- `rotate(...)`
- `skewX(...)`
- `skewY(...)`
- `matrix(...)`

For best results, prepare SVGs in Inkscape as simple outlines and paths.

## Install

No dependencies beyond Python 3.

```bash
chmod +x svg2ticvec.py
```

## Usage

```bash
python3 svg2ticvec.py examples/house.svg -o examples/house.lua -n icon_house
```

For smaller output:

```bash
python3 svg2ticvec.py examples/house.svg -o examples/house.lua -n icon_house --compact
```

For smoother curves:

```bash
python3 svg2ticvec.py examples/curve.svg -o examples/curve.lua -n icon_curve --curve-segments 16
```

Default curve quality is 8 line segments per Bézier command.

## TIC-80 usage

Paste `runtime/ticvec.lua` into your TIC-80 cartridge, then paste the generated Lua table.

```lua
drawvec(icon_house, 40, 40, 2)
```

Arguments:

```lua
drawvec(vector_table, x, y, scale)
```

## Generated command format

```lua
icon_house = {
  {"c", 12},
  {"m", 2, 12},
  {"l", 12, 3},
  {"l", 22, 12},
  {"z"},
  {"r", 5, 12, 14, 9},
}
```

Commands:

| Command | Meaning |
|---|---|
| `{"c", color}` | Set TIC-80 color |
| `{"m", x, y}` | Move drawing cursor |
| `{"l", x, y}` | Draw line |
| `{"z"}` | Close current path |
| `{"o", cx, cy, r}` | Circle outline |
| `{"f", cx, cy, r}` | Filled circle |
| `{"p", x1, y1, x2, y2, ...}` | Filled polygon |
| `{"r", x, y, w, h}` | Rectangle outline |
| `{"b", x, y, w, h}` | Filled rectangle |

## Recommended Inkscape workflow

1. Use a small canvas, for example `32×32`, `64×64`, or TIC-80-friendly proportions.
2. Avoid gradients, text, opacity, filters, masks, and clipping.
3. Convert objects to paths where needed:
   - `Path → Object to Path`
4. Simplify complex paths:
   - `Path → Simplify`
5. Avoid arcs or convert them to cubic paths.
6. Save as **Plain SVG**.
7. Convert with `svg2ticvec.py`.

## Examples

```bash
python3 svg2ticvec.py examples/house.svg -o examples/house.lua -n icon_house
python3 svg2ticvec.py examples/polyline.svg -o examples/polyline.lua -n icon_polyline
python3 svg2ticvec.py examples/curve.svg -o examples/curve.lua -n icon_curve --curve-segments 12
```

Then paste:

1. `runtime/ticvec.lua`
2. generated `examples/*.lua`
3. `examples/demo.lua`

## Limitations

This is deliberately small. It is meant to be hackable and understandable.

The converter currently starts every output with TIC-80 color `12`. It can read simple inline `fill`, `stroke`, and `style="fill:...;stroke:..."` hints for basic fill/outline decisions, but it does not preserve original SVG colors.

Rounded rectangles are approximated with line segments.

Filled paths and polygons are filled as simple polygons. Complex compound paths and holes are not handled with full SVG correctness.

## License

MIT.
