"""
Export the metafont-style curve specifications of the font to fit/letters.json
for the interactive template-fitting UI (see fit/README.md).

For every letter of the Czech alphabet chart (ceska-abeceda-0.jpg.big.jpg)
this writes the current glyph's knots/directions/tensions (recorded by svg.py
while building the contours) together with an initial placement (translation +
uniform scale) that positions the glyph on top of the corresponding cursive
sample in the chart. The placements are computed by detecting the pink
underline of every cell in the image.

Usage:  python3 export_fit.py [--force]

Refuses to overwrite an existing fit/letters.json without --force, because
that file accumulates your hand-edited curves.
"""

import json
import os
import sys

import svg

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE = os.path.join(HERE, "..", "ceska-abeceda-0.jpg.big.jpg")
OUT = os.path.join(HERE, "..", "fit", "letters.json")

# The 17 rows of each column of the chart. Each row name maps to (upper
# glyphs, lower glyphs) in svg.py naming; "CH" is composed of two glyphs.
ROWS_LEFT = ["A", "B", "C", "Ccaron", "D", "Dcaron", "E", "F", "G", "H",
             "CH", "I", "J", "K", "L", "M", "N"]
ROWS_RIGHT = ["Ncaron", "O", "P", "Q", "R", "Rcaron", "S", "Scaron", "T",
              "Tcaron", "U", "V", "W", "X", "Y", "Z", "Zcaron"]


def row_glyphs(name):
    "Return (cell_label, [(entry_id, glyph_name), ...upper], [...lower])."
    if name == "CH":
        return ("Ch ch",
                [("Ch.C", "C_"), ("Ch.h", "h")],
                [("ch.c", "c"), ("ch.h", "h")])
    lower = name.lower()
    upper = name[0] + "_" + name[1:]  # A -> A_, Ccaron -> C_caron
    label = name[0] + name[1:].replace("caron", "̌") \
        if "caron" in name else name
    # label like "Cc" with combining caron: build display label
    if "caron" in name:
        base = name.replace("caron", "")
        label = base + "̌ " + base.lower() + "̌"
    else:
        label = name + " " + lower
    return (label, [(name, upper)], [(lower, lower)])


def detect_baselines():
    """
    Find the pink underline of every chart cell.
    Returns (left, right): two lists of 17 (y, x0, x1) tuples, top to bottom.
    """
    from PIL import Image
    im = Image.open(IMAGE).convert("RGB")
    w, h = im.size
    px = im.load()

    def is_pink(p):
        r, g, b = p
        return r >= 140 and r - g >= 40 and r - b >= 30

    runs = []
    for y in range(100, 760):
        x = 30
        while x < 545:
            if is_pink(px[x, y]):
                x0 = x
                gap = 0
                while x < 545 and gap <= 3:
                    if is_pink(px[x, y]):
                        gap = 0
                    else:
                        gap += 1
                    x += 1
                x1 = x - gap
                if 30 <= x1 - x0 <= 120:
                    runs.append((y, x0, x1))
            else:
                x += 1
    lines = []  # [ymin, ymax, x0, x1]
    for y, x0, x1 in runs:
        for L in lines:
            if y - L[1] <= 2 and not (x1 < L[2] - 10 or x0 > L[3] + 10):
                L[1] = max(L[1], y)
                L[2] = min(L[2], x0)
                L[3] = max(L[3], x1)
                break
        else:
            lines.append([y, y, x0, x1])
    left = sorted([L for L in lines if L[2] < 280], key=lambda L: L[0])
    right = sorted([L for L in lines if L[2] >= 280], key=lambda L: L[0])
    assert len(left) == 17, "expected 17 left underlines, got %d" % len(left)
    assert len(right) == 17, \
        "expected 17 right underlines, got %d" % len(right)
    return ([(L[0], L[2], L[3]) for L in left],
            [(L[0], L[2], L[3]) for L in right]), (w, h)


def estimate_scale(baselines):
    """
    Pixels per metafont unit. The cap height of the written capitals is 14
    units; measure the ink height above the underline for rows without
    diacritics and take the median.
    """
    from PIL import Image
    im = Image.open(IMAGE).convert("RGB")
    px = im.load()

    def is_ink(p):
        r, g, b = p
        return r < 140 and g < 140 and b < 140

    left, right = baselines
    plain = [(i, False) for i, n in enumerate(ROWS_LEFT)
             if "caron" not in n and n != "CH"] + \
            [(i, True) for i, n in enumerate(ROWS_RIGHT)
             if "caron" not in n]
    heights = []
    for i, is_right in plain:
        y, x0, x1 = (right if is_right else left)[i]
        top = None
        for yy in range(y - 34, y - 2):
            for xx in range(x0 - 8, x1 + 4):
                if is_ink(px[xx, yy]):
                    top = yy
                    break
            if top is not None:
                break
        if top is not None:
            heights.append(y - top)
    heights.sort()
    cap = heights[len(heights)//2] if heights else 22
    return cap / 14.0


def build(force=False):
    if os.path.exists(OUT) and not force:
        raise SystemExit(
            "%s already exists; it may contain hand-edited curves.\n"
            "Re-run with --force to overwrite it." % OUT)

    baselines, (w, h) = detect_baselines()
    left, right = baselines
    s = estimate_scale(baselines)
    print("image %dx%d, scale %.3f px/unit" % (w, h, s))

    specs = svg._char_specs
    entries = []

    def add_entries(cell, case, glyphlist, y, x):
        for entry_id, glyph in glyphlist:
            e = specs.get(glyph)
            if e is None:
                raise Exception("no spec for glyph %r" % glyph)
            entries.append({
                "id": entry_id,
                "glyph": glyph,
                "cell": cell,
                "case": case,
                "width": e["width"],
                "transform": {"tx": round(x, 2), "ty": round(y, 2),
                              "s": round(s, 4)},
                # deep copy so each entry is independently editable
                "contours": json.loads(json.dumps(e["contours"])),
            })
            x += s * (e["width"] + 1.0)
        return x

    for rows, lines in [(ROWS_LEFT, left), (ROWS_RIGHT, right)]:
        for name, (y, x0, x1) in zip(rows, lines):
            cell, upper, lower = row_glyphs(name)
            x = add_entries(cell, "upper", upper, y, x0)
            add_entries(cell, "lower", lower, y, x + 2.0*s)

    data = {
        "image": "ceska-abeceda-0.jpg.big.jpg",
        "image_size": [w, h],
        "stroke_width": svg.stroke_width / svg.scale,
        "entries": entries,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    print("Wrote %d entries to %s" % (len(entries), OUT))


if __name__ == "__main__":
    build(force="--force" in sys.argv[1:])
