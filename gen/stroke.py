"""
Livarot-equivalent stroke-to-path.

Ports Inkscape's object-stroke-to-path (src/path/path-outline.cpp +
src/livarot/PathOutline.cpp):

  1. Two-sided offset of each subpath (lines exact; cubics via curvature-
     corrected Hermite cubics with midpoint-error subdivision).
  2. SVG caps and joins (butt / square / round, miter / bevel / round).
  3. Flatten self-overlaps with a planar graph and positive winding
     (Livarot ConvertToShape + fill_positive).
  4. Recover cubics from the offset pieces (ConvertToForme-style).

Coordinate system is the glif / Metafont one (Y up).  The offset side is
the clockwise normal, matching Livarot's Geom::Point::cw().
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from glif import Point, verify_contour


# ---------------------------------------------------------------------------
# Vector helpers (2-tuples).  Match lib2geom cw / ccw / rot90 / cross.
# ---------------------------------------------------------------------------

def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1])


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def vmul(a, s):
    return (a[0] * s, a[1] * s)


def vdot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def vcross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def vlen(a):
    return math.hypot(a[0], a[1])


def vlen2(a):
    return a[0] * a[0] + a[1] * a[1]


def vlinf(a):
    return max(abs(a[0]), abs(a[1]))


def vunit(a):
    l = vlen(a)
    if l <= 1e-18:
        return (0.0, 0.0)
    return (a[0] / l, a[1] / l)


def cw(a):
    """Clockwise 90°: (x, y) -> (y, -x).  Livarot offset normal."""
    return (a[1], -a[0])


def ccw(a):
    """Counter-clockwise 90°: (x, y) -> (-y, x).  lib2geom rot90 / ccw."""
    return (-a[1], a[0])


def rot90(a):
    return ccw(a)


def vdist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def veq(a, b, eps=1e-6):
    return vlinf(vsub(a, b)) < eps


# ---------------------------------------------------------------------------
# Path commands (Livarot PathDescr*).  Cubic handles are first derivatives:
#   P1 = P0 + start/3,  P2 = P3 - end/3
# ---------------------------------------------------------------------------

@dataclass
class MoveTo:
    p: tuple


@dataclass
class LineTo:
    p: tuple


@dataclass
class CubicTo:
    p: tuple
    start: tuple
    end: tuple


@dataclass
class Close:
    pass


class Path:
    def __init__(self):
        self.cmds: list = []

    def reset(self):
        self.cmds = []

    def move_to(self, p):
        self.cmds.append(MoveTo(p))

    def line_to(self, p):
        self.cmds.append(LineTo(p))
        return len(self.cmds) - 1

    def cubic_to(self, p, start, end):
        self.cmds.append(CubicTo(p, start, end))
        return len(self.cmds) - 1

    def arc_to(self, p, rx, ry, angle, large, clockwise):
        # Approximate a circular arc with cubics (used only for round joins/caps).
        # Livarot stores a real arc; RecStdArcTo then converts it to cubics
        # on the offset.  For caps/joins the arc is already the offset curve,
        # so we convert to cubics immediately.
        if not self.cmds:
            return -1
        p0 = _last_point(self.cmds)
        for cub in _arc_to_cubics(p0, p, rx, ry, angle, large, clockwise):
            self.cmds.append(cub)
        return len(self.cmds) - 1

    def close(self):
        self.cmds.append(Close())

    def copy(self):
        q = Path()
        q.cmds = list(self.cmds)
        return q


def _last_point(cmds):
    for c in reversed(cmds):
        if isinstance(c, (MoveTo, LineTo, CubicTo)):
            return c.p
    return (0.0, 0.0)


def prev_point(cmds, i):
    """Endpoint of command i, walking back through Close/forced."""
    while i >= 0:
        c = cmds[i]
        if isinstance(c, (MoveTo, LineTo, CubicTo)):
            return c.p
        i -= 1
    return (0.0, 0.0)


# ---------------------------------------------------------------------------
# Elliptical arc -> cubics (only needed for round caps / joins)
# ---------------------------------------------------------------------------

def _arc_to_cubics(p0, p1, rx, ry, angle_deg, large, clockwise):
    """Approximate an SVG arc by one or more cubics (κ = 4/3 tan(θ/4))."""
    rx, ry = abs(rx), abs(ry)
    if rx < 1e-8 or ry < 1e-8 or veq(p0, p1):
        return [LineTo(p1)]
    sang, eang, center = _arc_angles_center(
        p0, p1, rx, ry, angle_deg * math.pi / 180.0, large, clockwise
    )
    if clockwise:
        if sang < eang:
            sang += 2 * math.pi
    else:
        if sang > eang:
            sang -= 2 * math.pi
    sweep = eang - sang
    n = max(1, int(math.ceil(abs(sweep) / (math.pi / 2))))
    dt = sweep / n
    rot = angle_deg * math.pi / 180.0
    ca, sa = math.cos(rot), math.sin(rot)

    def pt(a):
        cb, sb = math.cos(a), math.sin(a)
        x, y = rx * cb, ry * sb
        return (center[0] + ca * x - sa * y, center[1] + sa * x + ca * y)

    def deriv(a):
        # d/da of the unrotated ellipse is (-rx sin, ry cos); rotate and
        # scale by da later.  Sign follows the sweep direction.
        cb, sb = math.cos(a), math.sin(a)
        dx, dy = -rx * sb, ry * cb
        return (ca * dx - sa * dy, sa * dx + ca * dy)

    out = []
    for i in range(n):
        a0 = sang + i * dt
        a1 = sang + (i + 1) * dt
        k = 4.0 / 3.0 * math.tan(dt / 4.0)
        d0 = vmul(deriv(a0), k)
        d1 = vmul(deriv(a1), k)
        out.append(CubicTo(pt(a1), d0, d1))
    return out


def _arc_angles_center(iS, iE, rx, ry, angle, large, wise):
    """Port of Livarot ArcAnglesAndCenter.  wise=True is clockwise."""
    se = vsub(iE, iS)
    ca, sa = math.cos(angle), math.sin(angle)
    cse = ((ca * se[0] + sa * se[1]) / rx, (-sa * se[0] + ca * se[1]) / ry)
    lensq = vdot(cse, cse)
    scale = math.sqrt(max(1.0 / lensq - 0.25, 0.0)) if lensq < 4 else 0.0
    csd = vmul(ccw(cse), scale)

    def ang_of(ra):
        if ra[0] <= -1:
            a = math.pi
        elif ra[0] >= 1:
            a = 0.0
        else:
            a = math.acos(max(-1.0, min(1.0, ra[0])))
            if ra[1] < 0:
                a = 2 * math.pi - a
        return a

    sang = ang_of(vsub(vmul(csd, -1), vmul(cse, 0.5)))
    eang = ang_of(vadd(vmul(csd, -1), vmul(cse, 0.5)))
    csd = (csd[0] * rx, csd[1] * ry)
    # inverse rotation of csd
    dr = (ca * csd[0] - sa * csd[1], sa * csd[0] + ca * csd[1])

    def flip():
        nonlocal dr, sang, eang
        dr = vmul(dr, -1)
        sang, eang = eang + math.pi, sang + math.pi
        if eang >= 2 * math.pi:
            eang -= 2 * math.pi
        if sang >= 2 * math.pi:
            sang -= 2 * math.pi

    if wise:
        if large:
            flip()
    else:
        if not large:
            flip()
    center = vadd(dr, vmul(vadd(iS, iE), 0.5))
    return sang, eang, center


# ---------------------------------------------------------------------------
# Tangents / curvature  (PathOutline.cpp TangentOnSegAt / TangentOnCubAt)
# ---------------------------------------------------------------------------

def tangent_on_seg_at(at, iS, iE):
    seg = vsub(iE, iS)
    l = vlen(seg)
    if l <= 1e-6:
        return iS, (0.0, 0.0), 0.0
    tgt = (seg[0] / l, seg[1] / l)
    pos = vadd(vmul(iS, 1 - at), vmul(iE, at))
    return pos, tgt, l


def tangent_on_cub_at(at, iS, cub: CubicTo, before):
    E, Sd, Ed = cub.p, cub.start, cub.end
    A = vadd(vadd(Sd, Ed), vadd(vmul(E, -2), vmul(iS, 2)))
    B = vmul(vsub(Ed, Sd), 0.5)
    C = vmul(vsub(vsub(vmul(E, 6), vmul(iS, 6)), vadd(Sd, Ed)), 0.25)
    D = vmul(vadd(vadd(vmul(iS, 4), vmul(E, 4)), vsub(Sd, Ed)), 0.125)
    atb = at - 0.5
    pos = vadd(
        vadd(vmul(A, atb ** 3), vmul(B, atb ** 2)),
        vadd(vmul(C, atb), D),
    )
    der = vadd(vadd(vmul(A, 3 * atb * atb), vmul(B, 2 * atb)), C)
    dder = vadd(vmul(A, 6 * atb), vmul(B, 2))
    ddder = vmul(A, 6)

    l = vlen(der)
    if l <= 1e-4:
        l2 = vlen(dder)
        if l2 <= 1e-4:
            l3 = vlen(ddder)
            if l3 <= 1e-4:
                return pos, (0.0, 0.0), 0.0, 0.0
            tgt = vmul(ddder, 1.0 / l3)
            if before:
                tgt = vmul(tgt, -1)
            return pos, tgt, 0.0, 1e8
        rad = -l2 * vdot(dder, dder) / (vcross(dder, ddder) or 1e-30)
        tgt = vmul(dder, 1.0 / l2)
        if before:
            tgt = vmul(tgt, -1)
        return pos, tgt, 0.0, rad
    rad = -l * vdot(der, der) / (vcross(der, dder) or 1e-30)
    tgt = vmul(der, 1.0 / l)
    return pos, tgt, l, rad


def is_nul_curve(cmd, curX):
    if isinstance(cmd, LineTo):
        return vlinf(vsub(cmd.p, curX)) < 1e-5
    if isinstance(cmd, CubicTo):
        A = vadd(vadd(cmd.start, cmd.end), vmul(vsub(curX, cmd.p), 2))
        B = vadd(vmul(vsub(cmd.p, curX), 3), vmul(vadd(vmul(cmd.start, 2), cmd.end), -1))
        C = cmd.start
        return vlinf(A) < 1e-4 and vlinf(B) < 1e-4 and vlinf(C) < 1e-4
    return True


# ---------------------------------------------------------------------------
# Cubic offset  (RecStdCubicTo / StdCubicTo)
#
# Livarot scales the offset-cubic handles by 1+w/R (curvature-corrected
# Hermite).  That is *not* the true parallel curve — it sags a fraction of
# a unit, which is the halo we used to fight.  Inkscape 1.4 emits these
# cubics unchanged through ConvertToForme, so matching them (halo and all)
# is what makes filled-region xor vanish.
#
# Cross (hence signed radius) flips under our Y-up vs Inkscape's Y-down,
# so the handle scale is 1 - w/R here rather than Livarot's 1 + w/R.
# ---------------------------------------------------------------------------

def rec_std_cubic_to(dest, p0, cub, tol, width, lev, t_st, t_en, piece):
    st_pos, st_tgt, st_tle, st_rad = tangent_on_cub_at(0.0, p0, cub, False)
    mi_pos, mi_tgt, mi_tle, mi_rad = tangent_on_cub_at(0.5, p0, cub, False)
    en_pos, en_tgt, en_tle, en_rad = tangent_on_cub_at(1.0, p0, cub, True)
    st_nor, mi_nor, en_nor = cw(st_tgt), cw(mi_tgt), cw(en_tgt)

    def gue(rad, tle):
        g = 1.0
        if abs(rad) > 0.01:
            g -= width / rad
        return g * tle

    st_g = gue(st_rad, st_tle)
    en_g = gue(en_rad, en_tle)

    def emit():
        dest.cubic_to(
            vadd(en_pos, vmul(en_nor, width)),
            vmul(st_tgt, st_g),
            vmul(en_tgt, en_g),
        )
        dest.cmds[-1]._piece = piece
        dest.cmds[-1]._t_st = t_st
        dest.cmds[-1]._t_en = t_en

    if lev <= 0:
        emit()
        return

    req = vadd(mi_pos, vmul(mi_nor, width))
    trial = CubicTo(
        vadd(en_pos, vmul(en_nor, width)),
        vmul(st_tgt, st_g),
        vmul(en_tgt, en_g),
    )
    chk, _, _, _ = tangent_on_cub_at(
        0.5, vadd(st_pos, vmul(st_nor, width)), trial, False
    )
    err = vlen2(vsub(req, chk))
    if err <= tol:
        emit()
        return

    left = CubicTo(mi_pos, vmul(st_tgt, 0.5 * st_tle), vmul(mi_tgt, 0.5 * mi_tle))
    right = CubicTo(cub.p, vmul(mi_tgt, 0.5 * mi_tle), vmul(en_tgt, 0.5 * en_tle))
    mid_t = 0.5 * (t_st + t_en)
    rec_std_cubic_to(dest, p0, left, tol, width, lev - 1, t_st, mid_t, piece)
    rec_std_cubic_to(dest, mi_pos, right, tol, width, lev - 1, mid_t, t_en, piece)


# ---------------------------------------------------------------------------
# Joins  (OutlineJoin)
# ---------------------------------------------------------------------------

_join_prev_pos = (0.0, 0.0)
_join_turn_inside = True


def outline_join(dest, pos, st_nor, en_nor, width, join, miter, ntype):
    """join: 'miter' | 'round' | 'bevel'.  ntype is the incoming dest command kind."""
    global _join_prev_pos, _join_turn_inside
    _join_turn_inside = _join_turn_inside != veq(pos, _join_prev_pos, 1e-18)
    _join_prev_pos = pos

    ang_si = vcross(st_nor, en_nor)
    ang_co = vdot(st_nor, en_nor)

    if abs(ang_si) < 1e-7 and ang_co > 0:
        return

    # Livarot uses this test in Y-down.  We offset in Y-up with the same
    # cw() normal, so the sign of the normal cross is flipped: a positive
    # cross is an *outside* corner here (e.g. the tip of '>').
    inside = (ang_si < 0 and width >= 0) or (ang_si > 0 and width < 0)
    if inside or (ang_si == 0 and _join_turn_inside):
        if dest.cmds and isinstance(dest.cmds[-1], LineTo) and ntype == "line":
            # Intersection of the two offset lines — same point Inkscape
            # keeps after flatten, for both acute and obtuse inside corners.
            diff = vsub(st_nor, en_nor)
            biss = vunit(rot90(diff))
            c2 = vdot(biss, en_nor)
            if abs(c2) > 1e-12:
                dest.cmds[-1].p = vadd(pos, vmul(biss, width / c2))
            else:
                dest.line_to(vadd(pos, vmul(en_nor, width)))
        else:
            dest.line_to(vadd(pos, vmul(en_nor, width)))
        return

    if join == "round":
        r = 1.0001 * abs(width)
        dest.arc_to(
            vadd(pos, vmul(en_nor, width)),
            r, r, 0.0, False, width > 0,
        )
        return

    if join == "miter":
        diff = vsub(st_nor, en_nor)
        biss = vunit(rot90(diff))
        c2 = vdot(biss, en_nor)
        if abs(c2) < 1e-18:
            dest.line_to(vadd(pos, vmul(en_nor, width)))
            return
        l = width / c2
        if abs(l) > miter:
            dest.line_to(vadd(pos, vmul(en_nor, width)))
            return
        tip = vadd(pos, vmul(biss, l))
        if dest.cmds and isinstance(dest.cmds[-1], LineTo):
            dest.cmds[-1].p = tip
        else:
            dest.line_to(tip)
        if ntype == "close":
            # If the subpath starts with a line, move its starting point to the tip.
            m_i = None
            for i in range(len(dest.cmds) - 1, -1, -1):
                if isinstance(dest.cmds[i], MoveTo):
                    m_i = i
                    break
            if m_i is not None and m_i + 1 < len(dest.cmds) and isinstance(dest.cmds[m_i + 1], LineTo):
                dest.cmds[m_i].p = tip
            else:
                dest.line_to(vadd(pos, vmul(en_nor, width)))
        elif ntype != "line":
            dest.line_to(vadd(pos, vmul(en_nor, width)))
        return

    dest.line_to(vadd(pos, vmul(en_nor, width)))


# ---------------------------------------------------------------------------
# One-sided offset of a (possibly open) path  (SubContractOutline)
# ---------------------------------------------------------------------------

def sub_contract_outline(src_cmds, dest, tol, width, join, miter,
                         close_if_needed, skip_moveto):
    last_p = (0.0, 0.0)
    last_t = (0.0, 0.0)
    if not src_cmds:
        return last_p, last_t

    off = 0
    num = len(src_cmds)
    cur_p = 1
    if isinstance(src_cmds[0], MoveTo):
        cur_x = src_cmds[0].p
    else:
        cur_x = (0.0, 0.0)
        cur_p = 0

    do_first = True
    first_p = (0.0, 0.0)
    first_t = (0.0, 0.0)
    cur_t = (0.0, 0.0)

    while cur_p < num:
        cmd = src_cmds[off + cur_p]
        if isinstance(cmd, MoveTo):
            next_x = cmd.p
            if not do_first and close_if_needed:
                _close_outline(dest, cur_x, first_p, cur_t, first_t,
                               width, join, miter)
            first_p = next_x
            cur_x = next_x
            cur_p += 1
            continue

        if isinstance(cmd, Close):
            if not do_first:
                _close_outline(dest, cur_x, first_p, cur_t, first_t,
                               width, join, miter)
            do_first = True
            cur_p += 1
            continue

        if isinstance(cmd, LineTo):
            next_x = cmd.p
            if is_nul_curve(cmd, cur_x):
                if num == 2:
                    st_tgt = (1.0, 0.0) if dest.cmds else (-1.0, 0.0)
                    en_tgt = st_tgt
                    st_pos, en_pos = cur_x, next_x
                    st_nor, en_nor = cw(st_tgt), cw(en_tgt)
                else:
                    cur_p += 1
                    continue
            else:
                st_pos, st_tgt, _ = tangent_on_seg_at(0.0, cur_x, next_x)
                en_pos, en_tgt, _ = tangent_on_seg_at(1.0, cur_x, next_x)
                st_nor, en_nor = cw(st_tgt), cw(en_tgt)
            last_p, last_t = en_pos, en_tgt
            if do_first:
                do_first = False
                first_p, first_t = st_pos, st_nor
                if skip_moveto:
                    skip_moveto = False
                else:
                    dest.move_to(vadd(cur_x, vmul(st_nor, width)))
            else:
                outline_join(dest, cur_x, cur_t, st_nor, width, join, miter, "line")
            dest.line_to(vadd(next_x, vmul(en_nor, width)))
            dest.cmds[-1]._piece = off + cur_p
            dest.cmds[-1]._t_st = 0.0
            dest.cmds[-1]._t_en = 1.0
            cur_x = next_x
            cur_t = en_nor
            cur_p += 1
            continue

        if isinstance(cmd, CubicTo):
            next_x = cmd.p
            if is_nul_curve(cmd, cur_x):
                cur_p += 1
                continue
            st_pos, st_tgt, _, _ = tangent_on_cub_at(0.0, cur_x, cmd, False)
            en_pos, en_tgt, _, _ = tangent_on_cub_at(1.0, cur_x, cmd, True)
            st_nor, en_nor = cw(st_tgt), cw(en_tgt)
            last_p, last_t = en_pos, en_tgt
            if do_first:
                do_first = False
                first_p, first_t = st_pos, st_nor
                if skip_moveto:
                    skip_moveto = False
                else:
                    dest.move_to(vadd(cur_x, vmul(st_nor, width)))
            else:
                outline_join(dest, cur_x, cur_t, st_nor, width, join, miter, "cubic")
            rec_std_cubic_to(dest, cur_x, cmd, tol, width, 8, 0.0, 1.0, off + cur_p)
            cur_x = next_x
            cur_t = en_nor
            cur_p += 1
            continue

        cur_p += 1

    return last_p, last_t


def _close_outline(dest, cur_x, first_p, cur_t, first_t, width, join, miter):
    if vlinf(vsub(cur_x, first_p)) < 1e-4:
        outline_join(dest, first_p, cur_t, first_t, width, join, miter, "close")
        dest.close()
        return
    st_pos, st_tgt, _ = tangent_on_seg_at(0.0, cur_x, first_p)
    en_pos, en_tgt, _ = tangent_on_seg_at(1.0, cur_x, first_p)
    st_nor, en_nor = cw(st_tgt), cw(en_tgt)
    outline_join(dest, st_pos, cur_t, st_nor, width, join, miter, "close")
    dest.line_to(vadd(en_pos, vmul(en_nor, width)))
    outline_join(dest, en_pos, en_nor, first_t, width, join, miter, "close")
    dest.close()


# ---------------------------------------------------------------------------
# Reverse a subpath  (Path::Outline)
# ---------------------------------------------------------------------------

def reverse_subpath(cmds):
    """Build the reverse of cmds[0..].  Drops trailing Close; caller re-adds."""
    if not cmds:
        return Path()
    cur = len(cmds) - 1
    need_close = isinstance(cmds[cur], Close)
    while cur > 0 and isinstance(cmds[cur], Close):
        cur -= 1
    rev = Path()
    if cur <= 0:
        return rev
    cur_x = prev_point(cmds, cur)
    rev.move_to(cur_x)
    while cur > 0:
        cmd = cmds[cur]
        if isinstance(cmd, MoveTo):
            cur -= 1
        elif isinstance(cmd, LineTo):
            nxt = prev_point(cmds, cur - 1)
            rev.line_to(nxt)
            cur -= 1
        elif isinstance(cmd, CubicTo):
            nxt = prev_point(cmds, cur - 1)
            rev.cubic_to(nxt, vmul(cmd.end, -1), vmul(cmd.start, -1))
            cur -= 1
        else:
            cur -= 1
    if need_close:
        rev.close()
    return rev, need_close


def _emit_cap(dest, end_pos, end_butt, width, cap):
    end_nor = ccw(end_butt)
    if cap == "round":
        dest.arc_to(vadd(end_pos, vmul(end_butt, width)), width, width, 0.0, False, True)
        dest.arc_to(vadd(end_pos, vmul(end_nor, width)), width, width, 0.0, False, True)
    elif cap == "square":
        dest.line_to(vadd(end_pos, vadd(vmul(end_nor, -width), vmul(end_butt, width))))
        dest.line_to(vadd(end_pos, vadd(vmul(end_nor, width), vmul(end_butt, width))))
        dest.line_to(vadd(end_pos, vmul(end_nor, width)))
    elif cap == "pointy":
        dest.line_to(vadd(end_pos, vmul(end_butt, width)))
        dest.line_to(vadd(end_pos, vmul(end_nor, width)))
    else:
        dest.line_to(vadd(end_pos, vmul(end_nor, width)))


def outline_path(src: Path, width, join, cap, miter):
    """Two-sided outline of every subpath.  Returns a Path of closed contours."""
    dest = Path()
    cmds = src.cmds
    if len(cmds) <= 1:
        return dest
    tol = 0.0025 * width * width
    cur = 0
    n = len(cmds)
    while cur < n:
        last_m = cur
        cur += 1
        while cur < n and not isinstance(cmds[cur], MoveTo):
            cur += 1
        if cur - last_m <= 1:
            continue
        sub = cmds[last_m:cur]
        rev, need_close = reverse_subpath(sub)
        if not rev.cmds:
            continue
        # Open loops that return to the start (dots) are closed in SVG
        # only if they have Z.  Ours start with "move", so treat start≈end
        # as closed: inner+outer rings, no butt-cap slit.  Matches
        # Inkscape flatten of a circular pen on a small cycle.
        if not need_close:
            p_s = prev_point(sub, 0)
            p_e = prev_point(sub, len(sub) - 1)
            if veq(p_s, p_e, 1e-4):
                need_close = True
                rev.close()
        if need_close:
            sub_contract_outline(rev.cmds, dest, tol, width, join, miter, True, False)
            sub_contract_outline(sub, dest, tol, width, join, miter, True, False)
        else:
            end_pos, end_butt = sub_contract_outline(
                rev.cmds, dest, tol, width, join, miter, False, False
            )
            _emit_cap(dest, end_pos, end_butt, width, cap)
            end_pos, end_butt = sub_contract_outline(
                sub, dest, tol, width, join, miter, False, True
            )
            _emit_cap(dest, end_pos, end_butt, width, cap)
            dest.close()
    return dest


# ---------------------------------------------------------------------------
# Polyline approximation  (ConvertWithBackData, threshold 1.0)
# ---------------------------------------------------------------------------

@dataclass
class PolyPt:
    p: tuple
    piece: int
    t: float
    moveto: bool = False


def rec_cubic_to_poly(iS, isD, iE, ieD, thresh, lev, st, et, piece, pts):
    if lev <= 0:
        return
    se = vsub(iE, iS)
    y1 = abs(vcross(isD, se))
    y2 = abs(vcross(ieD, se))
    if vlen2(se) < 1e-4:
        if vlen2(isD) < thresh and vlen2(ieD) < thresh:
            return
    else:
        bound = vlen(se) * thresh
        if y1 < bound and y2 < bound:
            return
    m = vadd(vmul(vadd(iS, iE), 0.5), vmul(vsub(isD, ieD), 0.125))
    md = vsub(vmul(vsub(iE, iS), 0.75), vmul(vadd(isD, ieD), 0.125))
    mt = 0.5 * (st + et)
    rec_cubic_to_poly(iS, vmul(isD, 0.5), m, md, thresh, lev - 1, st, mt, piece, pts)
    pts.append(PolyPt(m, piece, mt, False))
    rec_cubic_to_poly(m, md, iE, vmul(ieD, 0.5), thresh, lev - 1, mt, et, piece, pts)


def path_to_polylines(path: Path, thresh=1.0):
    """Return a list of closed polylines, each a list of PolyPt (no repeated last)."""
    pts: list[PolyPt] = []
    cmds = path.cmds
    if not cmds:
        return []
    cur_x = cmds[0].p if isinstance(cmds[0], MoveTo) else (0.0, 0.0)
    start = 0 if not isinstance(cmds[0], MoveTo) else 1
    last_m = 0
    pts.append(PolyPt(cur_x, 0, 0.0, True))
    for i in range(start, len(cmds)):
        cmd = cmds[i]
        if isinstance(cmd, MoveTo):
            last_m = len(pts)
            pts.append(PolyPt(cmd.p, i, 0.0, True))
            cur_x = cmd.p
        elif isinstance(cmd, Close):
            pts.append(PolyPt(pts[last_m].p, i, 1.0, False))
            cur_x = pts[last_m].p
        elif isinstance(cmd, LineTo):
            if not veq(cmd.p, cur_x, 1e-8):
                pts.append(PolyPt(cmd.p, i, 1.0, False))
            cur_x = cmd.p
        elif isinstance(cmd, CubicTo):
            rec_cubic_to_poly(cur_x, cmd.start, cmd.p, cmd.end, thresh, 8, 0.0, 1.0, i, pts)
            if not veq(cmd.p, cur_x, 1e-8):
                pts.append(PolyPt(cmd.p, i, 1.0, False))
            cur_x = cmd.p
    # split into closed loops
    loops = []
    cur = []
    for p in pts:
        if p.moveto:
            if len(cur) >= 3:
                if not veq(cur[0].p, cur[-1].p):
                    cur.append(PolyPt(cur[0].p, cur[-1].piece, 1.0, False))
                loops.append(cur)
            cur = [p]
        else:
            cur.append(p)
    if len(cur) >= 3:
        if not veq(cur[0].p, cur[-1].p):
            cur.append(PolyPt(cur[0].p, cur[-1].piece, 1.0, False))
        loops.append(cur)
    # drop the repeated closing vertex for the planar graph
    out = []
    for loop in loops:
        if veq(loop[0].p, loop[-1].p) and len(loop) >= 2:
            loop = loop[:-1]
        if len(loop) >= 3:
            out.append(loop)
    return out


# ---------------------------------------------------------------------------
# Planar flatten with positive winding
# ---------------------------------------------------------------------------

def _seg_intersect(a, b, c, d, eps=1e-12):
    """Intersections of segment ab with cd, as list of (t_ab, t_cd, point)."""
    r = vsub(b, a)
    s = vsub(d, c)
    den = vcross(r, s)
    q = vsub(c, a)
    if abs(den) < 1e-16:
        # Parallel.  Handle collinear overlap.
        if abs(vcross(q, r)) > 1e-10 * (vlen(r) + 1e-12):
            return []
        rr = vlen2(r)
        if rr < 1e-20:
            return []
        t0 = vdot(vsub(c, a), r) / rr
        t1 = vdot(vsub(d, a), r) / rr
        hits = []
        for t, src in ((t0, c), (t1, d)):
            if -eps <= t <= 1 + eps:
                u = vdot(vsub(src, c), s) / (vlen2(s) or 1.0)
                hits.append((max(0.0, min(1.0, t)), max(0.0, min(1.0, u)), src))
        # also project a,b onto cd
        ss = vlen2(s)
        if ss > 1e-20:
            for t_ab, p in ((0.0, a), (1.0, b)):
                u = vdot(vsub(p, c), s) / ss
                if -eps <= u <= 1 + eps:
                    hits.append((t_ab, max(0.0, min(1.0, u)), p))
        return hits
    t = vcross(q, s) / den
    u = vcross(q, r) / den
    if -eps <= t <= 1 + eps and -eps <= u <= 1 + eps:
        p = vadd(a, vmul(r, t))
        return [(max(0.0, min(1.0, t)), max(0.0, min(1.0, u)), p)]
    return []


class _VDB:
    def __init__(self, q=1e-4):
        self.q = q
        self.pts = []
        self._m = {}

    def _key(self, p):
        return (round(p[0] / self.q), round(p[1] / self.q))

    def add(self, p):
        k = self._key(p)
        if k in self._m:
            return self._m[k]
        # neighbour snap (handles 0.4999 / 0.5001 rounding)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                k2 = (k[0] + dx, k[1] + dy)
                if k2 in self._m:
                    j = self._m[k2]
                    if vdist(self.pts[j], p) < 2 * self.q:
                        self._m[k] = j
                        return j
        i = len(self.pts)
        self.pts.append(p)
        self._m[k] = i
        return i


@dataclass
class _E:
    u: int
    v: int
    piece: int
    t0: float
    t1: float


def _cleanup_loop(loop, eps):
    """Collapse collapsed-offset scribbles and spikes in a closed polyline."""
    if len(loop) < 3:
        return []
    pts = list(loop)
    # Drop consecutive points that sit on top of each other.
    cleaned = [pts[0]]
    for p in pts[1:]:
        if vdist(p.p, cleaned[-1].p) >= eps:
            cleaned.append(p)
    if len(cleaned) >= 2 and vdist(cleaned[0].p, cleaned[-1].p) < eps:
        cleaned.pop()
    # Repeatedly drop spikes A-B-A (the two radii of a collapsed inner offset).
    changed = True
    while changed and len(cleaned) >= 3:
        changed = False
        nxt = []
        m = len(cleaned)
        i = 0
        while i < m:
            prv = cleaned[i - 1]
            cur = cleaned[i]
            nxtp = cleaned[(i + 1) % m]
            if vdist(prv.p, nxtp.p) < eps and vdist(prv.p, cur.p) >= eps:
                # spike: drop `cur`; the next point coincides with prev
                i += 1
                changed = True
                continue
            nxt.append(cur)
            i += 1
        cleaned = nxt
    return cleaned if len(cleaned) >= 3 else []


def flatten_positive(loops):
    """loops: list of closed PolyPt lists (no repeated last).  Return cycles
    of (point, piece, t0, t1) along the boundary of the positive-winding region.
    """
    if not loops:
        return []

    cleaned = []
    for loop in loops:
        c = _cleanup_loop(loop, eps=0.15)
        if c:
            cleaned.append(c)
    loops = cleaned
    if not loops:
        return []

    segs = []  # (p0, p1, piece, t0, t1, loop_id, idx)
    for li, loop in enumerate(loops):
        m = len(loop)
        for i in range(m):
            a, b = loop[i], loop[(i + 1) % m]
            if veq(a.p, b.p, 1e-10):
                continue
            # Path::Fill (!invert, back): piece comes from the edge *end*
            # point; if the start belongs to a different command, tSt = 0.
            if a.piece == b.piece:
                piece, t0, t1 = b.piece, a.t, b.t
            else:
                piece, t0, t1 = b.piece, 0.0, b.t
            segs.append((a.p, b.p, piece, t0, t1, li, i))

    n = len(segs)
    cuts = [[] for _ in range(n)]
    for i in range(n):
        a0, a1, *_, li, ia = segs[i]
        for j in range(i + 1, n):
            b0, b1, *__, lj, ib = segs[j]
            # Adjacent segments of the same loop already share a vertex.
            if li == lj:
                m = len(loops[li])
                if (ia + 1) % m == ib or (ib + 1) % m == ia:
                    continue
            for t, u, p in _seg_intersect(a0, a1, b0, b1):
                if 1e-8 < t < 1 - 1e-8:
                    cuts[i].append((t, p))
                if 1e-8 < u < 1 - 1e-8:
                    cuts[j].append((u, p))

    vdb = _VDB(q=1e-3)
    edges: list[_E] = []
    for i, (p0, p1, piece, t0, t1, _li, _ia) in enumerate(segs):
        ts = [(0.0, p0), (1.0, p1)]
        for t, p in cuts[i]:
            ts.append((t, p))
        ts.sort(key=lambda x: x[0])
        # merge nearly-equal t
        merged = [ts[0]]
        for t, p in ts[1:]:
            if t - merged[-1][0] < 1e-9 or veq(p, merged[-1][1], 1e-6):
                continue
            merged.append((t, p))
        for k in range(len(merged) - 1):
            ta, pa = merged[k]
            tb, pb = merged[k + 1]
            ua, va = vdb.add(pa), vdb.add(pb)
            if ua == va:
                continue
            tt0 = t0 + (t1 - t0) * ta
            tt1 = t0 + (t1 - t0) * tb
            edges.append(_E(ua, va, piece, tt0, tt1))

    # Cancel opposite overlapping edges (a radial slit, a collapsed cap, …).
    by_pair = {}
    for i, e in enumerate(edges):
        by_pair.setdefault((min(e.u, e.v), max(e.u, e.v)), []).append(i)
    drop = set()
    for pair, idxs in by_pair.items():
        fwd = [i for i in idxs if edges[i].u < edges[i].v]
        rev = [i for i in idxs if edges[i].u > edges[i].v]
        ncan = min(len(fwd), len(rev))
        drop.update(fwd[:ncan])
        drop.update(rev[:ncan])
    edges = [e for i, e in enumerate(edges) if i not in drop]

    # adjacency: vertex -> list of (other, edge_index, forward)
    adj = [[] for _ in range(len(vdb.pts))]
    for i, e in enumerate(edges):
        adj[e.u].append((e.v, i, True))
        adj[e.v].append((e.u, i, False))

    def angle(u, v):
        p = vdb.pts[u]
        q = vdb.pts[v]
        return math.atan2(q[1] - p[1], q[0] - p[0])

    # Walk every directed edge exactly once.
    used = set()  # (u, v, edge_index)
    faces = []  # list of (cycle_of_directed, signed_area)

    def next_out(v, u):
        """Outgoing from v immediately CCW after the incoming arrival from u."""
        outs = [(angle(v, w), w, ej) for w, ej, _ in adj[v]]
        if not outs:
            return None
        outs.sort(key=lambda x: x[0])
        idx = None
        for i, (_, w, _) in enumerate(outs):
            if w == u:
                idx = i
                break
        if idx is None:
            inc = angle(v, u)
            best_d = 3 * math.pi
            for i, (ang, _, _) in enumerate(outs):
                d = (ang - inc) % (2 * math.pi)
                if d < best_d:
                    best_d = d
                    idx = i
        ang, w, ej = outs[(idx + 1) % len(outs)]
        return (v, w, ej)

    def walk(u0, v0, ei0):
        cycle = []
        u, v, ei = u0, v0, ei0
        for _ in range(len(edges) * 4 + 4):
            if (u, v, ei) in used:
                break
            used.add((u, v, ei))
            cycle.append((u, v, ei))
            nxt = next_out(v, u)
            if nxt is None:
                break
            u, v, ei = nxt
            if (u, v, ei) == (u0, v0, ei0):
                break
        return cycle

    for i, e in enumerate(edges):
        for u, v in ((e.u, e.v), (e.v, e.u)):
            if (u, v, i) in used:
                continue
            if not adj[u] or not adj[v]:
                continue
            cyc = walk(u, v, i)
            if len(cyc) < 3:
                continue
            area = 0.0
            for a, b, _ in cyc:
                pa, pb = vdb.pts[a], vdb.pts[b]
                area += pa[0] * pb[1] - pb[0] * pa[1]
            faces.append((cyc, 0.5 * area))

    # Winding of each face via BFS from the unbounded face (w = 0),
    # matching Livarot ConvertToShape: crossing a forward original edge
    # from left to right leaves the filled side and decreases winding.
    # Disjoint strokes (colon, quotes, accents) are separate components;
    # each has its own unbounded face.
    face_w = [0] * len(faces)
    if faces:
        left_face = {}
        for fi, (cyc, _) in enumerate(faces):
            for u, v, ei in cyc:
                left_face[(u, v, ei)] = fi
        adj_f = [[] for _ in faces]
        for i, e in enumerate(edges):
            lf = left_face.get((e.u, e.v, i))
            rf = left_face.get((e.v, e.u, i))
            if lf is None or rf is None or lf == rf:
                continue
            adj_f[lf].append((rf, -1))
            adj_f[rf].append((lf, +1))
        remaining = set(range(len(faces)))
        while remaining:
            unbound = min(remaining, key=lambda i: faces[i][1])
            seen = {unbound}
            queue = [unbound]
            face_w[unbound] = 0
            while queue:
                f = queue.pop()
                for g, dw in adj_f[f]:
                    if g in seen or g not in remaining:
                        continue
                    face_w[g] = face_w[f] + dw
                    seen.add(g)
                    queue.append(g)
            remaining -= seen

    # directed-edge -> left-face winding
    left_w = {}
    for (cyc, _), w in zip(faces, face_w):
        for u, v, ei in cyc:
            left_w[(u, v, ei)] = w

    keepers = []
    for i, e in enumerate(edges):
        for u, v in ((e.u, e.v), (e.v, e.u)):
            lw = left_w.get((u, v, i), 0)
            rw = left_w.get((v, u, i), 0)
            # fill_positive: keep the boundary of {winding > 0}.
            if lw > 0 and rw <= 0:
                keepers.append((u, v, i))

    kadj = {}
    for u, v, ei in keepers:
        kadj.setdefault(u, []).append((v, ei))

    used_k = set()
    cycles = []
    for u0, v0, ei0 in keepers:
        if (u0, v0, ei0) in used_k:
            continue
        cyc = []
        u, v, ei = u0, v0, ei0
        for _ in range(len(keepers) + 2):
            if (u, v, ei) in used_k:
                break
            used_k.add((u, v, ei))
            e = edges[ei]
            if u == e.u:
                piece, t0, t1 = e.piece, e.t0, e.t1
            else:
                piece, t0, t1 = e.piece, e.t1, e.t0
            cyc.append((vdb.pts[u], vdb.pts[v], piece, t0, t1))
            inc = angle(v, u)
            best = None
            best_d = 3 * math.pi
            for w, ej in kadj.get(v, []):
                d = (angle(v, w) - inc) % (2 * math.pi)
                if d < 1e-12:
                    d = 2 * math.pi
                if d < best_d:
                    best_d = d
                    best = (v, w, ej)
            if best is None:
                break
            u, v, ei = best
            if (u, v, ei) == (u0, v0, ei0):
                break
        if len(cyc) >= 3:
            area = 0.0
            for a, b, *_ in cyc:
                area += a[0] * b[1] - b[0] * a[1]
            if abs(area) > 0.5:
                cycles.append(cyc)
    return cycles


# ---------------------------------------------------------------------------
# Recover glif contours from flattened cycles + original offset pieces
# ---------------------------------------------------------------------------

def cubic_tangent(t, iS, isD, iE, ieD):
    """Path::CubicTangent: first derivative of a Livarot cubic at t."""
    ax = vadd(vsub(ieD, vmul(iE, 2.0)), vadd(vmul(iS, 2.0), isD))
    bx = vsub(vsub(vsub(vmul(iE, 3.0), ieD), vmul(isD, 2.0)), vmul(iS, 3.0))
    cx = isD
    return vadd(vadd(vmul(ax, 3.0 * t * t), vmul(bx, 2.0 * t)), cx)


def _reforme_cubic(p0, cub: CubicTo, ts, te, p_start, p_end):
    """Shape::ReFormeCubicTo: sub-range of an offset cubic, endpoints on
    the flattened graph.  Handles are P'(t)*(te-ts)."""
    sdx = cubic_tangent(ts, p0, cub.start, cub.p, cub.end)
    edx = cubic_tangent(te, p0, cub.start, cub.p, cub.end)
    dt = te - ts
    sdx, edx = vmul(sdx, dt), vmul(edx, dt)
    c1 = vadd(p_start, vmul(sdx, 1.0 / 3.0))
    c2 = vsub(p_end, vmul(edx, 1.0 / 3.0))
    return c1, c2


def _piece_map(path: Path):
    """piece index -> ('L', p0, p1) or ('C', p0, cub)."""
    m = {}
    cur = (0.0, 0.0)
    for i, cmd in enumerate(path.cmds):
        if isinstance(cmd, MoveTo):
            cur = cmd.p
        elif isinstance(cmd, LineTo):
            m[i] = ("L", cur, cmd.p)
            cur = cmd.p
        elif isinstance(cmd, CubicTo):
            m[i] = ("C", cur, cmd)
            cur = cmd.p
        elif isinstance(cmd, Close):
            # close is a line back to the last MoveTo
            mt = cur
            for c in reversed(path.cmds[:i]):
                if isinstance(c, MoveTo):
                    mt = c.p
                    break
            m[i] = ("L", cur, mt)
            cur = mt
    return m


def cycles_to_glif(cycles, pieces):
    contours = []
    for cyc in cycles:
        # group consecutive edges from the same piece with monotonic t
        groups = []
        cur = [cyc[0]]
        for e in cyc[1:]:
            prev = cur[-1]
            same = e[2] == prev[2]
            if same:
                # t direction consistent with the group
                dt_g = cur[-1][4] - cur[0][3]
                dt_e = e[4] - e[3]
                if dt_g * dt_e < -1e-9 and abs(dt_g) > 1e-9:
                    same = False
            if same:
                cur.append(e)
            else:
                groups.append(cur)
                cur = [e]
        groups.append(cur)

        segs = []  # ('L', p) or ('C', p1, p2, p)
        for g in groups:
            p_start, p_end = g[0][0], g[-1][1]
            piece = g[0][2]
            t0, t1 = g[0][3], g[-1][4]
            info = pieces.get(piece)
            if info is None or info[0] == "L" or abs(t1 - t0) < 1e-6:
                segs.append(("L", p_end))
                continue
            _, p0, cub = info
            c1, c2 = _reforme_cubic(p0, cub, t0, t1, p_start, p_end)
            # if the recovered cubic is essentially a line, emit a line
            chord = vsub(p_end, p_start)
            cl = vlen(chord)
            if cl < 1e-8:
                segs.append(("L", p_end))
                continue
            nrm = vunit(ccw(chord))
            d1 = abs(vdot(vsub(c1, p_start), nrm))
            d2 = abs(vdot(vsub(c2, p_start), nrm))
            if d1 < 0.15 and d2 < 0.15:
                segs.append(("L", p_end))
            else:
                segs.append(("C", c1, c2, p_end))

        if not segs:
            continue
        # first on-curve is the start of the first edge
        start = cyc[0][0]
        last_kind = segs[-1][0]
        first_type = "curve" if last_kind == "C" else "line"
        pts = [Point(x=start[0], y=start[1], type=first_type, smooth=False)]
        for s in segs[:-1]:
            if s[0] == "L":
                if not veq((pts[-1].x, pts[-1].y), s[1], 1e-8):
                    pts.append(Point(x=s[1][0], y=s[1][1], type="line", smooth=False))
            else:
                pts.append(Point(x=s[1][0], y=s[1][1], type="offcurve", smooth=False))
                pts.append(Point(x=s[2][0], y=s[2][1], type="offcurve", smooth=False))
                pts.append(Point(x=s[3][0], y=s[3][1], type="curve", smooth=False))
        if last_kind == "C":
            s = segs[-1]
            pts.append(Point(x=s[1][0], y=s[1][1], type="offcurve", smooth=False))
            pts.append(Point(x=s[2][0], y=s[2][1], type="offcurve", smooth=False))
        # drop a trailing on-curve that coincides with start (line close)
        if len(pts) >= 2 and pts[-1].type in ("line", "curve"):
            if veq((pts[-1].x, pts[-1].y), start, 1e-6):
                pts.pop()
        if len(pts) >= 2:
            try:
                verify_contour(pts)
                contours.append(pts)
            except Exception:
                # last-resort: polyline of on-curve points
                raw = [Point(x=cyc[0][0][0], y=cyc[0][0][1], type="line", smooth=False)]
                for e in cyc:
                    raw.append(Point(x=e[1][0], y=e[1][1], type="line", smooth=False))
                if veq((raw[-1].x, raw[-1].y), (raw[0].x, raw[0].y), 1e-6):
                    raw.pop()
                if len(raw) >= 3:
                    raw[0].type = "line"
                    contours.append(raw)
    return contours


def _poly_loop_to_cycle(loop):
    """Polyline loop -> ConvertToForme edge list (Fill back-data convention)."""
    cyc = []
    m = len(loop)
    for i in range(m):
        a, b = loop[i], loop[(i + 1) % m]
        if veq(a.p, b.p, 1e-10):
            continue
        if a.piece == b.piece:
            piece, t0, t1 = b.piece, a.t, b.t
        else:
            piece, t0, t1 = b.piece, 0.0, b.t
        cyc.append((a.p, b.p, piece, t0, t1))
    return cyc


def _abs_area_sum(contours):
    tot = 0.0
    for c in contours:
        on = [(p.x, p.y) for p in c if p.type != "offcurve"]
        a = 0.0
        n = len(on)
        for i in range(n):
            x1, y1 = on[i]
            x2, y2 = on[(i + 1) % n]
            a += x1 * y2 - x2 * y1
        tot += abs(0.5 * a)
    return tot


def convert_to_forme(outlined: Path, thresh=1.0):
    """ConvertWithBackData + ConvertToShape(fill_positive) + ConvertToForme.

    If the planar union inflates the filled area (a bad winding walk, as
    on a self-overlapping spiral like '@'), keep the flattened outline
    and only run ReFormeCubicTo.  Inkscape's ConvertToShape never grows a
    simple sausage by a large factor; it only unions small self-overlaps.
    """
    loops = path_to_polylines(outlined, thresh)
    if not loops:
        return []
    pieces = _piece_map(outlined)
    raw = cycles_to_glif(
        [c for c in (_poly_loop_to_cycle(lp) for lp in loops) if len(c) >= 3],
        pieces,
    )
    cycles = flatten_positive(loops)
    if not cycles:
        return raw
    merged = cycles_to_glif(cycles, pieces)
    if not merged:
        return raw
    raw_a = _abs_area_sum(raw)
    mer_a = _abs_area_sum(merged)
    # ConvertToShape only unions small self-overlaps.  Reject a walk that
    # invents a huge outer+hole or drops a whole component.
    if raw_a > 1.0 and (mer_a > 1.30 * raw_a or mer_a < 0.90 * raw_a):
        return raw
    return merged


# ---------------------------------------------------------------------------
# glif contours <-> Path
# ---------------------------------------------------------------------------

def glif_to_path(contours) -> Path:
    path = Path()
    for contour in contours:
        if not contour:
            continue
        p0 = contour[0]
        path.move_to((float(p0.x), float(p0.y)))
        prev = (float(p0.x), float(p0.y))
        i = 1
        n = len(contour)
        while i < n:
            p = contour[i]
            if p.type == "line":
                path.line_to((float(p.x), float(p.y)))
                prev = (float(p.x), float(p.y))
                i += 1
            elif p.type == "offcurve":
                if i + 2 >= n:
                    break
                c1, c2, c3 = contour[i], contour[i + 1], contour[i + 2]
                p1 = (float(c1.x), float(c1.y))
                p2 = (float(c2.x), float(c2.y))
                p3 = (float(c3.x), float(c3.y))
                path.cubic_to(p3, vmul(vsub(p1, prev), 3), vmul(vsub(p3, p2), 3))
                prev = p3
                i += 3
            elif p.type in ("curve", "move"):
                path.line_to((float(p.x), float(p.y)))
                prev = (float(p.x), float(p.y))
                i += 1
            else:
                i += 1
        if p0.type != "move":
            path.close()
    return path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _oncurves(contour):
    return [p for p in contour if p.type != "offcurve"]


def _is_closed_loop(contour, eps):
    """True if the centerline returns to its start (a dot, a ring)."""
    on = _oncurves(contour)
    if len(on) < 3:
        return False
    return veq((on[0].x, on[0].y), (on[-1].x, on[-1].y), eps)


def _copy_contour(contour):
    return [Point(x=p.x, y=p.y, type=p.type, smooth=p.smooth) for p in contour]


def merge_connected_contours(contours, eps=1e-3):
    """Join open centerlines that meet end-to-start into one path.

    Metafont draws the letter body and then `dotah` as a second `draw`.
    Those two strokes share an endpoint, so outlining them separately
    puts two butt caps on top of each other.  Stitching first makes a
    single tube.  Closed loops (dots) are left alone.
    """
    remaining = [_copy_contour(c) for c in contours if c]
    out = []
    while remaining:
        cur = remaining.pop(0)
        if _is_closed_loop(cur, eps):
            out.append(cur)
            continue
        progressed = True
        while progressed:
            progressed = False
            on = _oncurves(cur)
            if not on:
                break
            start = (on[0].x, on[0].y)
            end = (on[-1].x, on[-1].y)
            for i, other in enumerate(remaining):
                if _is_closed_loop(other, eps):
                    continue
                oon = _oncurves(other)
                if not oon:
                    continue
                o0 = (oon[0].x, oon[0].y)
                o1 = (oon[-1].x, oon[-1].y)
                if veq(end, o0, eps):
                    cur = cur + other[1:]
                    remaining.pop(i)
                    progressed = True
                    break
                if veq(start, o1, eps):
                    cur = other + cur[1:]
                    remaining.pop(i)
                    progressed = True
                    break
        out.append(cur)
    return out


def _linearize_straight_cubics(path: Path, thresh=1.0):
    """Inkscape ConvertWithBackData(1.0): a cubic whose handles stay
    within `thresh` of the chord is stored as a line."""
    out = Path()
    cur = None
    for cmd in path.cmds:
        if isinstance(cmd, MoveTo):
            cur = cmd.p
            out.move_to(cmd.p)
        elif isinstance(cmd, Close):
            out.close()
        elif isinstance(cmd, LineTo):
            out.line_to(cmd.p)
            cur = cmd.p
        elif isinstance(cmd, CubicTo):
            if cur is None:
                continue
            se = vsub(cmd.p, cur)
            sl2 = vlen2(se)
            if sl2 < 1e-8:
                straight = vlen2(cmd.start) < thresh and vlen2(cmd.end) < thresh
            else:
                sl = sl2 ** 0.5
                y1 = abs(vcross(cmd.start, se)) / sl
                y2 = abs(vcross(cmd.end, se)) / sl
                straight = y1 < thresh and y2 < thresh
            if straight:
                out.line_to(cmd.p)
            else:
                out.cubic_to(cmd.p, cmd.start, cmd.end)
            cur = cmd.p
    return out


def _drop_collapsed(path: Path, eps):
    """Remove offset cubics/lines that have collapsed to a point (inner
    offset of a loop whose radius is <= the pen radius)."""
    out = Path()
    cur = None
    for cmd in path.cmds:
        if isinstance(cmd, MoveTo):
            cur = cmd.p
            out.move_to(cmd.p)
        elif isinstance(cmd, Close):
            out.close()
        elif isinstance(cmd, LineTo):
            if cur is None or vdist(cur, cmd.p) >= eps:
                out.line_to(cmd.p)
                cur = cmd.p
        elif isinstance(cmd, CubicTo):
            if cur is None:
                continue
            mid, *_ = tangent_on_cub_at(0.5, cur, cmd, False)
            if vdist(cur, cmd.p) < eps and vdist(cur, mid) < eps:
                continue
            out.cubic_to(cmd.p, cmd.start, cmd.end)
            cur = cmd.p
    return out


def outlined_path_to_glif(path: Path):
    """Turn a Livarot outline Path (Move/Line/Cubic/Close) into glif contours."""
    contours = []
    segs = []  # ('M',p) then ('L',p) / ('C',p1,p2,p)
    start = None
    prev = None

    def flush():
        nonlocal segs, start, prev
        if not segs or start is None:
            segs = []
            start = prev = None
            return
        # Drop a trailing line that just returns to start (Close already
        # implies that).
        if segs and segs[-1][0] == "L" and veq(segs[-1][1], start, 1e-6):
            segs.pop()
        if not segs:
            start = prev = None
            return
        last = segs[-1]
        last_end = last[1] if last[0] == "L" else last[3]
        closes_with_curve = last[0] == "C" and veq(last_end, start, 1e-4)
        first_type = "curve" if closes_with_curve else "line"
        pts = [Point(x=start[0], y=start[1], type=first_type, smooth=False)]
        body = segs[:-1] if closes_with_curve else segs
        for s in body:
            if s[0] == "L":
                if not veq((pts[-1].x, pts[-1].y), s[1], 1e-8):
                    pts.append(Point(x=s[1][0], y=s[1][1], type="line", smooth=False))
            else:
                pts.append(Point(x=s[1][0], y=s[1][1], type="offcurve", smooth=False))
                pts.append(Point(x=s[2][0], y=s[2][1], type="offcurve", smooth=False))
                pts.append(Point(x=s[3][0], y=s[3][1], type="curve", smooth=False))
        if closes_with_curve:
            pts.append(Point(x=last[1][0], y=last[1][1], type="offcurve", smooth=False))
            pts.append(Point(x=last[2][0], y=last[2][1], type="offcurve", smooth=False))
        if len(pts) >= 2:
            verify_contour(pts)
            contours.append(pts)
        segs = []
        start = prev = None

    for cmd in path.cmds:
        if isinstance(cmd, MoveTo):
            flush()
            start = prev = cmd.p
        elif isinstance(cmd, LineTo):
            if prev is None:
                start = prev = cmd.p
                continue
            segs.append(("L", cmd.p))
            prev = cmd.p
        elif isinstance(cmd, CubicTo):
            if prev is None:
                continue
            p1 = vadd(prev, vmul(cmd.start, 1.0 / 3.0))
            p2 = vsub(cmd.p, vmul(cmd.end, 1.0 / 3.0))
            segs.append(("C", p1, p2, cmd.p))
            prev = cmd.p
        elif isinstance(cmd, Close):
            flush()
    flush()
    return contours


def stroke_to_path(contours, stroke_width, join="miter", cap="butt",
                   miter_limit=4.0):
    """Expand stroked centerline contours to filled outline contours.

    `contours` is a list of glif point lists (Y up).  `stroke_width` is the
    full SVG stroke-width (offset distance is half of that).

    Centerlines that meet end-to-start (letter body + connector) are
    stitched into one path before offsetting, so they do not produce
    overlapping tubes.
    """
    if stroke_width <= 0 or not contours:
        return []
    global _join_prev_pos, _join_turn_inside
    _join_prev_pos = (0.0, 0.0)
    _join_turn_inside = True
    contours = merge_connected_contours(contours)
    src = glif_to_path(contours)
    if len(src.cmds) <= 1:
        return []
    width = 0.5 * float(stroke_width)
    miter = miter_limit * width
    outlined = outline_path(src, width, join, cap, miter)
    if not outlined.cmds:
        return []
    # Inkscape: ConvertWithBackData(1.0) + ConvertToShape(fill_positive)
    # + ConvertToForme (ReFormeCubicTo).  Fall back to the raw outline if
    # the planar flatten finds no positive region.
    out = convert_to_forme(outlined)
    if not out:
        outlined = _linearize_straight_cubics(outlined, thresh=1.0)
        outlined = _drop_collapsed(outlined, eps=max(0.2, 0.02 * width))
        out = outlined_path_to_glif(outlined)
    # Collapsed inner offset of a small loop is a tiny inverted ring.
    # Inkscape's flatten discards it; keep only contours with real area.
    min_area = (abs(width) * 2) ** 2 * 0.5
    kept = []
    for c in out:
        on = [(p.x, p.y) for p in c if p.type != "offcurve"]
        a = 0.0
        n = len(on)
        for i in range(n):
            x1, y1 = on[i]
            x2, y2 = on[(i + 1) % n]
            a += x1 * y2 - x2 * y1
        if abs(a) * 0.5 >= min_area:
            kept.append(c)
    return kept if kept else out
