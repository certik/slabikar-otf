"""Sanity checks for the Livarot-equivalent stroke-to-path."""
from glif import Point
from stroke import stroke_to_path, vlen, vadd


def line_contour(a, b):
    return [
        Point(x=a[0], y=a[1], type="move", smooth=False),
        Point(x=b[0], y=b[1], type="line", smooth=False),
    ]


def signed_area(contour):
    pts = [(p.x, p.y) for p in contour if p.type != "offcurve"]
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return 0.5 * a


def bbox(contour):
    xs = [p.x for p in contour]
    ys = [p.y for p in contour]
    return min(xs), min(ys), max(xs), max(ys)


def test_horizontal_line():
    c = line_contour((0, 0), (100, 0))
    out = stroke_to_path([c], 10.0)
    assert len(out) == 1, out
    a = signed_area(out[0])
    assert a > 0, a
    xmin, ymin, xmax, ymax = bbox(out[0])
    assert abs(xmin - 0) < 0.2, xmin
    assert abs(xmax - 100) < 0.2, xmax
    assert abs(ymin - (-5)) < 0.2, ymin
    assert abs(ymax - 5) < 0.2, ymax
    assert abs(abs(a) - 1000) < 20, a
    print("ok horizontal line", a, (xmin, ymin, xmax, ymax), "n=", len(out[0]))


def test_vertical_line():
    c = line_contour((0, 0), (0, 80))
    out = stroke_to_path([c], 8.0)
    assert len(out) == 1
    a = signed_area(out[0])
    xmin, ymin, xmax, ymax = bbox(out[0])
    assert abs(abs(a) - 80 * 8) < 20, a
    assert abs(xmin - (-4)) < 0.2 and abs(xmax - 4) < 0.2
    print("ok vertical line", a, (xmin, ymin, xmax, ymax))


def test_two_segments_miter():
    c = [
        Point(x=0, y=0, type="move", smooth=False),
        Point(x=40, y=0, type="line", smooth=False),
        Point(x=40, y=40, type="line", smooth=False),
    ]
    out = stroke_to_path([c], 8.0, join="miter")
    assert len(out) >= 1
    a = sum(signed_area(k) for k in out)
    # roughly 40*8 + 40*8 + some miter, minus the corner overlap
    assert a > 400, a
    print("ok elbow", a, [bbox(k) for k in out])


def test_cubic():
    # a simple bow
    c = [
        Point(x=0, y=0, type="move", smooth=False),
        Point(x=10, y=40, type="offcurve", smooth=False),
        Point(x=50, y=40, type="offcurve", smooth=False),
        Point(x=60, y=0, type="curve", smooth=False),
    ]
    out = stroke_to_path([c], 8.0)
    assert len(out) >= 1
    a = sum(signed_area(k) for k in out)
    assert a > 200, a
    print("ok cubic", a, [len(k) for k in out])


def test_closed_diamond_dot():
    # like svg.py's `dot`: a small closed-looking loop (open, returns to start)
    e = 4.0
    c = [
        Point(x=e, y=0, type="move", smooth=False),
        Point(x=0, y=e, type="line", smooth=False),
        Point(x=-e, y=0, type="line", smooth=False),
        Point(x=0, y=-e, type="line", smooth=False),
        Point(x=e, y=0, type="line", smooth=False),
    ]
    out = stroke_to_path([c], 8.0)
    assert len(out) >= 1
    a = sum(signed_area(k) for k in out)
    # roughly a disk of radius ~8
    print("ok diamond-dot", a, [bbox(k) for k in out], [len(k) for k in out])
    assert a > 50, a


if __name__ == "__main__":
    test_horizontal_line()
    test_vertical_line()
    test_two_segments_miter()
    test_cubic()
    test_closed_diamond_dot()
    print("all ok")
