"""
Tests for the METAFONT path solving in bezier.py (solve_path).

Two kinds of checks:

1. Pure-Python: a single segment with directions given at both ends must
   reproduce compute_control_points() (the original Hobby formula that the
   font has always been built with).

2. Ground truth: every test path is also given to a real MetaPost binary
   (with -numbersystem=double) and the control points it chooses must match
   ours. This runs only if mpost is available (see _find_mpost below);
   otherwise those checks are skipped with a warning.

Run:  python3 test_bezier.py
"""

import os
import re
import shutil
import subprocess
import tempfile

from bezier import solve_path, compute_control_points


def knot(x, y, dir_in=None, dir_out=None, curl_in=None, curl_out=None):
    return {"x": x, "y": y, "dir_in": dir_in, "dir_out": dir_out,
            "curl_in": curl_in, "curl_out": curl_out}


def seg(tension=None, tension_out=None, tension_in=None, type="curve"):
    s = {"type": type}
    if tension is not None:
        s["tension"] = tension
    if tension_out is not None:
        s["tension_out"] = tension_out
    if tension_in is not None:
        s["tension_in"] = tension_in
    return s


# (name, knots, segments, cyclic, MetaPost path expression)
CASES = [
    ("open_defaults",
     [knot(0, 0), knot(10, 10), knot(20, 0)],
     [seg(), seg()], False,
     "(0,0)..(10,10)..(20,0)"),

    ("given_ends",
     [knot(0, 0, dir_out=90), knot(10, 10), knot(20, 0, dir_in=-90)],
     [seg(), seg()], False,
     "(0,0){dir 90}..(10,10)..{dir -90}(20,0)"),

    ("interior_dir",
     [knot(0, 0), knot(10, 10, dir_out=0), knot(20, 0)],
     [seg(), seg()], False,
     "(0,0)..(10,10){dir 0}..(20,0)"),

    ("tensions",
     [knot(0, 0), knot(10, 10), knot(20, 0)],
     [seg(tension=1.5), seg(tension_out=0.8, tension_in=2)], False,
     "(0,0)..tension 1.5..(10,10)..tension 0.8 and 2..(20,0)"),

    ("curl_ends",
     [knot(0, 0, curl_out=2), knot(10, 10), knot(20, 0, curl_in=0.5)],
     [seg(), seg()], False,
     "(0,0){curl 2}..(10,10)..{curl 0.5}(20,0)"),

    ("single_given_given",
     [knot(0, 0, dir_out=30), knot(20, 5, dir_in=-60)],
     [seg()], False,
     "(0,0){dir 30}..{dir -60}(20,5)"),

    ("single_curl_curl",
     [knot(0, 0), knot(20, 5)],
     [seg()], False,
     "(0,0)..(20,5)"),

    ("single_given_curl",
     [knot(0, 0, dir_out=80), knot(20, 5)],
     [seg()], False,
     "(0,0){dir 80}..(20,5)"),

    ("single_curl_given",
     [knot(0, 0), knot(20, 5, dir_in=-45)],
     [seg()], False,
     "(0,0)..{dir -45}(20,5)"),

    ("line_join",
     [knot(0, 0), knot(5, 5), knot(10, 5), knot(15, 0)],
     [seg(), seg(type="line"), seg()], False,
     "(0,0)..(5,5)--(10,5)..(15,0)"),

    ("longer_chain",
     [knot(0, 0), knot(3, 4), knot(7, 6), knot(12, 3), knot(15, -2),
      knot(21, 1)],
     [seg(), seg(tension=1.2), seg(), seg(tension_out=2, tension_in=0.9),
      seg()], False,
     "(0,0)..(3,4)..tension 1.2..(7,6)..(12,3)"
     "..tension 2 and 0.9..(15,-2)..(21,1)"),

    ("cycle",
     [knot(0, 0), knot(10, 2), knot(13, 9), knot(4, 12)],
     [seg(), seg(), seg(), seg()], True,
     "(0,0)..(10,2)..(13,9)..(4,12)..cycle"),

    ("cycle_tensions",
     [knot(0, 0), knot(10, 2), knot(13, 9), knot(4, 12)],
     [seg(tension=1.4), seg(), seg(tension_out=0.9, tension_in=1.8), seg()],
     True,
     "(0,0)..tension 1.4..(10,2)..(13,9)"
     "..tension 0.9 and 1.8..(4,12)..cycle"),

    ("cycle_one_dir",
     [knot(0, 0, dir_out=45), knot(10, 2), knot(13, 9), knot(4, 12)],
     [seg(), seg(), seg(), seg()], True,
     "(0,0){dir 45}..(10,2)..(13,9)..(4,12)..cycle"),

    ("cycle_two_dirs",
     [knot(0, 0, dir_out=45), knot(10, 2), knot(13, 9, dir_in=100, dir_out=160),
      knot(4, 12)],
     [seg(), seg(), seg(), seg()], True,
     "(0,0){dir 45}..(10,2)..{dir 100}(13,9){dir 160}..(4,12)..cycle"),

    ("slabikar_a_like",
     # Similar to the 'a' bowl but with the interior directions left free
     [knot(3, 7, dir_out=180), knot(1.5, 6.9), knot(0, 6),
      knot(-1, 0), knot(3, 7, dir_in=104)],
     [seg(), seg(), seg(tension=1.5), seg(tension=1.2)], False,
     "(3,7){dir 180}..(1.5,6.9)..(0,6)..tension 1.5.."
     "(-1,0)..tension 1.2..{dir 104}(3,7)"),
]


def controls(spec):
    "Flatten a solve_path result to a list of 8-tuples (line -> thirds)."
    out = []
    for s in spec:
        if s[0] == "line":
            (x0, y0), (x1, y1) = s[1], s[2]
            out.append((x0, y0,
                        x0 + (x1-x0)/3, y0 + (y1-y0)/3,
                        x0 + 2*(x1-x0)/3, y0 + 2*(y1-y0)/3,
                        x1, y1))
        else:
            (x0, y0), (c1x, c1y), (c2x, c2y), (x1, y1) = s[1:]
            out.append((x0, y0, c1x, c1y, c2x, c2y, x1, y1))
    return out


def _find_mpost():
    "Return the mpost argv prefix, or None if unavailable."
    if os.environ.get("MPOST"):
        return os.environ["MPOST"].split()
    if shutil.which("mpost"):
        return ["mpost"]
    if shutil.which("micromamba"):
        r = subprocess.run(["micromamba", "run", "-n", "mptest", "mpost",
                            "--version"], capture_output=True)
        if r.returncode == 0:
            return ["micromamba", "run", "-n", "mptest", "mpost"]
    return None


_PAIR = r"\(\s*(-?[\d.]+(?:e-?\d+)?)\s*,\s*(-?[\d.]+(?:e-?\d+)?)\s*\)"


def parse_mp_path(text):
    """
    Parse a MetaPost 'show' of a path, e.g.
    (0,0)..controls (1,2) and (3,4)..(10,10)..controls ... ..(20,0)[..cycle]
    Returns a list of 8-tuples per segment.
    """
    text = text.replace("\n", "")
    pairs = [(float(a), float(b)) for a, b in re.findall(_PAIR, text)]
    cyclic = text.rstrip().endswith("cycle")
    # points come as: z0 c1 c2 z1 c1 c2 z2 ... (zn omitted if cycle)
    if cyclic:
        pairs.append(pairs[0])
    assert (len(pairs) - 1) % 3 == 0, text
    out = []
    for i in range(0, len(pairs)-1, 3):
        z0, c1, c2, z1 = pairs[i:i+4]
        out.append((z0[0], z0[1], c1[0], c1[1], c2[0], c2[1], z1[0], z1[1]))
    return out


def mpost_ground_truth(mpost, exprs):
    "Run mpost on the given path expressions; return a list of parsed paths."
    here = os.path.dirname(os.path.abspath(__file__))
    plain = None
    for cand in [os.path.join(here, "plain.mp"),
                 os.path.join(here, "..", "fit", "plain.mp")]:
        if os.path.exists(cand):
            plain = cand
            break
    with tempfile.TemporaryDirectory() as tmp:
        src = ""
        if plain:
            shutil.copy(plain, os.path.join(tmp, "plain.mp"))
            src += "input plain;\n"
        for e in exprs:
            src += "show %s;\n" % e
        src += "end.\n"
        open(os.path.join(tmp, "job.mp"), "w").write(src)
        env = dict(os.environ, max_print_line="10000", MPINPUTS=tmp)
        r = subprocess.run(mpost + ["-ini", "-numbersystem=double", "job.mp"],
                           cwd=tmp, env=env, capture_output=True, text=True)
        log = open(os.path.join(tmp, "job.log")).read()
        if r.returncode != 0 and ">> " not in log:
            raise Exception("mpost failed:\n" + r.stdout + r.stderr)
    blocks = []
    cur = None
    for line in log.splitlines():
        if line.startswith(">> Path at line") or line.startswith(">> "):
            if cur is not None:
                blocks.append(cur)
            cur = line.split(":", 1)[-1] if "Path at line" in line \
                else line[3:]
        elif cur is not None:
            if line.strip() == "" or line.startswith("(see the transcript"):
                blocks.append(cur)
                cur = None
            else:
                cur += line
    if cur is not None:
        blocks.append(cur)
    paths = [b for b in blocks if "controls" in b]
    assert len(paths) == len(exprs), \
        "expected %d paths in log, found %d" % (len(exprs), len(paths))
    return [parse_mp_path(p) for p in paths]


def check_close(name, got, want, tol):
    assert len(got) == len(want), \
        "%s: %d segments, expected %d" % (name, len(got), len(want))
    for i, (g, w) in enumerate(zip(got, want)):
        for j, (a, b) in enumerate(zip(g, w)):
            assert abs(a - b) <= tol, \
                "%s seg %d comp %d: %.12g != %.12g (diff %.3g)" % \
                (name, i, j, a, b, abs(a-b))


def test_given_given_matches_compute_control_points():
    "solve_path on a fully specified segment == the original formula."
    from math import cos, sin, radians
    cases = [
        ((0, 0), (20, 5), 30, -60, 1.0),
        ((3, 7), (1.5, 6.9), 180, 194.0362434679265, 1.0),
        ((0, 6), (-1, 0), -50.194428907734805, 0, 1.5),
        ((1, 2), (8, -3), 10, 45, 0.75),
    ]
    for z0, z1, a0, a1, tau in cases:
        w0 = (cos(radians(a0)), sin(radians(a0)))
        w1 = (cos(radians(a1)), sin(radians(a1)))
        c1, c2 = compute_control_points(z0, z1, w0, w1, tau)
        r = solve_path([knot(z0[0], z0[1], dir_out=a0),
                        knot(z1[0], z1[1], dir_in=a1)],
                       [seg(tension=tau)], False)
        assert r[0][0] == "curve"
        got = (r[0][2][0], r[0][2][1], r[0][3][0], r[0][3][1])
        want = (c1[0], c1[1], c2[0], c2[1])
        for a, b in zip(got, want):
            assert abs(a - b) < 1e-12, (z0, z1, got, want)
    print("OK: given-given matches compute_control_points")


def test_against_mpost():
    mpost = _find_mpost()
    if mpost is None:
        print("SKIPPED: mpost not found (set MPOST=... to enable)")
        return
    truths = mpost_ground_truth(mpost, [c[4] for c in CASES])
    for (name, knots, segments, cyclic, _), want in zip(CASES, truths):
        got = controls(solve_path(knots, segments, cyclic))
        check_close(name, got, want, 1e-6)
        print("OK: %s matches MetaPost (%d segments)" % (name, len(got)))


def test_js_matches_python():
    "fit/hobby.js must produce identical control points to bezier.py."
    import json
    if not shutil.which("node"):
        print("SKIPPED: node not found")
        return
    here = os.path.dirname(os.path.abspath(__file__))
    hobby_js = os.path.join(here, "..", "fit", "hobby.js")
    payload = json.dumps({"cases": [
        {"knots": k, "segments": s, "cyclic": c}
        for (_, k, s, c, _) in CASES]})
    r = subprocess.run(["node", hobby_js], input=payload,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    js_results = json.loads(r.stdout)
    for (name, knots, segments, cyclic, _), js in zip(CASES, js_results):
        got = controls([(s[0],) + tuple(tuple(p) for p in s[1:])
                        for s in js])
        want = controls(solve_path(knots, segments, cyclic))
        check_close("js:" + name, got, want, 1e-9)
        print("OK: %s JS matches Python" % name)


def test_js_controls_roundtrip():
    """
    controlsToParams (used by the traditional-bezier edit mode) must invert
    solvePath: recovered dirs+tensions reproduce the same control points.
    """
    if not shutil.which("node"):
        print("SKIPPED: node not found")
        return
    here = os.path.dirname(os.path.abspath(__file__))
    hobby_js = os.path.join(here, "..", "fit", "hobby.js")
    js = """
    const H = require(%r);
    const cases = [
        [[0,0],[2,7],[14,9],[20,5]],
        [[3,7],[1.5,6.9],[0.2,6.5],[0,6]],
        [[0,0],[1,1],[19,1],[20,0]],
        [[-5,2],[-9,8],[3,14],[1,4]],
    ];
    let maxerr = 0;
    for (const [z0,c1,c2,z1] of cases) {
        const p = H.controlsToParams(z0,c1,c2,z1);
        const r = H.solvePath(
            [{x:z0[0],y:z0[1],dir_out:p.dir_out},
             {x:z1[0],y:z1[1],dir_in:p.dir_in}],
            [{type:"curve",tension_out:p.tension_out,
              tension_in:p.tension_in}], false);
        const [c1b,c2b] = [r[0][2], r[0][3]];
        maxerr = Math.max(maxerr,
            Math.abs(c1b[0]-c1[0]), Math.abs(c1b[1]-c1[1]),
            Math.abs(c2b[0]-c2[0]), Math.abs(c2b[1]-c2[1]));
    }
    console.log(maxerr);
    """ % (os.path.abspath(hobby_js),)
    r = subprocess.run(["node", "-e", js], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    maxerr = float(r.stdout.strip())
    assert maxerr < 1e-9, "roundtrip error %g" % maxerr
    print("OK: JS controls->params->controls roundtrip (err %.2g)" % maxerr)


if __name__ == "__main__":
    test_given_given_matches_compute_control_points()
    test_against_mpost()
    test_js_matches_python()
    test_js_controls_roundtrip()
    print("All bezier tests passed.")
