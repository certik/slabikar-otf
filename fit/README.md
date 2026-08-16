# Template fitting UI

Interactive editor for fitting the cursive letter curves onto the alphabet
chart `ceska-abeceda-0.jpg.big.jpg`. The letters are shown as stroked cubic
Bezier curves on top of the image; each letter has its own placement
(translation + uniform scale) and fully editable curves.

## Run

    python3 fit/serve.py
    # or, with pixi:
    pixi run serve
    # open http://localhost:8477/fit/

Edits are autosaved into `fit/letters.json` (the server writes the file; a
green "saved" indicator confirms it). Without the server the page still
works read/edit-only and you can download the JSON with *export*.

## Data

`fit/letters.json` was initially generated with

    cd gen && python3 export_fit.py        # --force to overwrite

which exports the current font's curves (from `svg.py`) in metafont form and
places them over the detected pink underline of every chart cell. Each entry:

- `transform`: `tx`, `ty` (image px of the metafont origin, baseline) and
  `s` (px per metafont unit; y axis is flipped).
- `contours`: metafont-style path specs — knots `{x, y, dir_in, dir_out}`
  (directions in degrees, `null` = chosen automatically) and segments
  `{type: curve|line, tension | tension_out+tension_in}`.

Directions left `null` are computed with Hobby's algorithm exactly as
METAFONT does it (`fit/hobby.js`, same as `solve_path()` in `gen/bezier.py`;
`gen/test_bezier.py` verifies both against a real MetaPost binary).

## Editing

Two modes (toolbar or `M` / `B`):

- **Metafont**: drag knots; each knot shows its outgoing/incoming direction
  as an arrow — solid = pinned (explicit in the data), ghost = chosen by the
  algorithm. Drag an arrow tip to pin a direction (Shift snaps to 15°),
  double-click it to make it automatic again. Curve segments show a tension
  badge at their midpoint; click it and edit the tension in the inspector or
  with `[` / `]`.
- **Bezier**: classic control-point handles. Dragging a handle pins both
  directions and both tensions of that segment (the exact metafont
  equivalent of the handles is stored, so the two views are always
  consistent).

Common: click a letter (canvas or sidebar; sidebar zooms to it), drag the
dashed box to move it, drag the orange corner handle to rescale it about
its origin (+ marker = baseline origin). Double-click a segment to insert a
knot, `Delete` removes the selected knot, arrow keys nudge it. `Ctrl+Z` /
`Ctrl+Shift+Z` undo/redo. Checkboxes in the sidebar hide letters.
