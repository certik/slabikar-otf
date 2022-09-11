from dataclasses import dataclass
from xml.etree.ElementTree import Element, tostring, fromstring, indent

# Abstract Semantic Representation of the Glif format:

@dataclass
class Point:
    x: int
    y: int
    type: str
    smooth: bool

@dataclass
class Anchor:
    x: int
    y: int
    name: str

@dataclass
class Glif:
    name: str
    unicode_hex: str
    w: int
    contours: list[list[Point]]
    anchors: list[Anchor]

# Verify

def require(cond, msg):
    if not cond:
        raise Exception(msg)

# TODO: verify "smooth" for each point as well. Give an error for
# smooth=yes that is not smooth; and a warning for not defined smooth parameter
# if it is smooth
def verify_contour(contour: list[Point]):
    debug_print = False
    for n, point in enumerate(contour):
        require(isinstance(point.x, (int,float)), "Point.x must be integer")
        require(isinstance(point.y, (int,float)), "Point.y must be integer")
        require(point.type in ["curve", "offcurve", "line", "move"],
                "Point.type is not correct")
        if n > 0:
            require(point.type != "move",
                    "Point.type cannot be move for n > 0")
    if len(contour) > 0:
        p = contour[0]
        # UFO 3 allows to start with any point (even offcurve), but we further
        # restrict it to always start with a line or curve, which simplifies
        # the writers.
        require(p.type in ["curve", "line", "move"],
                "The contour must start with a curve or line")
        if p.type == "move":
            require(contour[-1].type in ["curve", "line"],
                    "Open contour must end with curve or line")
        else:
            contour = contour + [p]
        # The previous point type:
        # 0 ... line node (line)
        # 1 ... 1st curve point (offcurve)
        # 2 ... 2nd curve point (offcurve)
        # 3 ... 3rd curve point (curve)
        if p.type in ["line", "move"]:
            last_point_type = 0
        else:
            assert p.type == "curve"
            last_point_type = 3
        if debug_print:
            print(p, "'first point'")
        for p in contour[1:]:
            if debug_print:
                print(p, last_point_type)
            if p.type == "line":
                require(last_point_type in [0,3],
                    "the last point before line must be line or curve")
                last_point_type = 0
            elif p.type == "curve":
                require(last_point_type == 2,
                    "the last point before curve must be second offcurve point")
                last_point_type = 3
            else:
                assert p.type == "offcurve"
                require(last_point_type != 2,
                    "three offcurve points in a row are not allowed")
                if last_point_type in [0, 3]:
                    # First offcurve point
                    last_point_type = 1
                else:
                    # Second offcurve point
                    assert last_point_type == 1
                    last_point_type = 2


def verify(glif: Glif):
    if glif.w is not None:
        require(isinstance(glif.w, (int,float)), "w must be integer")
    require(isinstance(glif.name, str), "name must be str")
    for contour in glif.contours:
        verify_contour(contour)

# Reader for Glif:

def num(x):
    try:
        return int(x)
    except ValueError:
        return float(x)

def parse_glif(glif: str) -> Glif:
    glif = fromstring(glif)
    name = glif.get("name")
    if glif.find("advance") is not None:
        w = int(glif.find("advance").get("width"))
    else:
        w = None
    if glif.find("unicode") is not None:
        unicode_hex = glif.find("unicode").get("hex")
    else:
        unicode_hex = None
    contours = []
    if glif.find("outline") is not None:
        for contour in glif.find("outline"):
            if contour.tag == "contour":
                c = []
                for p in contour:
                    x = num(p.get("x"))
                    y = num(p.get("y"))
                    type = p.get("type")
                    if type is None:
                        type = "offcurve"
                    smooth = p.get("smooth") == "yes"
                    c.append(Point(x, y, type, smooth))
                contours.append(c)
    anchors = []
    for a in glif:
        if a.tag == "anchor":
            x = int(a.get("x"))
            y = int(a.get("y"))
            anchor_name = a.get("name")
            anchors.append(Anchor(x, y, anchor_name))
    g = Glif(name, unicode_hex, w, contours, anchors)
    verify(g)
    return g

def parse_points(x, scale, height):
    points = []
    for p in x:
        if p.find(",") != -1:
            x, y = p.split(",")
            points.append([
                (float(x)*scale),
                ((height-float(y))*scale)
            ])
        else:
            break
    return points

def parse_svg(svg_str: str) -> Glif:
    #scale = 1/18 * 1000
    scale = 1.0
    svg = fromstring(svg_str)
    # FIXME:
    name = "a"
    width = float(svg.get("width"))
    height = float(svg.get("height"))
    w = round(width * scale)
    h = round(height * scale)
    unicode_hex = None

    contours = []
    path = svg[2]
    if path.get("id") != "path0":
        print("Path ID differs:", path.get("id"))
    p = path.get("d")
    x = p.split()

    i = 0
    contour = []
    current_x = 0
    current_y = h
    while True:
        if i >= len(x):
            break
        if x[i] == "m":
            points = parse_points(x[i+1:], scale, 0)
            p = points[0]
            current_x += p[0]
            current_y += p[1]
            contour.append(Point(
                x=current_x,
                y=current_y,
                type="move", smooth=False))
            for p in points[1:]:
                contour.append(Point(
                    x=current_x+p[0],
                    y=current_y+p[1],
                    type="line", smooth=False))
                current_x = contour[-1].x
                current_y = contour[-1].y
            i += len(points) + 1
        elif x[i] == "M":
            points = parse_points(x[i+1:], scale, height)
            p = points[0]
            current_x = p[0]
            current_y = p[1]
            contour.append(Point(
                x=current_x,
                y=current_y,
                type="move", smooth=False))
            for p in points[1:]:
                contour.append(Point(
                    x=p[0],
                    y=p[1],
                    type="line", smooth=False))
                current_x = contour[-1].x
                current_y = contour[-1].y
            i += len(points) + 1
        elif x[i] == "c":
            points = parse_points(x[i+1:], scale, 0)
            assert len(points) % 3 == 0
            for j in range(len(points) // 3):
                contour.append(Point(
                    x=current_x+points[3*j][0],
                    y=current_y+points[3*j][1],
                    type="offcurve", smooth=False))
                contour.append(Point(
                    x=current_x+points[3*j+1][0],
                    y=current_y+points[3*j+1][1],
                    type="offcurve", smooth=False))
                contour.append(Point(
                    x=current_x+points[3*j+2][0],
                    y=current_y+points[3*j+2][1],
                    type="curve", smooth=False))
                current_x = contour[-1].x
                current_y = contour[-1].y
            i += len(points) + 1
        elif x[i] == "C":
            points = parse_points(x[i+1:], scale, height)
            assert len(points) % 3 == 0
            for j in range(len(points) // 3):
                contour.append(Point(
                    x=points[3*j][0],
                    y=points[3*j][1],
                    type="offcurve", smooth=False))
                contour.append(Point(
                    x=points[3*j+1][0],
                    y=points[3*j+1][1],
                    type="offcurve", smooth=False))
                contour.append(Point(
                    x=points[3*j+2][0],
                    y=points[3*j+2][1],
                    type="curve", smooth=False))
            current_x = contour[-1].x
            current_y = contour[-1].y
            i += len(points) + 1
        elif x[i] == "l":
            points = parse_points(x[i+1:], scale, 0)
            for p in points:
                contour.append(Point(
                    x=current_x+p[0],
                    y=current_y+p[1],
                    type="line", smooth=False))
                current_x = contour[-1].x
                current_y = contour[-1].y
            i += len(points) + 1
        elif x[i] == "L":
            points = parse_points(x[i+1:], scale, height)
            for p in points:
                contour.append(Point(x=p[0], y=p[1], type="line", smooth=False))
                current_x = contour[-1].x
                current_y = contour[-1].y
            i += len(points) + 1
        elif x[i] == "h":
            points = [(float(x[i+1]))*scale]
            for p in points:
                contour.append(Point(x=current_x+p, y=current_y, type="line", smooth=False))
                current_x = contour[-1].x
                current_y = contour[-1].y
            i += len(points) + 1
        elif x[i] == "H":
            points = [(float(x[i+1]))*scale]
            for p in points:
                contour.append(Point(x=p, y=current_y, type="line", smooth=False))
                current_x = contour[-1].x
                current_y = contour[-1].y
            i += len(points) + 1
        elif x[i] == "v":
            points = [(-float(x[i+1]))*scale]
            for p in points:
                contour.append(Point(x=current_x, y=current_y+p, type="line", smooth=False))
                current_x = contour[-1].x
                current_y = contour[-1].y
            i += len(points) + 1
        elif x[i] == "V":
            points = [(height-float(x[i+1]))*scale]
            for p in points:
                contour.append(Point(x=current_x, y=p, type="line", smooth=False))
                current_x = contour[-1].x
                current_y = contour[-1].y
            i += len(points) + 1
        elif x[i] in ["A", "a"]:
            print(x[i])
            raise Exception("Elliptical Arc Curve (A, a) not supported")
        elif x[i] in ["z", "Z"]:
            contour[0].type = "line"
            contours.append(contour)
            current_x = contour[0].x
            current_y = contour[0].y
            contour = []
            i += 1
        else:
            print(x[i])
            raise Exception("Not supported")

    anchors = []
    g = Glif(name, unicode_hex, w, contours, anchors)
    verify(g)
    return g

# Glif -> SVG:

def glif2svg(glif: Glif, separate_paths: bool, fill: bool,
        stroke_width: int) -> str:
    h = 800
    svg = Element('svg', width=str(glif.w), height=str(h), version='1.1',
        xmlns='http://www.w3.org/2000/svg')

    path_str = ""

    for n, contour in enumerate(glif.contours):
        p0 = contour[0]
        assert p0.type != "offcurve"
        assert p0.type in ["curve", "line", "move"]
        is_curve = (contour[1].type in ["offcurve", "curve"])
        if is_curve:
            path_str += "M {},{} C".format(p0.x, h-p0.y)
        else:
            path_str += "M {},{} L".format(p0.x, h-p0.y)
        if p0.type != "move":
            contour = contour + [p0]
        for point in contour[1:]:
            if point.type in ["offcurve", "curve"]:
                if is_curve:
                    path_str += " {},{}".format(point.x, h-point.y)
                else:
                    is_curve = True
                    path_str += " C {},{}".format(point.x, h-point.y)
            else:
                assert point.type == "line"
                if is_curve:
                    is_curve = False
                    path_str += " L {},{}".format(point.x, h-point.y)
                else:
                    path_str += " {},{}".format(point.x, h-point.y)
        if p0.type != "move":
            path_str += " Z"
        if separate_paths:
            p = Element('path', d=path_str, fill='none', stroke="black",
                    style="stroke-linecap:butt;stroke-linejoin:mitter",
                    id=f"path{n}",
                    attrib={"stroke-width": str(stroke_width)})
            svg.append(p)
            path_str = ""
        else:
            path_str += " "
    if not separate_paths:
        if fill:
            p = Element('path', d=path_str, fill="black", stroke="black",
                    style="stroke-linecap:butt;stroke-linejoin:round",
                    id="path0",
                    attrib={"stroke-width": "0.0"})
        else:
            p = Element('path', d=path_str, fill="none", stroke="black",
                    style="stroke-linecap:butt;stroke-linejoin:mitter",
                    id="path0",
                    attrib={"stroke-width": str(stroke_width)})
        svg.append(p)

    for anchor in glif.anchors:
        p = Element('circle', cx=str(anchor.x), cy=str(h-anchor.y),
                stroke="black", r="10", id=f"{anchor.name}",
                attrib={"stroke-width": "2.0"})
        svg.append(p)

    svg_out = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
    indent(svg, space="    ")
    svg_out += tostring(svg).decode() + "\n"
    return svg_out

# Glif -> Glif:

def glif2glif(glif: Glif) -> str:
    attrib = {}
    svg = Element('glyph', name=glif.name, format="2")

    advance = Element("advance", width=str(glif.w))
    svg.append(advance)

    if len(glif.contours) > 0:
        outline = Element('outline')
        for contour in glif.contours:
            contour_ = Element("contour")
            for point in contour:
                attrib = {}
                if point.smooth:
                    attrib["smooth"] = "yes"
                if point.type != "offcurve":
                    attrib["type"] = point.type
                point_ = Element("point", x=str(point.x), y=str(point.y),
                        attrib=attrib)
                contour_.append(point_)
            outline.append(contour_)
        svg.append(outline)

#    for anchor in glif.anchors:
#        p = Element('circle', cx=str(anchor.x), cy=str(h-anchor.y),
#                stroke="black", r="10", id=f"{anchor.name}",
#                attrib={"stroke-width": "2.0"})
#        svg.append(p)

    svg_out = '<?xml version="1.0" encoding="UTF-8"?>\n'
    indent(svg, space="    ")
    svg_out += tostring(svg).decode() + "\n"
    return svg_out
