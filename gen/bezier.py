from math import atan2, pi, hypot
from numpy import array, sqrt, arctan2, sin, cos

def arg(z):
    # NumPy's arctan2(y,x) is equal to the arg(x,y) before equation (2) in [1]
    return arctan2(z[1], z[0])

def compute_control_points(z1, z2, w1, w2, tau):
    """
    z1, z2 ... the Bezier nodes (1st and 4th control point)
    w1, w2 ... tangent vectors (do not have to be unit vectors), just direction
    tau ... tension (0.75 .. oo)

    The formulas are implemented from [1], equations (3) and (10).

    Note: the unit tangent vector always points along the direction of the
    curve, so the first point "in" the curve, but the second points "out".

    [1] John D. Hobby: Smooth, Easy to Compute Interpolating Splines. 1985. CS-TR-85-1047.
        Online link: http://i.stanford.edu/pub/cstr/reports/cs/tr/85/1047/CS-TR-85-1047.pdf
    """
    z1 = array(z1)
    z2 = array(z2)
    tau1 = tau2 = tau

    # Metafont parameters, paragraph after (10) in [1]
    a = sqrt(2)
    b = 1/16
    c = (3-sqrt(5))/2

    # Paragraph above equation (2) in [1]
    theta = arg(w1) - arg(z2-z1)
    phi   = arg(z2-z1) - arg(w2)

    # Equations (10) in [1]
    alpha = a * (sin(theta) - b*sin(phi)) * (sin(phi) - b*sin(theta)) \
              * (cos(theta) -   cos(phi))
    rho   = (2 + alpha) / (1 + (1-c)*cos(theta) + c*cos(phi  ))
    sigma = (2 - alpha) / (1 + (1-c)*cos(phi  ) + c*cos(theta))

    # Paragraph above equation (3) in [1]
    c1 = rho/(3*tau1) * array([cos(theta), sin(theta)])
    c2 = array([1 - sigma/(3*tau2) * cos(phi), sigma/(3*tau2) * sin(phi)])

    # Shift and rotate the control points from (0,0)-(1,0) to z1-z2; equation (2) in [1]
    c1 = z1 + array([
        (z2[0]-z1[0])*c1[0]+(z1[1]-z2[1])*c1[1],
        (z2[1]-z1[1])*c1[0]+(z2[0]-z1[0])*c1[1]
        ])
    c2 = z1 + array([
        (z2[0]-z1[0])*c2[0]+(z1[1]-z2[1])*c2[1],
        (z2[1]-z1[1])*c2[0]+(z2[0]-z1[0])*c2[1]
        ])

    return c1, c2


################################################################################
# Full METAFONT path solving (Hobby's algorithm)
#
# Given a path specified by knots, *optional* directions on either side of
# each knot, and per-segment tensions, choose the unspecified directions the
# way METAFONT does ("mock curvature" equations) and produce cubic Bezier
# control points.
#
# The implementation follows METAFONT's make_choices/solve_choices exactly;
# see mf.web, part 18 "Choosing control points" (sections around
# solve_choices, curl_ratio, set_controls), and [1] above.
#
# Notation (mf.web):
#   d[k]      ... |z_{k+1} - z_k|
#   psi[k]    ... turning angle of the polygonal line at z_k
#   theta[k]  ... angle of the outgoing direction at z_k relative to chord k
#   phi[k]    ... angle of the incoming direction at z_k relative to chord k-1
#                 (theta[k] + phi[k] + psi[k] = 0 at smooth knots)
#   alpha[k]  ... 1/tension of segment k at its start (z_k)
#   beta[k]   ... 1/tension of segment k-1 at its end (z_k)
#
# The mock curvature equations for interior knots are
#   A_k theta_{k-1} + (B_k+C_k) theta_k + D_k theta_{k+1} = -B_k psi_k - D_k psi_{k+1}
# with
#   A_k = alpha_{k-1}/(beta_k^2 d_{k-1}),  B_k = (3-alpha_{k-1})/(beta_k^2 d_{k-1}),
#   C_k = (3-beta_{k+1})/(alpha_k^2 d_k),  D_k = beta_{k+1}/(alpha_k^2 d_k).
# Boundary conditions are either a given angle, or a "curl" gamma (default 1),
# which relates theta_0 to theta_1 through curl_ratio below.

def _reduce_angle(a):
    "Reduce an angle in radians to (-pi, pi]."
    while a > pi:
        a -= 2*pi
    while a <= -pi:
        a += 2*pi
    return a

def _velocity(theta, phi, tau):
    """
    METAFONT's "velocity" function: rho(theta, phi) / (3 tau), capped at 4.
    rho is the same expression as in compute_control_points() (equations (10)
    in [1]); sigma(theta, phi) = rho(phi, theta).
    """
    a = sqrt(2)
    b = 1/16
    c = (3-sqrt(5))/2
    alpha = a * (sin(theta) - b*sin(phi)) * (sin(phi) - b*sin(theta)) \
              * (cos(theta) -   cos(phi))
    rho = (2 + alpha) / (1 + (1-c)*cos(theta) + c*cos(phi))
    return min(rho / (3*tau), 4.0)

def _set_controls(z0, z1, theta, phi, tau0, tau1):
    "Control points of one segment, given the offset angles (mf set_controls)."
    dx = z1[0] - z0[0]
    dy = z1[1] - z0[1]
    rr = _velocity(theta, phi, tau0)
    ss = _velocity(phi, theta, tau1)
    st, ct = sin(theta), cos(theta)
    sf, cf = sin(phi), cos(phi)
    c1 = (z0[0] + rr*(dx*ct - dy*st), z0[1] + rr*(dy*ct + dx*st))
    c2 = (z1[0] - ss*(dx*cf + dy*sf), z1[1] - ss*(dy*cf - dx*sf))
    return c1, c2

def _curl_ratio(gamma, alpha, beta):
    """
    METAFONT's curl_ratio: ((3-alpha) alpha^2 gamma + beta^3) /
    (alpha^3 gamma + (3-beta) beta^2), capped at 4. alpha and beta are
    *reciprocals* of the tensions at the curl end and at the neighbor knot.
    """
    num = (3 - alpha)*alpha**2*gamma + beta**3
    den = alpha**3*gamma + (3 - beta)*beta**2
    if num >= 4*den:
        return 4.0
    return num/den

def _segment_controls(pts, theta, psi, tens_out, tens_in):
    "Compute controls of every segment of a run from the solved thetas."
    out = []
    for k in range(len(pts)-1):
        phi = -psi[k+1] - theta[k+1]
        c1, c2 = _set_controls(pts[k], pts[k+1], theta[k], phi,
                               tens_out[k], tens_in[k])
        out.append((c1, c2))
    return out

def _solve_run(pts, tens_out, tens_in, bc0, bcn):
    """
    Choose directions for an open run pts[0..n] whose interior knots are all
    smooth ("open" in METAFONT). tens_out[k]/tens_in[k] are the tensions of
    segment k at its start/end. bc0 and bcn are the boundary conditions:
    ("given", angle_in_radians) or ("curl", gamma).
    Returns [(c1, c2)] for each segment.
    """
    n = len(pts) - 1
    d = [0.0]*n
    ang = [0.0]*n
    for k in range(n):
        dx = pts[k+1][0] - pts[k][0]
        dy = pts[k+1][1] - pts[k][1]
        d[k] = hypot(dx, dy)
        if d[k] == 0:
            # Degenerate: coincident knots; make the controls coincide too
            d[k] = 1e-30
        ang[k] = atan2(dy, dx)
    psi = [0.0]*(n+1)
    for k in range(1, n):
        psi[k] = _reduce_angle(ang[k] - ang[k-1])

    alpha = [1/t for t in tens_out]         # alpha[k], k = 0..n-1
    beta = [None] + [1/t for t in tens_in]  # beta[k],  k = 1..n

    theta = [0.0]*(n+1)
    if n == 1 and bc0[0] == "given" and bcn[0] == "given":
        theta[0] = _reduce_angle(bc0[1] - ang[0])
        theta[1] = _reduce_angle(bcn[1] - ang[0])
        return _segment_controls(pts, theta, psi, tens_out, tens_in)
    if n == 1 and bc0[0] == "curl" and bcn[0] == "curl":
        # mf.web "Reduce to simple case of straight line": theta = phi = 0
        return _segment_controls(pts, theta, psi, tens_out, tens_in)

    u = [0.0]*(n+1)
    v = [0.0]*(n+1)
    if bc0[0] == "given":
        u[0] = 0.0
        v[0] = _reduce_angle(bc0[1] - ang[0])
    else:
        u[0] = _curl_ratio(bc0[1], alpha[0], beta[1])
        v[0] = -u[0]*psi[1]
    for k in range(1, n):
        A = alpha[k-1] / (beta[k]**2 * d[k-1])
        B = (3 - alpha[k-1]) / (beta[k]**2 * d[k-1])
        C = (3 - beta[k+1]) / (alpha[k]**2 * d[k])
        D = beta[k+1] / (alpha[k]**2 * d[k])
        t = B - u[k-1]*A + C
        u[k] = D/t
        v[k] = (-B*psi[k] - D*psi[k+1] - A*v[k-1]) / t
    if bcn[0] == "given":
        theta[n] = _reduce_angle(bcn[1] - ang[n-1])
    else:
        ff = _curl_ratio(bcn[1], beta[n], alpha[n-1])
        theta[n] = -ff*v[n-1] / (1 - ff*u[n-1])
    for k in range(n-1, -1, -1):
        theta[k] = v[k] - u[k]*theta[k+1]
    return _segment_controls(pts, theta, psi, tens_out, tens_in)

def _solve_cycle(pts, tens_out, tens_in):
    """
    Choose directions for a fully smooth cyclic path with knots pts[0..n-1]
    (segment k goes from knot k to knot (k+1) mod n).
    Returns [(c1, c2)] for each of the n segments.
    """
    n = len(pts)
    d = [0.0]*n
    ang = [0.0]*n
    for k in range(n):
        dx = pts[(k+1) % n][0] - pts[k][0]
        dy = pts[(k+1) % n][1] - pts[k][1]
        d[k] = hypot(dx, dy)
        if d[k] == 0:
            d[k] = 1e-30
        ang[k] = atan2(dy, dx)
    # psi[k] for k = 1..n; psi[n] is the turning angle at knot 0; also
    # psi[n+1] = psi[1] (mf.web: "psi[k] := psi[1]")
    psi = [0.0]*(n+2)
    for k in range(1, n+1):
        psi[k] = _reduce_angle(ang[k % n] - ang[k-1])
    psi[n+1] = psi[1]

    def al(k):
        return 1/tens_out[k % n]
    def be(k):
        return 1/tens_in[(k-1) % n]
    def dd(k):
        return d[k % n]

    u = [0.0]*(n+1)
    v = [0.0]*(n+1)
    w = [0.0]*(n+1)
    w[0] = 1.0
    for k in range(1, n+1):
        A = al(k-1) / (be(k)**2 * dd(k-1))
        B = (3 - al(k-1)) / (be(k)**2 * dd(k-1))
        C = (3 - be(k+1)) / (al(k)**2 * dd(k))
        D = be(k+1) / (al(k)**2 * dd(k))
        t = B - u[k-1]*A + C
        u[k] = D/t
        v[k] = (-B*psi[k] - D*psi[k+1] - A*v[k-1]) / t
        w[k] = -A*w[k-1] / t
    # Eliminate the w's: theta[n] = aa + bb*theta[n] (mf.web "Adjust theta_n")
    aa = 0.0
    bb = 1.0
    for k in list(range(n-1, 0, -1)) + [n]:
        aa = v[k] - aa*u[k]
        bb = w[k] - bb*u[k]
    theta_n = aa / (1 - bb)
    v[0] = theta_n
    for k in range(1, n):
        v[k] += theta_n*w[k]
    theta = [0.0]*(n+1)
    theta[n] = theta_n
    for k in range(n-1, -1, -1):
        theta[k] = v[k] - u[k]*theta[k+1]

    out = []
    for k in range(n):
        phi = -psi[k+1] - theta[k+1]
        c1, c2 = _set_controls(pts[k], pts[(k+1) % n], theta[k], phi,
                               tens_out[k], tens_in[k])
        out.append((c1, c2))
    return out

def solve_path(knots, segments, cyclic=False):
    """
    Solve a METAFONT-style path specification.

    knots ... list of dicts:
        x, y      ... knot coordinates
        dir_in    ... optional incoming direction in degrees (None = free)
        dir_out   ... optional outgoing direction in degrees (None = free)
        curl_in   ... optional curl for the incoming side (default 1)
        curl_out  ... optional curl for the outgoing side (default 1)
    segments ... list of dicts:
        type         ... "curve" or "line"
        tension      ... tension for both ends (default 1), or
        tension_out  ... tension at the segment start
        tension_in   ... tension at the segment end
    cyclic ... if True, segment k connects knot k to knot (k+1) mod n and
        len(segments) == len(knots); otherwise len(segments) == len(knots)-1.

    A knot is a breakpoint if any direction is specified on it, if it touches
    a "line" segment (METAFONT's `--` implies curl 1 there), or if it is an
    end of an open path. Unspecified directions at breakpoints default to
    curl 1, exactly like METAFONT.

    Returns a list with one entry per segment:
        ("line", (x0,y0), (x1,y1))
        ("curve", (x0,y0), (c1x,c1y), (c2x,c2y), (x1,y1))
    """
    nk = len(knots)
    ns = len(segments)
    if cyclic:
        assert ns == nk, "cyclic path needs as many segments as knots"
    else:
        assert ns == nk - 1, "open path needs len(knots)-1 segments"

    def deg(a):
        return a*pi/180 if a is not None else None

    def seg_tensions(s):
        t = s.get("tension")
        if t is None:
            return (s.get("tension_out", 1.0), s.get("tension_in", 1.0))
        return (t, t)

    def knot_xy(i):
        k = knots[i % nk]
        return (k["x"], k["y"])

    def is_line(j):
        return segments[j % ns]["type"] == "line"

    def is_break(i):
        k = knots[i]
        if k.get("dir_in") is not None or k.get("dir_out") is not None:
            return True
        if k.get("curl_in") is not None or k.get("curl_out") is not None:
            return True
        if cyclic:
            return is_line(i-1) or is_line(i)
        if i == 0 or i == nk-1:
            return True
        return is_line(i-1) or is_line(i)

    breaks = [i for i in range(nk) if is_break(i)]
    if cyclic and not breaks:
        pts = [knot_xy(i) for i in range(nk)]
        tens = [seg_tensions(s) for s in segments]
        ctrl = _solve_cycle(pts, [t[0] for t in tens], [t[1] for t in tens])
        return [("curve", pts[k], ctrl[k][0], ctrl[k][1], pts[(k+1) % nk])
                for k in range(ns)]

    # Split into runs of consecutive segments between breakpoints
    result = [None]*ns
    if cyclic:
        runs = []
        for bi in range(len(breaks)):
            i0 = breaks[bi]
            i1 = breaks[(bi+1) % len(breaks)]
            length = (i1 - i0) % nk
            if length == 0:
                length = nk  # single breakpoint: the run is the whole cycle
            runs.append((i0, length))
    else:
        runs = [(breaks[bi], breaks[bi+1] - breaks[bi])
                for bi in range(len(breaks)-1)]

    for (i0, length) in runs:
        segs = [(i0 + j) % ns for j in range(length)]
        if length == 1 and is_line(segs[0]):
            result[segs[0]] = ("line", knot_xy(i0), knot_xy(i0+1))
            continue
        pts = [knot_xy(i0 + j) for j in range(length+1)]
        tens = [seg_tensions(segments[j]) for j in segs]

        k0 = knots[i0 % nk]
        kn = knots[(i0 + length) % nk]
        d0 = k0.get("dir_out")
        if d0 is None:
            d0 = k0.get("dir_in")
        dn = kn.get("dir_in")
        if dn is None:
            dn = kn.get("dir_out")
        if d0 is not None:
            bc0 = ("given", deg(d0))
        else:
            bc0 = ("curl", k0.get("curl_out", k0.get("curl_in", 1.0)) or 1.0)
        if dn is not None:
            bcn = ("given", deg(dn))
        else:
            bcn = ("curl", kn.get("curl_in", kn.get("curl_out", 1.0)) or 1.0)

        ctrl = _solve_run(pts, [t[0] for t in tens], [t[1] for t in tens],
                          bc0, bcn)
        for j, sj in enumerate(segs):
            result[sj] = ("curve", pts[j], ctrl[j][0], ctrl[j][1], pts[j+1])
    return result
