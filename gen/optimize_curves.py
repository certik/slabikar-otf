"""
Improve the agreement of the curves in fit/letters.json with the template by
adjusting the metafont-style parameters of every letter: knot positions,
pinned direction angles, tensions, plus one width factor per letter. The
number of knots is never changed and automatic (Hobby-chosen) directions
stay automatic.

Objective (all in template pixels): the symmetric distance between the glyph
centerline and the template ink assigned to the letter --
    (mean dist curve->ink  +  mean dist ink->curve) / 2
capped at CAP px. Ink pixels are assigned up front to the nearest letter's
initial curve, so neighbors don't tug on each other. Optimized per entry
with Powell.

Guardrails against overfitting:
  - knots move at most KNOT_R units; knots sharing a position (stroke
    junctions, closing points) are tied and move together;
  - contours smaller than ~2 units (the i/j dots) move rigidly;
  - one anisotropic width factor SX (plus a compensating shift) per letter
    absorbs the template's different letter aspect with a single parameter;
  - pinned directions rotate at most DIR_R degrees; smooth knots (equal
    in/out directions) stay smooth;
  - tensions change at most by factor TENS_R, inside METAFONT's [3/4, 4];
  - quadratic regularization pulls every parameter back to its start, so
    parameters only move when the ink actually demands it.

Usage:  python3 optimize_curves.py [entry_id ...]
"""

import json
import os
import sys
from multiprocessing import Pool

import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree

from bezier import solve_path
from refine_fit import ink_distance_field

HERE = os.path.dirname(os.path.abspath(__file__))
LETTERS = os.path.join(HERE, "..", "fit", "letters.json")

KNOT_R = 1.5      # max knot movement (mf units)
DIR_R = 25.0      # max direction change (degrees)
TENS_R = 1.5      # max tension change (factor)
SX_R = 1.25       # max width factor
DTX_R = 2.0       # max width-compensation shift (units)
CAP = 6.0         # px, distance cap in the data terms
ASSIGN_R = 8.0    # px, ink is assigned to letters within this distance
LAMBDA_KNOT = 0.06   # regularization weights (px of cost per unit of
LAMBDA_DIR = 0.10    # squared normalized deviation)
LAMBDA_TENS = 0.10
LAMBDA_SX = 0.05
RIGID_DIAG = 2.0  # contours smaller than this move rigidly (units)


def bilinear(df, x, y):
    h, w = df.shape
    x = np.clip(x, 0, w - 1.001)
    y = np.clip(y, 0, h - 1.001)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    fx = x - x0
    fy = y - y0
    return (df[y0, x0] * (1-fx) * (1-fy) + df[y0, x0+1] * fx * (1-fy)
            + df[y0+1, x0] * (1-fx) * fy + df[y0+1, x0+1] * fx * fy)


def sample_counts(contours, spacing=0.5):
    "Per-contour, per-segment fixed sample counts (from the initial shape)."
    counts = []
    for c in contours:
        solved = solve_path(c["knots"], c["segments"], c["cyclic"])
        n = []
        for s in solved:
            if s[0] == "line":
                L = np.hypot(s[2][0]-s[1][0], s[2][1]-s[1][1])
            else:
                p = [np.array(q, float) for q in s[1:]]
                L = sum(np.hypot(*(p[i+1]-p[i])) for i in range(3))
            n.append(max(4, int(L / spacing)))
        counts.append(n)
    return counts


def sample_points(contours, counts):
    pts = []
    for c, cn in zip(contours, counts):
        solved = solve_path(c["knots"], c["segments"], c["cyclic"])
        for s, n in zip(solved, cn):
            t = np.linspace(0, 1, n + 1)[:, None]
            if s[0] == "line":
                p0, p1 = np.array(s[1], float), np.array(s[2], float)
                pts.append(p0 + (p1 - p0) * t)
            else:
                p0, c1, c2, p1 = (np.array(q, float) for q in s[1:])
                pts.append((1-t)**3*p0 + 3*(1-t)**2*t*c1
                           + 3*(1-t)*t**2*c2 + t**3*p1)
    return np.vstack(pts)


def to_image(entry, pts):
    t = entry["transform"]
    return np.column_stack([t["tx"] + t["s"] * pts[:, 0],
                            t["ty"] - t["s"] * pts[:, 1]])


class Params:
    """
    Parameter vector for one entry: global (log width factor sx, shift dtx),
    tied knot groups (dx, dy), rigid contours (dx, dy), direction deltas
    (degrees), log-tension deltas. apply() returns transformed contours.
    """

    def __init__(self, contours):
        self.orig = json.loads(json.dumps(contours))
        self.kinds = [("sx", None), ("dtx", None)]
        self.x0 = [0.0, 0.0]
        self.bounds = [(-np.log(SX_R), np.log(SX_R)), (-DTX_R, DTX_R)]

        self.rigid = []
        for c in self.orig:
            xs = [k["x"] for k in c["knots"]]
            ys = [k["y"] for k in c["knots"]]
            self.rigid.append(np.hypot(max(xs)-min(xs), max(ys)-min(ys))
                              < RIGID_DIAG)

        groups = {}
        for ci, c in enumerate(self.orig):
            if self.rigid[ci]:
                continue
            for ki, k in enumerate(c["knots"]):
                key = (round(k["x"], 6), round(k["y"], 6))
                groups.setdefault(key, []).append((ci, ki))
        for members in groups.values():
            self.kinds.append(("knot", members))
            self.x0 += [0.0, 0.0]
            self.bounds += [(-KNOT_R, KNOT_R)] * 2

        for ci, c in enumerate(self.orig):
            if self.rigid[ci]:
                self.kinds.append(("rigid", ci))
                self.x0 += [0.0, 0.0]
                self.bounds += [(-KNOT_R, KNOT_R)] * 2
                continue
            for ki, k in enumerate(c["knots"]):
                din, dout = k.get("dir_in"), k.get("dir_out")
                if din is not None and din == dout:
                    self.kinds.append(("dir", (ci, ki, "both")))
                    self.x0.append(0.0)
                    self.bounds.append((-DIR_R, DIR_R))
                else:
                    for side, v in [("dir_in", din), ("dir_out", dout)]:
                        if v is not None:
                            self.kinds.append(("dir", (ci, ki, side)))
                            self.x0.append(0.0)
                            self.bounds.append((-DIR_R, DIR_R))
            for si, s in enumerate(c["segments"]):
                if s["type"] != "curve":
                    continue
                keys = ["tension"] if s.get("tension") is not None \
                    else ["tension_out", "tension_in"]
                for key in keys:
                    t0 = s.get(key, 1.0)
                    lo = np.log(max(0.75, t0 / TENS_R) / t0)
                    hi = np.log(min(4.0, t0 * TENS_R) / t0)
                    self.kinds.append(("tens", (ci, si, key, t0)))
                    self.x0.append(0.0)
                    self.bounds.append((lo, hi))

        self.x0 = np.array(self.x0)

    @staticmethod
    def _scale_dir(angle_deg, sx):
        "Direction after scaling x by sx."
        a = np.radians(angle_deg)
        return float(np.degrees(np.arctan2(np.sin(a), sx * np.cos(a))))

    def apply(self, x):
        contours = json.loads(json.dumps(self.orig))
        sx = float(np.exp(x[0]))
        dtx = float(x[1])
        # width factor + shift first
        for c in contours:
            for k in c["knots"]:
                k["x"] = k["x"] * sx + dtx
                for side in ("dir_in", "dir_out"):
                    if k.get(side) is not None:
                        k[side] = self._scale_dir(k[side], sx)
        i = 2
        for kind, payload in self.kinds[2:]:
            if kind in ("knot", "rigid"):
                dx, dy = x[i], x[i+1]
                i += 2
                members = payload if kind == "knot" else \
                    [(payload, ki)
                     for ki in range(len(contours[payload]["knots"]))]
                for ci, ki in members:
                    contours[ci]["knots"][ki]["x"] += dx
                    contours[ci]["knots"][ki]["y"] += dy
            elif kind == "dir":
                ci, ki, side = payload
                d = float(x[i])
                i += 1
                k = contours[ci]["knots"][ki]
                if side == "both":
                    k["dir_in"] += d
                    k["dir_out"] += d
                else:
                    k[side] += d
            else:
                ci, si, key, t0 = payload
                contours[ci]["segments"][si][key] = t0 * float(np.exp(x[i]))
                i += 1
        return contours

    def regularization(self, x):
        r = LAMBDA_SX * ((x[0] / np.log(SX_R))**2 + (x[1] / DTX_R)**2)
        i = 2
        rk, rd, rt = [], [], []
        for kind, _ in self.kinds[2:]:
            if kind in ("knot", "rigid"):
                rk.append(x[i]**2 + x[i+1]**2)
                i += 2
            elif kind == "dir":
                rd.append((x[i] / DIR_R)**2)
                i += 1
            else:
                rt.append((x[i] / np.log(TENS_R))**2)
                i += 1
        if rk:
            r += LAMBDA_KNOT * np.mean(rk)
        if rd:
            r += LAMBDA_DIR * np.mean(rd)
        if rt:
            r += LAMBDA_TENS * np.mean(rt)
        return r


def assign_ink(data, df):
    """
    Assign every ink pixel within ASSIGN_R px of some letter's initial curve
    to the closest letter. Returns {entry_id: (M,2) pixel coords}.
    """
    ys, xs = np.nonzero(df == 0)
    ink = np.column_stack([xs, ys]).astype(float)
    all_pts = []
    owner = []
    for idx, e in enumerate(data["entries"]):
        counts = sample_counts(e["contours"])
        p = to_image(e, sample_points(e["contours"], counts))
        all_pts.append(p)
        owner += [idx] * len(p)
    tree = cKDTree(np.vstack(all_pts))
    owner = np.array(owner)
    d, j = tree.query(ink, k=1)
    keep = d <= ASSIGN_R
    result = {}
    for idx, e in enumerate(data["entries"]):
        result[e["id"]] = ink[keep & (owner[j] == idx)]
    return result


def optimize_entry(args):
    entry, df, ink_pts = args
    counts = sample_counts(entry["contours"])
    prm = Params(entry["contours"])

    def data_cost(contours):
        p = to_image(entry, sample_points(contours, counts))
        fwd = np.minimum(bilinear(df, p[:, 0], p[:, 1]), CAP).mean()
        if len(ink_pts):
            dcov, _ = cKDTree(p).query(ink_pts, k=1)
            cov = np.minimum(dcov, CAP).mean()
        else:
            cov = 0.0
        return float(fwd + cov) / 2

    def cost(x):
        try:
            return data_cost(prm.apply(x)) + prm.regularization(x)
        except Exception:
            return 1e3

    c0 = data_cost(prm.orig)
    res = minimize(cost, prm.x0, method="Powell", bounds=prm.bounds,
                   options={"maxfev": 5000, "xtol": 1e-3, "ftol": 1e-4})
    contours = prm.apply(res.x)
    c1 = data_cost(contours)
    if c1 >= c0:
        return entry["id"], None, c0, c0, {}

    for c in contours:
        for k in c["knots"]:
            k["x"] = round(k["x"], 3)
            k["y"] = round(k["y"], 3)
            for side in ("dir_in", "dir_out"):
                if k.get(side) is not None:
                    k[side] = round(k[side], 1)
        for s in c["segments"]:
            for key in ("tension", "tension_out", "tension_in"):
                if s.get(key) is not None:
                    s[key] = round(s[key], 3)

    stats = {"sx": float(np.exp(res.x[0])), "knot": 0.0, "dir": 0.0,
             "tens": 1.0}
    i = 2
    for kind, _ in prm.kinds[2:]:
        if kind in ("knot", "rigid"):
            stats["knot"] = max(stats["knot"],
                                float(np.hypot(res.x[i], res.x[i+1])))
            i += 2
        elif kind == "dir":
            stats["dir"] = max(stats["dir"], abs(float(res.x[i])))
            i += 1
        else:
            stats["tens"] = max(stats["tens"], float(np.exp(abs(res.x[i]))))
            i += 1
    return entry["id"], contours, c0, c1, stats


def main():
    data = json.load(open(LETTERS))
    image_path = os.path.join(HERE, "..", data["image"])
    df = ink_distance_field(image_path)
    ink = assign_ink(data, df)
    only = set(sys.argv[1:])
    todo = [e for e in data["entries"] if not only or e["id"] in only]

    jobs = [(e, df, ink[e["id"]]) for e in todo]
    by_id = {e["id"]: e for e in data["entries"]}
    total0 = total1 = 0.0
    with Pool() as pool:
        for eid, contours, c0, c1, st in pool.imap(optimize_entry, jobs):
            total0 += c0
            total1 += c1
            if contours is not None:
                by_id[eid]["contours"] = contours
                print("%-8s %.3f -> %.3f px   (sx %.2f, max knot %.2fu, "
                      "dir %.1f deg, tension x%.2f)"
                      % (eid, c0, c1, st["sx"], st["knot"], st["dir"],
                         st["tens"]))
            else:
                print("%-8s %.3f px (kept)" % (eid, c0))
    print("mean symmetric cost: %.3f -> %.3f px over %d entries"
          % (total0 / len(todo), total1 / len(todo), len(todo)))
    with open(LETTERS, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    print("Updated", LETTERS)


if __name__ == "__main__":
    main()
