"""Compare stroke_to_path against Inkscape object-stroke-to-path."""
from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from glif import Glif, glif2svg, parse_svg
from stroke import stroke_to_path, merge_connected_contours


def load_glyphs():
    src = Path(__file__).with_name("svg.py").read_text()
    src = src.split("# Save\n")[0]
    ns = {}
    exec(src, ns)
    return ns["_chars"], float(ns["stroke_width"])


def flatten_cubic(p0, p1, p2, p3, n=32):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def contours_to_loops(contours):
    loops = []
    for contour in contours:
        seq = [(float(p.x), float(p.y), p.type) for p in contour]
        ons = [k for k, p in enumerate(seq) if p[2] in ("line", "curve", "move")]
        if not ons:
            continue
        poly = []
        for j, oi in enumerate(ons):
            ni = ons[(j + 1) % len(ons)]
            p0 = (seq[oi][0], seq[oi][1])
            if seq[ni][2] in ("line", "move"):
                if j == 0:
                    poly.append(p0)
                poly.append((seq[ni][0], seq[ni][1]))
            else:
                offs = seq[oi + 1 : ni] if ni > oi else seq[oi + 1 :] + seq[:ni]
                if len(offs) == 2:
                    cub = flatten_cubic(
                        p0,
                        (offs[0][0], offs[0][1]),
                        (offs[1][0], offs[1][1]),
                        (seq[ni][0], seq[ni][1]),
                    )
                    poly.extend(cub if j == 0 else cub[1:])
                else:
                    if j == 0:
                        poly.append(p0)
                    poly.append((seq[ni][0], seq[ni][1]))
        if len(poly) >= 3:
            loops.append(poly)
    return loops


def raster_nonzero(loops, box, scale=1.0, pad=8):
    xmin, ymin, xmax, ymax = box
    W = max(1, int(math.ceil((xmax - xmin) * scale)) + 2 * pad)
    H = max(1, int(math.ceil((ymax - ymin) * scale)) + 2 * pad)

    def xy(p):
        return (pad + (p[0] - xmin) * scale, pad + (ymax - p[1]) * scale)

    edges = []
    for loop in loops:
        n = len(loop)
        for i in range(n):
            a = xy(loop[i])
            b = xy(loop[(i + 1) % n])
            if abs(a[1] - b[1]) < 1e-9:
                continue
            edges.append((a[0], a[1], b[0], b[1]))
    img = np.full((H, W), 255, np.uint8)
    for y in range(H):
        ys = y + 0.5
        xs = []
        for x0, y0, x1, y1 in edges:
            if (y0 <= ys < y1) or (y1 <= ys < y0):
                t = (ys - y0) / (y1 - y0)
                xs.append((x0 + t * (x1 - x0), 1 if y1 > y0 else -1))
        xs.sort()
        w = 0
        prev = None
        for x, d in xs:
            if w != 0 and prev is not None:
                ia = max(0, int(math.floor(prev)))
                ib = min(W, int(math.ceil(x)))
                if ib > ia:
                    img[y, ia:ib] = 0
            w += d
            prev = x
    return img


def bbox_of(loops, pad=24):
    xs = [p[0] for loop in loops for p in loop]
    ys = [p[1] for loop in loops for p in loop]
    if not xs:
        return (0, 0, 1, 1)
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def run_inkscape(commands_path):
    r = subprocess.run(
        ["inkscape", "--shell"],
        input=Path(commands_path).read_text(),
        text=True,
        capture_output=True,
    )
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-2000:])
        raise SystemExit(f"inkscape --shell failed: {r.returncode}")
    return r


def main():
    os.environ.setdefault("PATH", "")
    if "/Users/ondrej/bin" not in os.environ["PATH"]:
        os.environ["PATH"] = "/Users/ondrej/bin:" + os.environ["PATH"]

    chars, stroke_width = load_glyphs()
    work = Path("/tmp/ink_vs_py")
    work.mkdir(exist_ok=True)
    (work / "in").mkdir(exist_ok=True)
    (work / "ink").mkdir(exist_ok=True)
    (work / "diff").mkdir(exist_ok=True)

    jobs = []
    cmds = []
    for name, g in chars:
        if not g.contours:
            continue
        # Same SVG the old pipeline sent to Inkscape: unstitched centerlines.
        svg = glif2svg(g, False, False, stroke_width)
        inp = work / "in" / f"{name}.svg"
        outp = work / "ink" / f"{name}.svg"
        inp.write_text(svg)
        cmds.append(
            f"file-open:{inp}; select-by-id:path0; object-stroke-to-path; "
            f"export-filename:{outp}; export-type:svg; export-do; file-close"
        )
        jobs.append((name, g, outp))

    cmdfile = work / "commands.txt"
    cmdfile.write_text("\n".join(cmds) + "\n")
    missing = [outp for _, _, outp in jobs if not outp.exists()]
    if missing or "--force-inkscape" in sys.argv:
        print(f"Running Inkscape on {len(jobs)} glyphs...")
        run_inkscape(cmdfile)
    else:
        print(f"Reusing {len(jobs)} existing Inkscape SVGs in {work / 'ink'}")

    rows = []
    fail = 0
    for name, g, outp in jobs:
        if not outp.exists():
            print(f"{name:20} MISSING inkscape output")
            fail += 1
            continue
        try:
            ink = parse_svg(outp.read_text())
        except Exception as e:
            print(f"{name:20} PARSE FAIL {e}")
            fail += 1
            continue
        ours = stroke_to_path(g.contours, stroke_width)
        ink_loops = contours_to_loops(ink.contours)
        our_loops = contours_to_loops(ours)
        box = bbox_of(ink_loops + our_loops)
        a = raster_nonzero(ink_loops, box)
        b = raster_nonzero(our_loops, box)
        if a.shape != b.shape:
            H = max(a.shape[0], b.shape[0])
            W = max(a.shape[1], b.shape[1])
            aa = np.full((H, W), 255, np.uint8)
            bb = np.full((H, W), 255, np.uint8)
            aa[: a.shape[0], : a.shape[1]] = a
            bb[: b.shape[0], : b.shape[1]] = b
            a, b = aa, bb
        xor = (a < 128) != (b < 128)
        ink_px = int((a < 128).sum())
        our_px = int((b < 128).sum())
        diff = int(xor.sum())
        ratio = diff / max(ink_px, 1)
        rows.append((ratio, diff, ink_px, our_px, name))
        if ratio > 0.005:
            fail += 1
            xor_im = Image.fromarray(np.where(xor, 0, 255).astype(np.uint8))
            side = Image.new("L", (a.shape[1] * 3 + 8, a.shape[0]), 255)
            side.paste(Image.fromarray(a), (0, 0))
            side.paste(Image.fromarray(b), (a.shape[1] + 4, 0))
            side.paste(xor_im, (a.shape[1] * 2 + 8, 0))
            side.save(work / "diff" / f"{name}.png")

    rows.sort(reverse=True)
    print(f"\n{'glyph':20} {'xor/ink':>8} {'xor':>7} {'ink':>7} {'ours':>7}")
    for ratio, diff, ink_px, our_px, name in rows[:30]:
        print(f"{name:20} {ratio:8.4f} {diff:7d} {ink_px:7d} {our_px:7d}")
    print(f"... {len(rows)} glyphs")
    ratios = [r for r, *_ in rows]
    n = len(rows)
    n_ok = sum(1 for r in ratios if r <= 0.005)
    asc = sorted(ratios)
    med = asc[n // 2] if n else 0.0
    p90 = asc[int(0.9 * (n - 1))] if n else 0.0
    max_r, _, _, _, max_name = rows[0] if rows else (0, 0, 0, 0, "")
    print(f"\ncompared: {n}")
    print(f"<=0.5%: {n_ok}/{n}")
    print(f"median: {med:.4f}")
    print(f"p90: {p90:.4f}")
    print(f"max: {max_name} {max_r:.4f}")
    print(f"above 0.5%: {fail}")
    if fail:
        print(f"diff images in {work / 'diff'}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
