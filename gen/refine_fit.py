"""
Refine the placements in fit/letters.json so every glyph sits as closely as
possible on its cursive sample in the template image.

Method: build a mask of the template's ink (dark, grayish pixels), compute
its Euclidean distance transform, and for each entry minimize the mean
(capped) distance from points sampled along the glyph centerline to the
nearest ink pixel, over translation and mild uniform scaling, with a
coarse-to-fine grid search.

To keep letters from snapping onto their neighbor's ink, the letters of each
chart cell are fitted left to right with two structural constraints:
  - the baseline anchor ty must stay within a few px of the cell's detected
    pink underline;
  - a letter's leftmost ink must start after the previous letter's fitted
    right edge.

Only the "transform" of each entry is modified; the curves are untouched.

Usage:  python3 refine_fit.py
"""

import json
import os

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt

from bezier import solve_path
from export_fit import (detect_baselines, estimate_scale, row_glyphs,
                        ROWS_LEFT, ROWS_RIGHT)

HERE = os.path.dirname(os.path.abspath(__file__))
LETTERS = os.path.join(HERE, "..", "fit", "letters.json")

TY_RANGE = 4.0      # px around the detected baseline
S_RANGE = 0.10      # +-10 % around the exported scale
OVERLAP = 4.0       # px a letter may reach into the previous one
GAP_MAX = 30.0      # px of allowed gap after the previous letter


def ink_distance_field(image_path):
    im = Image.open(image_path).convert("RGB")
    a = np.asarray(im).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    ink = (mx < 165) & (mx - mn < 65)
    return distance_transform_edt(~ink)


def entry_points(entry, spacing=0.6):
    "Sample the glyph centerline (metafont units), ~spacing units apart."
    pts = []
    for c in entry["contours"]:
        try:
            solved = solve_path(c["knots"], c["segments"], c["cyclic"])
        except Exception:
            continue
        for s in solved:
            if s[0] == "line":
                p0, p1 = np.array(s[1], float), np.array(s[2], float)
                n = max(2, int(np.hypot(*(p1 - p0)) / spacing))
                for i in range(n + 1):
                    pts.append(p0 + (p1 - p0) * i / n)
            else:
                p0, c1, c2, p1 = (np.array(p, float) for p in s[1:])
                L = (np.hypot(*(c1 - p0)) + np.hypot(*(c2 - c1))
                     + np.hypot(*(p1 - c2)))
                n = max(4, int(L / spacing))
                t = np.linspace(0, 1, n + 1)[:, None]
                pts.extend((1-t)**3*p0 + 3*(1-t)**2*t*c1
                           + 3*(1-t)*t**2*c2 + t**3*p1)
    return np.array(pts)


def cost(df, pts_mf, tx, ty, s, cap=8.0):
    x = tx + s * pts_mf[:, 0]
    y = ty - s * pts_mf[:, 1]
    xi = np.clip(np.round(x).astype(int), 0, df.shape[1] - 1)
    yi = np.clip(np.round(y).astype(int), 0, df.shape[0] - 1)
    return float(np.minimum(df[yi, xi], cap).mean())


def refine_entry(df, entry, s0, base_y, min_left, max_left):
    """
    Fit one letter. s0: nominal px-per-unit scale; base_y: detected
    baseline. The letter's leftmost sampled x must fall in
    [min_left, max_left]. Returns (cost, right_edge_px).
    """
    pts = entry_points(entry)
    xmin_mf = pts[:, 0].min()
    xmax_mf = pts[:, 0].max()

    best = None
    scales = s0 * np.linspace(1 - S_RANGE, 1 + S_RANGE, 5)
    for s in scales:
        tx_lo = min_left - s * xmin_mf
        tx_hi = max_left - s * xmin_mf
        for tx in np.arange(tx_lo, tx_hi + 0.5, 1.0):
            for ty in np.arange(base_y - TY_RANGE, base_y + TY_RANGE + 0.5,
                                1.0):
                c = cost(df, pts, tx, ty, s)
                if best is None or c < best[0]:
                    best = (c, tx, ty, s)

    # fine pass around the best
    _, btx, bty, bs = best
    for s in bs * np.linspace(0.97, 1.03, 7):
        for tx in np.arange(btx - 1.5, btx + 1.51, 0.25):
            lo = tx + s * xmin_mf
            if lo < min_left - 0.75 or lo > max_left + 0.75:
                continue
            for ty in np.arange(max(bty - 1.5, base_y - TY_RANGE - 0.5),
                                min(bty + 1.51, base_y + TY_RANGE + 0.5),
                                0.25):
                c = cost(df, pts, tx, ty, s)
                if c < best[0]:
                    best = (c, tx, ty, s)

    c, btx, bty, bs = best
    entry["transform"] = {"tx": round(float(btx), 2),
                          "ty": round(float(bty), 2),
                          "s": round(float(bs), 4)}
    return c, btx + bs * xmax_mf


def main():
    data = json.load(open(LETTERS))
    image_path = os.path.join(HERE, "..", data["image"])
    df = ink_distance_field(image_path)
    (left, right), _ = detect_baselines()
    s0 = estimate_scale((left, right))
    print("nominal scale %.3f px/unit" % s0)

    by_id = {e["id"]: e for e in data["entries"]}
    # reconstruct cell order exactly like export_fit
    for rows, lines in [(ROWS_LEFT, left), (ROWS_RIGHT, right)]:
        for name, (y, x0, x1) in zip(rows, lines):
            _, upper, lower = row_glyphs(name)
            prev_right = x0 - 14.0
            for entry_id, _glyph in upper + lower:
                e = by_id[entry_id]
                c, prev_right = refine_entry(
                    df, e, s0, y,
                    min_left=prev_right - OVERLAP,
                    max_left=prev_right + GAP_MAX)
                print("%-8s cost %.2f px  right %6.1f  -> %s"
                      % (entry_id, c, prev_right, e["transform"]))

    with open(LETTERS, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    print("Updated", LETTERS)


if __name__ == "__main__":
    main()
