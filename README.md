# TIC-80 SVG Lite

A tiny SVG-to-Lua vector pipeline for [TIC-80](https://tic80.com/) games.

It is not a full SVG renderer. It is a small offline converter plus a tiny TIC-80 runtime for icons, line art, UI symbols, signs, and simple vector illustrations.

```text
SVG file -> svg2ticvec.py -> Lua command table -> drawvec() in TIC-80
```

## What It Does

- Converts a safe SVG subset into Lua tables
- Draws fills, outlines, circles, rectangles, and flattened curves in TIC-80
- Supports basic SVG transforms during conversion
- Supports fill and stroke presence
- Supports stroke width
- Supports label-driven palette roles via `inkscape:label`

## Authorship

- Design, concept, and debugging: motajama
- Implementation and coding assistance in this iteration: OpenAI Codex

## Install

No dependencies beyond Python 3.

```bash
chmod +x svg2ticvec.py
```

## Usage

Basic conversion:

```bash
python3 svg2ticvec.py examples/house.svg -o examples/house.lua -n icon_house
```

Compact output:

```bash
python3 svg2ticvec.py examples/house.svg -o examples/house.lua -n icon_house --compact
```

Smoother curves:

```bash
python3 svg2ticvec.py examples/curve.svg -o examples/curve.lua -n icon_curve --curve-segments 16
```

Default curve quality is `8` line segments per Bezier command.

## TIC-80 Usage

Paste [runtime/ticvec.lua](/home/motajama/Code/TIC-80/tic80-svg-lite/runtime/ticvec.lua:1) into your cartridge, then paste the generated Lua table.

Basic draw:

```lua
drawvec(icon_house, 40, 40, 2)
```

Draw with palette-role mapping:

```lua
drawvec(icon_house, 40, 40, 2, {
 roof = 6,
 wall = 12,
 door = 3,
})
```

Arguments:

```lua
drawvec(vector_table, x, y, scale, palette_map)
```

- `vector_table`: generated command table
- `x`, `y`: draw offset
- `scale`: optional, defaults to `1`
- `palette_map`: optional table used when `{"c", "role_name"}` appears in the vector data

## Generated Command Format

Example:

```lua
icon_house = {
  {"c", "roof"},
  {"p", 2, 12, 12, 3, 22, 12},
  {"c", "wall"},
  {"b", 5, 12, 14, 9},
  {"w", 2},
  {"r", 5, 12, 14, 9},
  {"w", 1},
}
```

Commands:

| Command | Meaning |
|---|---|
| `{"c", color_or_role}` | Set TIC-80 color or palette role |
| `{"w", width}` | Set stroke width for outline commands |
| `{"m", x, y}` | Move drawing cursor |
| `{"l", x, y}` | Draw line |
| `{"z"}` | Close current path |
| `{"o", cx, cy, r}` | Circle outline |
| `{"f", cx, cy, r}` | Filled circle |
| `{"p", x1, y1, x2, y2, ...}` | Filled polygon |
| `{"r", x, y, w, h}` | Rectangle outline |
| `{"b", x, y, w, h}` | Filled rectangle |

Notes:

- `{"w", ...}` affects later outline commands until another width command changes it.
- The converter resets stroke width back to `1` after each stroked element.
- `{"c", ...}` accepts either a numeric TIC-80 palette index or a string role such as `"roof"`.

## Supported SVG Subset

Elements:

- `path`
- `rect`
- `circle`
- `polyline`
- `polygon`

Path commands:

- `M`, `m`
- `L`, `l`
- `H`, `h`
- `V`, `v`
- `C`, `c`
- `Q`, `q`
- `Z`, `z`

Bezier curves are approximated as lines.

Supported transforms:

- `translate(...)`
- `scale(...)`
- `rotate(...)`
- `skewX(...)`
- `skewY(...)`
- `matrix(...)`

Supported style handling:

- `fill`
- `stroke`
- `stroke-width`
- simple inline `style="fill:...;stroke:...;stroke-width:..."`
- `inkscape:label` as a logical palette role name

## Palette Roles Via Inkscape Labels

If a shape has an Inkscape object label such as `roof`, the converter emits that label as the active color role:

```lua
{"c", "roof"}
```

At draw time, the game provides the actual TIC-80 palette index:

```lua
drawvec(icon, x, y, 1, {
 roof = 6,
 wall = 12,
})
```

Rules:

- Reusing the same Inkscape label across multiple shapes is supported.
- Unlabeled shapes fall back to TIC-80 color `12`.
- Numeric colors still work in the runtime.

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

## Inkscape Workflow

See [INKSCAPE.md](/home/motajama/Code/TIC-80/tic80-svg-lite/INKSCAPE.md:1) for the detailed authoring guide.

Short version:

1. Use a small canvas such as `32x32` or `64x64`.
2. Prefer separate shapes for separate fill/stroke/color-role parts.
3. Give reusable color-role labels in Inkscape, such as `roof`, `wall`, `outline`.
4. Convert text and advanced objects to paths when needed.
5. Save as Plain SVG.

## Limitations

This project is deliberately small and pragmatic.

Not supported:

- SVG arcs `A/a`
- text
- gradients
- filters
- masks
- clipping
- external CSS
- dashed strokes
- full SVG stroke join/cap semantics
- full SVG fill rules, holes, and compound-path semantics

Behavioral approximations:

- Curves are flattened to line segments.
- Rounded rectangles are approximated with lines.
- Thick line rendering is approximate in TIC-80.
- Thick circle outlines are approximated with stacked outlines.
- Filled paths and polygons are treated as simple polygons/subpaths.
- Original SVG RGB colors are not preserved directly; Inkscape labels are the intended palette-control mechanism.

## License

MIT.
