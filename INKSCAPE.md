# Preparing SVGs In Inkscape

This guide describes how to prepare artwork in Inkscape so [svg2ticvec.py](/home/motajama/Code/TIC-80/tic80-svg-lite/svg2ticvec.py:1) converts it cleanly for TIC-80.

Authorship note:

- Design, concept, and debugging: motajama
- Implementation and coding assistance in this iteration: OpenAI Codex

## Goal

Author simple vector shapes in Inkscape, assign palette roles with object labels, export Plain SVG, then convert to Lua.

The converter is designed for:

- icons
- UI symbols
- map signs
- simple illustrations
- clean outlined or filled shapes

It is not designed for full SVG artwork with filters, text, gradients, masks, clipping, or complex compound fill behavior.

## Recommended Canvas Setup

Use a small document size that matches the intended TIC-80 asset scale:

- `16x16`
- `24x24`
- `32x32`
- `64x64`

You can use larger canvases, but keeping the artwork small usually produces cleaner TIC-80 output.

Recommended:

1. `File -> Document Properties`
2. Set width and height to a TIC-80-friendly size
3. Use pixel units
4. Keep the artwork near the origin

## Shape Authoring Rules

Prefer simple separate objects.

Good:

- one roof shape
- one wall shape
- one window shape
- one outline shape

Avoid:

- one giant compound object containing many visual parts with different roles
- text objects left as text
- filter-heavy objects
- clipped or masked objects

If two parts need different game colors, make them separate objects in Inkscape.

## Fills

Fills are supported.

Use:

- filled paths
- filled polygons
- filled rectangles
- filled circles

Notes:

- Complex compound-path holes are not fully SVG-correct after conversion.
- If you need reliable results, prefer simple closed shapes.

## Strokes

Stroke presence is supported.

Stroke width is supported.

Use simple stroke settings:

- solid stroke
- reasonable stroke width

Current exporter/runtime do not fully preserve:

- dashed strokes
- exact line joins
- exact line caps

So if your art depends heavily on precise SVG miter/bevel/round behavior, expect approximation.

## Curves

Curves are supported for these path commands:

- cubic Bezier `C/c`
- quadratic Bezier `Q/q`

They are flattened into line segments during conversion.

If a curve looks too angular in TIC-80, increase converter quality:

```bash
python3 svg2ticvec.py art.svg -o art.lua -n icon_art --curve-segments 16
```

## Transforms

Basic transforms are supported by the converter:

- translate
- scale
- rotate
- skew
- matrix

That said, simpler geometry is still easier to reason about. If an asset becomes hard to debug, flattening transforms in Inkscape can still help.

## Color Roles With Inkscape Labels

This is the intended way to connect SVG art to the game palette.

### What To Label

Give each shape an Inkscape object label that represents its logical color role, for example:

- `roof`
- `wall`
- `shadow`
- `outline`
- `accent`

Shapes with the same label will use the same palette role in the generated Lua.

### How To Set A Label In Inkscape

In Inkscape, select an object and set its object name/label in the Objects panel.

Use short, stable names:

- good: `roof`
- good: `ui_border`
- good: `enemy_eye`
- bad: `Object 123`
- bad: `blue thing`

### Important Difference: Label vs ID

- `inkscape:label`: can be reused across multiple shapes, and should be used for palette roles
- `id`: should stay unique

So if three different shapes should all use the same in-game color, give them the same Inkscape label.

### Example

Three shapes in Inkscape:

- label `roof`
- label `roof`
- label `wall`

Generated Lua may contain:

```lua
{"c", "roof"}
...
{"c", "wall"}
...
```

In TIC-80:

```lua
drawvec(icon_house, 40, 40, 2, {
 roof = 6,
 wall = 12,
})
```

## Suggested Inkscape Workflow

1. Create the artwork using simple paths, rectangles, circles, polygons, and polylines.
2. Split visually different parts into separate objects.
3. Assign an Inkscape label to each object that should map to a game palette role.
4. Use fills and strokes as needed.
5. Keep stroke widths simple and intentional.
6. Convert special objects to paths when necessary.
7. Save as Plain SVG.
8. Run the converter.

## Converting Objects To Paths

Useful commands:

- `Path -> Object to Path`
- `Path -> Stroke to Path`

When to use them:

- convert text to paths before export
- convert unsupported fancy objects to paths
- use `Stroke to Path` only if you want the stroke to become a filled shape rather than a runtime stroke

Do not convert everything blindly. Native rectangles and circles are still useful because the exporter can keep them compact.

## Save Format

Use:

- `File -> Save As -> Plain SVG`

This reduces editor-specific noise and keeps conversion more predictable.

## Practical Asset Tips

For the best TIC-80 output:

- keep silhouettes simple
- avoid tiny decorative details
- prefer strong fills and clear outlines
- test at the actual game scale
- keep stroke widths readable after scaling

If an asset looks noisy in TIC-80:

- simplify the shape
- reduce the number of nodes
- split complex parts into cleaner separate shapes
- increase `--curve-segments` only when the shape truly needs it

## Known Trouble Spots

Watch out for:

- compound paths with holes
- dashed or decorative strokes
- filter-based appearance
- clipped groups
- masks
- text objects left unconverted
- huge amounts of tiny curve detail

If an asset depends on those, simplify it before export.

## Minimal Example

1. Draw a house with separate roof and wall objects.
2. Set roof object label to `roof`.
3. Set wall object label to `wall`.
4. Save as `house.svg`.
5. Convert:

```bash
python3 svg2ticvec.py house.svg -o house.lua -n icon_house
```

6. In TIC-80:

```lua
drawvec(icon_house, 20, 20, 2, {
 roof = 6,
 wall = 12,
})
```

That is the intended authoring loop.
